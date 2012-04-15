
import bge

import bxt
from . import store
from . import director
from . import camera

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

		door = c.sensors['sDoor']
		safety = c.sensors['sSafetyZone']

		mainChar = director.Director().mainCharacter

		# Eject all objects other than the snail.
		for ob in door.hitObjectList:
			if not ob == mainChar:
				# Only a snail can enter
				self.eject(ob)

		# If the bottle mode indicates that the snail is inside, double-check
		# that that's still the case.
		if self.snailInside and not mainChar in safety.hitObjectList:
			print("Exiting because snail not in safety.")
			self.transition(False)
			return

		if not mainChar in door.hitObjectList:
			return

		if not 'HasShell' in mainChar:
			# Touched by an occupied shell.
			self.eject(mainChar)
		elif mainChar['HasShell']:
			# Touched by a snail who is wearing a shell.
			bxt.types.Event('ShowDialogue',
					"You can't fit! Press X to drop your shell.").send()
			self.eject(mainChar)
		elif self.snailInside:
			print("Exiting because snail touched door.")
			self.transition(False)
		else:
			print("Entering because snail touched door.")
			self.transition(True)

	def transition(self, isEntering):
		if isEntering:
			store.set('/game/spawnPoint', 'SpawnBottle')
			self.open_window(True)

			relocPoint = self.children['SpawnBottleInner']
			transform = (relocPoint.worldPosition, relocPoint.worldOrientation)
			bxt.types.Event('RelocatePlayer', transform).send()

			camera.AutoCamera().add_goal(self.children['BottleCamera'])
		else:
			# Transitioning to outside; move camera to sensible location.
			self.open_window(False)

			relocPoint = self.children['SpawnBottle']
			transform = (relocPoint.worldPosition, relocPoint.worldOrientation)
			bxt.types.Event('RelocatePlayer', transform).send()

			camera.AutoCamera().remove_goal(self.children['BottleCamera'])
			cam = self.childrenRecursive['B_DoorCamera']
			transform = (cam.worldPosition, cam.worldOrientation)
			bxt.types.Event('RelocatePlayerCamera', transform).send()
		self.snailInside = isEntering

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
			if 'B_Outer' in sce.objects:
				sce.objects['B_Outer'].endObject()
		else:
			# Create bar exterior; destroy interior.
			if 'B_Inner' in sce.objects:
				sce.objects['B_Inner'].endObject()
			if not 'B_Outer' in sce.objects:
				sce.addObject('B_Outer', self)
		self.children['B_Rock'].visible = not isOpening
		self.children['B_SoilCrossSection'].visible = isOpening


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
