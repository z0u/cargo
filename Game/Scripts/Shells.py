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

class Shell(Actor.Actor):
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
	
	def OnPickedUp(self, snail):
		'''Called when a snail picks up this shell.'''
		self.Snail = snail
		self.Owner['Carried'] = True
		self.Owner.state = 1<<2 # state 3
	
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
		Camera.AutoCamera.PushGoal(self.CameraGoal, fac = self.CameraGoal['SlowFac'])
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
		Camera.AutoCamera.PopGoal()
		self.CameraGoal.state = 1<<0 # state 1

def CreateShell(c):
	cameraGoal = c.sensors['sCameraGoal'].owner
	Shell(c.owner, cameraGoal)

def CreateNut(c):
	cameraGoal = c.sensors['sCameraGoal'].owner
	Shell(c.owner, cameraGoal)

def CreateWheel(c):
	cameraGoal = c.sensors['sCameraGoal'].owner
	Shell(c.owner, cameraGoal)

class BottleCap(Shell):
	def Drown(self, water):
		return False

def CreateBottleCap(c):
	cameraGoal = c.sensors['sCameraGoal'].owner
	BottleCap(c.owner, cameraGoal)
