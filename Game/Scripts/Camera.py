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
		
		self.Q = Utilities.PriorityQueue()
		self.StackModified = False
		self.InstantCut = False
		
		self.Observers = []
		
		Utilities.SceneManager.Subscribe(self)
	
	def OnSceneEnd(self):
		self.__init__()
	
	def SetCamera(self, camera):
		'''Bind to a camera.'''
		self.Camera = camera
	
	def SetDefaultGoal(self, goal, factor):
		'''
		Set the default goal. If there is already a goal on the GoalStack, it
		will be used instead of this default one - until it is popped off the
		stack.
		'''
		self.DefaultGoal = CameraGoal(goal, factor, False)
		self.StackModified = True
	
	def OnRender(self):
		'''
		Update the location of the camera. Observers will be notified. The
		camera should have a controller set up to call this once per frame.
		'''
		if not self.Camera or not self.DefaultGoal:
			return
		
		if self.StackModified:
			self.CurrentGoal = self.DefaultGoal
			
			if len(self.Q) > 0:
				self.CurrentGoal = self.Q.top()
			
			if self.InstantCut:
				self.Camera.worldPosition = self.CurrentGoal.Goal.worldPosition
				self.Camera.worldOrientation = self.CurrentGoal.Goal.worldOrientation
				self.InstantCut = False
			self.StackModified = False
		
		fac = self.DefaultGoal.Factor
		if self.CurrentGoal.Factor != None:
			fac = self.CurrentGoal.Factor
		Utilities._SlowCopyLoc(self.Camera, self.CurrentGoal.Goal, fac)
		Utilities._SlowCopyRot(self.Camera, self.CurrentGoal.Goal, fac)
		
		for o in self.Observers:
			o.OnCameraMoved(self)
	
	def AddGoal(self, goal, priority, fac, instantCut):
		'''
		Give the camera a new goal, and remember the last one. Call RemoveGoal 
		to restore the previous relationship. The camera position isn't changed
		until OnRender is called.
		
		Paremeters:
		goal:       The new goal (KX_GameObject).
		highPriority: True if this goal should override regular goals.
		fac:        The speed factor to use for the slow parent relationship.
		            If None, the factor of the default goal will be used.
		            0.0 <= fac <= 1.0.
		instantCut: Whether to make the camera jump immediately to the new
		            position. Thereafter, the camera will follow its goal
		            according to 'fac'.
		'''
		self.Q.push(goal, CameraGoal(goal, fac, instantCut), priority)
		self.StackModified = True
		if instantCut:
			self.InstantCut = True
	
	def RemoveGoal(self, goalOb):
		'''
		Remove a goal from the stack. If it was currently in use, the camera
		will switch to follow the next one on the stack. The transform isn't
		changed until OnRender is called.
		'''
		try:
			if self.Q.top().Goal == goalOb:
				#
				# Goal is on top of the stack: it's in use!
				#
				oldGoal = self.Q.pop()
				self.StackModified = True
				if oldGoal.InstantCut:
					self.InstantCut = True
			else:
				#
				# Remove the goal from the rest of the stack.
				#
				self.Q.remove(goalOb)
		except (IndexError, KeyError):
			print "Warning: camera goal %s not found in stack." % goalOb.name
	
	def ResetGoal(self):
		'''Reset the camera to follow its original goal. This clears the
		relationship stack.'''
		while len(self.Q) > 0:
			g = self.Q.pop()
			if g.InstantCut:
				self.InstantCut = True
		self.StackModified = True
	
	def AddObserver(self, camObserver):
		self.Observers.append(camObserver)
	
	def RemoveObserver(self, camObserver):
		self.Observers.remove(camObserver)
 
AutoCamera = _AutoCamera()

def SetCamera(c):
	camera = c.owner
	AutoCamera.SetCamera(camera)

def SetDefaultGoal(c):
	goal = c.owner
	AutoCamera.SetDefaultGoal(goal, goal['SlowFac'])

def AddGoal(c):
	goal = c.owner
	
	pri = goal['Priority']
	
	fac = None
	if goal.has_key('SlowFac'):
		fac = goal['SlowFac']
		
	instant = False
	if goal.has_key('InstantCut'):
		instant = goal['InstantCut']
	
	AutoCamera.AddGoal(goal, pri, fac, instant)

def RemoveGoal(c):
	goal = c.owner
	AutoCamera.RemoveGoal(goal)

class CameraGoal:
	def __init__(self, goal, factor = None, instantCut = False):
		self.Goal = goal
		self.Factor = factor
		self.InstantCut = instantCut

