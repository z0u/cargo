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
import GameLogic

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
		self.instantCut = False
		
		self.Observers = []
		
		Utilities.SceneManager.Subscribe(self)
	
	def OnSceneEnd(self):
		self.__init__()
	
	def SetCamera(self, camera):
		'''Bind to a camera.'''
		self.Camera = camera
		self.DefaultLens = camera.lens
		GameLogic.getCurrentScene().active_camera = camera
	
	def SetDefaultGoal(self, goal):
		'''
		Set the default goal. If there is already a goal on the GoalStack, it
		will be used instead of this default one - until it is popped off the
		stack.
		'''
		self.DefaultGoal = goal
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
			
			if self.instantCut:
				self.Camera.worldPosition = self.CurrentGoal.owner.worldPosition
				self.Camera.worldOrientation = self.CurrentGoal.owner.worldOrientation
				targetLens = self.DefaultLens
				if hasattr(self.CurrentGoal.owner, 'lens'):
					targetLens = self.CurrentGoal.owner.lens
				self.Camera.lens = targetLens
				self.instantCut = False
			self.StackModified = False
		
		fac = self.DefaultGoal.factor
		if self.CurrentGoal.factor != None:
			fac = self.CurrentGoal.factor
		Utilities._SlowCopyLoc(self.Camera, self.CurrentGoal.owner, fac)
		Utilities._SlowCopyRot(self.Camera, self.CurrentGoal.owner, fac)
		
		targetLens = self.DefaultLens
		if hasattr(self.CurrentGoal.owner, 'lens'):
			targetLens = self.CurrentGoal.owner.lens
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
			self.instantCut = True
	
	def RemoveGoal(self, goalOb):
		'''
		Remove a goal from the stack. If it was currently in use, the camera
		will switch to follow the next one on the stack. The transform isn't
		changed until onRender is called.
		'''
		if len(self.Q) == 0:
			return
		
		if self.Q.top().owner == goalOb:
			#
			# Goal is on top of the stack: it's in use!
			#
			oldGoal = self.Q.pop()
			self.StackModified = True
			if oldGoal.instantCut:
				self.instantCut = True
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
			if g.instantCut:
				self.instantCut = True
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
	'''An object that acts as a camera that can be switched to. It defines a
	point in space, an orientation, and (optionally) a focal length. The
	AutoCamera copies its location, interpolating as need be.'''
	def __init__(self, owner, factor = None, instantCut = False):
		# The object defining the location. If it's a camera, the focal length
		# (lens value) will be used too.
		self.owner = owner
		# How quickly the camera moves to this goal (0.01 = slow, 0.1 = fast).
		self.factor = factor
		# Whether to interpolate to this goal. If false, the AutoCamera will
		# switch instantly to the new values.
		self.instantCut = instantCut

#
# Camera for following the player
#

class CameraPath(CameraGoal):
	'''A camera goal that follows the active player.'''
	
	# The maximum number of nodes to track. Once this number is reached, the
	# oldest nodes will be removed.
	MAX_NODES = 100
	# The minimum distance to leave between nodes. 
	# A new node will be created if the actor has travelled at least MIN_DIST
	# and the dot product is at most MAX_DOT.
	MIN_DIST = 1.0
	# The maxium difference in angle between two path segments, specified as a
	# dot product between the vectors (1.0 = 0 degrees, 0.0 = 90 degrees,
	# -1.0 = 180 degrees).
	MAX_DOT = 0.5
	
	ACCELERATION = 0.01
	DAMPING = 0.1
	REST_DISTANCE = 10.0
	ZOFFSET = 5.0
	THRESHOLD = 2.0
	
	def __init__(self, owner, factor, instantCut):
		CameraGoal.__init__(self, owner, factor, instantCut)
		# A list of CameraNodes.
		self.path = []
		self.linV = Utilities.ZEROVEC.copy()
		Utilities.SceneManager.Subscribe(self)
	
	def onRender(self):
		self.advanceGoal()
		self.updateWayPoints()
	
	def OnSceneEnd(self):
		for n in self.path:
			n.destroy()
		self.goal = None
		Utilities.SceneManager.Unsubscribe(self)
	
	def advanceGoal(self):
		'''Move the camera to follow the main character. This will either follow
		the path or the character, depending on which is closest. Don't worry
		about interpolation; the AutoCamera will smooth out the motion later.'''
		#
		# Get the vector from the camera to the target.
		#
		actor = Actor.Director.getMainCharacter()
		if actor == None:
			return
		dirAct = actor.owner.worldPosition - self.owner.worldPosition
		distAct = dirAct.magnitude
		
		#
		# Get the vector from the camera to the next way point.
		#
		wayPoint = self._getNextWayPoint()
		dirWay = wayPoint - self.owner.worldPosition
		distWay = dirWay.magnitude
		dirWay.normalize()
		
		#
		# Accelerate the camera towards or away from the next way point. 
		#
		acceleration = (distAct - self.REST_DISTANCE) * self.ACCELERATION
		self.linV = self.linV + (dirWay * acceleration)
		self.linV = self.linV * (1.0 - self.DAMPING)
		self.owner.worldPosition = self.owner.worldPosition + self.linV
		
		#
		# Align the camera's Y-axis with the global Z, and align
		# its Z-axis with the direction to the target.
		#
		dirAct.negate()
		self.owner.alignAxisToVect(Utilities.ZAXIS, 1)
		self.owner.alignAxisToVect(dirAct, 2)
	
	def _getNextWayPoint(self):
		actor = Actor.Director.getMainCharacter()
		closestPoint = self._getPos(actor.owner)
		
		shortestDistance = (closestPoint -
						self.owner.worldPosition).magnitude
		
		for node in self.path:
			if node.hit:
				break
			
			nextPoint = self._getPos(node.owner)
			dist = (nextPoint - self.owner.worldPosition).magnitude
			if dist < shortestDistance:
				if dist < self.THRESHOLD:
					node.hit = True
					break
				closestPoint = nextPoint
				shortestDistance = dist
		
		return closestPoint
	
	def _getPos(self, ob):
		targetPos = Utilities.ZAXIS.copy()
		targetPos *= self.ZOFFSET
		targetPos = Utilities._toWorld(ob, targetPos)
		return targetPos
	
	def updateWayPoints(self):
		actor = Actor.Director.getMainCharacter()
		if actor == None:
			return
		
		if len(self.path) == 0:
			Utilities.setCursorTransform(actor.owner)
			self.path.insert(0, CameraNode())
			return
		
		currentPos = actor.owner.worldPosition
		dir = currentPos - self.path[0].owner.worldPosition
		if dir.magnitude > self.MIN_DIST:
			# Add a new node to the end.
			Utilities.setCursorTransform(actor.owner)
			self.path.insert(0, CameraNode())
			
			if len(self.path) > self.MAX_NODES:
				# Delete the oldest node.
				self.path.pop().destroy()

def createCameraPath(c):
	owner = c.owner
	path = CameraPath(owner, owner['SlowFac'], owner['InstantCut'])
	owner['CameraPath'] = path
	AutoCamera.SetDefaultGoal(path)

def updatePath(c):
	c.owner['CameraPath'].onRender()

class CameraNode:
	'''A single point in a path used by the CameraPathGoal. These act as
	way points for the camera to follow.'''
	def __init__(self):
		# Defines the location of the way point. Using a way point allows the
		# node to parented to an object.
		scene = GameLogic.getCurrentScene()
		self.owner = scene.addObject('PointMarker', Utilities.getCursor(), 0)
		self.hit = False

	def destroy(self):
		self.owner.endObject()

#
# Camera for viewing the background scene
#

class BackgroundCamera(CameraObserver):
	'''Links a second camera to the main 3D camera. This second, background
	camera will always match the orientation and zoom of the main camera. It is
	guaranteed to update after the main one.'''
	
	def __init__(self, owner):
		self.owner = owner
		AutoCamera.AddObserver(self)
		Utilities.SceneManager.Subscribe(self)
	
	def OnSceneEnd(self):
		self.owner = None
		AutoCamera.RemoveObserver(self)
	
	def OnCameraMoved(self, autoCamera):
		self.owner.worldOrientation = autoCamera.Camera.worldOrientation
		self.owner.lens = autoCamera.Camera.lens

def createBackgroundCamera(c):
	BackgroundCamera(c.owner)
