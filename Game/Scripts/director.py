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

import logging

import bge
import mathutils

import bat.bats
import bat.containers
import bat.event
import bat.utils

import Scripts.impulse

DEBUG = False

class Actor(bat.bats.BX_GameObject):
	'''Actors are generally mobile objects. They can receive movement impulses,
	and can float (and drown!) in water.'''

	log = logging.getLogger(__name__ + ".Actor")

	SANITY_RAY_LENGTH = 10000.0
	SAFE_QUEUE_LENGTH = 10
	MIN_SAFE_DIST = 1.0

	touchedObject = bat.containers.weakprop('touchedObject')

	def __init__(self):
		self._currentLinV = bat.bmath.MINVECTOR.copy()
		self.lastLinV = bat.bmath.MINVECTOR.copy()
		self.localCoordinates = False
		self.touchedObject = None
		# Set property to allow logic bricks to find actors.
		self["Actor"] = True
		# This property is controlled by bat.water
		self["SubmergedFactor"] = 0.0
		self.safe_positions = []
		self.safe_orientations = []

		Director().add_actor(self)

	@bat.bats.expose
	@bat.utils.controller_cls
	def save_location(self, c):
		'''Save the location of the owner for later.'''
		if self["SubmergedFactor"] > 0.0:
			# Water is inherently unsafe
			return
		if not c.sensors['sSafe'].positive:
			return
		if c.sensors['sUnsafe'].positive:
			return

		pos = self.worldPosition.copy()
		orn = self.worldOrientation.copy()
		try:
			if (pos - self.safe_positions[0]).magnitude < Actor.MIN_SAFE_DIST:
				return
		except IndexError:
			pass

		self._save_location(pos, orn)

	def _save_location(self, pos, orn):
		# Store a queue of safe locations. In the event of a respawn, the oldest
		# one will be used; this makes it more likely that the respawn will
		# happen in a comfortable place.
		self.safe_positions.insert(0, pos)
		self.safe_orientations.insert(0, orn)
		# Truncate
		self.safe_positions = self.safe_positions[:Actor.SAFE_QUEUE_LENGTH]
		self.safe_orientations = self.safe_orientations[:Actor.SAFE_QUEUE_LENGTH]

	def relocate(self, pos, rot):
		self.worldPosition = pos
		self.worldOrientation = rot

	def respawn(self):
		self.worldPosition = self.safe_positions[-1]
		self.worldOrientation = self.safe_orientations[-1]
		self.setLinearVelocity(bat.bmath.MINVECTOR)
		self.setAngularVelocity(bat.bmath.MINVECTOR)

	def drown(self):
		'''Called when the Actor is fully submerged in water, and its Oxigen
		property reaches zero. Consider overriding on_drown instead.
		'''
		if self.parent != None:
			return False

		self.respawn()
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
				else:
					Actor.log.info('Safety ray of %s hit %s from the inside!',
							self, ob)
			return False

		# Cast a ray down. If it fails, try again with a small offset - due to
		# numerical error, it is possible for the ray to glance off an edge from
		# the outside and report itself as having hit from the inside.

		# First, look up.
		vecTo = mathutils.Vector((0.0, 0.0, -1.0))
		outside = cast_for_ground(vecTo)
		if not outside:
			vecTo.x = 0.1
			vecTo.y = 0.1
			outside = cast_for_ground(vecTo)

		if not outside:
			Actor.log.info('Object %s is inside the ground!', self)
		return outside

	def get_camera_tracking_point(self):
		return self

class VulnerableActor(Actor):
	'''An actor that has a measure of health, and may be damaged.'''

	_prefix = 'VA_'

	# The number of logic ticks between damages from a particular object
	DAMAGE_FREQUENCY = 120 # 2 seconds

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
		try:
			return self['Health']
		except KeyError:
			return self.maxHealth

	def set_health(self, value):
		'''Set the health of the actor. If this results in a health of zero, the
		actor will die.'''
		if value > self.maxHealth:
			value = self.maxHealth

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

	@bat.bats.expose
	@bat.utils.controller_cls
	def damage_auto(self, c):
		'''Should be attached to a Near or Collision sensor that looks for
		objects with the Damage property. Note that this is used for healing,
		too (when an object has a Damage property with a negative value).'''
		for ob in c.sensors[0].hitObjectList:
			aid = id(ob)
			if aid in self.attackerIds:
				# Wait before attacking again.
				continue

			if 'Shock' in ob and ob['Shock']:
				# This is shocking damage!
				self.shock()
			self.damage(ob['Damage'])
			self.attackerIds[aid] = VulnerableActor.DAMAGE_FREQUENCY
			if 'Death' in ob:
				self.respawn()

		# Count down to next attack.
		for aid in list(self.attackerIds.keys()):
			self.attackerIds[aid] -= 1
			if self.attackerIds[aid] <= 0:
				del self.attackerIds[aid]

	def die(self):
		'''Called when the actor runs out of health. The default action is for
		the object to be destroyed; override this function if you don't want
		that to happen.'''
		self.endObject()

class ActorTest(Actor, bge.types.KX_GameObject):
	def __init__(self, old_owner):
		Actor.__init__(self)
		evt = bat.event.WeakEvent('MainCharacterSet', self)
		bat.event.EventBus().notify(evt)
		evt = bat.event.Event('SetCameraType', 'OrbitCamera')
		bat.event.EventBus().notify(evt)
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

class Director(Scripts.impulse.Handler, metaclass=bat.bats.Singleton):
	_prefix = ''

	SLOW_TICS_PER_FRAME = 10

	mainCharacter = bat.containers.weakprop('mainCharacter')

	def __init__(self):
		self.mainCharacter = None
		self.actors = bat.containers.SafeSet()
		bat.event.EventBus().add_listener(self)
		bat.event.EventBus().replay_last(self, 'MainCharacterSet')
		self.slowMotionCount = 0

	def add_actor(self, actor):
		self.actors.add(actor)

	def rem_actor(self, actor):
		self.actors.discard(actor)

	def on_event(self, event):
		if event.message == 'MainCharacterSet':
			self.mainCharacter = event.body
		elif event.message == 'GameModeChanged':
			if event.body != 'Playing':
				Scripts.impulse.Input().add_handler(self, 'STORY')
			else:
				Scripts.impulse.Input().remove_handler(self)

	@bat.bats.expose
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
					actor.respawn()
			actor.record_velocity()

	@bat.bats.expose
	@bat.utils.all_sensors_positive
	@bat.utils.controller_cls
	def toggle_suspended(self, c):
		if self.mainCharacter == None:
			return

		scene = self.mainCharacter.scene
		if scene.suspended:
			scene.resume()
		else:
			scene.suspend()

	@bat.bats.expose
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
