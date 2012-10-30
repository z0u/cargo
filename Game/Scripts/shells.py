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

import logging

import bge
import mathutils

import bat.utils
import bat.bats
import bat.containers
import bat.event
import bat.bmath
import bat.sound

import Scripts.director
import bat.impulse
import Scripts.inventory

ZAXIS = mathutils.Vector((0.0, 0.0, 1.0))
EPSILON = 0.001

log = logging.getLogger(__name__)

def factory(name):
	scene = bge.logic.getCurrentScene()

	if not name in scene.objectsInactive:
		log.info("Loading shells")
		try:
			bge.logic.LibLoad('//ItemLoader.blend', 'Scene', load_actions=True)
		except ValueError:
			log.warn("Failed to open ItemLoader. May be open already. "
					"Proceeding...")

	return bat.bats.add_and_mutate_object(scene, name, name)

class ShellBase(bat.impulse.Handler, Scripts.director.Actor, bge.types.KX_GameObject):
	_prefix = 'SB_'

	log = logging.getLogger(__name__ + '.ShellBase')

	S_INIT     = 1
	S_IDLE     = 2
	S_ANCHOR   = 17
	S_CARRIED  = 3
	S_OCCUPIED = 4
	S_GRASPED  = 5 # Liked CARRIED, but not carried by a snail.
	S_ALWAYS   = 16

	snail = bat.containers.weakprop('snail')

	def __init__(self, old_owner):
		Scripts.director.Actor.__init__(self)

		self.snail = None
		self.cargoHook = self.find_descendant([('Type', 'CargoHook')])
		self.occupier = self.find_descendant([('Type', 'Occupier')])

		bat.utils.set_state(self.occupier, 1)

		self.set_default_prop('LookAt', 10)
		self['_DefaultLookAt'] = self['LookAt']
		self.set_state(ShellBase.S_IDLE)
		self.add_state(ShellBase.S_ALWAYS)

		bat.event.EventBus().add_listener(self)

	def on_event(self, evt):
		if evt.message == 'AnchorShell':
			# Only respond to this message if this shell has an owner.
			if self.is_occupied:
				if isinstance(evt.body, str):
					anchor = self.scene.objects[evt.body]
				else:
					anchor = evt.body
				self.anchor(anchor)

	def on_picked_up(self, snail, animate):
		'''Called when a snail picks up this shell.'''
		self.snail = snail
		self['Carried'] = True
		self.set_state(ShellBase.S_CARRIED)
		self.add_state(ShellBase.S_ALWAYS)
		self['NoPickupAnim'] = not animate
		self['_DefaultLookAt'] = self['LookAt']
		self['LookAt'] = -1
		# Clear anchor flag, if it was set.
		self.rem_state(ShellBase.S_ANCHOR)

	def on_grasped(self):
		self.set_state(ShellBase.S_GRASPED)
		self.add_state(ShellBase.S_ALWAYS)

	def on_dropped(self):
		'''Called when a snail drops this shell.'''
		self.snail = None
		self['Carried'] = False
		self.set_state(ShellBase.S_IDLE)
		self.add_state(ShellBase.S_ALWAYS)
		self.localScale = (1.0, 1.0, 1.0)
		self['LookAt'] = self['_DefaultLookAt']

	def on_pre_enter(self):
		'''Called when the snail starts to enter this shell. This may happen
		several frames before control is passed, but may be on the same frame.'''
		if self.occupier:
			bat.utils.set_state(self.occupier, 2)

	def on_entered(self):
		'''Called when a snail enters this shell (just after
		control is transferred).'''
		self.set_state(ShellBase.S_OCCUPIED)
		self.add_state(ShellBase.S_ALWAYS)

		bat.impulse.Input().add_handler(self)
		bat.event.WeakEvent('MainCharacterSet', self).send()

	def on_exited(self):
		'''Called when a snail exits this shell (as control is transferred).'''

		bat.impulse.Input().remove_handler(self)

		self.set_state(ShellBase.S_CARRIED)
		self.add_state(ShellBase.S_ALWAYS)
		self.localScale = (1.0, 1.0, 1.0)
		self['CurrentBuoyancy'] = self['Buoyancy']
		if self.occupier:
			bat.utils.set_state(self.occupier, 1)
		# Clear anchor flag, if it was set.
		self.rem_state(ShellBase.S_ANCHOR)

	def on_post_exit(self):
		'''Called when the snail has finished its exit shell
		animation.'''
		pass

	def can_handle_input(self, state):
		# Allow the snail to handle the camera event
		return state.name != 'Camera'

	def handle_input(self, state):
		if state.name == '1':
			self.handle_bt_1(state)
		elif state.name == 'Movement':
			self.handle_movement(state)

	def handle_bt_1(self, state):
		if not self.is_occupied:
			ShellBase.log.warn("Shell %s received impulse when not occupied.",
				self.name)
			return

		if state.activated:
			self.snail.exit_shell(animate = True)

	def handle_movement(self, state):
		pass

	def _save_location(self, pos, orn):
		if not self.is_occupied:
			return
		Scripts.director.Actor._save_location(self, pos, orn)
		self.snail._save_location(pos, orn)

	def respawn(self):
		if self.is_occupied:
			self.snail.respawn()
		elif self.is_carried:
			# Do nothing: shell is being carried, but snail is still in control
			# (so presumably the snail will be told to respawn too).
			pass
		else:
			# This should only happen if the snail dropped the shell, in which
			# case it can be reclaimed by pressing a button.
			self.endObject()

	def on_drown(self):
		if self.snail:
			self.snail.damage(amount=1)

	def on_oxygen_set(self):
		if self.is_occupied:
			bat.event.Event('OxygenSet', self['Oxygen']).send()

	@property
	def is_occupied(self):
		return self.has_state(ShellBase.S_OCCUPIED)
	@property
	def is_carried(self):
		return self.has_state(ShellBase.S_CARRIED)
	@property
	def is_grasped(self):
		return self.has_state(ShellBase.S_GRASPED)

	@bat.bats.expose
	def update_anchor(self):
		if not self.has_state(ShellBase.S_ANCHOR):
			return
		bat.bmath.copy_transform(self.anchor_ob, self)
		self.worldLinearVelocity = bat.bmath.MINVECTOR

	def anchor(self, anchor_ob):
		self.add_state(ShellBase.S_ANCHOR)
		self.anchor_ob = anchor_ob

class Shell(ShellBase):

	equip_message = 'You got the Shell! Your beautiful, dependable house and mail van.'

	def __init__(self, old_owner):
		ShellBase.__init__(self, old_owner)

		self.direction_mapper = bat.impulse.DirectionMapperGlobal()

		self.rolling_sound = bat.sound.Sample('//Sound/cc-by/Rolling.ogg')
		self.rolling_sound.loop = True
		self.rolling_sound.add_effect(bat.sound.Localise(self))
		self.rolling_sound.add_effect(bat.sound.FadeByLinV(self))

	@bat.bats.expose
	def rolling(self):
		if not self['OnGround']:
			self.rolling_sound.stop()
			return

		self.rolling_sound.play()

	def on_pre_enter(self):
		ShellBase.on_pre_enter(self)
		bat.event.Event('SetCameraType', 'PathCamera').send()

	def on_exited(self):
		ShellBase.on_exited(self)
		self.rolling_sound.add_effect(bat.sound.Fader())

#	def on_post_exit(self):
#		ShellBase.on_post_exit(self)
#		self.rolling_sound.stop()

	def handle_movement(self, state):
		'''Make the shell roll around based on user input.'''

		if not self['OnGround']:
			return

		self.direction_mapper.update(self, state.direction)
		force = self.direction_mapper.direction * state.direction.magnitude * self['Power']
		self.applyImpulse((0.0, 0.0, 0.0), force)

class WheelCameraAlignment:
	'''
	Aligns the camera with the wheel. This needs a special class because the
	wheel's z-axis points out to the side.

	@see: camera.OrbitCameraAlignment
	'''

	def get_home_axes(self, camera, target):
		upDir = bat.bmath.ZAXIS.copy()
		leftDir = target.getAxisVect(bat.bmath.ZAXIS)
		fwdDir = upDir.cross(leftDir)
		return fwdDir, upDir

	def get_axes(self, camera, target):
		return self.get_home_axes(camera, target)

class Wheel(ShellBase):

	equip_message = "You got the Wheel! It's strong and fast."

	# Speed needed to demolish stuff.
	DESTRUCTION_SPEED = 5.0

	TURN_SPEED = 2.0
	# How much the turning speed affects forward speed
	TURN_INFLUENCE = 0.6

	ROT_SPEED = 20.0
	# How quickly the wheel speeds up.
	SPEED_FAC = 0.05

	# How strongly the wheel tries to stay upright
	ORN_FAC = 0.2

	# How much gravity the wheel feels while driving fast (affects jumping).
	FLY_POWER = 1.0 / 3.0

	def __init__(self, old_owner):
		ShellBase.__init__(self, old_owner)
		self._reset_speed()
		self.fly_power = 0.0

		self.enter_sound = bat.sound.Sample('//Sound/CarStart.ogg')
		self.enter_sound.volume = 0.6
		self.exit_sound = bat.sound.Sample('//Sound/DoorOpenClose.ogg')
		self.exit_sound.volume = 0.5

		self.driving_sound = bat.sound.Sample('//Sound/cc-by/Driving.ogg')
		self.driving_sound.volume = 0.7
		self.driving_sound.loop = True
		self.driving_sound.add_effect(bat.sound.Localise(self))
		self.driving_sound.add_effect(bat.sound.PitchByAngV(self))

		bat.event.EventBus().replay_last(self, 'GravityChanged')

	def on_event(self, evt):
		ShellBase.on_event(self, evt)
		if evt.message == 'GravityChanged':
			self.fly_power = evt.body * -(1.0 - Wheel.FLY_POWER)

	def orient(self, turn_direction):
		'''Try to make the wheel sit upright.'''
		zlocal = self.getAxisVect(ZAXIS)
		horizontal = zlocal.copy()
		horizontal.z = -turn_direction * 0.25
		horizontal.normalize
		self.alignAxisToVect(horizontal, 2)

	def _reset_speed(self):
		self.currentRotSpeed = 0.0
		self.currentTurnSpeed = 0.0

	def on_pre_enter(self):
		ShellBase.on_pre_enter(self)
		self._reset_speed()
		#bat.event.Event('SetCameraType', 'PathCamera').send()
		self.enter_sound.play()

	def on_entered(self):
		ShellBase.on_entered(self)

		bat.event.Event('SetCameraType', 'OrbitCamera').send()
		alignment = WheelCameraAlignment()
		bat.event.Event('SetCameraAlignment', alignment).send()
		self.driving_sound.play()

	def on_exited(self):
		ShellBase.on_exited(self)
		self.driving_sound.stop()
		self.exit_sound.play()

	def handle_movement(self, state):
		#
		# Decide which direction to roll or turn.
		#
		direction = state.direction.copy()
		direction.y = max(direction.y * 0.5 + 0.5, 0.01)
		self.currentTurnSpeed = bat.bmath.lerp(self.currentTurnSpeed,
				Wheel.TURN_SPEED * -direction.x, Wheel.SPEED_FAC)

		self.orient(self.currentTurnSpeed)

		#
		# For jumping: when driving fast, reduce gravity!
		#
		if direction.y > 0.5:
			self.applyForce(self.fly_power)

		#
		# Turn (steer). Note that this is applied to the Z axis, but in world
		# space.
		#
		angv = ZAXIS * self.currentTurnSpeed

		#
		# Apply acceleration. The speed will be influenced by the rate that
		# the wheel is being steered at (above).
		#
		turnStrength = abs(self.currentTurnSpeed) / Wheel.TURN_SPEED
		targetRotSpeed = Wheel.ROT_SPEED * bat.bmath.safe_invert(
				turnStrength, Wheel.TURN_INFLUENCE)
		targetRotSpeed *= direction.y

		self.currentRotSpeed = bat.bmath.lerp(self.currentRotSpeed,
				targetRotSpeed, Wheel.SPEED_FAC)

		angv2 = self.getAxisVect(ZAXIS) * self.currentRotSpeed
		self.setAngularVelocity(angv + angv2, False)

	def can_destroy_stuff(self):
		if not self.is_occupied:
			return False
		if self.get_last_linear_velocity().magnitude < Wheel.DESTRUCTION_SPEED:
			return False
		return True

class Nut(ShellBase):

	equip_message = "You got the Nut! It's not shiny or red, but it's... heavy. Great!"

	def on_pre_enter(self):
		ShellBase.on_pre_enter(self)
		bat.event.Event('SetCameraType', 'PathCamera').send()

class BottleCap(ShellBase):

	_prefix = 'BC_'

	equip_message = "You got the Bottle Cap! It looks like it can float. It tastes like hoisin sauce - not bad!"

	# States - be careful not to let conflict with ShellBase states.
	S_EMERGE = 6
	S_JUMP = 7

	# Animation layers
	L_EMERGE = 1 # Entering/exiting shell
	L_JUMP = 2   # Jumping

	def __init__(self, old_owner):
		ShellBase.__init__(self, old_owner)

		self.direction_mapper = bat.impulse.DirectionMapperGlobal()

		self.jump_sound = bat.sound.Sample('//Sound/MouthPopOpen.ogg')
		self.jump_sound.pitchmin = 0.9
		self.jump_sound.pitchmax = 1.0
		self.jump_sound.add_effect(bat.sound.Localise(self))

		self.land_sound = bat.sound.Sample('//Sound/MouthPopClose.ogg')
		self.land_sound.pitchmin = 0.9
		self.land_sound.pitchmax = 1.0
		self.land_sound.add_effect(bat.sound.Localise(self))

	def orient(self):
		'''Try to make the cap sit upright, and face the direction of travel.'''
		vec = ZAXIS.copy()
		vec.negate()
		self.alignAxisToVect(vec, 2, self['OrnFac'])

		facing = self.getLinearVelocity(False)
		facing.z = 0.0
		if facing.magnitude > EPSILON:
			self.alignAxisToVect(facing, 1, self['TurnFac'] * facing.magnitude)

	def on_pre_enter(self):
		ShellBase.on_pre_enter(self)
		self.occupier.visible = True
		self.occupier.playAction('CapSnailEmerge', 1, 25, layer=BottleCap.L_EMERGE)
		self.add_state(BottleCap.S_EMERGE)
		bat.event.Event('SetCameraType', 'PathCamera').send()

	def on_exited(self):
		ShellBase.on_exited(self)
		self.occupier.playAction('CapSnailEmerge', 25, 1, layer=BottleCap.L_EMERGE)
		self.add_state(BottleCap.S_EMERGE)

	@bat.bats.expose
	def poll_emerge_action(self):
		'''Hides occupier when fully inside shell; shows when emerging.'''
		if self.occupier.getActionFrame(BottleCap.L_EMERGE) > 2:
			self.occupier.visible = True
		else:
			self.occupier.visible = False

		if not self.occupier.isPlayingAction(BottleCap.L_EMERGE):
			self.rem_state(BottleCap.S_EMERGE)

	@bat.bats.expose
	@bat.utils.controller_cls
	def poll_jump_action(self, c):
		'''Triggers a jump impulse at a certain point in the jump animation.'''
		if self.occupier.getActionFrame(BottleCap.L_JUMP) >= 5:
			self.jump()
			self.rem_state(BottleCap.S_JUMP)

	def start_jump(self, force_vec):
		'''Plays the jump action. The actual impulse will be given at the right
		time in the animation.'''
		self.force_vec = force_vec
		self.occupier.playAction('CapSnailJump', 1, 15, layer=BottleCap.L_JUMP)
		self.add_state(BottleCap.S_JUMP)

	def jump(self):
		'''Applies an impulse to the shell to make it jump.'''
		force_vec = self.force_vec.copy()
		force_vec.z = self['Lift']
		force_vec.normalize()
		force_vec *= self['Power']

		#
		# Apply the force.
		#
		self.applyImpulse((0.0, 0.0, 0.0), force_vec)
		self.jump_sound.play()

	def handle_movement(self, state):
		'''Make the cap jump around around based on user input.'''
		self.orient()

		if not self['OnGround']:
			return

		if self.occupier.isPlayingAction(BottleCap.L_JUMP):
			# Jump has been initiated already; wait for it to finish.
			return

		if state.direction.magnitude > 0.1:
			#
			# Decide which direction to jump on the two axes.
			#
			self.direction_mapper.update(self, state.direction)
			self.start_jump(self.direction_mapper.direction)
			bat.utils.add_state(self.occupier, 3)

	@bat.bats.expose
	def land(self):
		self.land_sound.play()


class Thimble(ShellBase):

	_prefix = 'Th_'

	equip_message = "You got the Thimble! It's impervious to sharp objects."

	S_CRAWLING = 19
	S_SHOCKED = 20

	NORMAL_SPEED = 0.08

	def __init__(self, old_owner):
		ShellBase.__init__(self, old_owner)

		self.attitude = Scripts.attitude.SurfaceAttitude(self,
				bat.bats.mutate(self.children['ArcRay_Root.0']),
				bat.bats.mutate(self.children['ArcRay_Root.1']),
				bat.bats.mutate(self.children['ArcRay_Root.2']),
				bat.bats.mutate(self.children['ArcRay_Root.3']))
		self.direction_mapper = bat.impulse.DirectionMapperLocal()
		self.engine = Scripts.attitude.Engine(self)

		self.damage_tracker = Scripts.director.DamageTracker()

		bat.event.EventBus().add_listener(self)
		bat.event.EventBus().replay_last(self, 'GravityChanged')

	def on_entered(self):
		ShellBase.on_entered(self)
		self.add_state(Thimble.S_CRAWLING)
		self.disableRigidBody()

	def on_exited(self):
		self.enableRigidBody()
		self.rem_state(Thimble.S_CRAWLING)
		ShellBase.on_exited(self)

	def on_event(self, evt):
		if evt.message == 'GravityChanged':
			antiG = evt.body.copy()
			antiG.negate()
			# Anti-gravity is applied in world coordinates.
			self.actuators['aAntiGravity'].force = antiG
			# Artificial gravity is applied in local coordinates.
			self.actuators['aArtificialGravity'].force = evt.body

	@bat.bats.expose
	@bat.utils.controller_cls
	def damage(self, c):
		if not self.is_occupied:
			return

		damage, shock, respawn = self.damage_tracker.attack(c.sensors[0].hitObjectList)
		if damage != 0:
			self.snail.damage(damage)

		if respawn:
			self.snail.respawn()
		elif shock:
			self.add_state(Thimble.S_SHOCKED)
			self.rem_state(Thimble.S_CRAWLING)
			self.localLinearVelocity.z += 20

	@bat.bats.expose
	def orient(self):
		self.attitude.apply()

	def handle_movement(self, state):
		speed = min(1.0, state.direction.magnitude)
		speed *= Thimble.NORMAL_SPEED
		self.direction_mapper.update(self, state.direction)
		self.engine.apply(self.direction_mapper.direction, speed)


def spawn_shell(c):
	'''Place an item that has not been picked up yet.'''
	o = c.owner

	if o['shell'] in Scripts.inventory.Shells().get_shells():
		# Player has already picked up this shell.
		return

	shell = factory(o["shell"])
	bat.bmath.copy_transform(o, shell)
	shell.anchor(c.owner)
