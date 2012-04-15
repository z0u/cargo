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

from . import director
from . import ui
from . import camera
from .story import *
from . import shaders

class LevelBeehive(GameLevel):
	def __init__(self, oldOwner):
		GameLevel.__init__(self, oldOwner)
		shaders.ShaderCtrl().set_mist_colour(
				mathutils.Vector((0.0, 0.0, 0.0)))
		#bxt.music.play("//Sound/Music/bumbly_intro.wav", "//Sound/Music/bumbly.wav", volume=0.4)
		bxt.music.play("//Sound/Music/bumbly.wav", volume=0.4)

class Bucket(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	DIR_UP = 1
	DIR_DOWN = 2

	LOC_TOP = 1
	LOC_BOTTOM = 2

	PROJECTION = [0.0, 0.0, 20.0]

	camTop = bxt.types.weakprop('camTop')
	camBottom = bxt.types.weakprop('camBottom')
	currentCamera = bxt.types.weakprop('currentCamera')
	player = bxt.types.weakprop('player')

	def __init__(self, old_owner):
		scene = bge.logic.getCurrentScene()
		self.water = self.find_descendant([('Type', 'BucketWater')])
		self.camTop = scene.objects['BucketTopCam']
		self.camBottom = scene.objects['BucketBottomCam']
		self.currentCamera = None

		self.direction = Bucket.DIR_UP
		self.loc = Bucket.LOC_BOTTOM
		self.isTouchingPlayer = False

	@bxt.types.expose
	@bxt.utils.controller_cls
	def update(self, c):
		sCollision = c.sensors['sPlayer']
		self.frame_changed()

		if director.Director().mainCharacter in sCollision.hitObjectList:
			self.set_touching_player(True)
		else:
			self.set_touching_player(False)

	def spawn_water_ball(self):
		'''Drop a ball of water at the top to make a splash.'''
		scene = bge.logic.getCurrentScene()
		waterBall = scene.addObject(self['WaterBallTemplate'], self.water)
		waterBall.setLinearVelocity(self.water.getAxisVect(Bucket.PROJECTION))

	def set_direction(self, direction):
		if direction == self.direction:
			return

		if direction == Bucket.DIR_UP:
			self.water.setVisible(True, False)
		else:
			self.water.setVisible(False, False)
			self.spawn_water_ball()
		self.direction = direction

	def set_location(self, loc):
		if loc == self.loc:
			return

		if loc == Bucket.LOC_TOP:
			self.water.setVisible(True, False)
		else:
			self.water.setVisible(False, False)
		self.loc = loc
		self.update_camera()

	def frame_changed(self):
		frame = self['Frame']
		if frame < 170:
			self.set_direction(Bucket.DIR_UP)
		else:
			self.set_direction(Bucket.DIR_DOWN)

		if frame > 100 and frame < 260:
			self.set_location(Bucket.LOC_TOP)
		else:
			self.set_location(Bucket.LOC_BOTTOM)

	def update_camera(self):
		cam = None
		if self.isTouchingPlayer:
			if self.loc == Bucket.LOC_BOTTOM:
				cam = self.camBottom
			else:
				cam = self.camTop

		if cam == None and self.currentCamera != None:
			# Player is being ejected; update camera position to prevent
			# jolting.
			pos = self.currentCamera.worldPosition
			orn = self.currentCamera.worldOrientation
			bxt.types.Event('RelocatePlayerCamera', (pos, orn)).send()

		if cam == self.currentCamera:
			return

		if self.currentCamera != None:
			camera.AutoCamera().remove_goal(self.currentCamera)
		if cam != None:
			camera.AutoCamera().add_goal(cam)

		self.currentCamera = cam

	def set_touching_player(self, isTouchingPlayer):
		if isTouchingPlayer == self.isTouchingPlayer:
			return

		self.isTouchingPlayer = isTouchingPlayer
		if isTouchingPlayer:
			bxt.types.EventBus().notify(bxt.types.Event('SuspendInput', True))
		else:
			bxt.types.EventBus().notify(bxt.types.Event('SuspendInput', False))
		self.update_camera()
