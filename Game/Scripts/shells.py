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
from . import director
from . import camera
from . import impulse
from . import inventory

ZAXIS = mathutils.Vector((0.0, 0.0, 1.0))
EPSILON = 0.001

def factory(name):
	scene = bge.logic.getCurrentScene()

	if not name in scene.objectsInactive:
		print("Loading shells")
		try:
			bge.logic.LibLoad('//ItemLoader.blend', 'Scene', load_actions=True)
		except ValueError:
			print("Warning: failed to open ItemLoader. May be open already. "
					"Proceeding...")

	return bxt.types.add_and_mutate_object(scene, name, name)

class ShellBase(impulse.Handler, director.Actor, bge.types.KX_GameObject):
	_prefix = 'SB_'

	S_INIT     = 1
	S_IDLE     = 2
	S_ANCHOR   = 17
	S_CARRIED  = 3
	S_OCCUPIED = 4
	S_GRASPED  = 5 # Liked CARRIED, but not carried by a snail.
	S_ALWAYS   = 16

	snail = bxt.types.weakprop('snail')

	def __init__(self, old_owner):
		director.Actor.__init__(self)

		self.snail = None
		self.cargoHook = self.find_descendant([('Type', 'CargoHook')])
		self.occupier = self.find_descendant([('Type', 'Occupier')])

		bxt.utils.set_state(self.occupier, 1)

		self.set_default_prop('LookAt', 10)
		self['_DefaultLookAt'] = self['LookAt']
		self.set_state(ShellBase.S_IDLE)
		self.add_state(ShellBase.S_ALWAYS)

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
			bxt.utils.set_state(self.occupier, 2)

	def on_entered(self):
		'''Called when a snail enters this shell (just after
		control is transferred).'''
		self.set_state(ShellBase.S_OCCUPIED)
		self.add_state(ShellBase.S_ALWAYS)

		impulse.Input().add_handler(self)
		bxt.types.WeakEvent('MainCharacterSet', self).send()

	def on_exited(self):
		'''Called when a snail exits this shell (as control is transferred).'''

		impulse.Input().remove_handler(self)

		self.set_state(ShellBase.S_CARRIED)
		self.add_state(ShellBase.S_ALWAYS)
		self.localScale = (1.0, 1.0, 1.0)
		self['CurrentBuoyancy'] = self['Buoyancy']
		if self.occupier:
			bxt.utils.set_state(self.occupier, 1)

	def on_post_exit(self):
		'''Called when the snail has finished its exit shell
		animation.'''
		pass

	def handle_bt_camera(self, state):
		# Allow the snail to handle this button event.
		return False

	def handle_bt_1(self, state):
		if not self.is_occupied():
			print("Warning: Shell %s received impulse when not occupied." %
				self.name)
			return False

		if state.activated:
			self.snail.exit_shell(animate = True)
		return True

	def save_location(self):
		super(ShellBase, self).save_location()
		if (self.parent is not None and
				hasattr(self.parent, "inherit_safe_location")):
			self.parent.inherit_safe_location(self)

	def respawn(self, reason = None):
		if self.is_occupied():
			self.snail.respawn(reason)
		elif self.is_carried():
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
		if self.is_occupied():
			bxt.types.Event('OxygenSet', self['Oxygen']).send()

	def is_occupied(self):
		return self.has_state(ShellBase.S_OCCUPIED)
	def is_carried(self):
		return self.has_state(ShellBase.S_CARRIED)
	def is_grasped(self):
		return self.has_state(ShellBase.S_GRASPED)

	@bxt.types.expose
	def update_anchor(self):
		if not self.has_state(ShellBase.S_ANCHOR):
			return
		bxt.bmath.copy_transform(self.anchor_ob, self)
		self.worldLinearVelocity = bxt.bmath.MINVECTOR

	def anchor(self, anchor_ob):
		self.add_state(ShellBase.S_ANCHOR)
		self.anchor_ob = anchor_ob

class Shell(ShellBase):

	def on_pre_enter(self):
		ShellBase.on_pre_enter(self)
		bxt.types.Event('SetCameraType', 'PathCamera').send()

	def handle_movement(self, state):
		'''Make the shell roll around based on user input.'''

		if not self['OnGround']:
			return True

		#
		# Get the vectors to apply force along.
		#
		p1 = bge.logic.getCurrentScene().active_camera.worldPosition
		p2 = self.worldPosition
		fwdVec = p2 - p1
		fwdVec.normalize()
		leftVec = ZAXIS.cross(fwdVec)

		#
		# Set the direction of the vectors.
		#
		fwdVec = fwdVec * state.direction.y
		leftVec = leftVec * -state.direction.x
		finalVec = (fwdVec + leftVec) * self['Power']

		#
		# Apply the force.
		#
		self.applyImpulse((0.0, 0.0, 0.0), finalVec)

		return True

class WheelCameraAlignment:
	'''
	Aligns the camera with the wheel. This needs a special class because the
	wheel's z-axis points out to the side.

	@see: camera.OrbitCameraAlignment
	'''

	def get_home_axes(self, camera, target):
		upDir = bxt.bmath.ZAXIS.copy()
		leftDir = target.getAxisVect(bxt.bmath.ZAXIS)
		fwdDir = upDir.cross(leftDir)
		return fwdDir, upDir

	def get_axes(self, camera, target):
		return self.get_home_axes(camera, target)

class Wheel(ShellBase):
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
		bxt.types.EventBus().add_listener(self)
		bxt.types.EventBus().replay_last(self, 'GravityChanged')

	def on_event(self, evt):
		if evt.message == 'GravityChanged':
			self.fly_power = evt.body * -(1.0 - Wheel.FLY_POWER)

	def orient(self):
		'''Try to make the wheel sit upright.'''
		vec = self.getAxisVect(ZAXIS)
		vec.z = 0.0
		vec.normalize
		self.alignAxisToVect(vec, 2)

	def _reset_speed(self):
		self.currentRotSpeed = 0.0
		self.currentTurnSpeed = 0.0

	def on_pre_enter(self):
		ShellBase.on_pre_enter(self)
		self._reset_speed()
		bxt.types.Event('SetCameraType', 'PathCamera').send()

	def on_entered(self):
		ShellBase.on_entered(self)

		bxt.types.Event('SetCameraType', 'OrbitCamera').send()
		alignment = WheelCameraAlignment()
		bxt.types.Event('SetCameraAlignment', alignment).send()

	def handle_movement(self, state):
		self.orient()

		#
		# Decide which direction to roll or turn.
		#
		direction = state.direction.copy()
		direction.y = max(direction.y * 0.5 + 0.5, 0.01)

		#
		# For jumping: when driving fast, reduce gravity!
		#
		if direction.y > 0.5:
			self.applyForce(self.fly_power)

		#
		# Turn (steer). Note that this is applied to the Z axis, but in world
		# space.
		#
		self.currentTurnSpeed = bxt.bmath.lerp(self.currentTurnSpeed,
				Wheel.TURN_SPEED * -direction.x, Wheel.SPEED_FAC)
		angv = ZAXIS * self.currentTurnSpeed

		#
		# Apply acceleration. The speed will be influenced by the rate that
		# the wheel is being steered at (above).
		#
		turnStrength = abs(self.currentTurnSpeed) / Wheel.TURN_SPEED
		targetRotSpeed = Wheel.ROT_SPEED * bxt.bmath.safe_invert(
				turnStrength, Wheel.TURN_INFLUENCE)
		targetRotSpeed *= direction.y

		self.currentRotSpeed = bxt.bmath.lerp(self.currentRotSpeed,
				targetRotSpeed, Wheel.SPEED_FAC)

		angv2 = self.getAxisVect(ZAXIS) * self.currentRotSpeed
		self.setAngularVelocity(angv + angv2, False)

		return True

	def can_destroy_stuff(self):
		if not self.is_occupied():
			return False
		if self.get_last_linear_velocity().magnitude < Wheel.DESTRUCTION_SPEED:
			return False
		return True

class Nut(ShellBase):

	def on_pre_enter(self):
		ShellBase.on_pre_enter(self)
		bxt.types.Event('SetCameraType', 'PathCamera').send()

class BottleCap(ShellBase):
	# States - be careful not to let conflict with ShellBase states.
	S_EMERGE = 6
	S_JUMP = 7

	# Animation layers
	L_EMERGE = 1 # Entering/exiting shell
	L_JUMP = 2   # Jumping

	_prefix = 'BC_'

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
		bxt.types.Event('SetCameraType', 'PathCamera').send()

	def on_exited(self):
		ShellBase.on_exited(self)
		self.occupier.playAction('CapSnailEmerge', 25, 1, layer=BottleCap.L_EMERGE)
		self.add_state(BottleCap.S_EMERGE)

	@bxt.types.expose
	def poll_emerge_action(self):
		'''Hides occupier when fully inside shell; shows when emerging.'''
		if self.occupier.getActionFrame(BottleCap.L_EMERGE) > 2:
			self.occupier.visible = True
		else:
			self.occupier.visible = False

		if not self.occupier.isPlayingAction(BottleCap.L_EMERGE):
			self.rem_state(BottleCap.S_EMERGE)

	@bxt.types.expose
	@bxt.utils.controller_cls
	def poll_jump_action(self, c):
		'''Triggers a jump impulse at a certain point in the jump animation.'''
		if self.occupier.getActionFrame(BottleCap.L_JUMP) >= 5:
			self.jump()
			self.rem_state(BottleCap.S_JUMP)
			c.activate(c.actuators['aPlayJump'])

	def start_jump(self, fwdMagnitude, leftMagnitude):
		'''Plays the jump action. The actual impulse will be given at the right
		time in the animation.'''
		self.fwdMagnitude = fwdMagnitude
		self.leftMagnitude = leftMagnitude
		self.occupier.playAction('CapSnailJump', 1, 15, layer=BottleCap.L_JUMP)
		self.add_state(BottleCap.S_JUMP)

	def jump(self):
		'''Applies an impulse to the shell to make it jump.'''
		#
		# Get the vectors to apply force along.
		#
		p1 = camera.AutoCamera().camera.worldPosition
		p2 = self.worldPosition
		fwdVec = p2 - p1
		fwdVec.z = 0.0
		fwdVec.normalize()
		leftVec = ZAXIS.cross(fwdVec)

		#
		# Set the direction of the vectors.
		#
		fwdVec = fwdVec * self.fwdMagnitude
		leftVec = leftVec * self.leftMagnitude
		finalVec = fwdVec + leftVec
		finalVec.z = self['Lift']
		finalVec.normalize()
		finalVec = finalVec * self['Power']

		#
		# Apply the force.
		#
		self.applyImpulse((0.0, 0.0, 0.0), finalVec)

	def handle_movement(self, state):
		'''Make the cap jump around around based on user input.'''
		self.orient()

		if not self['OnGround']:
			return True

		if self.occupier.isPlayingAction(BottleCap.L_JUMP):
			# Jump has been initiated already; wait for it to finish.
			return True

		if state.direction.magnitude > 0.1:
			#
			# Decide which direction to jump on the two axes.
			#
			self.start_jump(state.direction.y, -state.direction.x)
			bxt.utils.add_state(self.occupier, 3)

		return True

def spawn_shell(c):
	'''Place an item that has not been picked up yet.'''
	o = c.owner

	if o['shell'] in inventory.Shells().get_shells():
		# Player has already picked up this shell.
		return

	shell = factory(o["shell"])
	bxt.bmath.copy_transform(o, shell)
	shell.anchor(c.owner)
