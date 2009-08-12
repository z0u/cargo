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

import Utilities

class _AutoCamera:
	'''A Singleton; use the AutoCamera variable (below).'''
	
	def __init__(self):
		self.Camera = None
		self.Goal = None
		self.DefaultTarget = None
		self.CurrentTarget = None
		self.TargetStack = []
		self.StackModified = False
		self.InstantCut = False
		
		self.Observers = []
	
	def SetCamera(self, camera, goal, defaultTarget, defaultFactor):
		self.Camera = camera
		self.Goal = goal
		
		self.DefaultTarget = CameraTarget(defaultTarget, defaultFactor, False)
		self.StackModified = True
		self.InstantCut = False
	
	def OnRender(self):
		'''
		Update the location of the camera.
		'''
		if not self.Camera:
			return
		
		if self.StackModified:
			self.CurrentTarget = self.DefaultTarget
			if len(self.TargetStack) > 0:
				self.CurrentTarget = self.TargetStack[-1]
			
			self.Goal.removeParent()
			self.Goal.worldPosition = self.CurrentTarget.Target.worldPosition
			self.Goal.worldOrientation = self.CurrentTarget.Target.worldOrientation
			
			if self.InstantCut:
				self.Camera.setWorldPosition(self.Goal.worldPosition)
				self.Camera.worldOrientation = self.Goal.worldOrientation
			self.Goal.setParent(self.CurrentTarget.Target)
		
		Utilities._SlowCopyLoc(self.Camera, self.Goal, self.CurrentTarget.Factor)
		Utilities._SlowCopyRot(self.Camera, self.Goal, self.CurrentTarget.Factor)
	
	def PushTarget(self, target, fac = None, instantCut = False):
		'''Give the camera a new goal, and remember the last one.
		Call PopGoalParent to restore the previous relationship.
		
		Paremeters:
		newParent:  The new goal parent.
		fac:        The speed factor to use for the slow parent relationship.
		instantCut: Whether to make the camera jump immediately to the new
		            position.
		'''
		self.TargetStack.append(CameraTarget(target, fac, instantCut))
		self.StackModified = True
		if instantCut:
			self.InstantCut = True
	
	def PopTarget(self):
		'''Restore the camera goal's previous parent relationship.'''
		try:
			oldTarget = self.TargetStack.pop()
		except IndexError:
			print "Warning: Camera target stack already empty."
			return
		self.StackModified = True
		if oldTarget.InstantCut:
			self.InstantCut = True
	
	def ResetTarget(self):
		'''Reset the camera to follow its original goal. This
		clears the relationship stack.'''
		if len(self.TargetStack) == 0:
			return
		for t in self.TargetStack:
			if t.InstantCut:
				self.InstantCut = True
				break
		self.TargetStack = []
		self.StackModified = True
 
AutoCamera = _AutoCamera()

def SetCamera(c):
	camera = c.owner
	goal = c.sensors['sGoalHook'].owner
	target = c.sensors['sGoalParentHook'].owner
	AutoCamera.SetCamera(camera, goal, target, camera['SlowFac'])

class CameraTarget:
	def __init__(self, target, factor = None, instantCut = False):
		self.Target = target
		self.Factor = factor
		self.InstantCut = instantCut
