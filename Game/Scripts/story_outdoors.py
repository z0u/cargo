#
# Copyright 2009-2010 Alex Fraser <alex@phatcore.com>
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
import mathutils

import bxt

from .story import *
from . import director
from . import store
from Scripts import shells

class LevelOut(GameLevel):
	def __init__(self, oldOwner):
		GameLevel.__init__(self, oldOwner)
		# Load additional files
		self.load_foaliage()
		self.load_npcs()
		self.init_worm()

	def load_foaliage(self):
		'''Load extra files'''

		if store.get('/opt/foliage', True):
			try:
				bge.logic.LibLoad('//OutdoorsGrass_compiled.blend', 'Scene',
						load_actions=True)
			except ValueError:
				print('Could not load foliage. Try reinstalling the game.')
				evt = bxt.types.Event('ShowMessage',
					'Could not load foliage. Try reinstalling the game.')
				bxt.types.EventBus().notify(evt)

	def load_npcs(self):
		try:
			bge.logic.LibLoad('//OutdoorsNPCLoader.blend', 'Scene',
					load_actions=True)
		except ValueError:
			print('Could not load characters. Try reinstalling the game.')
			evt = bxt.types.Event('ShowMessage',
				'Could not load characters. Try reinstalling the game.')
			bxt.types.EventBus().notify(evt)

	def init_worm(self):
		sce = bge.logic.getCurrentScene()
		if not store.get('/game/level/wormMissionStarted', False):
			sce.addObject("G_Worm", "WormSpawn")
			bxt.math.copy_transform(sce.objects['WormSpawn'], sce.objects['Worm'])

class TestLevelCargoHouse(LevelOut):
	'''A level loader for Cargo's house - local testing only (not used by
	Outdoors.blend)'''

	def __init__(self, oldOwner):
		GameLevel.__init__(self, oldOwner)
		self.load_npcs()
		self.init_worm()

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
		self.lights.sort(key=bxt.math.DistanceKey(self))

		self.cols = list(map(lambda x: x.color.copy(), self.lights))
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
				target = col * 1.2
				self.targetLampCol += col
			else:
				target = col * 0.3
			self.targetCols[i] = target

	@bxt.types.expose
	def update(self):
		for light, targetCol in zip(self.lights, self.targetCols):
			light.color = bxt.math.lerp(light.color, targetCol, 0.1)

class Worm(Chapter, bge.types.BL_ArmatureObject):
	L_IDLE = 0
	L_ANIM = 1

	def __init__(self, old_owner):
		Chapter.__init__(self, old_owner)
		bxt.types.WeakEvent('StartLoading', self).send()
		self.create_state_graph()

	def create_state_graph(self):
		def letter_auto(c):
			sce = bge.logic.getCurrentScene()
			ob = sce.objects['Worm_Letter']
			hook = c.owner.childrenRecursive['CargoHoldAuto']
			ob.setParent(hook)
			bxt.math.copy_transform(hook, ob)
		def letter_manual(c):
			sce = bge.logic.getCurrentScene()
			ob = sce.objects['Worm_Letter']
			hook = c.owner.childrenRecursive['CargoHoldManual']
			ob.setParent(hook)
			bxt.math.copy_transform(hook, ob)
		def letter_hide(c):
			sce = bge.logic.getCurrentScene()
			ob = sce.objects['Worm_Letter']
			ob.visible = False

		def spray_dirt(c, number, maxSpeed):
			o = c.sensors['sParticleHook'].owner
			o['nParticles'] = o['nParticles'] + number
			o['maxSpeed'] = maxSpeed

		s = self.rootState.createTransition("Init")
		s.addEvent("ForceEnterShell", False)
		s.addAction(ActSetCamera('WormCamera_Enter'))
		s.addAction(ActShowDialogue("Press Return to start."))
		s.addAction(ActAction('ParticleEmitMove', 1, 1, Worm.L_ANIM, "ParticleEmitterLoc"))
		s.addAction(ActGenericContext(letter_manual))

		#
		# Peer out of ground
		#
		s = s.createTransition("Begin")
		s.addCondition(CondSensor('sReturn'))
		s.addAction(ActHideDialogue())
		s.addWeakEvent("FinishLoading", self)
		s.addAction(ActGenericContext(spray_dirt, 10, 15.0))
		s.addAction(ActAction('BurstOut', 1, 75, Worm.L_ANIM))
		s.addAction(ActAction('BurstOut_S', 1, 75, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition("Greet")
		s.addCondition(CondActionGE(Worm.L_ANIM, 74.0))
		s.addAction(ActShowDialogue("Cargo?"))

		#
		# Get out of the ground
		#
		s = s.createTransition("Get out of the ground")
		s.addCondition(CondSensor('sReturn'))
		s.addAction(ActHideDialogue())
		s.addAction(ActRemoveCamera('WormCamera_Enter'))
		s.addAction(ActSetCamera('WormCamera_Converse'))
		s.addAction(ActAction('BurstOut', 75, 186, Worm.L_ANIM))
		s.addAction(ActAction('BurstOut_S', 75, 186, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 115.0))
		s.addAction(ActGenericContext(spray_dirt, 3, 10.0))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 147.0))
		s.addAction(ActGenericContext(spray_dirt, 5, 10.0))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 153.0))
		s.addAction(ActGenericContext(spray_dirt, 5, 10.0))

		#
		# Knock on shell
		#
		s = s.createTransition("Knock on shell")
		s.addCondition(CondActionGE(Worm.L_ANIM, 185.0))
		s.addAction(ActSetCamera('WormCamera_Knock'))
		s.addAction(ActShowDialogue("Wake up, Cargo!"))
		s.addAction(ActAction('BurstOut', 185, 198, Worm.L_ANIM,
			play_mode=bge.logic.KX_ACTION_MODE_LOOP))
		s.addAction(ActAction('BurstOut_S', 185, 198, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition()
		s.addCondition(CondSensor('sReturn'))
		s.addAction(ActAction('BurstOut', 185, 220, Worm.L_ANIM))
		s.addAction(ActAction('BurstOut_S', 185, 220, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 200.0))
		s.addAction(ActRemoveCamera('WormCamera_Knock'))

		#
		# Wake / chastise
		#	
		s = s.createTransition("Wake")
		s.addCondition(CondActionGE(Worm.L_ANIM, 205.0))
		s.addEvent("ForceExitShell", True)
		s.addAction(ActHideDialogue())

		s = s.createTransition("Chastise")
		s.addCondition(CondEvent('ShellExited'))
		s.addAction(ActShowDialogue("Sleeping in, eh? Don't worry, I won't tell anyone."))

		s = s.createTransition()
		s.addCondition(CondSensor('sReturn'))
		s.addAction(ActShowDialogue("I have something for you!"))

		#
		# Dig up letter
		#
		s = s.createTransition("Dig up letter")
		s.addCondition(CondSensor('sReturn'))
		s.addAction(ActHideDialogue())
		s.addAction(ActAction('ParticleEmitMove', 2, 2, Worm.L_ANIM, "ParticleEmitterLoc"))
		s.addAction(ActAction('BurstOut', 220, 280, Worm.L_ANIM))
		s.addAction(ActAction('BurstOut_S', 220, 280, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 235))
		s.addAction(ActGenericContext(spray_dirt, 3, 10.0))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 241))
		s.addAction(ActGenericContext(spray_dirt, 3, 7.0))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 249))
		s.addAction(ActGenericContext(spray_dirt, 3, 7.0))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 257))
		s.addAction(ActGenericContext(spray_dirt, 3, 7.0))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 265))
		s.addAction(ActGenericContext(spray_dirt, 3, 7.0))
		s.addAction(ActGenericContext(letter_auto))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 275))
		s.addAction(ActSetCamera('WormCamera_Envelope'))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 279))
		s.addAction(ActShowDialogue("Ta-da! Please deliver this letter for me."))

		#
		# Give letter
		#
		s = s.createTransition("Give letter")
		s.addCondition(CondSensor('sReturn'))
		s.addAction(ActHideDialogue())
		s.addAction(ActRemoveCamera('WormCamera_Envelope'))
		s.addAction(ActAction('BurstOut', 290, 330, Worm.L_ANIM))
		s.addAction(ActAction('BurstOut_S', 290, 330, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 308))
		s.addAction(ActGenericContext(letter_manual))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 315))
		s.addAction(ActGenericContext(letter_hide))
		s.addAction(ActShowDialogue("Is that OK?"))

		#
		# Point to lighthouse
		#
		s = s.createTransition("Point to lighthouse")
		s.addCondition(CondSensor('sReturn'))
		s.addAction(ActShowDialogue("Great! Please take it to the lighthouse keeper."))
		s.addAction(ActAction('BurstOut', 330, 395, Worm.L_ANIM))
		s.addAction(ActAction('BurstOut_S', 330, 395, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 360))
		s.addAction(ActSetCamera('WormCamera_Lighthouse'))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 394))
		s.addCondition(CondSensor('sReturn'))
		s.addAction(ActRemoveCamera('WormCamera_Lighthouse'))
		s.addAction(ActShowDialogue("See you later!"))
		s.addAction(ActAction('BurstOut', 395, 420, Worm.L_ANIM))
		s.addAction(ActAction('BurstOut_S', 395, 420, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 420))
		s.addCondition(CondSensor('sReturn'))
		s.addAction(ActHideDialogue())
		s.addAction(ActAction('BurstOut', 420, 540, Worm.L_ANIM))
		s.addAction(ActAction('BurstOut_S', 420, 540, Worm.L_ANIM, 'WormBody'))

		#
		# Return to game
		#
		s = s.createTransition("Return to game")
		s.addCondition(CondActionGE(Worm.L_ANIM, 460))
		s.addAction(ActAction('SodFade', 120, 200, 0, 'Sods'))
		s.addAction(ActResumeInput())
		s.addAction(ActRemoveCamera('WormCamera_Converse'))
		s.addAction(ActStoreSet('/game/level/wormMissionStarted', True))

		#
		# Clean up. At this point, the worm is completely hidden and the sods have faded.
		#
		s = s.createTransition("Clean up")
		s.addCondition(CondActionGE(Worm.L_ANIM, 540))
		s.addAction(ActDestroy())

	def isInsideWorld(self):
		return True

@bxt.utils.controller
def worm_knock_sound(c):
	frame = c.owner['ActionFrame']
	if (frame > 187 and frame < 189) or (frame > 200 and frame < 201):
		bxt.sound.play_with_random_pitch(c)

class Bottle(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	'''The Sauce Bar'''

	_prefix = 'B_'

	def __init__(self, oldOwner):
		# Hide half of the lights until the end of the game.
		if not store.get('/game/level/bottleLights', False):
			self.children['BlinkenlightsRight'].setVisible(False, True)
		else:
			self.children['BlinkenlightsRight'].setVisible(True, True)
		self.snailInside = False
		self.open_window(False)

	@bxt.types.expose
	@bxt.utils.controller_cls
	def door_touched(self, c):
		'''Control access to the Sauce Bar. If the snail is carrying a shell,
		the door should be shut; otherwise, the SauceBar level should be loaded.
		'''

		inner = c.sensors['sDoorInner']
		outer = c.sensors['sDoorOuter']

		mainChar = director.Director().mainCharacter

		for ob in outer.hitObjectList:
			if not ob == mainChar:
				# Only the main character can enter
				self.eject(ob)
			elif not 'HasShell' in ob:
				# Only a snail can enter
				self.eject(ob)
			elif ob['HasShell']:
				# Only a snail without a shell can enter!
				self.eject(ob)
				evt = bxt.types.Event('ShowMessage', "You can't fit! Press X "
						"to drop your shell.")
				bxt.types.EventBus().notify(evt)

		if (mainChar in inner.hitObjectList and
				not mainChar in outer.hitObjectList):
			store.set('/game/spawnPoint', 'SpawnBottle')
			self.open_window(True)
			camera.AutoCamera().add_goal(self.children['BottleCamera'])
			self.snailInside = True
		elif (mainChar in outer.hitObjectList and
				not mainChar in inner.hitObjectList):
			self.open_window(False)
			camera.AutoCamera().remove_goal(self.children['BottleCamera'])

			if self.snailInside:
				# Transitioning to outside; move camera to sensible location.
				cam = self.childrenRecursive['B_DoorCamera']
				transform = (cam.worldPosition, cam.worldOrientation)
				bxt.types.Event('RelocatePlayerCamera', transform).send()
			self.snailInside = False

	def eject(self, ob):
		direction = self.children['B_DoorOuter'].getAxisVect(bxt.math.ZAXIS)
		ob.worldPosition += direction

	def open_window(self, open):
		sce = bge.logic.getCurrentScene()
		if open:
			# Create bar interior; destroy exterior (so it doesn't get in the
			# way when crawling).
			if not 'B_Inner' in sce.objects:
				sce.addObject('B_Inner', self)
			if 'B_Outer' in sce.objects:
				sce.objects['B_Outer'].endObject()
		else:
			# Create bar exterior; destroy interior.
			if 'B_Inner' in sce.objects:
				sce.objects['B_Inner'].endObject()
			if not 'B_Outer' in sce.objects:
				sce.addObject('B_Outer', self)
		self.children['B_Rock'].visible = not open
		self.children['B_SoilCrossSection'].visible = open

class Tree(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	def __init__(self, oldOwner):
		if not store.get('/game/level/treeDoorBroken', False):
			self.create_door()

	def create_door(self):
		hook = self.children['T_Door_Hook']
		scene = bge.logic.getCurrentScene()
		door = scene.addObject('T_Door', hook)
		door.worldPosition = hook.worldPosition
		door.worldOrientation = hook.worldOrientation

class TreeDoor(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	_prefix = 'TD_'

	def __init__(self, oldOnwer):
		pass

	def destruct(self):
		scene = bge.logic.getCurrentScene()
		for hook in self.children:
			i = hook.name[-3:]
			pieceName = 'T_Door_Broken.%s' % i
			try:
				scene.addObject(pieceName, hook)
			except ValueError:
				print('Failed to add object %s' % pieceName)
		self.endObject()
		store.set('/game/level/treeDoorBroken', True)

	@bxt.types.expose
	@bxt.utils.controller_cls
	def collide(self, c):
		for shell in c.sensors[0].hitObjectList:
			if shell.name != 'Wheel':
				continue
			if not shell.can_destroy_stuff():
				continue
			evt = bxt.types.Event('ForceExitShell', True)
			bxt.types.EventBus().notify(evt)
			self.destruct()
