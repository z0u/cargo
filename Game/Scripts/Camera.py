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

class CameraObserver:
	'''
	An observer of AutoCameras. One use for this is cameras in other scenes.
	For example, the background camera sets its worldOrientation to be the same
	as the camera in the game play scene, which is bound to the AutoCamera.
	'''
	def OnCameraMoved(self, autoCamera):
		pass

class _AutoCamera:
	'''
	Manages the transform of the camera, and provides transitions between camera
	locations. To transition to a new location, call PushGoal. The reverse
	transition can be performed by calling PopGoal.
	
	A Singleton; use the AutoCamera instance (below).
	'''
	
	def __init__(self):
		'''
		Create an uninitialised AutoCamera. Call SetCamera to bind it to a
		camera.
		'''
		self.Camera = None
		self.DefaultGoal = None
		self.CurrentGoal = None
		self.GoalStack = []
		self.StackModified = False
		self.InstantCut = False
		
		self.Observers = []
	
	def SetCamera(self, camera, defaultGoal, defaultFactor):
		'''
		Bind to a camera, and set the default goal. If there is already a goal
		on the GoalStack, it will be used intead of defaultGoal.
		'''
		self.Camera = camera
		
		self.DefaultGoal = CameraGoal(defaultGoal, defaultFactor, False)
		self.StackModified = True
		self.InstantCut = False
	
	def OnRender(self):
		'''
		Update the location of the camera. Observers will be notified. The
		camera should have a controller set up to call this once per frame.
		'''
		if not self.Camera:
			return
		
		if self.StackModified:
			self.CurrentGoal = self.DefaultGoal
			if len(self.GoalStack) > 0:
				self.CurrentGoal = self.GoalStack[-1]
			
			if self.InstantCut:
				self.Camera.worldPosition = self.CurrentGoal.Goal.worldPosition
				self.Camera.worldOrientation = self.CurrentGoal.Goal.worldOrientation
		
		Utilities._SlowCopyLoc(self.Camera, self.CurrentGoal.Goal, self.CurrentGoal.Factor)
		Utilities._SlowCopyRot(self.Camera, self.CurrentGoal.Goal, self.CurrentGoal.Factor)
		
		for o in self.Observers:
			o.OnCameraMoved(self)
	
	def PushGoal(self, goal, fac = None, instantCut = False):
		'''
		Give the camera a new goal, and remember the last one. Call PopGoal to
		restore the previous relationship. The camera position isn't changed
		until OnRender is called.
		
		Paremeters:
		goal:       The new goal (KX_GameObject).
		fac:        The speed factor to use for the slow parent relationship.
		            0.0 <= fac <= 1.0.
		instantCut: Whether to make the camera jump immediately to the new
		            position.
		'''
		self.GoalStack.append(CameraGoal(goal, fac, instantCut))
		self.StackModified = True
		if instantCut:
			self.InstantCut = True
	
	def PopGoal(self):
		'''
		Restore the camera's previous goal relationship. The transform isn't
		changed until OnRender is called.
		'''
		try:
			oldGoal = self.GoalStack.pop()
		except IndexError:
			print "Warning: Camera goal stack already empty."
			return
		self.StackModified = True
		if oldGoal.InstantCut:
			self.InstantCut = True
	
	def ResetGoal(self):
		'''Reset the camera to follow its original goal. This clears the
		relationship stack.'''
		if len(self.GoalStack) == 0:
			return
		for g in self.GoalStack:
			if g.InstantCut:
				self.InstantCut = True
				break
		self.GoalStack = []
		self.StackModified = True
	
	def AddObserver(self, camObserver):
		self.Observers.append(camObserver)
	
	def RemoveObserver(self, camObserver):
		self.Observers.remove(camObserver)
 
AutoCamera = _AutoCamera()

def SetCamera(c):
	camera = c.owner
	goal = c.sensors['sGoalHook'].owner
	AutoCamera.SetCamera(camera, goal, camera['SlowFac'])

class CameraGoal:
	def __init__(self, goal, factor = None, instantCut = False):
		self.Goal = goal
		self.Factor = factor
		self.InstantCut = instantCut
