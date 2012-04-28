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
from .story import *

class Bottle(impulse.Handler, bxt.types.BX_GameObject, bge.types.KX_GameObject):
	'''The Sauce Bar'''

	_prefix = 'B_'

	def __init__(self, oldOwner):
		# Hide half of the lights until the end of the game.
		if not store.get('/game/level/bottleLights', False):
			self.children['BlinkenlightsRight'].setVisible(False, True)
		else:
			self.children['BlinkenlightsRight'].setVisible(True, True)
		self.snailInside = False
		self.transition_delay = 0
		self.open_window(False)
		bxt.types.EventBus().add_listener(self)

		# Only handle overridden input events (see impulse.Handler).
		self.default_handler_response = False
		self.shell_drop_initiated_at_door = False

	def on_event(self, evt):
		if evt.message == 'EnterBottle':
			self.transition(True)
		elif evt.message == 'ExitBottle':
			self.transition(False)
		elif evt.message == 'ShellDropped':
			if self.shell_drop_initiated_at_door:
				cbEvent = bxt.types.Event("EnterBottle")
				bxt.types.Event("ShowLoadingScreen", (True, cbEvent)).send()
				self.shell_drop_initiated_at_door = False

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
			self.transition(False)
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

	@bxt.types.expose
	@bxt.utils.controller_cls
	def drop_zone_touched(self, c):
		'''Register self as an input handler to allow snail to drop shell.'''
		s = c.sensors[0]
		mainChar = director.Director().mainCharacter
		if mainChar in s.hitObjectList:
			impulse.Input().add_handler(self, 'STORY')
		else:
			impulse.Input().remove_handler(self)

	def transition(self, isEntering):
		bxt.types.Event("ShowLoadingScreen", (False, None)).send()
		if isEntering:
			store.set('/game/spawnPoint', 'SpawnBottle')
			self.open_window(True)
			bxt.types.Event('TeleportSnail', 'SpawnBottleInner').send()
			camera.AutoCamera().add_goal(self.children['BottleCamera'])
		else:
			# Transitioning to outside; move camera to sensible location.
			self.open_window(False)
			bxt.types.Event('TeleportSnail', 'SpawnBottle').send()
			camera.AutoCamera().remove_goal(self.children['BottleCamera'])
			if not store.get("/game/canDropShell", False):
				# Don't let a snail wander around with no shell until the time
				# is right!
				bxt.types.Event('ForceReclaimShell').send()

		self.snailInside = isEntering
		self.transition_delay = 1

	def eject(self, ob):
		direction = self.children['B_Door'].getAxisVect(bxt.bmath.ZAXIS)
		ob.worldPosition += direction

	def open_window(self, isOpening):
		sce = bge.logic.getCurrentScene()
		if isOpening:
			# Create bar interior; destroy exterior (so it doesn't get in the
			# way when crawling).
			if not 'B_Inner' in sce.objects:
				sce.addObject('B_Inner', self)
				sce.addObject('BarKeeper', 'B_BK_SpawnPoint')
			if 'B_Outer' in sce.objects:
				sce.objects['B_Outer'].endObject()
		else:
			# Create bar exterior; destroy interior.
			if 'B_Inner' in sce.objects:
				sce.objects['B_Inner'].endObject()
			if 'BarKeeper' in sce.objects:
				sce.objects['BarKeeper'].endObject()
			if not 'B_Outer' in sce.objects:
				sce.addObject('B_Outer', self)
		self.children['B_Rock'].visible = not isOpening
		self.children['B_SoilCrossSection'].visible = isOpening

	def handle_bt_2(self, state):
		'''
		Handle a drop-shell request when the snail is nearby. This is required
		because the shell cannot be dropped at will until later in the game.
		'''
		if state.activated:
			bxt.types.Event('ForceDropShell', True).send()
			self.shell_drop_initiated_at_door = True
		return True

bxt.types.Event('TeleportSnail', "SpawnBottle").send(50)

class BarKeeper(Chapter, bge.types.KX_GameObject):

	_prefix = 'BK_'

	L_IDLE = 0
	L_ANIM = 1

	def __init__(self, old_owner):
		Chapter.__init__(self, old_owner)
		#bxt.types.WeakEvent('StartLoading', self).send()
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
		#s.addAction(ActSetCamera('LK_Cam_Long'))
		#s.addAction(ActSetFocalPoint('LighthouseKeeper'))

		s = s.createTransition()
		s.addCondition(CondWait(1))
		s.addWeakEvent("FinishLoading", self)
		s.addEvent("TeleportSnail", "BK_SnailTalkPos")

		sdeliver = self.sg_firstmeeting([s])

		#
		# Return to game
		#
		s = State("Return to game")
		sdeliver.addTransition(s)
		s.addAction(ActResumeInput())
		#s.addAction(ActRemoveCamera('LK_Cam_CU_Cargo'))
		#s.addAction(ActRemoveFocalPoint('LighthouseKeeper'))

		#
		# Loop back to start when snail moves away.
		#
		s = s.createTransition("Reset")
		s.addCondition(CondSensorNot('Near'))
		s.addTransition(self.rootState)

	def sg_firstmeeting(self, preceding_states):
		s = State("delivery")
		for ps in preceding_states:
			ps.addTransition(s)
		s.addEvent("ShowDialogue", ("Hi there, Mr Postman. What can I do for you?",
				("\[envelope].", "1 tomato sauce, please.")))

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))

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
