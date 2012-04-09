#
# Copyright 2009 - 2011, Alex Fraser <alex@phatcore.com>
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

import bge
from bge import logic

import bxt
from . import director, store

DEBUG = False
log = bxt.utils.get_logger(DEBUG)

def hasLineOfSight(ob, other):
	hitOb, _, _ = bxt.bmath.ray_cast_p2p(other, ob, prop = 'Ray')
	return hitOb == None

class CameraObserver:
	'''
	An observer of AutoCameras. One use for this is cameras in other scenes.
	For example, the background camera sets its worldOrientation to be the same
	as the camera in the game play scene, which is bound to the AutoCamera.
	'''
	def on_camera_moved(self, autoCamera):
		pass

class AutoCamera(metaclass=bxt.types.Singleton):
	'''Manages the transform of the camera, and provides transitions between
	camera locations. To transition to a new location, call PushGoal. The
	reverse transition can be performed by calling PopGoal.
	'''
	_prefix = 'AC_'

	COLLISION_BIAS = 0.8
	MIN_FOCAL_DIST = 5.0
	FOCAL_FAC = 0.1

	camera = bxt.types.weakprop('camera')
	lastGoal = bxt.types.weakprop('lastGoal')

	def __init__(self):
		'''Create an uninitialised AutoCamera. Call SetCamera to bind it to a
		camera.
		'''
		self.camera = None
		self.defaultLens = 22.0
		self.queue = bxt.types.SafePriorityQueue()
		self.focusQueue = bxt.types.SafePriorityQueue()
		self.lastGoal = None
		self.instantCut = False
		self.errorReported = False

		bxt.types.EventBus().add_listener(self)
		bxt.types.EventBus().replay_last(self, 'Spawned')

	def on_event(self, evt):
		if evt.message == 'Spawned':
			spawnPoint = evt.body
			if len(spawnPoint.children) <= 0:
				return
			pos = spawnPoint.children[0].worldPosition
			orn = spawnPoint.children[0].worldOrientation
			bxt.types.Event('RelocatePlayerCamera', (pos, orn)).send()

	@bxt.types.expose
	@bxt.utils.owner_cls
	def set_camera(self, camera):
		'''Bind to a camera.'''
		log('setting camera')
		self.camera = camera
		self.defaultLens = camera.lens
		bxt.utils.get_scene(camera).active_camera = camera

	@bxt.types.expose
	@bxt.utils.controller_cls
	def init_filters(self, c):
		'''Initialise filters.'''
		if store.get('/opt/depthOfField', True):
			c.activate(c.actuators['aDof'])

	@bxt.types.expose
	def update(self):
		'''Update the location of the camera. observers will be notified. The
		camera should have a controller set up to call this once per frame.
		'''

		if not self.camera:
			return

		currentGoal = None
		if DEBUG:
			log.write("\rCamera queue: {}".format(self.queue))
			log.flush()
		try:
			currentGoal = self.queue.top()
		except IndexError:
			if not self.errorReported:
				print('Warning: AutoCamera queue is empty')
				self.errorReported = True
			return

		# Keeping track of goals being added and removed it very
		# difficult, so we just consider the last action when deciding
		# whether or not to cut instantly.
		if not self.instantCut:
			# ... but if there's an object in the way, teleport to the nearest
			# safe position.
			ob, hitPoint, _ = self.camera.rayCast(currentGoal, self.camera, 0.0,
				'Ray', True, True, False)
			if ob != None:
				vectTo = hitPoint - currentGoal.worldPosition
				vectTo *= AutoCamera.COLLISION_BIAS
				self.camera.worldPosition = currentGoal.worldPosition + vectTo

		if self.instantCut:
			self.camera.worldPosition = currentGoal.worldPosition
			self.camera.worldOrientation = currentGoal.worldOrientation
			if hasattr(currentGoal, 'lens'):
				self.camera.lens = currentGoal.lens
			self.instantCut = False

		bxt.bmath.slow_copy_loc(self.camera, currentGoal, currentGoal['LocFac'])
		bxt.bmath.slow_copy_rot(self.camera, currentGoal, currentGoal['RotFac'])

		targetLens = self.defaultLens
		if hasattr(currentGoal, 'lens'):
			targetLens = currentGoal.lens
		self.camera.lens = bxt.bmath.lerp(self.camera.lens, targetLens,
				currentGoal['RotFac'])

		self.lastGoal = currentGoal

		self._update_focal_depth()

		evt = bxt.types.WeakEvent('CameraMoved', self)
		bxt.types.EventBus().notify(evt)

	def _update_focal_depth(self):
		focalPoint = None
		try:
			focalPoint = self.focusQueue.top()
		except IndexError:
			focalPoint = director.Director().mainCharacter
			if focalPoint == None:
				return

		cam = bge.logic.getCurrentScene().active_camera

		# Convert to depth; assume very large zFar
		# http://www.sjbaker.org/steve/omniv/love_your_z_buffer.html
		vecTo = focalPoint.worldPosition - cam.worldPosition
		z = vecTo.project(cam.getAxisVect((0.0, 0.0, 1.0))).magnitude
		z = max(z, AutoCamera.MIN_FOCAL_DIST)
		depth = 1.0 - cam.near / z
		cam['focalDepth'] = bxt.bmath.lerp(cam['focalDepth'], depth,
				AutoCamera.FOCAL_FAC)

		cam['blurRadius'] = cam['baseBlurRadius'] * (cam.lens / self.defaultLens)

	@bxt.types.expose
	@bxt.utils.owner_cls
	def add_goal(self, goal):
		'''Give the camera a new goal, and remember the last one. Call
		RemoveGoal to restore the previous relationship. The camera position
		isn't changed until update is called.
		'''
		# Set some defaults for properties.
		bxt.utils.set_default_prop(goal, 'LocFac', 0.1)
		bxt.utils.set_default_prop(goal, 'RotFac', 0.1)
		bxt.utils.set_default_prop(goal, 'InstantCut', False)
		bxt.utils.set_default_prop(goal, 'Priority', 1)

		# Add the goal to the queue.
		self.queue.push(goal, goal['Priority'])

		if self.queue.top() == goal and goal['InstantCut']:
			# Goal is on top of the stack: it will be switched to next
			self.instantCut = True
			self.update()

		self.errorReported = False

	@bxt.types.expose
	@bxt.utils.owner_cls
	def remove_goal(self, goal):
		'''Remove a goal from the stack. If it was currently in use, the camera
		will switch to follow the next one on the stack. The transform isn't
		changed until update is called.
		'''
		if not goal in self.queue:
			return

		if self.queue.top() == goal and goal['InstantCut']:
			# Goal is on top of the stack: it's in use!
			self.instantCut = True
			self.update()

		self.queue.discard(goal)

	@bxt.types.expose
	@bxt.utils.owner_cls
	def add_focus_point(self, target):
		bxt.utils.set_default_prop(target, 'FocusPriority', 1)
		self.focusQueue.push(target, target['FocusPriority'])

	@bxt.types.expose
	@bxt.utils.owner_cls
	def remove_focus_point(self, target):
		self.focusQueue.discard(target)

class MainCharSwitcher(bxt.types.BX_GameObject, bge.types.KX_Camera):
	'''Adds self as a goal when an attached sensor is touched by the main
	character.'''
	_prefix = 'MCS_'

	def __init__(self, old_owner):
		self.attached = False

	@bxt.types.expose
	@bxt.utils.controller_cls
	def on_touched(self, c):
		mainChar = director.Director().mainCharacter
		shouldAttach = False
		for s in c.sensors:
			if mainChar in s.hitObjectList:
				shouldAttach = True
				break

		if shouldAttach and not self.attached:
			AutoCamera().add_goal(self)
		elif not shouldAttach and self.attached:
			AutoCamera().remove_goal(self)
		self.attached = shouldAttach

class MainGoalManager(metaclass=bxt.types.Singleton):
	'''Creates cameras that follow the player in response to SetCameraType
	messages. The body of the message should be the name of the camera to
	create (i.e. the name of the objects that embodies that camera).'''

	currentCamera = bxt.types.weakprop('currentCamera')

	def __init__(self):
		self.cameraType = None
		bxt.types.EventBus().add_listener(self)
		bxt.types.EventBus().replay_last(self, 'SetCameraType')

	def on_event(self, evt):
		if evt.message == 'SetCameraType':
			if (self.currentCamera == None or
					self.cameraType != evt.body):
				scene = bge.logic.getCurrentScene()
				oldCamera = self.currentCamera
				self.currentCamera = bxt.types.add_and_mutate_object(scene,
						evt.body)

				ac = AutoCamera().camera
				if ac != None:
					bxt.types.Event('RelocatePlayerCamera',
							(ac.worldPosition, ac.worldOrientation)).send()
				self.cameraType = evt.body
				if oldCamera != None:
					oldCamera.endObject()

class OrbitCameraAlignment:
	'''
	Defines how the camera aligns with its target; use with OrbitCamera.

	This class gives the classic 3rd-person adventure camera. It looks towards
	the character, but does not always sit behind. Imagine a circle in the
	air above the character: on each frame, the camera moves the shortest
	distance possible to remain on that circle, unless it is blocked by a wall.
	'''

	def get_home_axes(self, camera, target):
		'''
		Get an alignment that represents the 'natural' view of the target, e.g.
		behind the shoulder.

		@return: forwardVector, upVector
		'''
		upDir = target.getAxisVect(bxt.bmath.ZAXIS)
		self.upDir = upDir.copy()
		fwdDir = target.getAxisVect(bxt.bmath.YAXIS)
		fwdDir.negate()
		return fwdDir, upDir

	def get_axes(self, camera, target):
		'''
		Get an alignment that is a progression from the previous alignment.

		@return: forwardVector, upVector
		'''
		rawUpDir = target.getAxisVect(bxt.bmath.ZAXIS)
		try:
			rawUpDir = bxt.bmath.lerp(self.upDir, rawUpDir,
					OrbitCamera.ZALIGN_FAC)
			rawUpDir.normalize()
		except AttributeError:
			pass
		self.upDir = rawUpDir.copy()

		vectTo = camera.worldPosition - target.worldPosition
		upDir = vectTo.project(rawUpDir)
		fwdDir = vectTo - upDir
		fwdDir.normalize()

		return fwdDir, rawUpDir

class OrbitCamera(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	'''A 3rd-person camera that stays a constant distance from its target.'''

	_prefix = 'Orb_'

	UP_DIST = 8.0
	BACK_DIST = 25.0
	DIST_BIAS = 0.5
	EXPAND_FAC = 0.005
	ZALIGN_FAC = 0.025

	def __init__(self, old_owner):
		self.reset = False

		# These must be members. This information can't be computed from the
		# current state of the frame: they would become smaller when going over
		# a convex surface.
		self.distUp = None
		self.distBack = None

		self.alignment = None

		AutoCamera().add_goal(self)
		bxt.types.EventBus().add_listener(self)
		bxt.types.EventBus().replay_last(self, 'RelocatePlayerCamera')
		bxt.types.EventBus().replay_last(self, 'SetCameraAlignment')

	@bxt.types.expose
	def update(self):
		if self.alignment is None:
			return

		# Project up.
		mainChar = director.Director().mainCharacter
		if mainChar == None:
			return
		target = mainChar.get_camera_tracking_point()

		if self.reset:
			fwdDir, upDir = self.alignment.get_home_axes(self, target)
			self.reset = False
		else:
			fwdDir, upDir = self.alignment.get_axes(self, target)

		if self.distUp is None:
			# The first time this is run (after creation), distUp and distBack
			# are not known - so calculate them. On subsequent frames, the
			# cached values will be used.
			relPos = self.worldPosition - target.worldPosition
			relUpPos = relPos.project(upDir)
			relFwdPos = relPos - relUpPos
			self.distUp = relUpPos.magnitude
			self.distBack = relFwdPos.magnitude

		# Look for the ceiling above the target.
		upPos, self.distUp = self.cast_ray(target.worldPosition, upDir,
				self.distUp, OrbitCamera.UP_DIST)

		# Search backwards for a wall.
		backDir = fwdDir.copy()
		backPos, self.distBack = self.cast_ray(upPos, backDir, self.distBack,
				OrbitCamera.BACK_DIST)
		self.worldPosition = backPos
		self.worldLinearVelocity = (0, 0, 0.0001)

		# Orient the camera towards the target.
		self.alignAxisToVect(upDir, 1)
		self.alignAxisToVect(fwdDir, 2)

	def cast_ray(self, origin, direction, lastDist, maxDist):
		through = origin + direction

		hitOb, hitPoint, hitNorm = self.rayCast(
			through,		# obTo
			origin,			# obFrom
			maxDist,        # dist
			'Ray',			# prop
			1,				# face normal
			1				# x-ray
		)

		targetDist = maxDist
		if hitOb and (hitNorm.dot(direction) < 0):
			#
			# If dot > 0, the tracking object is inside another mesh.
			# It's not perfect, but better not bring the camera forward
			# in that case, or the camera will be inside too.
			#
			targetDist = (hitPoint - origin).magnitude

		targetDist = targetDist * OrbitCamera.DIST_BIAS

		if targetDist < lastDist:
			dist = targetDist
		else:
			dist = bxt.bmath.lerp(lastDist, targetDist,
					OrbitCamera.EXPAND_FAC)

		pos = origin + (direction * dist)
		return pos, dist

	def on_event(self, evt):
		if evt.message == 'ResetCameraPos':
			self.reset = True
		elif evt.message == 'RelocatePlayerCamera':
			pos, orn = evt.body
			self.worldPosition = pos
			if orn != None:
				self.worldOrientation = orn
		elif evt.message == 'SetCameraAlignment':
			self.alignment = evt.body

class PathCamera(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	'''A camera goal that follows the active player. It tries to follow the same
	path as the player, so that it avoids static scenery.
	'''

	_prefix = 'PC_'

	# The maximum number of nodes to track. Once this number is reached, the
	# oldest nodes will be removed.
	MAX_NODES = 50
	# The minimum distance to leave between nodes. 
	MIN_DIST = 2

	ACCELERATION = 0.05
	DAMPING = 0.2

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
	ZOFFSET = 5.0
	CEILING_AVOIDANCE_BIAS = 0.5
	# The maximum height difference between two consecutive targets. This
	# smoothes off the path as the actor goes under a ceiling.
	ZOFFSET_INCREMENT = MIN_DIST * 0.5

	# The number of consecutive nodes that must be seen before being accepted.
	# If this is too low, the camera will clip through sharp corners. 
	NODE_DELAY = 2
	# The number of frames to wait before deciding that the predictive node is
	# obscured.
	EXPAND_ON_WAIT = 10
	EXPAND_OFF_WAIT = 5
	# Responsiveness of the radius adjustment.
	RADIUS_SPEED = 0.1
	# Responsiveness of the camera orientation.
	ALIGN_Y_SPEED = 0.15
	ALIGN_Z_SPEED = 0.5
	# Distance to project predictive node.
	PREDICT_FWD = 20.0
	PREDICT_UP = 50.0

	class CameraNode:
		'''A single point in a path used by the CameraPathGoal. These act as
		way points for the camera to follow.'''

		# Note: This class uses strong references, so it will hang around even
		# when the associated game object dies. But that's OK, because the only
		# class that uses this one is PathCamera, which should end with its
		# object, thus releasing this one.

		def __init__(self):
			# Defines the location of the way point. Using a way point allows the
			# node to parented to an object.
			self.owner = bxt.utils.add_object('PointMarker')
			if not DEBUG:
				self.owner.visible = False
			else:
				self.marker = bxt.utils.add_object("PointMarker")
				self.marker.color = bxt.render.BLUE
				self.marker.visible = True
				self.owner.visible = True

			# It is an error to access these next two before calling update().
			self.ceilingHeight = None
			self.target = None

		def update(self):
			self.target = bxt.bmath.ZAXIS.copy()
			self.target *= PathCamera.ZOFFSET
			self.target = bxt.bmath.to_world(self.owner, self.target)
			hitOb, hitPoint, _ = bxt.bmath.ray_cast_p2p(
					self.target, # objto
					self.owner.worldPosition, # objfrom
					prop = 'Ray')

			if hitOb:
				vec = hitPoint - self.owner.worldPosition
				self.setCeilingHeight(vec.magnitude)
			else:
				self.setCeilingHeight(PathCamera.ZOFFSET)

		def get_target(self):
			bias = self.ceilingHeight / PathCamera.ZOFFSET
			bias *= PathCamera.CEILING_AVOIDANCE_BIAS
			return bxt.bmath.lerp(self.owner.worldPosition, self.target, bias)

		def destroy(self):
			self.owner.endObject()
			if DEBUG: self.marker.endObject()

		def setCeilingHeight(self, height):
			self.ceilingHeight = height
			if DEBUG: self.marker.worldPosition = self.get_target()

	target = bxt.types.weakprop('target')

	def __init__(self, old_owner):
		# A list of CameraNodes.
		self.path = []
		self.pathHead = PathCamera.CameraNode()
		self.linV = bxt.bmath.ZEROVEC.copy()

		self.radMult = 1.0
		self.expand = bxt.types.FuzzySwitch(PathCamera.EXPAND_ON_WAIT,
										PathCamera.EXPAND_OFF_WAIT, True)
		self.target = None

		AutoCamera().add_goal(self)
		bxt.types.EventBus().add_listener(self)
		bxt.types.EventBus().replay_last(self, 'MainCharacterSet')
		bxt.types.EventBus().replay_last(self, 'RelocatePlayerCamera')

		if DEBUG:
			self.targetVis = bxt.utils.add_object('DebugReticule')
			self.predictVis = bxt.utils.add_object('DebugReticule')

	def on_event(self, event):
		if event.message == 'MainCharacterSet':
			self.target = event.body
		elif event.message == 'RelocatePlayerCamera':
			pos, orn = event.body
			self.worldPosition = pos
			if orn != None:
				self.worldOrientation = orn

	@bxt.types.expose
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
		actor = self.target
		if actor == None:
			return

		# Get the vector from the camera to the next way point.
		node, pathLength = self._getNextWayPoint()
		target = node.get_target()
		dirWay = target - self.worldPosition
		dirWay.normalize()

		# Adjust preferred distance from actor based on current conditions.
		contract = False
		if node.ceilingHeight < PathCamera.ZOFFSET:
			# Bring the camera closer when under a low ceiling or in a tunnel.
			contract = True

		if self._canSeeFuture():
			# Otherwise, relax the camera if the predicted point is visible.
			self.expand.turn_on()
		else:
			self.expand.turn_off()

		radMult = 1.0
		if contract:
			radMult = 1.0 + (node.ceilingHeight / PathCamera.ZOFFSET)
		elif self.expand.is_on():
			radMult = PathCamera.EXPAND_FACTOR
		else:
			radMult = PathCamera.REST_FACTOR
		self.radMult = bxt.bmath.lerp(self.radMult, radMult,
									PathCamera.RADIUS_SPEED)
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
		# its Z-axis with the direction to the target. The alignment with Y is
		# modulated by how horizontal the camera is right now - this prevents
		# the camera from spinning too rapidly when pointing up.
		look = dirWay.copy()
		look.negate()
		yfac = 1 - abs(self.getAxisVect(bxt.bmath.ZAXIS).dot(bxt.bmath.ZAXIS))
		yfac = (yfac * 0.5) + 0.5
		yfac *= PathCamera.ALIGN_Y_SPEED

		if actor.localCoordinates:
			axis = node.owner.getAxisVect(bxt.bmath.ZAXIS)
			self.alignAxisToVect(axis, 1, yfac)
		else:
			self.alignAxisToVect(bxt.bmath.ZAXIS, 1, yfac)
		self.alignAxisToVect(look, 2, PathCamera.ALIGN_Z_SPEED)

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
		projectedPoint = a.owner.worldPosition + (ba * PathCamera.PREDICT_FWD)

		hitOb, hitPoint, _ = bxt.bmath.ray_cast_p2p(
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
			pp2 = projectedPoint - (upAxis * PathCamera.PREDICT_FWD)

			hitOb, hitPoint, _ = bxt.bmath.ray_cast_p2p(
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
		target = node.get_target()
		if (hasLineOfSight(self, node.owner) and
			hasLineOfSight(self, target)):
			return node, 0.0

		# Actor is obscured; find a good way point.
		nSearched = 0
		for currentNode in self.path:
			nSearched += 1

			currentTarget = currentNode.get_target()

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
		actor = self.target
		if actor == None:
			return

		if actor.localCoordinates:
			bxt.bmath.copy_transform(actor, self.pathHead.owner)
		else:
			self.pathHead.owner.worldPosition = actor.worldPosition
			bxt.bmath.reset_orientation(self.pathHead.owner)

		# Add a new node if the actor has moved far enough.
		addNew = False
		if len(self.path) == 0:
			addNew = True
		else:
			currentPos = actor.worldPosition
			vec = currentPos - self.path[0].owner.worldPosition
			if vec.magnitude > self.MIN_DIST:
				addNew = True

		if addNew:
			node = PathCamera.CameraNode()

			if actor.localCoordinates:
				bxt.bmath.copy_transform(actor, node.owner)
			else:
				node.owner.worldPosition = actor.worldPosition
			node.owner.worldPosition = actor.worldPosition
			self.path.insert(0, node)
			if actor.touchedObject != None:
				node.owner.setParent(actor.touchedObject, False)
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

		def marginMin(current, nxt, margin):
			return min(current + margin, nxt)

		currentOffset = self.pathHead.ceilingHeight
		for node in pingPong(self.path):
			node.setCeilingHeight(marginMin(currentOffset, node.ceilingHeight,
								self.ZOFFSET_INCREMENT))
			currentOffset = node.ceilingHeight
		self.pathHead.setCeilingHeight(marginMin(currentOffset,
										self.pathHead.ceilingHeight,
										self.ZOFFSET_INCREMENT))
	def endObject(self):
		for node in self.path:
			node.destroy()
		if DEBUG:
			self.targetVis.endObject()
			self.predictVis.endObject()
		self.pathHead.destroy()
		bge.types.KX_GameObject.endObject(self)

#
# Helper for sensing when camera is inside something.
#

class CameraCollider(CameraObserver, bxt.types.BX_GameObject, bge.types.KX_GameObject):
	'''Senses when the camera is inside something. This senses when the
	camera touches a volumetric object, and then tracks to see when the camera
	enters and leaves that object, adjusting the screen filter appropriately.'''

	MAX_DIST = 1000.0

	def __init__(self, old_owner):
		bxt.types.EventBus().add_listener(self)

	def on_event(self, evt):
		if evt.message == 'CameraMoved':
			self.on_camera_moved(evt.body)

	def on_camera_moved(self, autoCamera):
		self.worldPosition = autoCamera.camera.worldPosition
		pos = autoCamera.camera.worldPosition.copy()

		direction = bxt.bmath.ZAXIS.copy()
		ob = self.cast_for_water(pos, direction)
		if ob != None:
			# Double check - works around bug with rays that strike a glancing
			# blow on an edge.
			direction.x = direction.y = 0.1
			direction.normalize()
			ob = self.cast_for_water(pos, direction)

		if ob != None:
			evt = bxt.types.Event('ShowFilter', ob['VolumeCol'])
			bxt.types.EventBus().notify(evt)
		else:
			evt = bxt.types.Event('ShowFilter', None)
			bxt.types.EventBus().notify(evt)

	def cast_for_water(self, pos, direction):
		through = pos + direction * CameraCollider.MAX_DIST
		ob, _, normal = bxt.bmath.ray_cast_p2p(through, pos, prop='VolumeCol')
		if ob != None and normal.dot(direction) > 0.0:
			return ob
		else:
			return None

#
# camera for viewing the background scene
#

class BackgroundCamera(CameraObserver, bxt.types.BX_GameObject, bge.types.KX_Camera):
	'''Links a second camera to the main 3D camera. This second, background
	camera will always match the orientation and zoom of the main camera. It is
	guaranteed to update after the main one.'''

	def __init__(self, old_owner):
		bxt.types.EventBus().add_listener(self)

	def on_event(self, evt):
		if evt.message == 'CameraMoved':
			self.on_camera_moved(evt.body)

	def on_camera_moved(self, autoCamera):
		self.worldOrientation = autoCamera.camera.worldOrientation
		self.lens = autoCamera.camera.lens
