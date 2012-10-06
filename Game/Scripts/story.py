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


class CondHasShell(bat.story.Condition):
	def __init__(self, name):
		self.name = name

	def evaluate(self, c):
		return self.name in Scripts.inventory.Shells().get_shells()

	def get_short_name(self):
		return " HS"

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
		evt = bat.event.Event('GravityChanged', g)
		bat.event.EventBus().notify(evt)

		evt = bat.event.Event('GameModeChanged', 'Playing')
		bat.event.EventBus().notify(evt)

class GameLevel(Level):
	'''A level that is part of the main game. Handles things such as spawn
	points and level transitions. Test scenes may use these too, but it is not
	required.'''

	def __init__(self, old_owner):
		Level.__init__(self, old_owner)

		self.spawn()
		self.set_map()

		bat.event.EventBus().add_listener(self)

	def spawn(self):
		scene = bge.logic.getCurrentScene()
		spawn_point = bat.store.get('/game/level/spawnPoint',
				self['defaultSpawnPoint'])
		if not spawn_point in scene.objects:
			print("Error: spawn point %s not found." % spawn_point)
			spawn_point = self['defaultSpawnPoint']

		bat.bats.add_and_mutate_object(scene, 'Snail', self)
		bat.event.Event('TeleportSnail', spawn_point).send()

	def set_map(self):
		if 'Map' not in self:
			return

		map_file = self['Map']

		if 'MapScaleX' in self:
			scale_x = self['MapScaleX']
		else:
			scale_x = 1.0
		if 'MapScaleY' in self:
			scale_y = self['MapScaleY']
		else:
			scale_y = 1.0

		if 'MapOffsetX' in self:
			off_x = self['MapOffsetX']
		else:
			off_x = 0.0
		if 'MapOffsetY' in self:
			off_y = self['MapOffsetY']
		else:
			off_y = 0.0

		if 'MapZoom' in self:
			zoom = self['MapZoom']
		else:
			zoom = 1.0

		scale = mathutils.Vector((scale_x, scale_y))
		offset = mathutils.Vector((off_x, off_y))
		bat.event.Event('SetMap', (map_file, scale, offset, zoom)).send()

	def on_event(self, event):
		if event.message == "LoadLevel":
			# Listen for load events from portals.
			level = bat.store.get('/game/levelFile')
			bge.logic.startGame(level)

def load_level(caller, level, spawnPoint):
	print('Loading next level: %s, %s' % (level, spawnPoint))

	bat.store.put('/game/levelFile', level)
	bat.store.put('/game/level/spawnPoint', spawnPoint, level=level)
	bat.store.save()

	callback = bat.event.Event('LoadLevel')

	# Start showing the loading screen. When it has finished, the LoadLevel
	# event defined above will be sent, and received by GameLevel.
	bat.event.Event('ShowLoadingScreen', (True, callback)).send()

def activate_portal(c):
	'''Loads the next level, based on the properties of the owner.

	Properties:
		level: The name of the .blend file to load.
		spawnPoint: The name of the spawn point that the player should start at.
	'''
	if Scripts.director.Director().mainCharacter in c.sensors[0].hitObjectList:
		portal = c.owner
		load_level(portal, portal['level'], portal['spawnPoint'])
