#
# Copyright 2009 Alex Fraser <alex@phatcore.com>
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

import Actor
import Camera
import Mathutils
import Utilities

ZAXIS = Mathutils.Vector((0.0, 0.0, 1.0))
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
	def __init__(self, owner, cameraGoal):
		Actor.Actor.__init__(self, owner)
		
		self.Snail = None
		self.CargoHook = None
		self.CameraGoal = cameraGoal
		
		Utilities.parseChildren(self, owner)
		
		#
		# A cargo hook is required.
		#
		if not self.CargoHook:
			raise Utilities.SemanticException, (
				"Warning: Shell %s has no cargo hook." % self.Owner.name)
		
		if self.Occupier:
			self.Occupier.state = 1<<0 # state 1
		
		self.LookAt = -1
		Utilities.setState(self.Owner, S_IDLE)
		Utilities.addState(self.Owner, S_ALWAYS)
	
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
		if self.Owner['Carried']:
			return False
		elif self.Owner['Occupied']:
			return True
		else:
			return True
	
	def OnPickedUp(self, snail, animate):
		'''Called when a snail picks up this shell.'''
		self.Snail = snail
		self.Owner['Carried'] = True
		Utilities.setState(self.Owner, S_CARRIED)
		Utilities.addState(self.Owner, S_ALWAYS)
		self.Owner['NoPickupAnim'] = not animate
		
		try:
			self.LookAt = self.Owner['LookAt']
			self.Owner['LookAt'] = -1
		except KeyError:
			self.Owner['LookAt'] = -1
	
	def OnDropped(self):
		'''Called when a snail drops this shell.'''
		self.Snail = None
		self.Owner['Carried'] = False
		Utilities.setState(self.Owner, S_IDLE)
		Utilities.addState(self.Owner, S_ALWAYS)
		
		self.Owner['LookAt'] = self.LookAt
	
	def OnPreEnter(self):
		'''Called when the snail starts to enter this shell. This may happen
		seveal frames before control is passed, but may be on the same frame.'''
		#
		# Set a new goal for the camera, initialised to the
		# current camera position.
		#
		activeCam = Camera.AutoCamera.Camera
		self.CameraGoal.worldPosition = activeCam.worldPosition
		self.CameraGoal.worldOrientation = activeCam.worldOrientation
		Camera.AutoCamera.AddGoal(
			self.CameraGoal,
			self.CameraGoal['Priority'],
			self.CameraGoal['SlowFac'],
			False)
		self.CameraGoal.state = 1<<1 # state 2
		if self.Occupier:
			self.Occupier.state = 1<<1 # state 2
	
	def OnEntered(self):
		'''Called when a snail enters this shell (just after
		control is transferred).'''
		Utilities.setState(self.Owner, S_OCCUPIED)
		Utilities.addState(self.Owner, S_ALWAYS)
	
	def OnExited(self):
		'''Called when a snail exits this shell (just after
		control is transferred).'''
		Utilities.setState(self.Owner, S_CARRIED)
		Utilities.addState(self.Owner, S_ALWAYS)
		self.Owner['CurrentBuoyancy'] = self.Owner['Buoyancy']
		self.CameraGoal.state = 1<<0 # state 1
		if self.Occupier:
			self.Occupier.state = 1<<0 # state 1
	
	def OnPostExit(self):
		'''Called when the snail has finished its exit shell
		animation.'''
		Camera.AutoCamera.RemoveGoal(self.CameraGoal)
	
	def IsCarried(self):
		return self.Owner['Carried']
	
	def OnButton1(self, positive, triggered):
		if not Utilities.hasState(self.Owner, S_OCCUPIED):
			return
		
		if positive and triggered:
			self.Snail.exitShell(animate = True)
		
	def RestoreLocation(self):
		Actor.Actor.RestoreLocation(self)
		if Utilities.hasState(self.Owner, S_OCCUPIED):
			self.Snail.exitShell(False)

class Shell(ShellBase):
	def OnMovementImpulse(self, fwd, back, left, right):
		'''Make the shell roll around based on user input.'''
		if not self.Owner['OnGround']:
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
		cam = Camera.AutoCamera.Camera
		p1 = Mathutils.Vector(cam.worldPosition)
		p2 = Mathutils.Vector(self.Owner.worldPosition)
		fwdVec = p2 - p1
		fwdVec.normalize()
		leftVec = Mathutils.CrossVecs(ZAXIS, fwdVec)
		
		#
		# Set the direction of the vectors.
		#
		fwdVec = fwdVec * fwdMagnitude
		leftVec = leftVec * leftMagnitude
		finalVec = (fwdVec + leftVec) * self.Owner['Power']
		
		#
		# Apply the force.
		#
		self.Owner.applyImpulse((0.0, 0.0, 0.0), finalVec)

class Wheel(ShellBase):
	def __init__(self, owner, cameraGoal):
		ShellBase.__init__(self, owner, cameraGoal)
		self._ResetSpeed()
	
	def Orient(self):
		'''Try to make the wheel sit upright.'''
		vec = Mathutils.Vector(self.Owner.getAxisVect(ZAXIS))
		vec.z = 0.0
		vec.normalize
		self.Owner.alignAxisToVect(vec, 2, self.Owner['OrnFac'])
	
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
		self.CurrentTurnSpeed = Utilities._lerp(
			self.CurrentTurnSpeed,
			self.Owner['TurnSpeed'] * leftMagnitude,
			self.Owner['SpeedFac'])
		self.Owner.applyRotation(
			ZAXIS * self.CurrentTurnSpeed, False)
		
		#
		# Apply acceleration. The speed will be influenced by the rate that
		# the wheel is being steered at (above).
		#
		turnStrength = abs(self.CurrentTurnSpeed) / self.Owner['TurnSpeed']
		targetRotSpeed = self.Owner['RotSpeed'] * Utilities._safeInvert(
			turnStrength, self.Owner['TurnInfluence'])
		
		self.CurrentRotSpeed = Utilities._lerp(
			self.CurrentRotSpeed,
			targetRotSpeed,
			self.Owner['SpeedFac'])
		self.Owner.setAngularVelocity(ZAXIS * self.CurrentRotSpeed, True)

class Nut(ShellBase):
	pass

class BottleCap(ShellBase):
	def Orient(self):
		'''Try to make the cap sit upright, and face the direction of travel.'''
		vec = Mathutils.Vector(ZAXIS)
		vec.negate()
		self.Owner.alignAxisToVect(vec, 2, self.Owner['OrnFac'])
		
		facing = Mathutils.Vector(self.Owner.getLinearVelocity(False))
		facing.z = 0.0
		if facing.magnitude > EPSILON:
			self.Owner.alignAxisToVect(
				facing, 1, self.Owner['TurnFac'] * facing.magnitude)
	
	def OnMovementImpulse(self, fwd, back, left, right):
		'''Make the cap jump around around based on user input.'''
		self.Orient()
		
		if not self.Occupier['JumpReady']:
			return
		
		if not self.Owner['OnGround']:
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
		cam = Camera.AutoCamera.Camera
		p1 = Mathutils.Vector(cam.worldPosition)
		p2 = Mathutils.Vector(self.Owner.worldPosition)
		fwdVec = p2 - p1
		fwdVec.z = 0.0
		fwdVec.normalize()
		leftVec = Mathutils.CrossVecs(ZAXIS, fwdVec)
		
		#
		# Set the direction of the vectors.
		#
		fwdVec = fwdVec * fwdMagnitude
		leftVec = leftVec * leftMagnitude
		finalVec = fwdVec + leftVec
		finalVec.z = self.Owner['Lift']
		finalVec.normalize()
		finalVec = finalVec * self.Owner['Power']
		
		#
		# Apply the force.
		#
		self.Owner.applyImpulse((0.0, 0.0, 0.0), finalVec)
		self.Occupier['JumpNow'] = False
	
	def OnExited(self):
		'''Called when control is transferred to the snail. Reset propulsion.'''
		ShellBase.OnExited(self)
		self.FwdMagnitude = 0.0
		self.LeftMagnitude = 0.0
		self.Occupier['JumpFrame'] = 0

def CreateShell(c):
	cameraGoal = c.sensors['sCameraGoal'].owner
	Shell(c.owner, cameraGoal)

def CreateNut(c):
	cameraGoal = c.sensors['sCameraGoal'].owner
	Nut(c.owner, cameraGoal)

def CreateWheel(c):
	cameraGoal = c.sensors['sCameraGoal'].owner
	Wheel(c.owner, cameraGoal)

def CreateBottleCap(c):
	cameraGoal = c.sensors['sCameraGoal'].owner
	BottleCap(c.owner, cameraGoal)
