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

import bxt
from . import Actor
from . import camera
import mathutils
from . import Utilities

ZAXIS = mathutils.Vector((0.0, 0.0, 1.0))
EPSILON = 0.001

#
# States.
#
S_INIT     = 1
S_IDLE     = 2
S_CARRIED  = 3
S_OCCUPIED = 4
S_ALWAYS   = 16

class ShellBase(Actor.Actor):
	def __init__(self, owner):
		Actor.Actor.__init__(self, owner)
		
		self.Snail = None
		self.CargoHook = None
		
		Utilities.parseChildren(self, owner)
		
		#
		# A cargo hook is required.
		#
		if not self.CargoHook:
			raise Utilities.SemanticException(
				"Warning: Shell %s has no cargo hook." % self.owner.name)
		
		if self.Occupier:
			self.Occupier.state = 1<<0 # state 1
		
		self.LookAt = -1
		bxt.utils.set_state(self.owner, S_IDLE)
		bxt.utils.add_state(self.owner, S_ALWAYS)
	
	def parseChild(self, child, t):
		if t == 'CargoHook':
			self.CargoHook = child
			return True
		elif t == 'Occupier':
			self.Occupier = child
			return True
		else:
			return False
	
	def CanSuspend(self):
		'''Only suspend if this shell is currently dynamic.
		No attached snail -> Dynamic.
		Being carried by snail -> Not dynamic.
		Occupied by snail -> Dynamic.'''
		if self.owner['Carried']:
			return False
		elif self.owner['Occupied']:
			return True
		else:
			return True
	
	def OnPickedUp(self, snail, animate):
		'''Called when a snail picks up this shell.'''
		self.Snail = snail
		self.owner['Carried'] = True
		bxt.utils.set_state(self.owner, S_CARRIED)
		bxt.utils.add_state(self.owner, S_ALWAYS)
		self.owner['NoPickupAnim'] = not animate
		
		try:
			self.LookAt = self.owner['LookAt']
			self.owner['LookAt'] = -1
		except KeyError:
			self.owner['LookAt'] = -1
	
	def OnDropped(self):
		'''Called when a snail drops this shell.'''
		self.Snail = None
		self.owner['Carried'] = False
		bxt.utils.set_state(self.owner, S_IDLE)
		bxt.utils.add_state(self.owner, S_ALWAYS)
		
		self.owner['LookAt'] = self.LookAt
	
	def OnPreEnter(self):
		'''Called when the snail starts to enter this shell. This may happen
		seveal frames before control is passed, but may be on the same frame.'''
		if self.Occupier:
			self.Occupier.state = 1<<1 # state 2
	
	def OnEntered(self):
		'''Called when a snail enters this shell (just after
		control is transferred).'''
		bxt.utils.set_state(self.owner, S_OCCUPIED)
		bxt.utils.add_state(self.owner, S_ALWAYS)
	
	def OnExited(self):
		'''Called when a snail exits this shell (just after
		control is transferred).'''
		bxt.utils.set_state(self.owner, S_CARRIED)
		bxt.utils.add_state(self.owner, S_ALWAYS)
		self.owner['CurrentBuoyancy'] = self.owner['Buoyancy']
		if self.Occupier:
			self.Occupier.state = 1<<0 # state 1
	
	def OnPostExit(self):
		'''Called when the snail has finished its exit shell
		animation.'''
		pass
	
	def IsCarried(self):
		return self.owner['Carried']
	
	def OnButton1(self, positive, triggered):
		if not bxt.utils.has_state(self.owner, S_OCCUPIED):
			return
		
		if positive and triggered:
			self.Snail.exitShell(animate = True)
		
	def RestoreLocation(self, reason = None):
		Actor.Actor.RestoreLocation(self, reason)
		if bxt.utils.has_state(self.owner, S_OCCUPIED):
			self.Snail.exitShell(False)
	
	def getHealth(self):
		if (bxt.utils.has_state(self.owner, S_CARRIED) or
		    bxt.utils.has_state(self.owner, S_OCCUPIED)):
			return self.Snail.getHealth()
		else:
			return Actor.Actor.getHealth(self)
	
	def setHealth(self, value):
		if (bxt.utils.has_state(self.owner, S_CARRIED) or
		    bxt.utils.has_state(self.owner, S_OCCUPIED)):
			return self.Snail.setHealth(value)
		else:
			return Actor.Actor.setHealth(self, value)
		

class Shell(ShellBase):
	def OnMovementImpulse(self, fwd, back, left, right):
		'''Make the shell roll around based on user input.'''
		if not self.owner['OnGround']:
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
		p1 = camera.AutoCamera().get_camera().worldPosition
		p2 = self.owner.worldPosition
		fwdVec = p2 - p1
		fwdVec.normalize()
		leftVec = ZAXIS.cross(fwdVec)
		
		#
		# Set the direction of the vectors.
		#
		fwdVec = fwdVec * fwdMagnitude
		leftVec = leftVec * leftMagnitude
		finalVec = (fwdVec + leftVec) * self.owner['Power']
		
		#
		# Apply the force.
		#
		self.owner.applyImpulse((0.0, 0.0, 0.0), finalVec)

class Wheel(ShellBase):
	def __init__(self, owner):
		ShellBase.__init__(self, owner)
		self._ResetSpeed()
	
	def Orient(self):
		'''Try to make the wheel sit upright.'''
		vec = self.owner.getAxisVect(ZAXIS)
		vec.z = 0.0
		vec.normalize
		self.owner.alignAxisToVect(vec, 2, self.owner['OrnFac'])
	
	def _ResetSpeed(self):
		self.CurrentRotSpeed = 0.0
		self.CurrentTurnSpeed = 0.0
	
	def OnPreEnter(self):
		ShellBase.OnPreEnter(self)
		self._ResetSpeed()
	
	def OnMovementImpulse(self, fwd, back, left, right):
		self.Orient()
		
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
		self.CurrentTurnSpeed = bxt.math.lerp(
			self.CurrentTurnSpeed,
			self.owner['TurnSpeed'] * leftMagnitude,
			self.owner['SpeedFac'])
		self.owner.applyRotation(
			ZAXIS * self.CurrentTurnSpeed, False)
		
		#
		# Apply acceleration. The speed will be influenced by the rate that
		# the wheel is being steered at (above).
		#
		turnStrength = abs(self.CurrentTurnSpeed) / self.owner['TurnSpeed']
		targetRotSpeed = self.owner['RotSpeed'] * bxt.math.safe_invert(
			turnStrength, self.owner['TurnInfluence'])
		
		self.CurrentRotSpeed = bxt.math.lerp(
			self.CurrentRotSpeed,
			targetRotSpeed,
			self.owner['SpeedFac'])
		self.owner.setAngularVelocity(ZAXIS * self.CurrentRotSpeed, True)

class Nut(ShellBase):
	pass

class BottleCap(ShellBase):
	def Orient(self):
		'''Try to make the cap sit upright, and face the direction of travel.'''
		vec = ZAXIS.copy()
		vec.negate()
		self.owner.alignAxisToVect(vec, 2, self.owner['OrnFac'])
		
		facing = self.owner.getLinearVelocity(False)
		facing.z = 0.0
		if facing.magnitude > EPSILON:
			self.owner.alignAxisToVect(
				facing, 1, self.owner['TurnFac'] * facing.magnitude)
	
	def OnMovementImpulse(self, fwd, back, left, right):
		'''Make the cap jump around around based on user input.'''
		self.Orient()
		
		if not self.Occupier['JumpReady']:
			return
		
		if not self.owner['OnGround']:
			return
		
		if fwd or back or left or right:
			self.Occupier.state = self.Occupier.state | 1<<2 # Plus state 3
		
		if not self.Occupier['JumpNow']:
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
		p1 = camera.AutoCamera().get_camera().worldPosition
		p2 = self.owner.worldPosition
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
		finalVec.z = self.owner['Lift']
		finalVec.normalize()
		finalVec = finalVec * self.owner['Power']
		
		#
		# Apply the force.
		#
		self.owner.applyImpulse((0.0, 0.0, 0.0), finalVec)
		self.Occupier['JumpNow'] = False
	
	def OnExited(self):
		'''Called when control is transferred to the snail. Reset propulsion.'''
		ShellBase.OnExited(self)
		self.FwdMagnitude = 0.0
		self.LeftMagnitude = 0.0
		self.Occupier['JumpFrame'] = 0

@bxt.utils.owner
def CreateShell(o):
	Shell(o)

@bxt.utils.owner
def CreateNut(o):
	Nut(o)

@bxt.utils.owner
def CreateWheel(o):
	Wheel(o)

@bxt.utils.owner
def CreateBottleCap(o):
	BottleCap(o)
