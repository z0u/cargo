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
import mathutils
import logging

import bat.bats
import bat.event
import bat.story

import Scripts.camera
import Scripts.director
import bat.store
import Scripts.inventory

GRAVITY = 75.0

log = logging.getLogger(__name__)

class CondHasShell(bat.story.Condition):
	def __init__(self, name):
		self.name = name

	def evaluate(self, c):
		return self.name in Scripts.inventory.Shells().get_shells()

	def get_short_name(self):
		return "HasShell(%s)" % self.name

class CondNotInShell(bat.story.Condition):
	def evaluate(self, c):
		player = Scripts.director.Director().mainCharacter
		if player is None:
			return False
		# If the player object has a shell attribute, it must be a snail. If the
		# snail was in its shell, then Director.mainCharacter would be a shell
		# instead.
		return hasattr(player, 'shell')

	def get_short_name(self):
		return "NotInShell"

class ActSuspendInput(bat.story.BaseAct):
	'''Prevent the player from moving around.'''
	def execute(self, c):
		bat.event.Event('GameModeChanged', 'Cutscene').send()

class ActResumeInput(bat.story.BaseAct):
	'''Let the player move around.'''
	def execute(self, c):
		bat.event.Event('GameModeChanged', 'Playing').send()

class ActShowMarker(bat.story.BaseAct):
	'''Show a marker on the screen that points to an object.'''

	target = bat.containers.weakprop("target")

	def __init__(self, target):
		'''
		@para target: The object to highlight. If None, the highlight will be
				hidden.
		'''
		if isinstance(target, str):
			try:
				self.target = bge.logic.getCurrentScene().objects[target]
			except KeyError:
				self.target = None
		else:
			self.target = target

	def execute(self, c):
		bat.event.WeakEvent('ShowMarker', self.target).send()

	def __str__(self):
		if self.target is not None:
			name = self.target.name
		else:
			name = "None"
		return 'ActShowMarker(%s)' % name

class ActSetCamera(bat.story.BaseAct):
	'''Switch to a named camera.'''

	log = logging.getLogger(__name__ + '.ActSetCamera')

	def __init__(self, camName):
		self.CamName = camName

	def execute(self, c):
		try:
			cam = bge.logic.getCurrentScene().objects[self.CamName]
		except KeyError:
			ActSetCamera.log.warn(
					"Couldn't find camera %s. Not adding." %
					self.CamName)
			return
		Scripts.camera.AutoCamera().add_goal(cam)

	def __str__(self):
		return "ActSetCamera(%s)" % self.CamName

class ActRemoveCamera(bat.story.BaseAct):

	log = logging.getLogger(__name__ + '.ActRemoveCamera')

	def __init__(self, camName):
		self.CamName = camName

	def execute(self, c):
		try:
			cam = bge.logic.getCurrentScene().objects[self.CamName]
		except KeyError:
			ActRemoveCamera.log.warn(
					"Couldn't find camera %s. Not removing." %
					self.CamName)
			return
		Scripts.camera.AutoCamera().remove_goal(cam)

	def __str__(self):
		return "ActRemoveCamera(%s)" % self.CamName

class ActSetFocalPoint(bat.story.BaseAct):
	'''Focus on a named object.'''

	log = logging.getLogger(__name__ + '.ActSetFocalPoint')

	def __init__(self, targetName):
		self.targetName = targetName

	def execute(self, c):
		try:
			target = bge.logic.getCurrentScene().objects[self.targetName]
		except KeyError:
			ActSetFocalPoint.log.warn(
					"Couldn't find focus point %s. Not adding." %
					self.targetName)
			return
		Scripts.camera.AutoCamera().add_focus_point(target)

	def __str__(self):
		return "ActSetFocalPoint(%s)" % self.targetName

class ActRemoveFocalPoint(bat.story.BaseAct):

	log = logging.getLogger(__name__ + '.ActRemoveFocalPoint')

	def __init__(self, targetName):
		self.targetName = targetName

	def execute(self, c):
		try:
			target = bge.logic.getCurrentScene().objects[self.targetName]
		except KeyError:
			ActRemoveFocalPoint.log.warn(
					"Couldn't find focus point %s. Not removing." %
					self.targetName)
			return
		Scripts.camera.AutoCamera().remove_focus_point(target)

	def __str__(self):
		return "ActRemoveFocalPoint(%s)" % self.targetName



class Level(bat.bats.BX_GameObject, bge.types.KX_GameObject):
	'''Embodies a level. By default, this just sets some common settings when
	initialised. This should not be included in cut scenes etc; just in scenes
	where the player can move around.'''

	def __init__(self, old_owner):
		# Adjust gravity to be appropriate for the size of the scene..
		g = mathutils.Vector((0.0, 0.0, 0 - GRAVITY))
		bge.logic.setGravity(g)
		bat.event.Event('GravityChanged', g).send()
		bat.event.Event('GameModeChanged', 'Playing').send()

class GameLevel(Level):
	'''A level that is part of the main game. Handles things such as spawn
	points and level transitions. Test scenes may use these too, but it is not
	required.'''

	log = logging.getLogger(__name__ + ".GameLevel")

	@property
	def spawn_points(self):
		return [
				# Main island
				'SpawnCargoHouse', 'SpawnTorch', 'SpawnBottle',
				'SI_StartSpawnPoint', 'SI_WebSpawnPoint',
				# Dungeon
				'SpawnBottomDoor', 'SpawnFirstLanding', 'SpawnMaelstrom',
				'SpawnMachine', 'SpawnHive', 'SpawnTopDoor']

	def __init__(self, old_owner):
		Level.__init__(self, old_owner)

		self.spawn()
		set_map(self)

		bat.event.EventBus().add_listener(self)

		if 'InitCamera' in self.scene.objects:
			log.info('Setting initial camera location to cache shaders')
			init_cam = self.scene.objects['InitCamera']
			init_cam['InstantCut'] = 'BOTH'
			init_cam['Priority'] = 2
			# Make sure the loading screen stays until one frame has been
			# rendered by the init camera.
			bat.event.Event('StartLoading', self).send()
			bat.event.Event('AddCameraGoal', 'InitCamera').send(2)
			bat.event.Event('FinishLoading', self).send(3)
			bat.event.Event('RemoveCameraGoal', 'InitCamera').send(4)

	def spawn(self):
		scene = bge.logic.getCurrentScene()
		spawn_point = bat.store.get('/game/level/spawnPoint',
				self['defaultSpawnPoint'])
		if not spawn_point in scene.objects:
			print("Error: spawn point %s not found." % spawn_point)
			spawn_point = self['defaultSpawnPoint']

		bat.bats.add_and_mutate_object(scene, 'Snail', self)
		bat.event.Event('TeleportSnail', spawn_point).send()

	def on_event(self, event):
		if event.message == "LoadLevel":
			# Listen for load events from portals.
			level = bat.store.get('/game/levelFile')
			bge.logic.startGame(level)
		elif event.message == "ShellFound":
			self.on_shell_found(event.body)
		elif event.message == "PickupReceived":
			self.on_pickup(event.body)
		elif event.message == "TeleportCheat":
			self.on_teleport_cheat()
		elif event.message == "PlayFanfare":
			sample = bat.sound.Sample('//Sound/Fanfare1.ogg')
			sample.play()

	def on_shell_found(self, shell):
		bat.event.Event('PlayFanfare').send(15)
		if shell == 'Shell':
			bat.event.Event('ShowDialogue', "You got the Shell! Your beautiful, dependable house and mail van.").send(30)
		elif shell == 'BottleCap':
			bat.event.Event('ShowDialogue', "You got the Bottle Cap! It looks like it can float. It tastes like hoisin sauce - not bad!").send(30)
			bat.store.put('/game/level/mapGoal', None)
			bat.event.Event('MapGoalChanged').send()
			bat.store.put('/game/storySummary', 'gotBottleCap')
		elif shell == 'Nut':
			bat.event.Event('ShowDialogue', "You got the Nut! It's not shiny or red, but it's... heavy. Great!").send(30)
			bat.store.put('/game/storySummary', 'gotNut')
		elif shell == 'Wheel':
			# Wheel is handled specially in story_spider.py
			pass
		elif shell == 'Thimble':
			# Thimble is handled specially in story_ant.py
			pass
		else:
			GameLevel.log.warn('Unrecognised shell %s', shell)

	def on_pickup(self, power_up_type):
		if power_up_type == 'Nectar':
			if not bat.store.get('/game/hasUsedNectar', defaultValue=False):
				bat.event.Event('ShowDialogue', 'Speed boost! These flowers drop nectar which makes you go fast.').send()
				bat.store.put('/game/hasUsedNectar', True)

	def on_teleport_cheat(self):
		character = Scripts.director.Director().mainCharacter
		if character is None:
			return

		GameLevel.log.info("Teleporting!")

		# Find closest
		sps = []
		for sp in self.spawn_points:
			try:
				sps.append(self.scene.objects[sp])
			except KeyError:
				continue
		closest, index, _ = bat.bmath.find_closest(character.worldPosition, sps)
		GameLevel.log.info("Closest: %s @ %s", closest, index)

		# Move to next spawn point
		index += 1
		index %= len(sps)
		next_sp = sps[index]
		GameLevel.log.info("Next: %s @ %s", next_sp, index)
		bat.event.Event('TeleportSnail', next_sp.name).send()


def load_level(caller, level, spawnPoint):
	log.info('Loading next level: %s, %s' % (level, spawnPoint))

	bat.store.put('/game/levelFile', level)
	bat.store.put('/game/level/spawnPoint', spawnPoint, level=level)
	bat.store.save()

	callback = bat.event.Event('LoadLevel')

	# Start showing the loading screen. When it has finished, the LoadLevel
	# event defined above will be sent, and received by GameLevel.
	bat.event.Event('ShowLoadingScreen', (True, callback, True)).send()

def activate_portal(c):
	'''Loads the next level, based on the properties of the owner.

	Properties:
		level: The name of the .blend file to load.
		spawnPoint: The name of the spawn point that the player should start at.
	'''
	if Scripts.director.Director().mainCharacter in c.sensors[0].hitObjectList:
		portal = c.owner
		log.info("Portal touched: %s", portal)
		load_level(portal, portal['level'], portal['spawnPoint'])

def set_spawn_point(c):
	s = c.sensors[0]
	log.debug("Spawn point %s", c.owner)
	if not s.positive:
		return
	char = Scripts.director.Director().mainCharacter
	for ob in s.hitObjectList:
		# Search up through hierarchy in case sensor was triggered by snail in
		# shell
		while ob is not None:
			if ob is char:
				sp = c.owner
				log.info("Setting spawn point to %s", sp)
				bat.store.put('/game/level/spawnPoint', sp.name)
				return
			ob = ob.parent

@bat.utils.some_sensors_positive
@bat.utils.owner
def set_map(o):
	if 'Map' not in o:
		return

	map_file = o['Map']

	if 'MapScaleX' in o:
		scale_x = o['MapScaleX']
	else:
		scale_x = 1.0
	if 'MapScaleY' in o:
		scale_y = o['MapScaleY']
	else:
		scale_y = 1.0

	if 'MapOffsetX' in o:
		off_x = o['MapOffsetX']
	else:
		off_x = 0.0
	if 'MapOffsetY' in o:
		off_y = o['MapOffsetY']
	else:
		off_y = 0.0

	if 'MapZoom' in o:
		zoom = o['MapZoom']
	else:
		zoom = 1.0

	scale = mathutils.Vector((scale_x, scale_y))
	offset = mathutils.Vector((off_x, off_y))
	bat.event.Event('SetMap', (map_file, scale, offset, zoom)).send()
