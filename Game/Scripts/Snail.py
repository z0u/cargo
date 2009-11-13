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

'''
Create the structure required to control a snail. Python objects
will be created to match the types of Blender objects in the
hierarchy, with the owner as the root.

Call this script once. The rest of the processing should be done
by fetching the resulting object from the GameLogic.Snails
dictionary.
'''

from Blender import Mathutils
import Utilities
import Actor
import GameLogic

MAX_SPEED = 3.0
MIN_SPEED = -3.0

#
# States for main snail object. The commented-out ones aren't currently used
# in the code, and are only set by logic bricks.
#
#S_INIT     = 1
S_CRAWLING = 2
S_FALLING  = 3
#S_ACTIVE   = 4
S_NOSHELL  = 16
S_HASSHELL = 17
S_POPPING  = 18
S_INSHELL  = 19
S_EXITING  = 20
#S_REINCARNATE = 29
#S_DROWNING    = 30


ZAXIS  = Mathutils.Vector([0.0, 0.0, 1.0])
ORIGIN = Mathutils.Vector([0.0, 0.0, 0.0])

#
# Abstract classes
#
class ISnailRay:
	def getHitPosition(self):
		return ORIGIN

#
# Concrete classes
#
	
class SnailSegment(Utilities.SemanticGameObject):
	def __init__(self, owner, parent):
		self.Parent  = parent # SnailSegment or None
		self.Child   = None   # SnailSegment or None
		self.Fulcrum = None   # KX_GameObject
		self.Rays    = {}     # Dictionary of SnailRays
		Utilities.SemanticGameObject.__init__(self, owner)

	def parseChild(self, child, type):
		if (type == "SnailRay"):
			self.Rays[child.Position] = SnailRay(child)
			return True
		elif (type == "SnailRayCluster"):
			self.Rays[child.Position] = SnailRayCluster(child)
			return True
		elif (type == "SnailSegment"):
			if (self.Child):
				raise SemanticException, (
					"Segment %s already has a child." % self.Owner.name)
			self.Child = SnailSegment(child, self)
			return True
		elif (type == "SegmentChildPivot"):
			if (self.Child):
				raise SemanticException, (
					"Segment %s already has a child." % self.Owner.name)
			self.Child = SegmentChildPivot(child)
			return True
		elif (type == "Fulcrum"):
			if (self.Fulcrum):
				raise SemanticException, (
					"Segment %s already has a fulcrum." % self.Owner.name)
			self.Fulcrum = child
			return True
		else:
			return False
		
	def getOrientation(self):
		ornMat = self.Owner.worldOrientation
		ornMat = Mathutils.Matrix(ornMat[0], ornMat[1], ornMat[2])
		ornMat.transpose()
		return ornMat

	def orient(self, parentOrnMat):
		if (self.Parent):
			right = self.Parent.Owner.getAxisVect([1.0, 0.0, 0.0])
			self.Owner.alignAxisToVect(right, 0)
		
		hit, p1 = self.Parent.Rays['Right'].getHitPosition()
		hit, p2 = self.Parent.Rays['Left'].getHitPosition()
		p3 = Mathutils.Vector(self.Parent.Fulcrum.worldPosition)
		normal = Mathutils.TriangleNormal(p1, p2, p3)
		
		parNorm = ZAXIS * parentOrnMat
		dot = Mathutils.DotVecs(normal, parNorm)
		if (dot > 0.0):
			#
			# Normal is within 90 degrees of parent's normal -> segment not
			# doubling back on itself.
			#
			# Interpolate between normals for current and previous frames.
			# Don't use a factor of 0.5: potential for normal to average out
			# to be (0,0,0)
			#
			orientation = Mathutils.Vector(self.Owner.getAxisVect(ZAXIS))
			orientation = Utilities._lerp(normal, orientation, 0.4)
			self.Owner.alignAxisToVect(orientation, 2)
		
		#
		# Make orientation available to armature. Use the inverse of the
		# parent's orientation to find the local orientation.
		#
		ornMat = self.getOrientation()
		parentOrnMat.invert()
		localOrnMat = ornMat * parentOrnMat
		euler = localOrnMat.toEuler()
		self.Owner['Heading'] = euler.x
		self.Owner['Pitch'] = euler.y
		self.Owner['Roll'] = euler.z
		
		if (self.Child):
			self.Child.orient(ornMat)
	
	def setBendAngle(self, angle):
		if self.Child:
			self.Child.setBendAngle(angle)

class AppendageRoot(SnailSegment):
	def __init__(self, owner):
		SnailSegment.__init__(self, owner, None)
		
	def orient(self):
		self.Child.orient(self.getOrientation())

class SegmentChildPivot(SnailSegment):
	def __init__(self, owner):
		SnailSegment.__init__(self, owner, None)
		
	def orient(self, parentOrnMat):
		self.Child.orient(parentOrnMat)
	
	def setBendAngle(self, angle):
		self.Owner['BendAngle'] = angle
		self.Child.setBendAngle(angle)

class Snail(SnailSegment, Actor.StatefulActor):
	def __init__(self, owner, cargoHold, eyeLocL, eyeLocR):
		Actor.StatefulActor.__init__(self, owner)
		Actor.Director.SetMainSubject(self)
		
		self.Head = None
		self.Tail = None
		self.CargoHold = cargoHold
		self.EyeLocL = eyeLocL
		self.EyeLocR = eyeLocR
		self.Shell = None
		self.Shockwave = None
		self.Trail = None
		self.Armature = None
		SnailSegment.__init__(self, owner, None)
		if not self.Head:
			raise Exception("No head defined.")
		if not self.Tail:
			raise Exception("No tail defined.")
		if not self.CargoHold:
			raise Exception("No CargoHold defined.")
		if not self.Shockwave:
			raise Exception("No Shockwave defined.")
	
	def parseChild(self, child, type):
		if type == "AppendageRoot":
			if child['Location'] == 'Fore':
				self.Head = AppendageRoot(child)
			elif child['Location'] == 'Aft':
				self.Tail = AppendageRoot(child)
			else:
				raise SemanticException, ("Unknown appendage type %s on %s." %
			                    (child['Location'], child.name))
			return True
		elif type == "Shockwave":
			self.Shockwave = child
			#
			# Remove this from the hierarchy: the shockwave only needs to be
			# positioned when it fires; other than that, it doesn't matter where
			# it is. Removing it from the hierarchy prevents it from being
			# implicitely and incorrectly made visible.
			#
			child.removeParent()
			return True
		elif type == "SnailTrail":
			self.Trail = SnailTrail(child, self)
			return True
		elif type == 'Armature':
			self.Armature = child
			return True
		else:
			return SnailSegment.parseChild(self, child, type)
	
	def orient(self):
		hitPs = []
		hitNs = []
		nHit = 0
		hit, p0 = self.Rays['0'].getHitPosition()
		if (hit):
			nHit = nHit + 1
		hit, p1 = self.Rays['1'].getHitPosition()
		if (hit):
			nHit = nHit + 1
		hit, p2 = self.Rays['2'].getHitPosition()
		if (hit):
			nHit = nHit + 1
		hit, p3 = self.Rays['3'].getHitPosition()
		if (hit):
			nHit = nHit + 1
		
		#
		# Set property on object so it knows whether it's falling.
		#
		if (self.Owner['nHit'] != nHit):
			self.Owner['nHit'] = nHit
		
		#
		# Derive normal from hit points and update orientation.
		#
		normal = Mathutils.QuadNormal(p0, p1, p2, p3)
		oldNormal = Mathutils.Vector(self.Owner.getAxisVect([0,0,1]))
		
		#
		# Don't use a factor of 0.5: potential for normal to average out to be (0,0,0)
		#
		orientation = Utilities._lerp(normal, oldNormal, 0.4)
		
		self.Owner.alignAxisToVect(orientation, 2)
		
		self.Head.orient()
		self.Tail.orient()
	
	def lookAt(self, targetList):
		'''Turn the eyes to face the nearest object in targetList.'''
		def getAngZ(vec):
			vec.normalize()
			angZIndex = 0.0
			if vec.y >= 0:
				angZIndex = vec.x * 100.0
			else:
				if vec.x >= 0:
					angZIndex = ((1.0 - vec.x) * 100.0) + 100.0
				else:
					angZIndex = ((-1.0 - vec.x) * 100.0) - 100.0
			return angZIndex
		
		if len(targetList) < 1:
			self.Armature['Eye_X_L'] = 0
			self.Armature['Eye_X_R'] = 0
			self.Armature['Eye_Z_L'] = 0
			self.Armature['Eye_Z_R'] = 0
			return
		
		nearest = targetList[0]
		minDist = self.Owner.getDistanceTo(nearest)
		for target in targetList[1:]:
			dist = self.Owner.getDistanceTo(target)
			if dist < minDist:
				nearest = target
				minDist = dist
		
		#
		# Normally we would need to find cos(x) to get the angle on the Z-axis.
		# But here, x drives an IPO curve with the cosine wave baked into it.
		#
		p = Utilities._toLocal(self.EyeLocL,
			Mathutils.Vector(nearest.worldPosition))
		p.normalize()
		angZIndex = Utilities._clamp(-150.0, 150.0, getAngZ(p))
		self.Armature['Eye_Z_L'] = Utilities._lerp(self.Armature['Eye_Z_L'],
			angZIndex, self.Owner['EyeRotFac'])
		self.Armature['Eye_X_L'] = p.z * 100.0
		
		p = Utilities._toLocal(self.EyeLocR,
			Mathutils.Vector(nearest.worldPosition))
		p.normalize()
		angZIndex = Utilities._clamp(-150.0, 150.0, getAngZ(p))
		self.Armature['Eye_Z_R'] = Utilities._lerp(self.Armature['Eye_Z_R'],
			angZIndex, self.Owner['EyeRotFac'])
		self.Armature['Eye_X_R'] = p.z * 100.0
	
	def _stowShell(self, shell):
		referential = shell
		for child in shell.children:
			if child.has_key('Type') and (child.Type == 'CargoHook'):
				referential = child
		
		Utilities.setRelOrn(shell, self.CargoHold, referential)
		Utilities.setRelPos(shell, self.CargoHold, referential)
		shell.setParent(self.CargoHold)
	
	def setShell(self, shell, animate):
		'''
		Add the shell as a descendant of the snail. It will be
		made a child of the CargoHold. If the shell has a child
		of type "CargoHook", that will be used as the
		referential (offset). Otherwise, the shell will be
		positioned with its own origin at the same location as
		the CargoHold.
		
		Adding the shell as a child prevents collision with the
		parent. The shell's inactive state will also be set.
		'''
		Utilities.remState(self.Owner, S_NOSHELL)
		Utilities.addState(self.Owner, S_HASSHELL)
		
		self._stowShell(shell.Owner)
		
		self.Shell = shell
		self.Owner['HasShell'] = 1
		self.Owner['DynamicMass'] = self.Owner['DynamicMass'] + self.Shell.Owner['DynamicMass']
		self.Shell.OnPickedUp(self, animate)
		if animate:
			self.Shockwave.worldPosition = self.Shell.Owner.worldPosition
			self.Shockwave.worldOrientation = self.Shell.Owner.worldOrientation
			Utilities.setState(self.Shockwave, 2)
	
	def removeShell(self):
		'''Unhooks the current shell by un-setting its parent.'''
		
		Utilities.remState(self.Owner, S_POPPING)
		Utilities.remState(self.Owner, S_HASSHELL)
		Utilities.addState(self.Owner, S_NOSHELL)
		
		self.Shell.Owner.removeParent()
		velocity = self.Owner.getAxisVect(ZAXIS)
		velocity = Mathutils.Vector(velocity)
		velocity = velocity * self.Owner['ShellPopForce']
		self.Shell.Owner.applyImpulse(self.Shell.Owner.worldPosition, velocity)
		self.Owner['HasShell'] = 0
		self.Owner['DynamicMass'] = self.Owner['DynamicMass'] - self.Shell.Owner['DynamicMass']
		self.Shell.OnDropped()
		self.Shell = None
	
	def onPreEnterShell(self):
		'''Called when the snail starts getting into the shell
		(several frames before control is transferred).'''
		self.Shell.OnPreEnter()
	
	def onEnterShell(self):
		'''Transfers control of the character to the shell.
		The snail must have a shell.'''
		Utilities.remState(self.Owner, S_CRAWLING)
		
		self.Shell.Owner.removeParent()
		self.Owner.setVisible(0, 1)
		self.Owner.setParent(self.Shell.Owner)
	
		#
		# Swap mass with shell so the shell can influence bendy leaves properly
		#
		dm = self.Shell.Owner['DynamicMass']
		self.Shell.Owner['DynamicMass'] = self.Owner['DynamicMass']
		self.Owner['DynamicMass'] = dm
		
		self.Owner['InShell'] = 1
		self.Shell.OnEntered()
		Actor.Director.SetMainSubject(self.Shell)
	
	def exitShell(self):
		'''
		Tries to make the snail exit the shell. If possible, control will be
		transferred to the snail. The snail must currently be in a shell.
		'''
		if not Utilities.hasState(self.Owner, S_INSHELL):
			return
		
		Utilities.remState(self.Owner, S_INSHELL)
		Utilities.addState(self.Owner, S_EXITING)
		Utilities.addState(self.Owner, S_FALLING)
		
		linV = self.Shell.Owner.getLinearVelocity()
		angV = self.Shell.Owner.getAngularVelocity()
		self.Owner.removeParent()
		self.Owner.setVisible(1, 1)
		self._stowShell(self.Shell.Owner)
		self.Owner.setLinearVelocity(linV)
		self.Owner.setAngularVelocity(angV)
	
		#
		# Swap mass with shell so the body can influence bendy leaves properly
		#
		dm = self.Shell.Owner['DynamicMass']
		self.Shell.Owner['DynamicMass'] = self.Owner['DynamicMass']
		self.Owner['DynamicMass'] = dm
		
		self.Owner['InShell'] = 0
		self.Shell.OnExited()
		Actor.Director.SetMainSubject(self)
	
	def onPostExitShell(self):
		'''Called when the snail has finished its exit shell
		animation (several frames after control has been
		transferred).'''
		Utilities.remState(self.Owner, S_EXITING)
		Utilities.addState(self.Owner, S_HASSHELL)
		self.Shell.OnPostExit()
	
	def onStartCrawling(self):
		'''Called when the snail enters its crawling state.'''
		#
		# Don't set it quite to zero: zero vectors are ignored!
		#
		self.Owner.setAngularVelocity([0.0, 0.0, 0.0001], 0)
		self.Owner.setLinearVelocity([0.0, 0.0, 0.0001], 0)
	
	def setSpeedMultiplier(self, mult):
		self.Owner['SpeedMultiplier'] = max(min(mult, MAX_SPEED), MIN_SPEED)

	def decaySpeed(self):
		'''Bring the speed of the snail one step closer to normal speed.'''
		o = self.Owner
		dr = o['SpeedDecayRate']
		mult = o['SpeedMultiplier']
		
		if mult == 1.0:
			return
		elif mult > 1.0:
			o['SpeedMultiplier'] = max(mult - dr, 1.0)
		else:
			o['SpeedMultiplier'] = min(mult + dr, 1.0)
	
	def crawling(self):
		return Utilities.hasState(self.Owner, S_CRAWLING)
	
	def Drown(self):
		if not Utilities.hasState(self.Owner, S_INSHELL):
			return Actor.Actor.Drown(self)
		else:
			return False
	
	def onMovementImpulse(self, fwd, back, left, right):
		'''
		Make the snail move. If moving forward or backward, this implicitely
		calls decaySpeed.
		'''
		if not self.crawling():
			return
		
		o = self.Owner
		
		#
		# Decide which direction to move in on the Y-axis.
		#
		fwdSign = 0
		if fwd:
			fwdSign = fwdSign + 1
		if back:
			fwdSign = fwdSign - 1
		
		#
		# Apply forward/backward motion.
		#
		speed = o['NormalSpeed'] * o['SpeedMultiplier'] * float(fwdSign)
		o.applyMovement((0.0, speed, 0.0), True)
		self.decaySpeed()
		
		#
		# Decide which way to turn.
		#
		targetBendAngleFore = 0.0
		targetRot = 0.0
		targetBendAngleAft = None
		if left:
			#
			# Bend left.
			#
			targetBendAngleFore = targetBendAngleFore - o['MaxBendAngle']
			targetRot = targetRot + o['MaxRot']
		if right:
			#
			# Bend right. If bending left too, the net result will be
			# zero.
			#
			targetBendAngleFore = targetBendAngleFore + o['MaxBendAngle']
			targetRot = targetRot - o['MaxRot']
		
		locomotionStep = self.Owner['SpeedMultiplier'] * 0.4
		if fwdSign > 0:
			#
			# Moving forward.
			#
			targetBendAngleAft = targetBendAngleFore
			self.Armature['LocomotionFrame'] = (
				self.Armature['LocomotionFrame'] + locomotionStep)
		elif fwdSign < 0:
			#
			# Reversing: invert rotation direction.
			#
			targetBendAngleAft = targetBendAngleFore
			targetRot = 0.0 - targetRot
			self.Armature['LocomotionFrame'] = (
				self.Armature['LocomotionFrame'] - locomotionStep)
		else:
			#
			# Stationary. Only bend the head.
			#
			targetBendAngleAft = 0.0
			targetRot = 0.0
		
		self.Armature['LocomotionFrame'] = (
			self.Armature['LocomotionFrame'] % 19)
		
		#
		# Rotate the snail.
		#
		o['Rot'] = Utilities._lerp(o['Rot'], targetRot, o['RotFactor'])
		o.applyRotation((0.0, 0.0, o['Rot']), True)
		
		#
		# Match the bend angle with the current speed.
		#
		targetBendAngleAft = targetBendAngleAft / o['SpeedMultiplier']
		
		o['BendAngleFore'] = Utilities._lerp(o['BendAngleFore'],
		                                     targetBendAngleFore,
		                                     o['BendFactor'])
		if fwdSign != 0:
			o['BendAngleAft'] = Utilities._lerp(o['BendAngleAft'],
		                                        targetBendAngleAft,
		                                        o['BendFactor'])
		
		#
		# Bend the snail. This will be applied by other logic bricks, so it may
		# happen one frame later.
		#
		self.Head.setBendAngle(o['BendAngleFore'])
		self.Tail.setBendAngle(o['BendAngleAft'])
		
		self.Trail.onSnailMoved()

class SnailRayCluster(ISnailRay, Utilities.SemanticGameObject):
	'''A collection of SnailRays. These will cast a ray once per frame in the
	order defined by their Priority property (ascending order). The first one
	that hits is used.'''
	Rays = None
	LastHitPoint = None
	Marker = None
	
	def __init__(self, owner):
		self.Rays = []
		self.Marker = None
		Utilities.SemanticGameObject.__init__(self, owner)
		if (len(self.Rays) <= 0):
			raise Exception("Ray cluster %s has no ray children." % self.Owner.name)
		self.Rays.sort(lambda a, b: a.Owner.Priority - b.Owner.Priority)
		self.LastHitPoint = Mathutils.Vector([0,0,0])
	
	def parseChild(self, child, type):
		if (type == "SnailRay"):
			self.Rays.append(SnailRay(child))
			return True
		elif (type == "SnailRayCluster"):
			self.Rays.append(SnailRayCluster(child))
			return True
		elif (type == "Marker"):
			self.Marker = child
			child.removeParent()
			return True
		else:
			return False

	def getHitPosition(self):
		"""Return the hit point of the first child ray that hits.
		If none hit, the default value of the first ray is returned."""
		p = None
		n = None
		hit = False
		for ray in self.Rays:
			hit, p = ray.getHitPosition()
			if (hit == True):
				self.LastHitPoint = Utilities._toLocal(self.Owner, p)
				break
		
		if (self.Marker):
			self.Marker.setWorldPosition(Utilities._toWorld(self.Owner, self.LastHitPoint))
			
		return hit, Utilities._toWorld(self.Owner, self.LastHitPoint)

class SnailRay(ISnailRay, Utilities.SemanticGameObject):
	LastPoint = None

	def __init__(self, owner):
		self.Marker = None
		Utilities.SemanticGameObject.__init__(self, owner)
		self.LastPoint = Mathutils.Vector(self.Owner.worldPosition)
	
	def parseChild(self, child, type):
		if (type == "Marker"):
			self.Marker = child
			child.removeParent()
			return True

	def getHitPosition(self):
		origin = Mathutils.Vector(self.Owner.worldPosition)
		vec = Mathutils.Vector(self.Owner.getAxisVect(ZAXIS))
		through = origin + vec
		ob, hitPoint, normal = self.Owner.rayCast(
			through,            # to
			origin,             # from
			self.Owner.Length,  # dist
			'Ground',           # prop
			1,                  # face
			1                   # xray
		)
		
		hit = False
		if (ob):
			#
			# Ensure the hit was not from inside an object.
			#
			normal = Mathutils.Vector(normal)
			if (Mathutils.DotVecs(normal, vec) < 0.0):
				hit = True
				self.LastPoint = Mathutils.Vector(hitPoint)
		
		if (self.Marker):
			self.Marker.setWorldPosition(self.LastPoint)
		
		return hit, self.LastPoint

class SnailTrail(Utilities.SemanticGameObject):
	def __init__(self, owner, snail):
		self.LastTrailPos = Mathutils.Vector(owner.worldPosition)
		self.TrailSpots = []
		self.SpotIndex = 0
		self.Snail = snail
		Utilities.SemanticGameObject.__init__(self, owner)
	
	def parseChild(self, child, type):
		if (type == "TrailSpot"):
			self.TrailSpots.append(child)
			child.removeParent()
			return True
	
	def AddSpot(self):
		scene = GameLogic.getCurrentScene()
		spot = self.TrailSpots[self.SpotIndex]
		spotI = scene.addObject(spot, self.Owner)
		
		#
		# Find the nearest object below the spawn point.
		#
		origin = Mathutils.Vector(self.Owner.worldPosition)
		vec = Mathutils.Vector(self.Owner.getAxisVect(ZAXIS))
		through = origin - vec
		hitOb, _, _ = self.Owner.rayCast(
			through,            # to
			origin,             # from
			1.0,                # dist
			'Ground',           # prop
			0,                  # face
			1                   # xray
		)
		spotI.setParent(hitOb)
		
		spotI.state = 1<<1
		self.LastTrailPos = Mathutils.Vector(self.Owner.worldPosition)
		self.SpotIndex = (self.SpotIndex + 1) % len(self.TrailSpots)
	
	def onSnailMoved(self):
		if self.DistanceReached():
			self.AddSpot()
	
	def DistanceReached(self):
		pos = Mathutils.Vector(self.Owner.worldPosition)
		dist = (pos - self.LastTrailPos).magnitude
		return dist > self.Snail.Owner.TrailSpacing

#
# Module interface functions.
#

def Init(cont):
	cargoHold = cont.sensors['sCargoHoldHook'].owner
	eyeLocL = cont.sensors['sEyeLocHookL'].owner
	eyeLocR = cont.sensors['sEyeLocHookR'].owner
	snail = Snail(cont.owner, cargoHold, eyeLocL, eyeLocR)
	cont.owner['Snail'] = snail

def Orient(c):
	c.owner['Snail'].orient()

def Look(c):
	sLookAt = c.sensors['sLookAt']
	c.owner['Snail'].lookAt(sLookAt.hitObjectList)

def _OnShellTouched(c, animate):
	if not Utilities.allSensorsPositive(c):
		return
	
	o = c.owner
	
	if not o['HasShell']:
		ob = c.sensors['sShellPickup'].hitObject
		shell = ob['Actor']
		if (not shell.IsCarried()):
			o['Snail'].setShell(shell, animate)

def OnShellTouchedNoAnim(c):
	_OnShellTouched(c, False)

def OnShellTouched(c):
	_OnShellTouched(c, True)

def DropShell(c):
	c.owner['Snail'].removeShell()

def ExitShell(c):
	'''
	Transfers control of the character to the snail. To be run from a controller
	on the snail. The snail must be carrying a shell. To reverse this, run
	OnShellExit from a controller on the snail.
	'''
	if Utilities.allSensorsPositive(c):
		c.owner['Snail'].exitShell()

def OnShellPostExit(c):
	'''Called when the shell has been fully exited.'''
	if Utilities.allSensorsPositive(c):
		c.owner['Snail'].onPostExitShell()

def OnShellEnter(c):
	'''
	Transfers control of the snail to its shell. Allows for things like
	steering a rolling shell. This must be run from a controller on the
	snail. The snail must be carrying a shell. To reverse this, run
	OnShellExit from a controller on the snail.
	'''
	if Utilities.allSensorsPositive(c):
		c.owner['Snail'].onEnterShell()

def OnShellPreEnter(c):
	'''Called when the shell is starting to be entered.'''
	if Utilities.allSensorsPositive(c):
		c.owner['Snail'].onPreEnterShell()

def OnStartCrawling(c):
	c.owner['Snail'].onStartCrawling()

def OnTouchSpeedModifier(c):
	mult = 0.0
	hitObs = c.sensors[0].hitObjectList
	
	if len(hitObs) == 0:
		return
	
	for hitOb in hitObs:
		mult = mult + hitOb['SetSpeedMultiplier']
		if hitOb.has_key('SingleUse'):
			hitOb.endObject()
	
	mult = mult / float(len(hitObs))
	c.owner['Snail'].setSpeedMultiplier(mult)

#
# Independent functions.
#

def EyeLength(c):
	'''Sets the length of the eyes. To be called by the snail.'''
	def getRayLength(sensor):
		origin = Mathutils.Vector(sensor.owner.worldPosition)
		through = Mathutils.Vector(sensor.hitPosition)
		return (through - origin).magnitude
	
	def getEyeLength(currentProportion, maxLen, sensor, factorUp):
		targetLength = 0.0
		if (sensor.positive):
			targetLength = getRayLength(sensor) * 0.9
		else:
			targetLength = maxLen
		targetProportion = (targetLength / maxLen) * 100
		
		if (currentProportion >= targetProportion):
			return targetProportion * 0.5
		else:
			return Utilities._lerp(currentProportion, targetProportion, factorUp)
	
	o = c.owner
	sRayL = c.sensors['sEyeRay_L']
	sRayR = c.sensors['sEyeRay_R']
	aActionL = c.actuators['aEyeLen_L']
	aActionR = c.actuators['aEyeLen_R']
	
	o['EyeProp_L'] = getEyeLength(o['EyeProp_L'], o['EyeRestLen'], sRayL, o['EyeLenFac'])
	o['EyeProp_R'] = getEyeLength(o['EyeProp_R'], o['EyeRestLen'], sRayR, o['EyeLenFac'])
	
	c.activate(aActionL)
	c.activate(aActionR)

def CopyRotToArmature(c):
	'''
	Copies the orientation of each snail segment to attributes in its
	corresponding bone in the armature. To be called by the armature. The
	controller must have sensors ('hooks', below) attached to the segments.
	'''
	o = c.owner
	
	h1 = c.sensors['sHook_H1'].owner
	h2 = c.sensors['sHook_H2'].owner
	t1 = c.sensors['sHook_T1'].owner
	t2 = c.sensors['sHook_T2'].owner
	
	o['Heading_H1'] = h1['Heading']
	o['Pitch_H1'] = h1['Pitch']
	o['Roll_H1'] = h1['Roll']
	
	o['Heading_H2'] = h2['Heading']
	o['Pitch_H2'] = h2['Pitch']
	o['Roll_H2'] = h2['Roll']
	
	o['Heading_T1'] = t1['Heading']
	o['Pitch_T1'] = t1['Pitch']
	o['Roll_T1'] = t1['Roll']
	
	o['Heading_T2'] = t2['Heading']
	o['Pitch_T2'] = t2['Pitch']
	o['Roll_T2'] = t2['Roll']
