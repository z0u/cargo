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

class Actor(bxt.types.BX_GameObject):
	'''Actors are generally mobile objects. They can receive movement impulses,
	and can float (and drown!) in water.'''

	SANITY_RAY_LENGTH = 10000.0

	touchedObject = bxt.types.weakprop('touchedObject')

	def __init__(self):
		self.save_location()
		self._currentLinV = bxt.math.MINVECTOR.copy()
		self.lastLinV = bxt.math.MINVECTOR.copy()
		self.localCoordinates = False
		self.touchedObject = None
		Director().add_actor(self)

	@bxt.types.expose
	def save_location(self):
		'''Save the location of the owner for later. This may happen when the
		object touches a safe point.'''
		self.safePosition = self.worldPosition.copy()
		self.safeOrientation = self.worldOrientation.copy()

	def respawn(self, reason = None):
		self.worldPosition = self.safePosition
		self.worldOrientation = self.safeOrientation
		self.setLinearVelocity(bxt.math.MINVECTOR)
		self.setAngularVelocity(bxt.math.MINVECTOR)
		if self == Director().mainCharacter and reason != None:
			evt = bxt.types.Event('ShowMessage', reason)
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

		foundGround = False
		outsideGround = True

		# First, look up.
		origin = self.worldPosition.copy()
		vec = bxt.math.ZAXIS.copy()
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
		ob, _, normal = self.rayCast(
			through,             # to
			origin,              # from
			Actor.SANITY_RAY_LENGTH,   # dist
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

class Director(metaclass=bxt.types.Singleton):
	_prefix = ''

	SLOW_TICS_PER_FRAME = 10

	mainCharacter = bxt.types.weakprop('mainCharacter')

	def __init__(self):
		self.mainCharacter = None
		self.actors = bxt.types.GameObjectSet()
		self.inputSuspended = False
		bxt.types.EventBus().add_listener(self)
		bxt.types.EventBus().replay_last(self, 'MainCharacterSet')
		bxt.types.EventBus().replay_last(self, 'SuspendInput')
		self.slowMotionCount = 0

	def add_actor(self, actor):
		self.actors.add(actor)

	def rem_actor(self, actor):
		self.actors.discard(actor)

	def on_event(self, event):
		if event.message == 'MainCharacterSet':
			self.mainCharacter = event.body
		elif event.message == 'SuspendInput':
			self.inputSuspended = event.body

	@bxt.types.expose
	def update(self):
		'''Make sure all actors are within the world.'''
		for actor in self.actors:
			if not actor.is_inside_world():
				actor.respawn("Ouch! You got squashed.")
			actor.record_velocity()

	@bxt.types.expose
	@bxt.utils.controller_cls
	def on_movement_impulse(self, c):
		fwd = c.sensors['sForward']
		fwd2 = c.sensors['sForward2']
		back = c.sensors['sBackward']
		back2 = c.sensors['sBackward2']
		left = c.sensors['sLeft']
		left2 = c.sensors['sLeft2']
		right = c.sensors['sRight']
		right2 = c.sensors['sRight2']
		if self.mainCharacter != None and not self.inputSuspended:
			self.mainCharacter.on_movement_impulse(
				fwd.positive or fwd2.positive,
				back.positive or back2.positive,
				left.positive or left2.positive,
				right.positive or right2.positive)

	@bxt.types.expose
	@bxt.utils.controller_cls
	def on_button1(self, c):
		s = c.sensors[0]
		if self.mainCharacter != None and not self.inputSuspended:
			self.mainCharacter.on_button1(s.positive, s.triggered)

	@bxt.types.expose
	@bxt.utils.controller_cls
	def on_button2(self, c):
		s = c.sensors[0]
		if self.mainCharacter != None and not self.inputSuspended:
			self.mainCharacter.on_button2(s.positive, s.triggered)

	@bxt.types.expose
	@bxt.utils.controller_cls
	def on_next(self, c):
		s = c.sensors[0]
		if self.mainCharacter != None and not self.inputSuspended:
			self.mainCharacter.on_next(s.positive, s.triggered)

	@bxt.types.expose
	@bxt.utils.controller_cls
	def on_previous(self, c):
		s = c.sensors[0]
		if self.mainCharacter != None and not self.inputSuspended:
			self.mainCharacter.on_previous(s.positive, s.triggered)

	@bxt.types.expose
	@bxt.utils.controller_cls
	def on_view_button(self, c):
		s = c.sensors[0]
		if s.positive and not self.inputSuspended:
			evt = bxt.types.Event('ResetCameraPos', None)
			bxt.types.EventBus().notify(evt)

	def _get_main_scene(self):
		if self.mainCharacter == None:
			return None
		for s in bge.logic.getSceneList():
			if self.mainCharacter in s.objects:
				return s
		return None

	@bxt.types.expose
	@bxt.utils.all_sensors_positive
	@bxt.utils.controller_cls
	def toggle_suspended(self, c):
		if self.mainCharacter == None:
			return

		scene = self._get_main_scene()
		if scene == None:
			return

		if scene.suspended:
			scene.resume()
		else:
			scene.suspend()

	@bxt.types.expose
	def slow_motion_pulse(self):
		scene = self._get_main_scene()
		if scene == None:
			return

		self.slowMotionCount += 1
		if self.slowMotionCount == self.SLOW_TICS_PER_FRAME:
			scene.resume()
		elif self.slowMotionCount > self.SLOW_TICS_PER_FRAME:
			scene.suspend()
			self.slowMotionCount = 0

Director()
