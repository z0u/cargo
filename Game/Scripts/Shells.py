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

ZAXIS = Mathutils.Vector((0.0, 0.0, 1.0))

class ShellBase(Actor.Actor):
	def __init__(self, owner, cameraGoal):
		Actor.Actor.__init__(self, owner)
		self.Snail = None
		self.CameraGoal = cameraGoal
	
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
		self.Owner.state = 1<<2 # state 3
		self.Owner['NoPickupAnim'] = not animate
	
	def OnDropped(self):
		'''Called when a snail drops this shell.'''
		self.Snail = None
		self.Owner['Carried'] = False
		self.Owner.state = 1<<1 # state 2
	
	def OnPreEnter(self):
		'''Called when the snail starts to enter this shell
		(seveal frames before control is passed).'''
		#
		# Set a new goal for the camera, initialised to the
		# current camera position.
		#
		activeCam = Camera.AutoCamera.Camera
		self.CameraGoal.worldPosition = activeCam.worldPosition
		self.CameraGoal.worldOrientation = activeCam.worldOrientation
		Camera.AutoCamera.AddGoal(self.CameraGoal, fac = self.CameraGoal['SlowFac'])
		self.CameraGoal.state = 1<<1 # state 2
	
	def OnEntered(self):
		'''Called when a snail enters this shell (just after
		control is transferred).'''
		self.Owner.state = 1<<3 # state 4
	
	def OnExited(self):
		'''Called when a snail exits this shell (just after
		control is transferred).'''
		self.Owner.state = 1<<2 # state 3
	
	def OnPostExit(self):
		'''Called when the snail has finished its exit shell
		animation.'''
		Camera.AutoCamera.RemoveGoal(self.CameraGoal)
		self.CameraGoal.state = 1<<0 # state 1
	
	def IsCarried(self):
		return self.Owner['Carried']

class Shell(ShellBase):
	def onMovementImpulse(self, fwd, back, left, right):
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
	pass

class Nut(ShellBase):
	pass

class BottleCap(ShellBase):
	def Drown(self, water):
		return False

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
