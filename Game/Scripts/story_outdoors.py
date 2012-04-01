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
from . import shaders

class LevelOut(GameLevel):
	def __init__(self, oldOwner):
		GameLevel.__init__(self, oldOwner)

		#bxt.music.play("//Sound/Music/explore.ogg", volume=0.3)
		bxt.music.play_permutation(
				"//Sound/cc-by/PondAmbience1.ogg",
				"//Sound/cc-by/PondAmbience2.ogg",
				"//Sound/cc-by/PondAmbience3.ogg",
				volume=0.7)

		# Load additional files
		self.load_foaliage()
		self.load_npcs()
		self.init_worm()

		shaders.ShaderCtrl().set_mist_colour(
				mathutils.Vector((0.749020, 0.737255, 0.745098)))

	def load_foaliage(self):
		'''Load extra files'''
		err = False

		try:
			bge.logic.LibLoad('//OutdoorsBase_flowers.blend', 'Scene',
					load_actions=True)
		except ValueError:
			err = True

		if store.get('/opt/foliage', True):
			try:
				bge.logic.LibLoad('//OutdoorsBase_grass.blend', 'Scene',
						load_actions=True)
			except ValueError:
				err = True

		if err:
			print('Error: Could not load foliage. Try reinstalling the game.')
			evt = bxt.types.Event('ShowMessage',
				'Error: Could not load foliage. Try reinstalling the game.')
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
			bxt.bmath.copy_transform(sce.objects['WormSpawn'], sce.objects['Worm'])

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
			bxt.bmath.copy_transform(hook, ob)
		def letter_manual(c):
			sce = bge.logic.getCurrentScene()
			ob = sce.objects['Worm_Letter']
			hook = c.owner.childrenRecursive['CargoHoldManual']
			ob.setParent(hook)
			bxt.bmath.copy_transform(hook, ob)
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
		s.addAction(ActSetFocalPoint('CargoHoldAuto'))
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

		sKnock = s.createSubStep("Knock sound")
		sKnock.addCondition(CondActionGE(Worm.L_ANIM, 187, tap=True))
		sKnock.addAction(ActSound('//Sound/Knock.ogg', vol=0.6, pitchmin=0.8,
				pitchmax= 1.1))

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
		s.addAction(ActSetFocalPoint('Torch'))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 394))
		s.addCondition(CondSensor('sReturn'))
		s.addAction(ActRemoveCamera('WormCamera_Lighthouse'))
		s.addAction(ActRemoveFocalPoint('Torch'))
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
		s.addAction(ActRemoveFocalPoint('CargoHoldAuto'))
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

class Lighthouse(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	'''Watches for Cargo's approach of the lighthouse, and creates the
	lighthouse keeper in response.'''
	_prefix = 'LH_'

	# Note that this is a little convoluted:
	#  1. Cargo touches a sensor, causing the loading screen to be shown.
	#  2. When the loading screen has been fully displayed, it sends an event
	#     (specified in 1.)
	#  3. When the event is received here, the lighthouse keeper is spawned.
	#  4. Then, the loading screen is hidden again.
	# This is because spawning the lighthouse keeper results in a small delay.
	# Showing the loading screen also allows us to reposition the snail for the
	# conversation.

	def __init__(self, old_owner):
		bxt.types.EventBus().add_listener(self)
		self.inLocality = False

	def on_event(self, event):
		if event.message == "EnterLighthouse":
			self.spawn_keeper()

	def spawn_keeper(self):
		# Need to use get_scene() here because we might be called from another
		# scene (due to the event bus).
		sce = self.get_scene()
		if "LighthouseKeeper" in sce.objects:
			print("Warning: tried to create LighthouseKeeper twice.")
			return

		obTemplate = sce.objectsInactive["LighthouseKeeper"]
		spawnPoint = sce.objects["LighthouseKeeperSpawn"]
		ob = sce.addObject(obTemplate, spawnPoint)
		bxt.bmath.copy_transform(spawnPoint, ob)
		bxt.types.Event("ShowLoadingScreen", (False, None)).send()

	def kill_keeper(self):
		sce = self.get_scene()
		try:
			ob = sce.objects["LighthouseKeeper"]
			ob.endObject()
		except KeyError:
			print("Warning: could not delete LighthouseKeeper")

	def arrive(self):
		print("Arriving at lighthouse.")
		self.inLocality = True
		cbEvent = bxt.types.Event("EnterLighthouse")
		bxt.types.Event("ShowLoadingScreen", (True, cbEvent)).send()

	def leave(self):
		# Remove the keeper to prevent its armature from chewing up resources.
		print("Leaving lighthouse.")
		self.kill_keeper()
		self.inLocality = False

	@bxt.types.expose
	@bxt.utils.controller_cls
	def touched(self, c):
		if self.inLocality:
			# Check whether the snail is leaving.
			sNear = c.sensors["Near"]
			if not director.Director().mainCharacter in sNear.hitObjectList:
				self.leave()
		else:
			# Check whether the snail is entering.
			sCollision = c.sensors[0]
			if director.Director().mainCharacter in sCollision.hitObjectList:
				self.arrive()

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

		for ob in door.hitObjectList:
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

		if self.snailInside:
			# Check to see if the snail is exiting.
			if not mainChar in safety.hitObjectList:
				print("Exiting because snail not in safety.")
				self.transition(False)
			elif mainChar in door.hitObjectList:
				print("Exiting because snail touched door.")
				self.transition(False)
		else:
			if mainChar in door.hitObjectList:
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
