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

import bat.bats
import bat.event
import bat.utils
import bat.bmath
import bat.sound
import bat.render

import Scripts.store
import Scripts.director
import Scripts.camera
import Scripts.snail
import bat.impulse
import Scripts.story_bird
from Scripts.story import *

class Bottle(bat.impulse.Handler, bat.bats.BX_GameObject, bge.types.KX_GameObject):
	'''The Sauce Bar'''

	_prefix = 'B_'

	def __init__(self, oldOwner):
		self.snailInside = False
		self.transition_delay = 0
		self.open_window(False)
		bat.event.EventBus().add_listener(self)
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

	@bat.bats.expose
	@bat.utils.controller_cls
	def door_touched(self, c):
		'''Control access to the Sauce Bar. If the snail is carrying a shell,
		the door should be shut; otherwise, the SauceBar level should be loaded.
		'''

		door = c.sensors['sDoor']
		safety = c.sensors['sSafetyZone']

		mainChar = Scripts.director.Director().mainCharacter

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
			bat.event.Event('ShowDialogue',
					"You can't fit! Press X to drop your shell.").send()
			self.eject(mainChar)
		elif self.snailInside:
			#print("Exiting because snail touched door.")
			cbEvent = bat.event.Event("ExitBottle")
			bat.event.Event("ShowLoadingScreen", (True, cbEvent)).send()
			self.transition_delay = -1
		else:
			#print("Entering because snail touched door.")
			cbEvent = bat.event.Event("EnterBottle")
			bat.event.Event("ShowLoadingScreen", (True, cbEvent)).send()
			self.transition_delay = -1

	def enter_bottle(self):
		Scripts.store.put('/game/spawnPoint', 'SpawnBottle')
		self.open_window(True)
		bat.event.Event('TeleportSnail', 'SpawnBottleInner').send()
		bat.event.Event("AddCameraGoal", 'BottleCamera').send()
		bat.impulse.Input().add_handler(self, 'STORY')

		self.snailInside = True
		self.transition_delay = 1
		bat.event.Event("ShowLoadingScreen", (False, None)).send()

	def exit_bottle(self):
		# Transitioning to outside; move camera to sensible location.
		self.open_window(False)
		bat.event.Event('TeleportSnail', 'SpawnBottle').send()
		bat.event.Event("RemoveCameraGoal", 'BottleCamera').send()

		if self.bird_arrived:
			# The bird has interrupted the story (triggered by conversation with
			# barkeeper).
			# First, really make sure the snail hasn't got a shell. Just in
			# case!
			bat.event.Event('ForceDropShell', False).send()
			# Then spawn the bird.
			spawn_point = self.scene.objects["Bird_SauceBar_Spawn"]
			bird = Scripts.story_bird.factory()
			bat.bmath.copy_transform(spawn_point, bird)
			self.bird_arrived = False

		elif not Scripts.store.get("/game/canDropShell", False):
			# Don't let a snail wander around with no shell until after the bird
			# has taken one.
			bat.event.Event('ForceReclaimShell').send()
		bat.impulse.Input().remove_handler(self)

		self.snailInside = False
		self.transition_delay = 1
		bat.event.Event("ShowLoadingScreen", (False, None)).send()

	def eject(self, ob):
		direction = self.children['B_Door'].getAxisVect(bat.bmath.ZAXIS)
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
		bat.sound.Jukebox().play_files(inner, 1,
				'//Sound/Music/Idea-Random2.ogg')

	def can_handle_input(self, state):
		'''Don't allow snail to reclaim shell when inside.'''
		return state.name in ('1', '2', 'Switch')

class BottleRock(bat.bats.BX_GameObject, bge.types.KX_GameObject):
	'''A rock that hides itself when the snail enters the bar.'''
	def __init__(self, old_owner):
		bat.event.EventBus().add_listener(self)

	def on_event(self, evt):
		if evt.message == 'EnterBottle':
			self.visible = False
			self.children['B_SoilCrossSection'].visible = True
		elif evt.message == 'ExitBottle':
			self.visible = True
			self.children['B_SoilCrossSection'].visible = False


class BottleDropZone(bat.impulse.Handler, bat.bats.BX_GameObject, bge.types.KX_GameObject):
	'''
	Allows snail to drop shell, but only when standing at the door of the
	bottle.
	'''

	_prefix = 'DZ_'

	def __init__(self, old_owner):
		bat.event.EventBus().add_listener(self)
		# Only handle overridden input events (see impulse.Handler).
		self.default_handler_response = False
		self.shell_drop_initiated_at_door = False

	def on_event(self, evt):
		if evt.message == 'ShellDropped':
			if self.shell_drop_initiated_at_door:
				cbEvent = bat.event.Event("EnterBottle")
				bat.event.Event("ShowLoadingScreen", (True, cbEvent)).send()
				self.shell_drop_initiated_at_door = False

	@bat.bats.expose
	@bat.utils.controller_cls
	def touched(self, c):
		'''Register self as an input handler to allow snail to drop shell.'''
		s = c.sensors[0]
		mainChar = Scripts.director.Director().mainCharacter
		if mainChar in s.hitObjectList:
			bat.impulse.Input().add_handler(self, 'STORY')
		else:
			bat.impulse.Input().remove_handler(self)

	def can_handle_input(self, state):
		'''Allow snail to drop shell.'''
		return state.name == '2'

	def handle_input(self, state):
		if state.name == '2':
			self.handle_bt_2(state)

	def handle_bt_2(self, state):
		'''
		Handle a drop-shell request when the snail is nearby. This is required
		because the shell cannot be dropped at will until later in the game.
		'''
		if state.activated:
			bat.event.Event('ForceDropShell', True).send()
			self.shell_drop_initiated_at_door = True


class BarKeeper(Chapter, bge.types.KX_GameObject):

	_prefix = 'BK_'

	L_IDLE = 0
	L_ANIM = 1

	def __init__(self, old_owner):
		Chapter.__init__(self, old_owner)
		arm = bat.bats.add_and_mutate_object(self.scene, "SlugArm_Min",
				self.children["SlugSpawnPos"])
		arm.setParent(self)
		arm.look_at("Snail")
		arm.playAction("Slug_AtBar", 1, 50)
		self.arm = arm
		self.arm.localScale = (0.75, 0.75, 0.75)
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
		s.addAction(ActSetFocalPoint("SlugLookTarget"))
		s.addEvent("TeleportSnail", "BK_SnailTalkPos")

		# Split story.
		# Note that these are added IN ORDER: if the first one fails, it will
		# fall through to the second, and so on. Therefore, the ones that come
		# later in the story are listed first.
		safterbottlecap = self.sg_afterbottlecap([s])
		safterbird = self.sg_afterbird([s])
		sbeforebird = self.sg_beforebird([s])
		sbeforelighthouse = self.sg_beforelighthouse([s])

		#
		# Merge, and return to game
		#
		s = State("Return to game")
		safterbottlecap.addTransition(s)
		safterbird.addTransition(s)
		sbeforebird.addTransition(s)
		sbeforelighthouse.addTransition(s)
		s.addAction(ActResumeInput())
		s.addAction(ActRemoveCamera('BottleCamera_Close'))
		s.addAction(ActRemoveFocalPoint("SlugLookTarget"))

		#
		# Loop back to start when snail moves away.
		#
		s = s.createTransition("Reset")
		s.addCondition(CondSensorNot('Near'))
		s.addTransition(self.rootState)

	def sg_beforelighthouse(self, preceding_states):
		s = State("beforelighthouse")
		for ps in preceding_states:
			ps.addTransition(s)
		s.addEvent("ShowDialogue", "Hi Cargo. What will it be, the usual?")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "There you go - one tomato sauce. Enjoy!")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		return s

	def sg_beforebird(self, preceding_states):
		s = State("beforebird")
		for ps in preceding_states:
			ps.addTransition(s)
		s.addCondition(CondStore('/game/level/lkMissionStarted', True, False))
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

		stweet1 = sdeliver.createSubStep("Bird Sound 1")
		stweet1.addCondition(CondActionGE(0, 20, ob="BottleCamera_Close", tap=True))
		stweet1.addAction(ActSound('//Sound/cc-by/BirdTweet1.ogg'))

		stweet2 = sdeliver.createSubStep("Bird Sound 2")
		stweet2.addCondition(CondActionGE(0, 50, ob="BottleCamera_Close", tap=True))
		stweet2.addAction(ActSound('//Sound/cc-by/BirdTweet2.ogg'))

		sdeliver = sdeliver.createTransition()
		sdeliver.addCondition(CondWait(1))
		sdeliver.addSubStep(stweet1)
		sdeliver.addSubStep(stweet2)
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


def lighthouse_stub():
	Scripts.store.put('/game/level/lkMissionStarted', True)

@bat.utils.all_sensors_positive
def test_bird():
	sce = bge.logic.getCurrentScene()
	spawn_point = sce.objects["Bird_SauceBar_Spawn"]
	bird = Scripts.story_bird.factory()
	bat.bmath.copy_transform(spawn_point, bird)


class Blinkenlights(bat.bats.BX_GameObject, bge.types.KX_GameObject):
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
		self.lights.sort(key=bat.bmath.DistanceKey(self))

		self.cols = list(map(
				lambda x: bat.render.parse_colour(x["colour"]), self.lights))
		self.targetCols = list(self.cols)
		self.targetLampCol = bat.render.BLACK.copy()

		# Hide half of the lights until the end of the game.
		if self['side'] == 'right':
			if not Scripts.store.get('/game/level/bottleLights', False):
				self.setVisible(False, True)

	@bat.bats.expose
	def blink(self):
		stringLen = self['cycleLen']
		self.step = (self.step + 1) % stringLen
		self.targetLampCol = bat.render.BLACK.copy()
		for i, col in enumerate(self.cols):
			target = None
			if (i % stringLen) == self.step:
				target = col * 2.0
				self.targetLampCol += col
			else:
				target = col * 0.2
				target.w = 1.0
			self.targetCols[i] = target

	@bat.bats.expose
	def update(self):
		for light, targetCol in zip(self.lights, self.targetCols):
			light.color = bat.bmath.lerp(light.color, targetCol, 0.1)
