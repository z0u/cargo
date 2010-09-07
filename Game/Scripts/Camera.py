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
import Actor
import GameTypes

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
		self.DefaultLens = 22.0
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
		self.DefaultLens = camera.lens
	
	def SetDefaultGoal(self, goal, factor):
		'''
		Set the default goal. If there is already a goal on the GoalStack, it
		will be used instead of this default one - until it is popped off the
		stack.
		'''
		self.DefaultGoal = CameraGoal(goal, factor, False)
		self.StackModified = True
	
	def onRender(self):
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
				targetLens = self.DefaultLens
				if hasattr(self.CurrentGoal.Goal, 'lens'):
					targetLens = self.CurrentGoal.Goal.lens
				self.Camera.lens = targetLens
				self.InstantCut = False
			self.StackModified = False
		
		fac = self.DefaultGoal.Factor
		if self.CurrentGoal.Factor != None:
			fac = self.CurrentGoal.Factor
		Utilities._SlowCopyLoc(self.Camera, self.CurrentGoal.Goal, fac)
		Utilities._SlowCopyRot(self.Camera, self.CurrentGoal.Goal, fac)
		
		targetLens = self.DefaultLens
		if hasattr(self.CurrentGoal.Goal, 'lens'):
			targetLens = self.CurrentGoal.Goal.lens
		self.Camera.lens = Utilities._lerp(self.Camera.lens, targetLens, fac)
		
		for o in self.Observers:
			o.OnCameraMoved(self)
	
	def AddGoal(self, goal, priority, fac, instantCut):
		'''
		Give the camera a new goal, and remember the last one. Call RemoveGoal 
		to restore the previous relationship. The camera position isn't changed
		until onRender is called.
		
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
		changed until onRender is called.
		'''
		if len(self.Q) == 0:
			return
		
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
			self.Q.discard(goalOb)
	
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

def onRender(c):
	AutoCamera.onRender()

def setCamera(c):
	camera = c.owner
	AutoCamera.SetCamera(camera)

def SetDefaultGoal(c):
	goal = c.owner
	AutoCamera.SetDefaultGoal(goal, goal['SlowFac'])

def addGoalOb(goal):
	pri = False
	if 'Priority' in goal:
		pri = goal['Priority']
	
	fac = None
	if 'SlowFac' in goal:
		fac = goal['SlowFac']
		
	instant = False
	if 'InstantCut' in goal:
		instant = goal['InstantCut']
	
	AutoCamera.AddGoal(goal, pri, fac, instant)

def AddGoal(c):
	if not Utilities.allSensorsPositive(c):
		return
	goal = c.owner
	addGoalOb(goal)

def RemoveGoal(c):
	if not Utilities.allSensorsPositive(c):
		return
	goal = c.owner
	removeGoalOb(goal)
	
def AddGoalIfMainChar(c):
	'''
	Add the owner of this controller as a goal if the main actor has been hit.
	
	@see Actor._hitMainCharacter.
	'''
	if not Actor._hitMainCharacter(c):
		return
	
	goal = c.owner
	addGoalOb(goal)

def RemoveGoalIfNotMainChar(c):
	if Actor._hitMainCharacter(c):
		return
	
	goal = c.owner
	removeGoalOb(goal)

def removeGoalOb(goal):
	AutoCamera.RemoveGoal(goal)

class CameraGoal:
	def __init__(self, goal, factor = None, instantCut = False):
		self.Goal = goal
		self.Factor = factor
		self.InstantCut = instantCut

class BackgroundCamera(CameraObserver):
	'''Links a second camera to the main 3D camera. This second, background
	camera will always match the orientation and zoom of the main camera. It is
	guaranteed to update after the main one.'''
	
	def __init__(self, owner):
		self.Owner = owner
		AutoCamera.AddObserver(self)
		Utilities.SceneManager.Subscribe(self)
	
	def OnSceneEnd(self):
		self.Owner = None
		AutoCamera.RemoveObserver(self)
	
	def OnCameraMoved(self, autoCamera):
		self.Owner.worldOrientation = autoCamera.Camera.worldOrientation
		self.Owner.lens = autoCamera.Camera.lens

def createBackgroundCamera(c):
	BackgroundCamera(c.owner)
