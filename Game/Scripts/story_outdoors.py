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

def init():
	'''Load extra files'''
	if store.get('/opt/foliage', True):
		try:
			bge.logic.LibLoad('//OutdoorsGrass_compiled.blend', 'Scene')
		except ValueError:
			print('Could not load foliage. Try reinstalling the game.')
			evt = bxt.types.Event('ShowMessage',
				'Could not load foliage. Try reinstalling the game.')
			bxt.types.EventBus().notify(evt)

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
		self.lamp = None
		for ob in self.children:
			if isLamp(ob):
				self.lamp = ob
			else:
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

		if self.lamp:
			currentLampCol = mathutils.Vector(self.lamp.color)
			lampCol = self.targetLampCol.copy()
			lampCol.resize_3d()
			self.lamp.color =  bxt.math.lerp(currentLampCol, lampCol, 0.1)

class Worm(Character, bge.types.BL_ArmatureObject):
	def __init__(self, old_owner):
		Character.__init__(self, old_owner)
		evt = bxt.types.WeakEvent('StartLoading', self)
		bxt.types.EventBus().notify(evt)

	def CreateSteps(self):
		#
		# Local utility functions
		#
		def SleepSnail(c, animate):
			snail = c.sensors['sNearSnail'].hitObject['Actor']
			snail.enter_shell(animate)

		def WakeSnail(c, animate):
			snail = c.sensors['sNearSnail'].hitObject['Actor']
			snail.exit_shell(animate)

		def SprayDirt(c, number, maxSpeed):
			o = c.sensors['sParticleHook'].owner
			o['nParticles'] = o['nParticles'] + number
			o['maxSpeed'] = maxSpeed

		def CleanUp(c):
			worm = c.owner['Actor']
			worm.Destroy()

		step = self.NewStep()
		step.AddAction(ActGenericContext(SleepSnail, False))
		step.AddAction(ActSuspendInput())

		step = self.NewStep()
		step.AddCondition(CondSensor('sSnailAsleep'))
		step.AddAction(ActSetCamera('WormCamera_Enter'))
		step.AddAction(ActShowDialogue("Press Return to start."))

		#
		# Peer out of ground
		#
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActHideDialogue())
		step.AddAction(ActEvent(bxt.types.WeakEvent('FinishLoading', self)))
		step.AddAction(ActGenericContext(SprayDirt, 10, 15.0))
		step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 1.0, 75.0))

		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 75.0))
		step.AddAction(ActShowDialogue("Cargo?"))

		#
		# Get out of the ground
		#
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActHideDialogue())
		step.AddAction(ActRemoveCamera('WormCamera_Enter'))
		step.AddAction(ActSetCamera('WormCamera_Converse'))
		step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 75.0, 186.0))

		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 115))
		step.AddAction(ActGenericContext(SprayDirt, 3, 10.0))

		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 147))
		step.AddAction(ActGenericContext(SprayDirt, 5, 10.0))

		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 153))
		step.AddAction(ActGenericContext(SprayDirt, 5, 10.0))

		#
		# Knock on shell
		#
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 185.0))
		step.AddAction(ActSetCamera('WormCamera_Knock'))
		step.AddAction(ActShowDialogue("Wake up, Cargo!"))
		step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 185.0, 198.0, True))

		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 185.0, 220.0))

		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 200.0))
		step.AddAction(ActRemoveCamera('WormCamera_Knock'))

		#
		# Wake / chastise
		#	
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 205.0))
		step.AddAction(ActGenericContext(WakeSnail, True))
		step.AddAction(ActHideDialogue())

		step = self.NewStep()
		step.AddCondition(CondSensor('sSnailAwake'))
		step.AddAction(ActShowDialogue("Sleeping in, eh? Don't worry, I won't tell anyone."))

		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActShowDialogue("I have something for you!"))

		#
		# Dig up letter
		#
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActHideDialogue())
		step.AddAction(ActActuate('aParticleEmitMove'))
		step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 220.0, 280.0))

		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 235))
		step.AddAction(ActGenericContext(SprayDirt, 3, 10.0))

		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 241))
		step.AddAction(ActGenericContext(SprayDirt, 3, 7.0))

		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 249))
		step.AddAction(ActGenericContext(SprayDirt, 3, 7.0))

		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 257))
		step.AddAction(ActGenericContext(SprayDirt, 3, 7.0))

		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 265))
		step.AddAction(ActGenericContext(SprayDirt, 3, 7.0))

		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 275.0))
		step.AddAction(ActSetCamera('WormCamera_Envelope'))

		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 280.0))
		step.AddAction(ActShowDialogue("Ta-da! Please deliver this letter for me."))

		#
		# Give letter
		#
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActHideDialogue())
		step.AddAction(ActRemoveCamera('WormCamera_Envelope'))
		step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 290.0, 330.0))

		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 315.0))
		step.AddAction(ActActuate('aHideLetter'))
		step.AddAction(ActShowDialogue("Is that OK?"))

		#
		# Point to lighthouse
		#
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActShowDialogue("Great! Please take it to the lighthouse keeper."))
		step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 330.0, 395.0))

		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 360.0))
		step.AddAction(ActSetCamera('WormCamera_Lighthouse'))

		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 395.0))
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActRemoveCamera('WormCamera_Lighthouse'))
		step.AddAction(ActShowDialogue("See you later!"))
		step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 395.0, 420.0))

		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 420.0))
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActHideDialogue())
		step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 420.0, 540.0))

		#
		# Return to game
		#
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 460.0))
		step.AddAction(ActActuate('aFadeSods'))
		step.AddAction(ActResumeInput())
		step.AddAction(ActRemoveCamera('WormCamera_Converse'))

		#
		# Clean up. At this point, the worm is completely hidden and the sods have faded.
		#
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 540.0))
		step.AddAction(ActGenericContext(CleanUp))

	def isInsideWorld(self):
		return True

@bxt.utils.controller
def worm_knock_sound(c):
	frame = c.owner['ActionFrame']
	if (frame > 187 and frame < 189) or (frame > 200 and frame < 201):
		bxt.sound.play_with_random_pitch(c)

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
			evt = bxt.types.Event('ForceExitShell')
			bxt.types.EventBus().notify(evt)
			self.destruct()
