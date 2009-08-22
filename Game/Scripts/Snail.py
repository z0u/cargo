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
				raise Exception("Segment %s already has a child." % self.Owner.name)
			self.Child = SnailSegment(child, self)
			return True
		elif (type == "SegmentChildPivot"):
			if (self.Child):
				raise Exception("Segment %s already has a child." % self.Owner.name)
			self.Child = SegmentChildPivot(child)
			return True
		elif (type == "Fulcrum"):
			if (self.Fulcrum):
				raise Exception("Segment %s already has a fulcrum." % self.Owner.name)
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

class Snail(SnailSegment, Actor.StatefulActor):
	def __init__(self, owner, cargoHold):
		Actor.StatefulActor.__init__(self, owner)
		
		self.Appendages = []
		self.CargoHold = cargoHold
		self.Shell = None
		self.Shockwave = None
		self.Trail = None
		SnailSegment.__init__(self, owner, None)
		if (self.Appendages == []):
			print "Warning: no appendages defined."
		if (self.CargoHold == None):
			raise Exception("No CargoHold defined.")
		if self.Shockwave == None:
			raise Exception("No Shockwave defined.")
	
	def parseChild(self, child, type):
		if type == "AppendageRoot":
			self.Appendages.append(AppendageRoot(child))
			return True
		elif type == "Shockwave":
			self.Shockwave = child
			return True
		elif type == "SnailTrail":
			self.Trail = SnailTrail(child, self)
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
		
		for appendage in self.Appendages:
			appendage.orient()
	
	def setOrientation(self, ob, target, ref):
		'''
		Sets the orientation of 'ob' to match that of 'target'
		using 'ref' as the referential. The final orientation
		will be offset from 'target's by the difference between
		'ob' and 'ref's orientations.
		'''
		
		oOrn = ob.worldOrientation
		oOrn = Mathutils.Matrix(oOrn[0], oOrn[1], oOrn[2])
		
		rOrn = ref.worldOrientation
		rOrn = Mathutils.Matrix(rOrn[0], rOrn[1], rOrn[2])
		rOrn.invert()
		
		localOrn = rOrn * oOrn
		
		orn = target.worldOrientation
		orn = Mathutils.Matrix(orn[0], orn[1], orn[2])
		orn = orn * localOrn
		
		ob.localOrientation = orn
	
	def setPosition(self, ob, target, ref):
		'''
		Sets the position of 'ob' to match that of 'target'
		using 'ref' as the referential. The final position
		will be offset from 'target's by the difference between
		'ob' and 'ref's positions.
		'''
		oPos = Mathutils.Vector(ob.worldPosition)
		rPos = Mathutils.Vector(ref.worldPosition)
		tPos = Mathutils.Vector(target.worldPosition)
		offset = rPos - oPos
		posFinal = tPos - offset
		
		ob.worldPosition = posFinal
	
	def _stowShell(self, shell):
		referential = shell
		for child in shell.children:
			if (child.Type == 'CargoHook'):
				referential = child
		
		self.setOrientation(shell, self.CargoHold, referential)
		self.setPosition(shell, self.CargoHold, referential)
		shell.setParent(self.CargoHold)
	
	def setShell(self, shell):
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
		
		self._stowShell(shell.Owner)
		
		self.Shell = shell
		self.Owner['HasShell'] = 1
		self.Owner['DynamicMass'] = self.Owner['DynamicMass'] + self.Shell.Owner['DynamicMass']
		self.Shell.OnPickedUp(self)
		self.Shockwave.state = 1<<1 # state 2
	
	def removeShell(self):
		'''Unhooks the current shell by un-setting its parent.'''
		self.Shell.Owner.removeParent()
		velocity = self.Owner.getAxisVect(ZAXIS)
		velocity = Mathutils.Vector(velocity)
		velocity = velocity * self.Owner['ShellPopForce']
		self.Shell.Owner.applyImpulse(self.Shell.Owner.worldPosition, velocity)
		self.Owner['HasShell'] = 0
		self.Owner['DynamicMass'] = self.Owner['DynamicMass'] - self.Shell.Owner['DynamicMass']
		self.Shell.OnDropped()
		self.Shell = None
	
	def preEnterShell(self):
		'''Called when the snail starts getting into the shell
		(several frames before control is transferred).'''
		self.Shell.OnPreEnter()
	
	def enterShell(self):
		'''Transfers control of the character to the shell.
		The snail must have a shell.'''
		self.Shell.Owner.removeParent()
		self.Owner.setParent(self.Shell.Owner)
	
		#
		# Swap mass with shell so the shell can influence bendy leaves properly
		#
		dm = self.Shell.Owner['DynamicMass']
		self.Shell.Owner['DynamicMass'] = self.Owner['DynamicMass']
		self.Owner['DynamicMass'] = dm
		
		self.Owner['InShell'] = 1
		self.Shell.OnEntered()
		self.Owner.setVisible(0, 1)
	
	def exitShell(self):
		'''Transfers control of the character to the snail.
		The snail must be the child of a shell.'''
		linV = self.Shell.Owner.getLinearVelocity()
		angV = self.Shell.Owner.getAngularVelocity()
		self.Owner.removeParent()
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
		self.Owner.setVisible(1, 1)
	
	def postExitShell(self):
		'''Called when the snail has finished its exit shell
		animation (several frames after control has been
		transferred).'''
		self.Shell.OnPostExit()

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
		hit = 0
		for ray in self.Rays:
			hit, p = ray.getHitPosition()
			if (hit == 1):
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

	def lerp(self, A, B, fac):
		return (A * fac) + (B * (1.0 - fac))

	def getHitPosition(self):
		origin = Mathutils.Vector(self.Owner.worldPosition)
		dir = Mathutils.Vector(self.Owner.getAxisVect(ZAXIS))
		through = origin + dir
		object, hitPoint, normal = self.Owner.rayCast(
			through,            # to
			origin,             # from
			self.Owner.Length,  # dist
			'Ground',           # prop
			1,                  # face
			1                   # xray
		)
		
		hit = 0
		if (object):
			#
			# Ensure the hit was not from inside an object.
			#
			normal = Mathutils.Vector(normal)
			if (Mathutils.DotVecs(normal, dir) < 0.0):
				hit = 1
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
			return True
	
	def AddSpot(self, touchedObject, addActuator):
		spot = self.TrailSpots[self.SpotIndex]
		addActuator.object = spot
		addActuator.instantAddObject()
		spotI = addActuator.objectLastCreated
		spotI.setParent(touchedObject)
		spotI.state = 1<<1
		self.LastTrailPos = Mathutils.Vector(self.Owner.worldPosition)
		self.SpotIndex = (self.SpotIndex + 1) % len(self.TrailSpots)
	
	def DistanceReached(self):
		pos = Mathutils.Vector(self.Owner.worldPosition)
		dist = (pos - self.LastTrailPos).magnitude
		return dist > self.Snail.Owner.TrailSpacing

#
# Module interface functions.
#

def Init(cont):
	cargoHold = cont.sensors['sCargoHoldHook'].owner
	snail = Snail(cont.owner, cargoHold)
	cont.owner['Snail'] = snail

def Orient(c):
	c.owner['Snail'].orient()

def OnShellTouched(c):
	o = c.owner
	
	activate = True
	for s in c.sensors:
		if not s.positive:
			activate = False
	
	if not activate:
		return
	
	if not o['HasShell']:
		ob = c.sensors['sShellPickup'].hitObject
		shell = ob['Actor']
		if (not shell.Owner['Carried']):
			o['Snail'].setShell(shell)

def DropShell(c):
	c.owner['Snail'].removeShell()

def OnShellPostExit(c):
	'''Called when the shell has been fully exited.'''
	for s in c.sensors:
		if not s.positive:
			return
	c.owner['Snail'].postExitShell()

def OnShellExit(c):
	'''
	Transfers control of the character to the snail. To be run from a controller
	on the snail. The snail must be carrying a shell. To reverse this, run
	OnShellExit from a controller on the snail.
	'''
	for s in c.sensors:
		if not s.positive:
			return
	c.owner['Snail'].exitShell()

def OnShellEnter(c):
	'''
	Transfers control of the snail to its shell. Allows for things like
	steering a rolling shell. This must be run from a controller on the
	snail. The snail must be carrying a shell. To reverse this, run
	OnShellExit from a controller on the snail.
	'''
	for s in c.sensors:
		if not s.positive:
			return
	c.owner['Snail'].enterShell()

def OnShellPreEnter(c):
	'''Called when the shell is starting to be entered.'''
	for s in c.sensors:
		if not s.positive:
			return
	c.owner['Snail'].preEnterShell()

#
# Independent functions.
#

def Turn(c):
	'''
	Make the snail bend to turn a corner.
	
	Sensors:
	sLeft:  Makes the snail bend left.
	sRight: Makes the snail bend right.
	sDown:  Reverses the bend direction.
	sHook_[H,T][1,2]: Sensors owned by the bend objects in the rig. The bend 
	        angle will be copied to each object using the property "TurnAngle".
	
	Properties:
	MaxTurnAngle: The amount to bend each segment by.
	TurnAngle:    The current bend amount.
	TurnFactor:   The speed at which the snail bends.
	              0.0 <= TurnFactor <= 1.0
	'''
	
	o = c.owner
	sl = c.sensors['sLeft']
	sr = c.sensors['sRight']
	sfwd = c.sensors['sUp']
	sbkwd = c.sensors['sDown']
	
	targetBendAngleFore = 0.0
	targetRot = 0.0
	targetBendAngleAft = None
	if sl.positive:
		#
		# Bend left.
		#
		targetBendAngleFore = targetBendAngleFore - o['MaxBendAngle']
		targetRot = targetRot + o['MaxRot']
	if sr.positive:
		#
		# Bend right. If bending left too, the net result will be
		# zero.
		#
		targetBendAngleFore = targetBendAngleFore + o['MaxBendAngle']
		targetRot = targetRot - o['MaxRot']
	
	if sfwd.positive and not sbkwd.positive:
		#
		# Moving forward.
		#
		targetBendAngleAft = targetBendAngleFore
	elif sbkwd.positive and not sfwd.positive:
		#
		# Reversing: invert rotation direction.
		#
		targetBendAngleAft = targetBendAngleFore
		targetRot = 0.0 - targetRot
	else:
		#
		# Stationary. Only bend the head.
		#
		targetBendAngleAft = 0.0
		targetRot = 0.0
		
	o['BendAngleFore'] = Utilities._lerp(o['BendAngleFore'],
	                                     targetBendAngleFore,
	                                     o['BendFactor'])
	o['BendAngleAft'] = Utilities._lerp(o['BendAngleAft'],
	                                    targetBendAngleAft,
	                                    o['BendFactor'])
	
	o['Rot'] = Utilities._lerp(o['Rot'], targetRot, o['RotFactor'])
	o.setAngularVelocity([0.0, 0.0, o['Rot']], 1)
	
	ah1 = c.actuators['aTurn_H1']
	ah2 = c.actuators['aTurn_H2']
	at1 = c.actuators['aTurn_T1']
	at2 = c.actuators['aTurn_T2']
	
	h1 = ah1.owner
	h2 = ah2.owner
	t1 = at1.owner
	t2 = at2.owner
	
	h1['BendAngle'] = o['BendAngleFore']
	h2['BendAngle'] = o['BendAngleFore']
	t1['BendAngle'] = o['BendAngleAft']
	t2['BendAngle'] = o['BendAngleAft']
	
	c.activate(ah1)
	c.activate(ah2)
	c.activate(at1)
	c.activate(at2)

def SpawnTrail(c):
	'''Add a piece of snail trail.'''
	o = c.owner
	addActuator = c.actuators['aSpawnTrail']
	
	sGrounded = c.sensors['sNearGround']
	sUp = c.sensors['sDown']
	sDown = c.sensors['sUp']
	
	if (sUp.positive or sDown.positive) and sGrounded.positive:
		hitOb = sGrounded.hitObject
		snail = o['Snail']
		if snail.Trail.DistanceReached():
			snail.Trail.AddSpot(hitOb, addActuator)

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
