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
from . import Utilities
from . import Actor
from . import UI
from bge import logic
import weakref

DEBUG = False

def hasLineOfSight(ob, other):
	hitOb, _, _ = bxt.math.ray_cast_p2p(other, ob, prop = 'Ray')
	return hitOb == None
	
class CameraObserver:
	'''
	An observer of AutoCameras. One use for this is cameras in other scenes.
	For example, the background camera sets its worldOrientation to be the same
	as the camera in the game play scene, which is bound to the AutoCamera.
	'''
	def on_camera_moved(self, autoCamera):
		pass

@bxt.types.singleton('set_camera', 'update', 'add_goal', 'remove_goal',
					prefix='AC_')
class AutoCamera:
	'''Manages the transform of the camera, and provides transitions between
	camera locations. To transition to a new location, call PushGoal. The
	reverse transition can be performed by calling PopGoal.
	'''

	def __init__(self):
		'''Create an uninitialised AutoCamera. Call SetCamera to bind it to a
		camera.
		'''
		self.camera = None
		self.defaultLens = 22.0
		self.queue = bxt.utils.WeakPriorityQueue()
		self.lastGoal = None
		self.instantCut = False
		self.observers = weakref.WeakSet()

	@bxt.utils.owner_cls
	def set_camera(self, camera):
		'''Bind to a camera.'''

		def auto_unset_camera(ref):
			if ref == self.camera:
				self.camera = None

		wrapper = bxt.types.wrap(camera, bxt.types.ProxyCamera)
		self.camera = weakref.ref(wrapper, auto_unset_camera)
		self.defaultLens = camera.lens
		logic.getCurrentScene().active_camera = camera

	def get_camera(self):
		if self.camera == None:
			return None
		else:
			return self.camera()
	
	def update(self):
		'''Update the location of the camera. observers will be notified. The
		camera should have a controller set up to call this once per frame.
		'''

		if not self.get_camera() or len(self.queue) == 0:
			return

		currentGoal = self.queue.top()
		ref = weakref.ref(currentGoal)
		if self.lastGoal != ref:
			# Keeping track of goals being added and removed it very
			# difficult, so we just consider the last action when deciding
			# whether or not to cut instantly.
			if self.instantCut:
				self.get_camera().worldPosition = currentGoal.worldPosition
				self.get_camera().worldOrientation = currentGoal.worldOrientation
				if hasattr(currentGoal, 'lens'):
					self.get_camera().lens = currentGoal.lens
				self.instantCut = False

		fac = currentGoal['SlowFac']
		bxt.math.slow_copy_loc(self.get_camera(), currentGoal, fac)
		bxt.math.slow_copy_rot(self.get_camera(), currentGoal, fac)

		targetLens = self.defaultLens
		if hasattr(currentGoal, 'lens'):
			targetLens = currentGoal.lens
		self.get_camera().lens = bxt.math.lerp(self.get_camera().lens, targetLens, fac)

		self.lastGoal = ref
		
		for o in self.observers:
			o.on_camera_moved(self)

	@bxt.utils.owner_cls
	def add_goal(self, goal):
		'''Give the camera a new goal, and remember the last one. Call
		RemoveGoal to restore the previous relationship. The camera position
		isn't changed until update is called.
		'''

		# Wrap the goal in a proxy object, if it doesn't already have one.
		wrapper = None
		if bxt.types.has_wrapper(goal):
			wrapper = bxt.types.get_wrapper(goal)
		elif bxt.types.is_wrapper(goal):
			wrapper = goal
		else:
			if hasattr(goal, 'lens'):
				wrapper = bxt.types.ProxyCamera(goal)
			else:
				wrapper = bxt.types.ProxyGameObject(goal)

		# Set some defaults for properties.
		wrapper.set_default_prop('SlowFac', 0.1)
		wrapper.set_default_prop('InstantCut', False)
		wrapper.set_default_prop('Priority', 1)

		# Add the goal to the queue.
		self.queue.push(wrapper, wrapper['Priority'])

		if self.queue.top() == wrapper['InstantCut']:
			# Goal is on top of the stack: it will be switched to next
			self.instantCut = True

	@bxt.utils.owner_cls
	def remove_goal(self, goal):
		'''Remove a goal from the stack. If it was currently in use, the camera
		will switch to follow the next one on the stack. The transform isn't
		changed until update is called.
		'''

		wrapper = None
		if bxt.types.has_wrapper(goal):
			wrapper = bxt.types.get_wrapper(goal)
		elif bxt.types.is_wrapper(goal):
			wrapper = goal
		else:
			# add_goal would have added a wrapper, so this object can't be in
			# the queue.
			return

		if not wrapper in self.queue:
			return

		if self.queue.top() == wrapper and wrapper['InstantCut']:
			# Goal is on top of the stack: it's in use!
			self.instantCut = True

		self.queue.discard(wrapper)
	
	def add_observer(self, camObserver):
		self.observers.add(camObserver)
	
	def remove_observer(self, camObserver):
		self.observers.remove(camObserver)

def add_goal_if_main_char():
	'''
	Add the owner of this controller as a goal if the main actor has been hit.
	
	@see Actor._hitMainCharacter.
	'''
	if not Actor._hitMainCharacter():
		return

	AutoCamera().add_goal()

def remove_goal_if_not_main_char():
	if Actor._hitMainCharacter():
		return

	AutoCamera().remove_goal()

@bxt.types.singleton('set_active', prefix='CCM_')
class CloseCameraManager(Actor.DirectorListener):
	def __init__(self):
		Actor.Director().addListener(self)
		self.active = False

	def directorMainCharacterChanged(self, oldActor, newActor):
		if oldActor == None:
			return

		closeCam = oldActor.getCloseCamera()
		if closeCam != None:
			AutoCamera().remove_goal(closeCam)
			self.active = False

	def toggleCloseMode(self):
		actor = Actor.Director().getMainCharacter()
		closeCam = actor.getCloseCamera()
		if closeCam == None:
			return

		if self.active:
			AutoCamera().remove_goal(closeCam)
			self.active = False
		else:
			AutoCamera().add_goal(closeCam)
			self.active = True

	def set_active(self):
		if self.active != bxt.utils.allSensorsPositive():
			self.toggleCloseMode()

#
# camera for following the player
#

@bxt.types.gameobject('update', prefix='CP_')
class CameraPath(bxt.types.ProxyGameObject):
	'''A camera goal that follows the active player.'''
	
	# The maximum number of nodes to track. Once this number is reached, the
	# oldest nodes will be removed.
	MAX_NODES = 50
	# The minimum distance to leave between nodes. 
	MIN_DIST = 1.0
	
	ACCELERATION = 0.01
	DAMPING = 0.1
	
	# The preferred distance from the target (a point above the actor).
	# Note that this mill change depending on the situation; e.g. it becomes
	# lower when the ceiling is low.
	REST_DISTANCE = 5.0
	# The amount to expand the radius when it is safe to do so.
	EXPAND_FACTOR = 4.0
	# The amount to expand the radius when no other factors are at play. Ideally
	# REST_DISTANCE would just be increased, but in practice the contraction
	# factor is never below about 1.5 - so a similar value is used for
	# continuity.
	REST_FACTOR = 1.5
	
	# The distance above the actor that the camera should aim for. Actually, the
	# camera will aim for a point ZOFFSET * CEILING_AVOIDANCE_BIAS away from the
	# actor.
	ZOFFSET = 10.0
	CEILING_AVOIDANCE_BIAS = 0.5
	# The maximum height difference between two consecutive targets. This
	# smoothes off the path as the actor goes under a ceiling.
	ZOFFSET_INCREMENT = MIN_DIST * 0.5
	
	# The number of consecutive nodes that must be seen before being accepted.
	# If this is too low, the camera will clip through sharp corners. 
	NODE_DELAY = 2
	# The number of frames to wait before deciding that the predictive node is
	# obscured.
	EXPAND_ON_WAIT = 20
	EXPAND_OFF_WAIT = 15
	# Responsiveness of the radius adjustment.
	RADIUS_SPEED = 0.1
	# Responsiveness of the camera orientation.
	ALIGN_Y_SPEED = 0.05
	ALIGN_Z_SPEED = 1.0
	# Distance to project predictive node.
	PREDICT_FWD = 20.0
	PREDICT_UP = 50.0
	
	def __init__(self, owner):
		bxt.types.ProxyGameObject.__init__(self, owner)
		# A list of CameraNodes.
		self.path = []
		self.pathHead = CameraNode()
		self.linV = bxt.math.ZEROVEC.copy()
		
		self.radMult = 1.0
		self.expand = bxt.utils.FuzzySwitch(CameraPath.EXPAND_ON_WAIT,
										CameraPath.EXPAND_OFF_WAIT, True)

		AutoCamera().add_goal(self)
		
		if DEBUG:
			self.targetVis = bxt.utils.add_object('DebugReticule')
			self.predictVis = bxt.utils.add_object('DebugReticule')
	
	def update(self):
		self.updateWayPoints()
		self.advanceGoal()
	
	def advanceGoal(self):
		'''Move the camera to follow the main character. This will either follow
		the path or the character, depending on which is closest. Don't worry
		about interpolation; the AutoCamera will smooth out the motion later.'''
		#
		# Get the vector from the camera to the target.
		#
		actor = Actor.Director().getMainCharacter()
		if actor == None:
			return
		
		# Get the vector from the camera to the next way point.
		node, pathLength = self._getNextWayPoint()
		target = node.getTarget()
		dirWay = target - self.worldPosition
		dirWay.normalize()
		
		# Adjust preferred distance from actor based on current conditions.
		contract = False
		if node.ceilingHeight < CameraPath.ZOFFSET:
			# Bring the camera closer when under a low ceiling or in a tunnel.
			contract = True
		
		if self._canSeeFuture():
			# Otherwise, relax the camera if the predicted point is visible.
			self.expand.turn_on()
		else:
			self.expand.turn_off()
		
		radMult = 1.0
		if contract:
			radMult = 1.0 + (node.ceilingHeight / CameraPath.ZOFFSET)
		elif self.expand.is_on():
			radMult = CameraPath.EXPAND_FACTOR
		else:
			radMult = CameraPath.REST_FACTOR
		self.radMult = bxt.math.lerp(self.radMult, radMult,
									CameraPath.RADIUS_SPEED)
		restNear = self.REST_DISTANCE
		restFar = self.REST_DISTANCE * self.radMult
		
		# Determine the acceleration, based on the distance from the actor.
		dist = self.getDistanceTo(node.owner) + pathLength
		acceleration = 0.0
		if dist < restNear:
			acceleration = (dist - restNear) * self.ACCELERATION
		elif dist > restFar:
			acceleration = (dist - restFar) * self.ACCELERATION
		
		# Apply the acceleration.
		self.linV = self.linV + (dirWay * acceleration)
		self.linV = self.linV * (1.0 - self.DAMPING)
		self.worldPosition = self.worldPosition + self.linV

		# Align the camera's Y-axis with the global Z, and align
		# its Z-axis with the direction to the target.
		look = actor.owner.worldPosition - self.worldPosition
		look.negate()
		if actor.useLocalCoordinates():
			axis = node.owner.getAxisVect(bxt.math.ZAXIS)
			self.alignAxisToVect(axis, 1, CameraPath.ALIGN_Y_SPEED)
		else:
			self.alignAxisToVect(bxt.math.ZAXIS, 1, 0.5)
		self.alignAxisToVect(look, 2, CameraPath.ALIGN_Z_SPEED)
		
		if DEBUG: self.targetVis.worldPosition = target
	
	def _canSeeFuture(self):
		# TODO: Make a DEBUG function decorator that runs stuff before and after
		ok, projectedPoint = self._canSeeFuture_()
		if DEBUG:
			self.predictVis.worldPosition = projectedPoint
			if ok:
				self.predictVis.color = bxt.render.BLACK
			else:
				self.predictVis.color = bxt.render.RED
		return ok
	
	def _canSeeFuture_(self):
		if len(self.path) < 2:
			# Can't determine direction. Return True if actor is visible.
			projectedPoint = self.pathHead.owner.worldPosition
			return hasLineOfSight(self, projectedPoint), projectedPoint
		
		# Try a point ahead of the actor. If the path is curving, project the
		# point 'down' in anticipation of the motion.
		a, b = self.path[0], self.path[1]
		ba = a.owner.worldPosition - b.owner.worldPosition
		ba.normalize()
		projectedPoint = a.owner.worldPosition + (ba * CameraPath.PREDICT_FWD)
		
		hitOb, hitPoint, _ = bxt.math.ray_cast_p2p(
				projectedPoint, a.owner, prop = 'Ray')
		if hitOb != None:
			vect = hitPoint - a.owner.worldPosition
			vect.magnitude = vect.magnitude * 0.9
			projectedPoint = a.owner.worldPosition + vect
		
		# Check the difference in direction of consecutive line segments.
		dot = 1.0
		cb = ba.copy()
		for c in self.path[2:7]:
			cb = b.owner.worldPosition - c.owner.worldPosition
			cb.normalize()
			
			dot = ba.dot(cb)
			if dot < 0.999:
				break
		
		if dot < 0.999:
			# The path is bent; project the point in the direction of the
			# curvature. The cross product gives us the axis of rotation.
			rotAxis = ba.cross(cb)
			upAxis = rotAxis.cross(ba)
			pp2 = projectedPoint - (upAxis * CameraPath.PREDICT_FWD)
		
			hitOb, hitPoint, _ = bxt.math.ray_cast_p2p(
					pp2, projectedPoint, prop = 'Ray')
			if hitOb != None:
				vect = hitPoint - projectedPoint
				vect.magnitude = vect.magnitude * 0.9
				pp2 = projectedPoint + vect
			projectedPoint = pp2
			
		if hasLineOfSight(self, projectedPoint):
			return True, projectedPoint
		else:
			return False, projectedPoint
	
	def _getNextWayPoint(self):
		# TODO: Make a DEBUG function decorator that runs stuff before and after
		node, pathLength = self._getNextWayPoint_()
		if DEBUG:
			# Colour nodes.
			found = False
			
			if node == self.pathHead:
				found = True
				node.owner.color = bxt.render.RED
			else:
				node.owner.color = bxt.render.WHITE
			
			for n in self.path:
				if node == n:
					n.owner.color = bxt.render.RED
					found = True
				elif found:
					n.owner.color = bxt.render.BLACK
				else:
					n.owner.color = bxt.render.WHITE
		
		return node, pathLength
	
	def _getNextWayPoint_(self):
		'''Find the next point that the camera should advance towards.'''
		
		# Try to go straight to the actor.
		nFound = 0
		node = self.pathHead
		target = node.getTarget()
		if (hasLineOfSight(self, node.owner) and
			hasLineOfSight(self, target)):
			return node, 0.0
		
		# Actor is obscured; find a good way point.
		nSearched = 0
		for currentNode in self.path:
			nSearched += 1
			
			currentTarget = currentNode.getTarget()
			
			if (not hasLineOfSight(self, currentNode.owner) or
				not hasLineOfSight(self, currentTarget)):
				nFound = 0
				continue
			
			nFound += 1
			if nFound >= self.NODE_DELAY:
				node = currentNode
				break
		
		distance = nSearched * self.MIN_DIST
		if len(self.path) > 0:
			distance += self.pathHead.owner.getDistanceTo(self.path[0].owner)
		return node, distance
	
	def updateWayPoints(self):
		actor = Actor.Director().getMainCharacter()
		if actor == None:
			return
		
		if actor.useLocalCoordinates():
			bxt.math.copy_transform(actor.owner, self.pathHead.owner)
		else:
			self.pathHead.owner.worldPosition = actor.owner.worldPosition
			bxt.math.reset_orientation(self.pathHead.owner)
		
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
			node = CameraNode()
			if actor.useLocalCoordinates():
				bxt.math.copy_transform(actor.owner, node.owner)
			else:
				node.owner.worldPosition = actor.owner.worldPosition
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

class CameraNode:
	'''A single point in a path used by the CameraPathGoal. These act as
	way points for the camera to follow.'''
	
	def __init__(self):
		# Defines the location of the way point. Using a way point allows the
		# node to parented to an object.
		self.owner = bxt.utils.add_object('PointMarker')
		if not DEBUG:
			self.owner.visible = False
		else:
			self.marker = bxt.utils.add_object("PointMarker")
			self.marker.color = bxt.render.BLUE
		
		# It is an error to access these next two before calling update().
		self.ceilingHeight = None
		self.target = None

	def update(self):
		self.target = bxt.math.ZAXIS.copy()
		self.target *= CameraPath.ZOFFSET
		self.target = bxt.math.to_world(self.owner, self.target)
		hitOb, hitPoint, _ = bxt.math.ray_cast_p2p(
				self.target, # objto
				self.owner.worldPosition, # objfrom
				prop = 'Ray')
		
		if hitOb:
			vec = hitPoint - self.owner.worldPosition
			self.setCeilingHeight(vec.magnitude)
		else:
			self.setCeilingHeight(CameraPath.ZOFFSET)
	
	def getTarget(self):
		bias = self.ceilingHeight / CameraPath.ZOFFSET
		bias *= CameraPath.CEILING_AVOIDANCE_BIAS
		return bxt.math.lerp(self.owner.worldPosition, self.target, bias)

	def destroy(self):
		self.owner.endObject()
		if DEBUG: self.marker.endObject()
	
	def setCeilingHeight(self, height):
		self.ceilingHeight = height
		if DEBUG: self.marker.worldPosition = self.getTarget()

#
# Helper for sensing when camera is inside something.
#

@bxt.types.gameobject()
class CameraCollider(CameraObserver, bxt.types.ProxyGameObject):
	'''Helper for sensing when camera is inside something. This senses when the
	camera touches a volumetric object, and then tracks to see when the camera
	enters and leaves that object, adjusting the screen filter appropriately.'''
	
	MAX_DIST = 1000.0
	
	def __init__(self, owner):
		bxt.types.ProxyGameObject.__init__(self, owner)
		AutoCamera().add_observer(self)
	
	def on_camera_moved(self, autoCamera):
		self.worldPosition = autoCamera.get_camera().worldPosition
		pos = autoCamera.get_camera().worldPosition.copy()
		through = pos.copy()
		through.z += CameraCollider.MAX_DIST
		vec = through - pos

		ob, _, normal = bxt.math.ray_cast_p2p(through, pos, prop='VolumeCol')

		inside = False
		if ob != None:
			if normal.dot(vec) > 0.0:
				inside = True

		if inside:
			if not '_VolColCache' in ob:
				ob['_VolColCache'] = bxt.render.parse_colour(ob['VolumeCol'])
			UI.HUD().showFilter(ob['_VolColCache'])
		else:
			UI.HUD().hideFilter()

#
# camera for viewing the background scene
#

@bxt.types.gameobject()
class BackgroundCamera(CameraObserver, bxt.types.ProxyGameObject):
	'''Links a second camera to the main 3D camera. This second, background
	camera will always match the orientation and zoom of the main camera. It is
	guaranteed to update after the main one.'''
	
	def __init__(self, owner):
		bxt.types.ProxyGameObject.__init__(self, owner)
		AutoCamera().add_observer(self)
	
	def on_camera_moved(self, autoCamera):
		self.worldOrientation = autoCamera.get_camera().worldOrientation
		self.lens = autoCamera.get_camera().lens
