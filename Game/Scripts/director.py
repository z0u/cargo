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

import bge
import mathutils

import bxt.types
import bxt.utils

from . import impulse

DEBUG = False

class Actor(bxt.types.BX_GameObject):
	'''Actors are generally mobile objects. They can receive movement impulses,
	and can float (and drown!) in water.'''

	SANITY_RAY_LENGTH = 10000.0

	touchedObject = bxt.types.weakprop('touchedObject')

	def __init__(self):
		self.save_location()
		self._currentLinV = bxt.bmath.MINVECTOR.copy()
		self.lastLinV = bxt.bmath.MINVECTOR.copy()
		self.localCoordinates = False
		self.touchedObject = None
		# Set property to allow logic bricks to find actors.
		self["Actor"] = True
		Director().add_actor(self)

	@bxt.types.expose
	def save_location(self):
		'''Save the location of the owner for later. This may happen when the
		object touches a safe point.'''
		self.safePosition = self.worldPosition.copy()
		self.safeOrientation = self.worldOrientation.copy()

	def inherit_safe_location(self, otherActor):
		self.safePosition = otherActor.safePosition
		self.safeOrientation = otherActor.safeOrientation

	def relocate(self, pos, rot):
		self.worldPosition = pos
		self.worldOrientation = rot

	def respawn(self, reason = None):
		self.worldPosition = self.safePosition
		self.worldOrientation = self.safeOrientation
		self.setLinearVelocity(bxt.bmath.MINVECTOR)
		self.setAngularVelocity(bxt.bmath.MINVECTOR)
		if self == Director().mainCharacter and reason != None:
			evt = bxt.types.Event('ShowDialogue', reason)
			bxt.types.EventBus().notify(evt)

	def drown(self):
		'''Called when the Actor is fully submerged in water, and its Oxigen
		property reaches zero. Consider overriding on_drown instead.
		'''
		if self.parent != None:
			return False

		self.respawn("You drowned! Try again.")
		self.on_drown()

	def on_drown(self):
		pass

	def record_velocity(self):
		'''Store the velocity of this object for one frame. See
		get_last_linear_velocity.'''
		self.lastLinV = self._currentLinV
		self._currentLinV = self.getLinearVelocity().copy()

	def get_last_linear_velocity(self):
		'''Get the second-last velocity of this actor. This is useful in touch
		handlers, because the object's energy is absorbed by the time the
		handler is called.'''
		return self.lastLinV

	def is_inside_world(self):
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
		if self.parent != None:
			# Responsibility delegated to parent.
			return True

		origin = self.worldPosition.copy()
		def cast_for_ground(vec):
			through = origin + vec
			ob, _, normal = self.rayCast(
				through,             # to
				origin,              # from
				Actor.SANITY_RAY_LENGTH,   # dist
				'Ground',            # prop
				1,                   # face
				1                    # xray
			)
			if ob != None:
				if "TwoSided" in ob:
					return True
				elif normal.dot(vec) <= 0.0:
					# Hit was from outside.
					return True
			return False

		# Cast a ray down. If it fails, try again with a small offset - due to
		# numerical error, it is possible for the ray to glance off an edge from
		# the outside and report itself as having hit from the inside.

		# First, look up.
		vecTo = mathutils.Vector((0.0, 0.0, -1.0))
		if cast_for_ground(vecTo):
			return True
		else:
			vecTo.x = 0.1
			vecTo.y = 0.1
			return cast_for_ground(vecTo)

	def get_camera_tracking_point(self):
		return self

class VulnerableActor(Actor):
	'''An actor that has a measure of health, and may be damaged.'''

	_prefix = 'VA_'

	# The number of logic ticks between damages from a particular object
	DAMAGE_FREQUENCY = 60

	def __init__(self, maxHealth = 1):
		Actor.__init__(self)
		self.maxHealth = maxHealth
		self.set_health(maxHealth)
		# A map of current passive attackers, so we can keep track of when we
		# were last attacked. NOTE this keeps only the IDs of the objects as its
		# keys to prevent invalid object access.
		self.attackerIds = {}

	def on_drown(self):
		'''Respawn happens automatically; we just need to apply damage.'''
		self.damage(amount=1)

	def get_health(self):
		return self['Health']

	def set_health(self, value):
		'''Set the health of the actor. If this results in a health of zero, the
		actor will die.'''
		if value > self.maxHealth:
			value = self.maxHealth

		try:
			if self['Health'] == value:
				return
		except KeyError:
			pass

		self['Health'] = value
		if value <= 0:
			self.die()

	def damage(self, amount=1):
		'''Inflict damage on the actor. If this results in a health of zero, the
		actor will die.
		@param amount The amount of damage to inflict (int).'''

		self.set_health(self.get_health() - amount)

	def shock(self):
		'''The actor should have its current action interrupted, and may become
		stunned.'''
		pass

	@bxt.types.expose
	@bxt.utils.controller_cls
	def damage_auto(self, c):
		'''Should be attached to a Near or Collision sensor that looks for
		objects with the Damage property.'''
		def apply_damage(ob):
			if 'Shock' in ob and ob['Shock']:
				self.shock()
			self.damage(ob['Damage'])

		# Walk the list of attackers and decide which ones will actually deal
		# damage on this frame.
		currentAttackers = []
		for ob in c.sensors[0].hitObjectList:
			aId = id(ob)
			currentAttackers.append(aId)
			if aId in self.attackerIds:
				self.attackerIds[aId] -= 1
				if self.attackerIds[aId] <= 0:
					apply_damage(ob)
					self.attackerIds[aId] = VulnerableActor.DAMAGE_FREQUENCY
			else:
				apply_damage(ob)
				self.attackerIds[aId] = VulnerableActor.DAMAGE_FREQUENCY

		# Remove stale attackers.
		for aId in list(self.attackerIds.keys()):
			if aId not in currentAttackers:
				del self.attackerIds[aId]

	def die(self):
		'''Called when the actor runs out of health. The default action is for
		the object to be destroyed; override this function if you don't want
		that to happen.'''
		self.endObject()

class ActorTest(Actor, bge.types.KX_GameObject):
	def __init__(self, old_owner):
		Actor.__init__(self)
		evt = bxt.types.WeakEvent('MainCharacterSet', self)
		bxt.types.EventBus().notify(evt)
		evt = bxt.types.Event('SetCameraType', 'OrbitCamera')
		bxt.types.EventBus().notify(evt)
	def on_movement_impulse(self, left, right, fwd, back):
		pass
	def on_button1(self, pos, trig):
		pass
	def on_button2(self, pos, trig):
		pass
	def on_next(self, pos, trig):
		pass
	def on_previous(self, pos, trig):
		pass

class Director(impulse.Handler, metaclass=bxt.types.Singleton):
	_prefix = ''

	SLOW_TICS_PER_FRAME = 10

	mainCharacter = bxt.types.weakprop('mainCharacter')

	def __init__(self):
		self.mainCharacter = None
		self.actors = bxt.types.SafeSet()
		bxt.types.EventBus().add_listener(self)
		bxt.types.EventBus().replay_last(self, 'MainCharacterSet')
		self.slowMotionCount = 0

	def add_actor(self, actor):
		self.actors.add(actor)

	def rem_actor(self, actor):
		self.actors.discard(actor)

	def on_event(self, event):
		if event.message == 'MainCharacterSet':
			self.mainCharacter = event.body
		elif event.message == 'SuspendInput':
			if event.body == True:
				impulse.Input().add_handler(self, 'STORY')
			else:
				impulse.Input().remove_handler(self)

	@bxt.types.expose
	def update(self):
		# Make sure all actors are within the world.
		for actor in self.actors:
			if not actor.is_inside_world():
				if DEBUG:
					actor.scene.suspend()
					print("Actor %s was outside world." % actor.name)
					print("Loc:", actor.worldPosition)
					print("Vel:", actor.worldLinearVelocity)
					print("PrevVel:", actor.lastLinV)
				else:
					actor.respawn("Ouch! You got squashed.")
			actor.record_velocity()

	@bxt.types.expose
	@bxt.utils.all_sensors_positive
	@bxt.utils.controller_cls
	def toggle_suspended(self, c):
		if self.mainCharacter == None:
			return

		scene = self.mainCharacter.scene
		if scene.suspended:
			scene.resume()
		else:
			scene.suspend()

	@bxt.types.expose
	def slow_motion_pulse(self):
		if self.mainCharacter == None:
			return

		scene = self.mainCharacter.scene
		self.slowMotionCount += 1
		if self.slowMotionCount == self.SLOW_TICS_PER_FRAME:
			scene.resume()
		elif self.slowMotionCount > self.SLOW_TICS_PER_FRAME:
			scene.suspend()
			self.slowMotionCount = 0

Director()
