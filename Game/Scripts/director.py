#
# Copyright 2009-2011 Alex Fraser <alex@phatcore.com>
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

import weakref

import mathutils

import bxt.types
import bxt.utils

class Actor:
	def __init__(self):
		self.safePosition = self.worldPosition
		Director().add_actor(self)

	def restore_location(self):
		self.worldPosition = self.safePosition

@bxt.utils.singleton('update', 'on_movement_impulse', 'on_button1',
		'on_button2', prefix='')
class Director(bxt.utils.EventListener):
	SANITY_RAY_LENGTH = 10000.0

	def __init__(self):
		self.mainCharacter = None
		self.actors = weakref.WeakSet()
		bxt.utils.EventBus().addListener(self)
		bxt.utils.EventBus().replayLast(self, 'MainCharacterSet')

	def add_actor(self, actor):
		self.actors.add(actor)
	def rem_actor(self, actor):
		self.actors.remove(actor)

	def onEvent(self, event):
		if event.message == 'MainCharacterSet':
			self.mainCharacter = event.body

	def update(self):
		'''Make sure all actors are within the world.'''
		for actor in self.actors:
			if not self.is_inside_world(actor):
				actor.restore_location("Ouch! You got squashed.")
			actor.RecordVelocity()

	def is_inside_world(self, actor):
		'''Make sure the actor is in a sensible place. This searches for objects
		with the 'Ground' property directly above and directly below the actor.
		A free actor is considered to be outside the world if:
		 - No ground is found.
		 - Ground is found but the actor is on the wrong side of it, i.e. the
		   surface normal is facing away from the actor.
		Otherwise, the actor is inside the world.
		
		If the actor is the child of another object, it is always considered to
		be inside the world.
		
		Returns True if the object seems to be inside the world; False
		otherwise.
		'''
		if actor.parent != None:
			# Responsibility delegated to parent.
			return True

		foundGround = False
		outsideGround = True

		# First, look up.
		origin = actor.worldPosition.copy()
		vec = bxt.math.ZAXIS.copy()
		through = origin + vec
		ob, _, normal = self.owner.rayCast(
			through,             # to
			origin,              # from
			Director.SANITY_RAY_LENGTH,   # dist
			'Ground',            # prop
			1,                   # face
			1                    # xray
		)

		if ob != None:
			# Found some ground. Are we outside of it?
			foundGround = True
			if (ob):
				if normal.dot(vec) > 0.0:
					# Hit was from inside.
					outsideGround = False

		# Now look down.
		vec = bxt.math.ZAXIS.copy()
		vec.negate()
		through = origin + vec
		ob, _, normal = self.owner.rayCast(
			through,             # to
			origin,              # from
			Director.SANITY_RAY_LENGTH,   # dist
			'Ground',            # prop
			1,                   # face
			1                    # xray
		)

		if ob != None:
			# Found some ground. Are we outside of it?
			foundGround = True
			if (ob):
				if normal.dot(vec) > 0.0:
					# Hit was from inside.
					outsideGround = False

		return foundGround and outsideGround

	@bxt.utils.controller_cls
	def on_movement_impulse(self, c):
		fwd = c.sensors['sForward']
		back = c.sensors['sBackward']
		left = c.sensors['sLeft']
		right = c.sensors['sRight']
		if self.mainCharacter:
			self.mainCharacter.on_movement_impulse(fwd.positive, back.positive,
					left.positive, right.positive)

	@bxt.utils.controller_cls
	def on_button1(self, c):
		s = c.sensors[0]
		if self.mainCharacter:
			self.mainCharacter.on_button1(s.positive, s.triggered)

	@bxt.utils.controller_cls
	def on_button2(self, c):
		s = c.sensors[0]
		if self.mainCharacter:
			self.mainCharacter.on_button2(s.positive, s.triggered)

	def _set_main_character(self, object):
		def autorelease(ref):
			self._mainCharacter = None

		if object != None:
			self._mainCharacter = weakref.ref(object, autorelease)
		else:
			self._mainCharacter = None
	def _get_main_character(self):
		if self._mainCharacter == None:
			return None
		else:
			return self._mainCharacter()
	mainCharacter = property(_get_main_character, _set_main_character)

Director()
