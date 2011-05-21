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

ZAXIS = mathutils.Vector((0.0, 0.0, 1.0))
EPSILON = 0.001

class ShellBase(director.Actor, bge.types.KX_GameObject):
	S_INIT     = 1
	S_IDLE     = 2
	S_CARRIED  = 3
	S_OCCUPIED = 4
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

		evt = bxt.types.WeakEvent('MainCharacterSet', self)
		bxt.types.EventBus().notify(evt)

	def on_exited(self):
		'''Called when a snail exits this shell (just after
		control is transferred).'''
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

	def on_button1(self, positive, triggered):
		if not self.has_state(ShellBase.S_OCCUPIED):
			return

		if positive and triggered:
			self.snail.exit_shell(animate = True)

	def on_button2(self, positive, triggered):
		pass

	def on_view_button(self, pos, trig):
		pass

	def save_location(self):
		super(ShellBase, self).save_location()
		if self.snail != None:
			self.snail.save_location()

	def respawn(self, reason = None):
		if self.has_state(ShellBase.S_OCCUPIED):
			self.snail.respawn(reason)
		elif self.has_state(ShellBase.S_CARRIED):
			# Do nothing: shell is being carried, but snail is still in control
			# (so presumably the snail will be told to respawn too).
			pass
		else:
			super(ShellBase, self).respawn(reason)

	def get_health(self):
		if (self.has_state(ShellBase.S_CARRIED) or
		    self.has_state(ShellBase.S_OCCUPIED)):
			return self.snail.get_health()
		else:
			return super(ShellBase, self).get_health()

	def set_health(self, value):
		if (self.has_state(ShellBase.S_CARRIED) or
		    self.has_state(ShellBase.S_OCCUPIED)):
			return self.snail.set_health(value)
		else:
			return super(ShellBase, self).set_health(value)

class Shell(ShellBase):
	def on_movement_impulse(self, fwd, back, left, right):
		'''Make the shell roll around based on user input.'''
		if not self['OnGround']:
			return

		#
		# Decide which direction to roll in on the two axes.
		#
		fwdMagnitude = 0.0
		leftMagnitude = 0.0
		if fwd:
			fwdMagnitude = fwdMagnitude + 1.0
		if back:
			fwdMagnitude = fwdMagnitude - 1.0
		if left:
			leftMagnitude = leftMagnitude + 1.0
		if right:
			leftMagnitude = leftMagnitude - 1.0

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
		fwdVec = fwdVec * fwdMagnitude
		leftVec = leftVec * leftMagnitude
		finalVec = (fwdVec + leftVec) * self['Power']

		#
		# Apply the force.
		#
		self.applyImpulse((0.0, 0.0, 0.0), finalVec)

class Wheel(ShellBase):
	def __init__(self, old_owner):
		ShellBase.__init__(self, old_owner)
		self._reset_speed()

	def orient(self):
		'''Try to make the wheel sit upright.'''
		vec = self.getAxisVect(ZAXIS)
		vec.z = 0.0
		vec.normalize
		self.alignAxisToVect(vec, 2, self['OrnFac'])

	def _reset_speed(self):
		self.currentRotSpeed = 0.0
		self.currentTurnSpeed = 0.0

	def on_pre_enter(self):
		ShellBase.on_pre_enter(self)
		self._reset_speed()

	def on_movement_impulse(self, fwd, back, left, right):
		self.orient()

		#
		# Decide which direction to roll or turn.
		#
		leftMagnitude = 0.0
		if left:
			leftMagnitude = leftMagnitude + 1.0
		if right:
			leftMagnitude = leftMagnitude - 1.0

		#
		# Turn (steer).
		#
		self.currentTurnSpeed = bxt.math.lerp(self.currentTurnSpeed,
				self['TurnSpeed'] * leftMagnitude, self['SpeedFac'])
		self.applyRotation(
				ZAXIS * self.currentTurnSpeed, False)

		#
		# Apply acceleration. The speed will be influenced by the rate that
		# the wheel is being steered at (above).
		#
		turnStrength = abs(self.currentTurnSpeed) / self['TurnSpeed']
		targetRotSpeed = self['RotSpeed'] * bxt.math.safe_invert(
				turnStrength, self['TurnInfluence'])

		self.currentRotSpeed = bxt.math.lerp(self.currentRotSpeed,
				targetRotSpeed, self['SpeedFac'])
		self.setAngularVelocity(ZAXIS * self.currentRotSpeed, True)

class Nut(ShellBase):
	def on_movement_impulse(self, fwd, back, left, right):
		# Can't move!
		pass

class BottleCap(ShellBase):
	def orient(self):
		'''Try to make the cap sit upright, and face the direction of travel.'''
		vec = ZAXIS.copy()
		vec.negate()
		self.alignAxisToVect(vec, 2, self['OrnFac'])

		facing = self.getLinearVelocity(False)
		facing.z = 0.0
		if facing.magnitude > EPSILON:
			self.alignAxisToVect(facing, 1, self['TurnFac'] * facing.magnitude)

	def on_movement_impulse(self, fwd, back, left, right):
		'''Make the cap jump around around based on user input.'''
		self.orient()

		if not self.occupier['JumpReady']:
			return

		if not self['OnGround']:
			return

		if fwd or back or left or right:
			bxt.utils.add_state(self.occupier, 3)

		if not self.occupier['JumpNow']:
			return

		#
		# Decide which direction to jump on the two axes.
		#
		fwdMagnitude = 0.0
		if fwd and not back:
			fwdMagnitude = 1.0
		elif back and not fwd:
			fwdMagnitude = -1.0
		leftMagnitude = 0.0
		if left and not right:
			leftMagnitude = 1.0
		elif right and not left:
			leftMagnitude = -1.0

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
		fwdVec = fwdVec * fwdMagnitude
		leftVec = leftVec * leftMagnitude
		finalVec = fwdVec + leftVec
		finalVec.z = self['Lift']
		finalVec.normalize()
		finalVec = finalVec * self['Power']

		#
		# Apply the force.
		#
		self.applyImpulse((0.0, 0.0, 0.0), finalVec)
		self.occupier['JumpNow'] = False

	def on_exited(self):
		'''Called when control is transferred to the snail. Reset propulsion.'''
		ShellBase.on_exited(self)
		self.FwdMagnitude = 0.0
		self.LeftMagnitude = 0.0
		self.occupier['JumpFrame'] = 0
