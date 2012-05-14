#
# Copyright 2009-2012 Alex Fraser <alex@phatcore.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import bge

import bxt
from . import store
from . import director
from . import camera
from . import snail
from . import impulse
from . import jukebox
from . import story_bird
from .story import *

class Bottle(impulse.Handler, bxt.types.BX_GameObject, bge.types.KX_GameObject):
	'''The Sauce Bar'''

	_prefix = 'B_'

	def __init__(self, oldOwner):
		self.snailInside = False
		self.transition_delay = 0
		self.open_window(False)
		bxt.types.EventBus().add_listener(self)
		# Only handle overridden input events (see impulse.Handler).
		self.default_handler_response = False
		self.bird_arrived = False

	def on_event(self, evt):
		if evt.message == 'EnterBottle':
			self.enter_bottle()
		elif evt.message == 'ExitBottle':
			self.exit_bottle()
		elif evt.message == 'BirdArrived':
			self.bird_arrived = True

	@bxt.types.expose
	@bxt.utils.controller_cls
	def door_touched(self, c):
		'''Control access to the Sauce Bar. If the snail is carrying a shell,
		the door should be shut; otherwise, the SauceBar level should be loaded.
		'''

		door = c.sensors['sDoor']
		safety = c.sensors['sSafetyZone']

		mainChar = director.Director().mainCharacter

		# Eject all objects other than the snail.
		for ob in door.hitObjectList:
			if ob.parent is not None:
				continue
			if not ob == mainChar:
				# Only a snail can enter
				self.eject(ob)

		# If the bottle mode indicates that the snail is inside, double-check
		# that that's still the case.
		if self.snailInside and not mainChar in safety.hitObjectList:
			print("Exiting because snail not in safety.")
			self.exit_bottle()
			return

		if self.transition_delay > 0:
			self.transition_delay -= 1
			return
		elif self.transition_delay < 0:
			return

		if not mainChar in door.hitObjectList:
			return

		if not 'HasShell' in mainChar:
			# Touched by an occupied shell.
			self.eject(mainChar)
		elif not self.snailInside and mainChar['HasShell']:
			# Touched by a snail who is wearing a shell.
			bxt.types.Event('ShowDialogue',
					"You can't fit! Press X to drop your shell.").send()
			self.eject(mainChar)
		elif self.snailInside:
			#print("Exiting because snail touched door.")
			cbEvent = bxt.types.Event("ExitBottle")
			bxt.types.Event("ShowLoadingScreen", (True, cbEvent)).send()
			self.transition_delay = -1
		else:
			#print("Entering because snail touched door.")
			cbEvent = bxt.types.Event("EnterBottle")
			bxt.types.Event("ShowLoadingScreen", (True, cbEvent)).send()
			self.transition_delay = -1

	def enter_bottle(self):
		store.set('/game/spawnPoint', 'SpawnBottle')
		self.open_window(True)
		bxt.types.Event('TeleportSnail', 'SpawnBottleInner').send()
		bxt.types.Event("AddCameraGoal", 'BottleCamera').send()
		impulse.Input().add_handler(self, 'STORY')

		self.snailInside = True
		self.transition_delay = 1
		bxt.types.Event("ShowLoadingScreen", (False, None)).send()

	def exit_bottle(self):
		# Transitioning to outside; move camera to sensible location.
		self.open_window(False)
		bxt.types.Event('TeleportSnail', 'SpawnBottle').send()
		bxt.types.Event("RemoveCameraGoal", 'BottleCamera').send()

		if self.bird_arrived:
			# The bird has interrupted the story (triggered by conversation with
			# barkeeper).
			# First, really make sure the snail hasn't got a shell. Just in
			# case!
			bxt.types.Event('ForceDropShell', False).send()
			# Then spawn the bird.
			spawn_point = self.scene.objects["Bird_SauceBar_Spawn"]
			bird = story_bird.factory()
			bxt.bmath.copy_transform(spawn_point, bird)
			self.bird_arrived = False

		elif not store.get("/game/canDropShell", False):
			# Don't let a snail wander around with no shell until after the bird
			# has taken one.
			bxt.types.Event('ForceReclaimShell').send()
		impulse.Input().remove_handler(self)

		self.snailInside = False
		self.transition_delay = 1
		bxt.types.Event("ShowLoadingScreen", (False, None)).send()

	def eject(self, ob):
		direction = self.children['B_Door'].getAxisVect(bxt.bmath.ZAXIS)
		ob.worldPosition += direction

	def open_window(self, isOpening):
		sce = bge.logic.getCurrentScene()
		if isOpening:
			# Create bar interior; destroy exterior (so it doesn't get in the
			# way when crawling).
			if not 'B_Inner' in sce.objects:
				inner = sce.addObject('B_Inner', self)
				self.start_music(inner)
			if 'B_Outer' in sce.objects:
				sce.objects['B_Outer'].endObject()
		else:
			# Create bar exterior; destroy interior.
			if 'B_Inner' in sce.objects:
				sce.objects['B_Inner'].endObject()
			if not 'B_Outer' in sce.objects:
				sce.addObject('B_Outer', self)

	def start_music(self, inner):
		'''
		Play the music for this locality. Don't need to stop it, because the
		'inner' object gets destroyed when the player leaves.
		'''
		jukebox.Jukebox().play(inner, 1,
				'//Sound/Music/explore.ogg')

	def handle_bt_1(self, state):
		'''Don't allow snail to reclaim shell when inside.'''
		return True

	def handle_switch(self, state):
		'''Don't allow snail to reclaim shell when inside.'''
		return True

	def handle_bt_2(self, state):
		return True


class BottleRock(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	'''A rock that hides itself when the snail enters the bar.'''
	def __init__(self, old_owner):
		bxt.types.EventBus().add_listener(self)

	def on_event(self, evt):
		if evt.message == 'EnterBottle':
			self.visible = False
			self.children['B_SoilCrossSection'].visible = True
		elif evt.message == 'ExitBottle':
			self.visible = True
			self.children['B_SoilCrossSection'].visible = False


class BottleDropZone(impulse.Handler, bxt.types.BX_GameObject, bge.types.KX_GameObject):
	'''
	Allows snail to drop shell, but only when standing at the door of the
	bottle.
	'''

	_prefix = 'DZ_'

	def __init__(self, old_owner):
		bxt.types.EventBus().add_listener(self)
		# Only handle overridden input events (see impulse.Handler).
		self.default_handler_response = False
		self.shell_drop_initiated_at_door = False

	def on_event(self, evt):
		if evt.message == 'ShellDropped':
			if self.shell_drop_initiated_at_door:
				cbEvent = bxt.types.Event("EnterBottle")
				bxt.types.Event("ShowLoadingScreen", (True, cbEvent)).send()
				self.shell_drop_initiated_at_door = False

	@bxt.types.expose
	@bxt.utils.controller_cls
	def touched(self, c):
		'''Register self as an input handler to allow snail to drop shell.'''
		s = c.sensors[0]
		mainChar = director.Director().mainCharacter
		if mainChar in s.hitObjectList:
			impulse.Input().add_handler(self, 'STORY')
		else:
			impulse.Input().remove_handler(self)

	def handle_bt_2(self, state):
		'''
		Handle a drop-shell request when the snail is nearby. This is required
		because the shell cannot be dropped at will until later in the game.
		'''
		if state.activated:
			bxt.types.Event('ForceDropShell', True).send()
			self.shell_drop_initiated_at_door = True
		return True


class BarKeeper(Chapter, bge.types.KX_GameObject):

	_prefix = 'BK_'

	L_IDLE = 0
	L_ANIM = 1

	def __init__(self, old_owner):
		Chapter.__init__(self, old_owner)
		self.create_state_graph()

	def create_state_graph(self):
		'''
		Create the state machine that drives interaction with the lighthouse
		keeper.
		@see ../../doc/story_states/LighthouseKeeper.dia
		'''
		#
		# Set scene with a long shot camera.
		#
		s = self.rootState.createTransition("Init")
		s.addCondition(CondSensor('Near'))
		s.addAction(ActSuspendInput())
		s.addWeakEvent("StartLoading", self)

		s = s.createTransition()
		s.addCondition(CondWait(1))
		s.addWeakEvent("FinishLoading", self)
		s.addAction(ActSetCamera('BottleCamera_Close'))
		s.addAction(ActSetFocalPoint('BK_LookTarget'))
		s.addEvent("TeleportSnail", "BK_SnailTalkPos")

		# Split story.
		# Note that these are added IN ORDER: if the first one fails, it will
		# fall through to the second, and so on.
		safterbottlecap = self.sg_afterbottlecap([s])
		safterbird = self.sg_afterbird([s])
		sbeforebird = self.sg_beforebird([s])

		#
		# Merge, and return to game
		#
		s = State("Return to game")
		safterbottlecap.addTransition(s)
		safterbird.addTransition(s)
		sbeforebird.addTransition(s)
		s.addAction(ActResumeInput())
		s.addAction(ActRemoveCamera('BottleCamera_Close'))
		s.addAction(ActRemoveFocalPoint('BK_LookTarget'))

		#
		# Loop back to start when snail moves away.
		#
		s = s.createTransition("Reset")
		s.addCondition(CondSensorNot('Near'))
		s.addTransition(self.rootState)

	def sg_beforebird(self, preceding_states):
		s = State("beforebird")
		for ps in preceding_states:
			ps.addTransition(s)
		s.addEvent("ShowDialogue", ("Hi there, Mr Postman. What can I do for you?",
				("\[envelope].", "1 tomato sauce, please.")))

		sauce = s.createTransition("sauce please")
		sauce.addCondition(CondEventEq("DialogueDismissed", 1))
		sauce.addEvent("ShowDialogue", "There you go.")

		sauce = sauce.createTransition()
		sauce.addCondition(CondEvent("DialogueDismissed"))

		sauce = sauce.createTransition()
		sauce.addCondition(CondWait(2))
		sauce.addEvent("ShowDialogue", "Be careful, Cargo. It's a strange day.")

		sauce = sauce.createTransition()
		sauce.addCondition(CondEvent("DialogueDismissed"))

		sdeliver = s.createTransition("deliver")
		sdeliver.addCondition(CondEventNe("DialogueDismissed", 1))
		sdeliver.addEvent("ShowDialogue", "Ah, cheers for the letter. So, the "
				"lighthouse keeper wants some more black bean sauce, eh?")

		sdeliver = sdeliver.createTransition()
		sdeliver.addCondition(CondEvent("DialogueDismissed"))
		sdeliver.addEvent("ShowDialogue", "She must be busy to not come here to get it herself.")

		sdeliver = sdeliver.createTransition()
		sdeliver.addCondition(CondEvent("DialogueDismissed"))
		sdeliver.addEvent("ShowDialogue", "Oh, the lighthouse is broken?")

		sdeliver = sdeliver.createTransition()
		sdeliver.addCondition(CondEvent("DialogueDismissed"))
		sdeliver.addEvent("ShowDialogue", "There has been a thief here too. You must have noticed the missing lights on your way in?")

		sdeliver = sdeliver.createTransition()
		sdeliver.addCondition(CondEvent("DialogueDismissed"))
		sdeliver.addEvent("ShowDialogue", "They disappeared just last night.")

		sdeliver = sdeliver.createTransition()
		sdeliver.addCondition(CondEvent("DialogueDismissed"))
		sdeliver.addEvent("ShowDialogue", "What is the island coming to? I can imagine this happening on Spider Isle, but not here.")

		sdeliver = sdeliver.createTransition()
		sdeliver.addCondition(CondEvent("DialogueDismissed"))

		# Bird arrives! Shake the camera about.
		sdeliver = sdeliver.createTransition()
		sdeliver.addCondition(CondWait(2))
		sdeliver.addAction(ActAction("BottleCamera_CloseAction", 1, 90, 0,
				"BottleCamera_Close"))
		sdeliver.addEvent('BirdArrived')

		sdeliver = sdeliver.createTransition()
		sdeliver.addCondition(CondWait(1))
		sdeliver.addEvent("ShowDialogue", "Look out! It's that cursed thing again. It must be back for the rest of the lights.")

		sdeliver = sdeliver.createTransition()
		sdeliver.addCondition(CondEvent("DialogueDismissed"))

		s = State("merge")
		sauce.addTransition(s)
		sdeliver.addTransition(s)

		return s

	def sg_afterbird(self, preceding_states):
		s = State("afterbird")
		for ps in preceding_states:
			ps.addTransition(s)
		s.addCondition(CondStore('/game/level/birdTookShell', True, False))
		s.addEvent("ShowDialogue", "Hi again, Cargo. Terribly sorry to hear about your shell!")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "That pesky bird needs to be taught a lesson!")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "It's no good charging up the tree: the bees won't allow it. They're very protective of their honey.")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "But, first things first, eh? You need to get your shell back.")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "I don't know how you'll get to the nest, but, hmm... shiny red things...")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))

		s = s.createTransition()
		s.addCondition(CondWait(2))
		s.addEvent("ShowDialogue", "Ah, that's right! This bottle used to have a bright red lid \[bottlecap]!")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "I used to use it as a door, but it washed away one day in heavy rain.")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "I think I saw the \[bottlecap] on that little island near your house.")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "The water is deep, though, so you'll have to figure out how to get there dry.")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "Quick, go and get it!")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		return s

	def sg_afterbottlecap(self, preceding_states):
		s = State("afterbottlecap")
		for ps in preceding_states:
			ps.addTransition(s)
		s.addCondition(CondStore('/game/level/birdTookShell', True, False))
		s.addCondition(CondHasShell('BottleCap'))
		s.addEvent("ShowDialogue", ("Hi Cargo, what's happening?",
				("\[bottlecap]!", "I'm thirsty.")))

		## Second option.
		sauce = s.createTransition("sauce please")
		sauce.addCondition(CondEventEq("DialogueDismissed", 1))
		sauce.addEvent("ShowDialogue", "More tomato sauce? There you go.")

		sauce = sauce.createTransition()
		sauce.addCondition(CondEvent("DialogueDismissed"))

		## First option.
		scap = s.createTransition("cap")
		scap.addCondition(CondEventNe("DialogueDismissed", 1))
		scap.addEvent("ShowDialogue", "You found my bottle cap! That's great news.")

		scap = scap.createTransition()
		scap.addCondition(CondEvent("DialogueDismissed"))
		scap.addEvent("ShowDialogue", "It's OK, you can keep it. I like not having a door: I get more customers this way.")

		scap = scap.createTransition()
		scap.addCondition(CondEvent("DialogueDismissed"))
		scap.addEvent("ShowDialogue", "Only two more shiny red things to go, eh? Sadly I haven't seen anything else that is shiny and red.")

		scap = scap.createTransition()
		scap.addCondition(CondEvent("DialogueDismissed"))
		scap.addEvent("ShowDialogue", "You'll just have to keep looking.")

		scap = scap.createTransition()
		scap.addCondition(CondEvent("DialogueDismissed"))

		s = State("merge")
		sauce.addTransition(s)
		scap.addTransition(s)
		return s


class BarKeeperArm(snail.NPCSnail):
	_prefix = 'BKA_'

	def __init__(self, old_owner):
		snail.NPCSnail.__init__(self, old_owner)

	@bxt.types.expose
	@bxt.utils.controller_cls
	def look(self, c):
		s = c.sensors[0]
		if s.hitObject is not None:
			self.look_at(s.hitObject)


class Blinkenlights(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	'''A series of blinking lights, like you find outside take away joints.'''

	def __init__(self, old_owner):
		'''Create a new Blinkenlights object.

		The owner should be the 'string' holding up the lights. This object
		should have the following children:
			 - One lamp.
			 - Any number of mesh objects. These must have a keyed object
			   colour.
		The mesh children will have their luminance cycled. The lamp will be
		given the colour of the lights that are on.

		Owner properties:
		cycleLen: The number of lights in a pattern. E.g. with a cycle length of
			3, lights will have the pattern [on, off, off, etc.]
		frames: The number of impulses to wait before moving stepping to the
			next state.'''

		self.step = 0

		def isLamp(x): return hasattr(x, 'energy')

		# Sort lights by distance from cord origin.
		self.lights = []
		for ob in self.children:
			self.lights.append(ob)
		self.lights.sort(key=bxt.bmath.DistanceKey(self))

		self.cols = list(map(
				lambda x: bxt.render.parse_colour(x["colour"]), self.lights))
		self.targetCols = list(self.cols)
		self.targetLampCol = bxt.render.BLACK.copy()

		# Hide half of the lights until the end of the game.
		if self['side'] == 'right':
			if not store.get('/game/level/bottleLights', False):
				self.setVisible(False, True)

	@bxt.types.expose
	def blink(self):
		stringLen = self['cycleLen']
		self.step = (self.step + 1) % stringLen
		self.targetLampCol = bxt.render.BLACK.copy()
		for i, col in enumerate(self.cols):
			target = None
			if (i % stringLen) == self.step:
				target = col * 2.0
				self.targetLampCol += col
			else:
				target = col * 0.2
				target.w = 1.0
			self.targetCols[i] = target

	@bxt.types.expose
	def update(self):
		for light, targetCol in zip(self.lights, self.targetCols):
			light.color = bxt.bmath.lerp(light.color, targetCol, 0.1)
