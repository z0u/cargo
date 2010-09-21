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

DEBUG = True

def hasLineOfSight(ob, other):
	hitOb, _, _ = ob.rayCast(
			other, # objto
			None, # objfrom
			0, # dist (go only as far as 'other'
			'Ray', # prop (look only for Ray objects)
			1, # face
			1, # xray (ignore other objects)
			0) # poly (don't care about polygon)
	
	return hitOb == None
	
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
	MAX_NODES = 50
	# The minimum distance to leave between nodes. 
	MIN_DIST = 1.0
	
	ACCELERATION = 0.01
	DAMPING = 0.1
	REST_DISTANCE_NEAR = 5.0
	REST_DISTANCE_FAR = 15.0
	
	ZOFFSET_INCREMENT = MIN_DIST * 0.5
	CURVE_LENGTH = 5
	# The number of consecutive nodes that must be seen before being accepted.
	# If this is too low, the camera will clip through sharp corners. 
	NODE_DELAY = 2
	THRESHOLD = 1.0
	
	def __init__(self, owner, factor, instantCut):
		CameraGoal.__init__(self, owner, factor, instantCut)
		# A list of CameraNodes.
		self.path = []
		self.pathHead = CameraNode()
		self.linV = Utilities.ZEROVEC.copy()
		if DEBUG:
			self.debugReticule = Utilities.addObject('DebugReticule')
			self.debugReticule2 = Utilities.addObject('DebugReticule')
		Utilities.SceneManager.Subscribe(self)
	
	def onRender(self):
		self.updateWayPoints()
		self.advanceGoal()
	
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
		wayObject, wayTarget, pathLength, ceilingHeight = self._getNextWayPoint()
		if DEBUG:
			self.debugReticule.worldPosition = wayTarget
		dirWay = wayTarget - self.owner.worldPosition
		distWay = dirWay.magnitude
		dirWay.normalize()
		
		#
		# Accelerate the camera towards or away from the next way point. 
		#
		radiusMultiplier = ceilingHeight / CameraNode.ZOFFSET
		radiusMultiplier = min(radiusMultiplier, 1.0)
		if self._canSeeFuture():
			radiusMultiplier *= 2.0
		restNear = self.REST_DISTANCE_NEAR
		restFar = Utilities._lerp(restNear, self.REST_DISTANCE_FAR, radiusMultiplier)

		dist = self.owner.getDistanceTo(wayObject) + pathLength
		acceleration = 0.0
		if dist < restNear:
			acceleration = (dist - restNear) * self.ACCELERATION
		elif dist > restFar:
			acceleration = (dist - restFar) * self.ACCELERATION
		
		self.linV = self.linV + (dirWay * acceleration)
		self.linV = self.linV * (1.0 - self.DAMPING)
		self.owner.worldPosition = self.owner.worldPosition + self.linV

		#
		# Align the camera's Y-axis with the global Z, and align
		# its Z-axis with the direction to the target.
		#
		look = dirAct.copy()
		look.negate()
		self.owner.alignAxisToVect(Utilities.ZAXIS, 1)
		self.owner.alignAxisToVect(look, 2)
	
	def _canSeeFuture(self):		
		actor = Actor.Director.getMainCharacter()
		actorPos = actor.owner.worldPosition
		
		if len(self.path) <= 0:
			# Can't determine direction. Return True if actor is visible.
			return hasLineOfSight(self.owner, actorPos)
		
		# First try a point just ahead of the actor.
		direction = actorPos - self.path[0].owner.worldPosition
		direction.normalize()
		projectedPoint = actorPos + (direction * self.MIN_DIST)
		if DEBUG: self.debugReticule2.worldPosition = projectedPoint
		if hasLineOfSight(self.owner, projectedPoint):
			if DEBUG: self.debugReticule2.color = Utilities.RED
			return True

		if len(self.path) < 3:
			if DEBUG: self.debugReticule2.color = Utilities.BLACK
			return False
		
		# Get the curvature, sampled over a few points.
		offsetFromLinear = 0.0
		for A, B, C in zip(self.path[0:self.CURVE_LENGTH],
							self.path[1:self.CURVE_LENGTH],
							self.path[2:self.CURVE_LENGTH]):
			direction = B.owner.worldPosition - C.owner.worldPosition
			projectedPoint = B.owner.worldPosition + direction
			direction = A.owner.worldPosition - projectedPoint
			offsetFromLinear += direction.magnitude
		
		# Project a point further out, using the curvature determined above.
		A, B, C = self.path[0], self.path[1], self.path[2]
		direction = B.owner.worldPosition - C.owner.worldPosition
		projectedPoint = B.owner.worldPosition + direction
		direction = A.owner.worldPosition - projectedPoint
		direction.normalize()
		projectedPoint = A.owner.worldPosition + (direction * 10.0)
		
		if DEBUG: self.debugReticule2.worldPosition = projectedPoint
		if hasLineOfSight(self.owner, projectedPoint):
			if DEBUG: self.debugReticule2.color = Utilities.RED
			return True
		
		if DEBUG: self.debugReticule2.color = Utilities.BLACK
		return False
	
	def _getNextWayPoint(self):
		'''Find the next point that the camera should advance towards.'''
		def colourNodes(node):
			found = False
			
			if node == self.pathHead:
				found = True
				node.owner.color = Utilities.RED
			else:
				node.owner.color = Utilities.WHITE
			
			for n in self.path:
				if node == n:
					n.owner.color = Utilities.RED
					found = True
				elif found:
					n.owner.color = Utilities.BLACK
				else:
					n.owner.color = Utilities.WHITE
		
		# Try to go straight to the actor.
		nFound = 0
		node = self.pathHead
		target = node.getTarget()
		if (hasLineOfSight(self.owner, node.owner) and
			hasLineOfSight(self.owner, target)):
			if DEBUG: colourNodes(node)
			return node.owner, target, 0.0, node.ceilingHeight
		
		# Actor is obscured; find a good way point.
		nSearched = 0
		cumulativeHeight = self.pathHead.ceilingHeight
		for currentNode in self.path:
			nSearched += 1
			
			currentTarget = currentNode.getTarget()
			cumulativeHeight += currentNode.ceilingHeight
			
			if currentNode.hit:
				break
			
			if (not hasLineOfSight(self.owner, currentNode.owner) or
				not hasLineOfSight(self.owner, currentTarget)):
				nFound = 0
				continue
			
			nFound += 1
			if nFound >= self.NODE_DELAY:
				node = currentNode
				target = currentTarget
				
				dist = self.owner.getDistanceTo(node.owner)
#				if dist < self.THRESHOLD:
#					currentNode.setHit()
				
				break
		
		if DEBUG: colourNodes(node)
		
		distance = nSearched * self.MIN_DIST
		offset = cumulativeHeight / (nSearched + 1)
		if len(self.path) > 0:
			distance += self.pathHead.owner.getDistanceTo(self.path[0].owner)
		return node.owner, target, distance, offset
	
	def updateWayPoints(self):
		actor = Actor.Director.getMainCharacter()
		if actor == None:
			return
		
		Utilities._copyTransform(actor.owner, self.pathHead.owner)
		
		# Add a new node if the actor has moved far enough.
		addNew = False
		if len(self.path) == 0:
			addNew = True
		else:
			currentPos = actor.owner.worldPosition
			vec = currentPos - self.path[0].owner.worldPosition
			if vec.magnitude > self.MIN_DIST:
				addNew = True
		
		if addNew:
			Utilities.setCursorTransform(actor.owner)
			node = CameraNode()
			self.path.insert(0, node)
			if actor.getTouchedObject() != None:
				node.owner.setParent(actor.getTouchedObject(), False)
			if len(self.path) > self.MAX_NODES:
				# Delete the oldest node.
				self.path.pop().destroy()
		
		# Update the ceiling height for each node, ensuring a smooth transition
		# between consecutive z-offsets.
		self.pathHead.update()
		for node in self.path:
			node.update()
		
		def pingPong(iterable):
			# pingPong('ABC') --> A B C C B A
			for element in iterable:
				yield element
			for element in reversed(iterable):
				yield element

		def marginMin(current, next, margin):
			return min(current + margin, next)
		
		currentOffset = self.pathHead.ceilingHeight
		for node in pingPong(self.path):
			node.setCeilingHeight(marginMin(currentOffset, node.ceilingHeight,
								self.ZOFFSET_INCREMENT))
			currentOffset = node.ceilingHeight
		self.pathHead.setCeilingHeight(marginMin(currentOffset,
										self.pathHead.ceilingHeight,
										self.ZOFFSET_INCREMENT))

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
	
	ZOFFSET = 20.0
	CEILING_AVOIDANCE_BIAS = 0.5
	
	def __init__(self):
		# Defines the location of the way point. Using a way point allows the
		# node to parented to an object.
		self.owner = Utilities.addObject('PointMarker')
		if not DEBUG:
			self.owner.visible = False
		else:
			scene = GameLogic.getCurrentScene()
			self.marker = Utilities.addObject("PointMarker")
			self.marker.color = Utilities.BLUE
		self.hit = False
		
		# It is an error to access these next two before calling update().
		self.ceilingHeight = None
		self.target = None

	def update(self):
		self.target = Utilities.ZAXIS.copy()
		self.target *= self.ZOFFSET
		self.target = Utilities._toWorld(self.owner, self.target)
		hitOb, hitPoint, hitNorm = Utilities._rayCastP2P(
				self.target, # objto
				self.owner.worldPosition, # objfrom
				prop = 'Ray')
		
		if hitOb:
			vec = hitPoint - self.owner.worldPosition
			self.setCeilingHeight(vec.magnitude)
		else:
			self.setCeilingHeight(CameraNode.ZOFFSET)
	
	def getTarget(self):
		bias = self.ceilingHeight / CameraNode.ZOFFSET
		bias *= CameraNode.CEILING_AVOIDANCE_BIAS
		return Utilities._lerp(self.owner.worldPosition, self.target, bias)

	def destroy(self):
		self.owner.endObject()
		if DEBUG: self.marker.endObject()
		
	def setHit(self):
		self.hit = True
	
	def setCeilingHeight(self, height):
		self.ceilingHeight = height
		if DEBUG: self.marker.worldPosition = self.getTarget()

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
