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

from Blender import Mathutils

class SemanticGameObject:
	'''Abstract class that decorates game engine objects. Children will be
	parsed and decorated according to their type.'''
	Owner = None
	
	def __init__(self, owner):
		self.Owner = owner
		self.parseChildren()

	def parseChild(self, child, type):
		return False
	
	def parseChildren(self):
		for child in self.Owner.children:
			try:
				if (not self.parseChild(child, child['Type'])):
					print "Warning: child %s of %s has unexpected type (%s)" % (
						child.name,
						self.Owner.name,
						child['Type'])
			
			except KeyError:
				continue

class Box2D:
	'''A 2D bounding box.'''
	def __init__(self, xLow, yLow, xHigh, yHigh):
		self.xLow = xLow
		self.yLow = yLow
		self.xHigh = xHigh
		self.yHigh = yHigh
	
	def Intersect(self, other):
		if other.xHigh < self.xHigh:
			self.xHigh = other.xHigh
		if other.yHigh < self.yHigh:
			self.yHigh = other.yHigh
		
		if other.xLow > self.xLow:
			self.xLow = other.xLow
		if other.yLow > self.yLow:
			self.yLow = other.yLow
		
		#
		# Ensure box is not inside-out.
		#
		if self.xLow > self.xHigh:
			self.xLow = self.xHigh
		if self.yLow > self.yHigh:
			self.yLow = self.yHigh
	
	def GetArea(self):
		w = self.xHigh - self.xLow
		h = self.yHigh - self.yLow
		return w * h

def _lerp(A, B, fac):
	return A + ((B - A) * fac)

def _smerp(CurrentDelta, CurrentValue, Target, SpeedFactor, Responsiveness):
	'''Smooth exponential average interpolation
	For each time step, try to move toward the target by some fraction of
	the distance (as is the case for normal exponential averages). If this
	would result in a positive acceleration, take a second exponential
	average of the acceleration. The resulting resulting motion has smooth
	acceleration and smooth deceleration.'''
	
	targetDelta = (Target - CurrentValue) * SpeedFactor
	if (targetDelta * targetDelta > CurrentDelta * CurrentDelta):
	    CurrentDelta = CurrentDelta * (1.0 - Responsiveness) + targetDelta * Responsiveness
	else:
		CurrentDelta = targetDelta
	
	CurrentValue = CurrentValue + CurrentDelta
	return CurrentDelta, CurrentValue


def _toLocal(referential, point):
	'''
	Transform 'point' (specified in world space) into the coordinate space of
	the object 'referential'.
	
	Parameters:
	referential: The object that defines the coordinate space to transform to.
	             (KX_GameObject)
	point:       The point, in world space, to transform. (Mathutils.Vector)
	'''
	refP = Mathutils.Vector(referential.worldPosition)
	refOMat = referential.worldOrientation
	refOMat = Mathutils.Matrix(refOMat[0], refOMat[1], refOMat[2])
	refOMat.transpose()
	refOMat.invert()
	return (point - refP) * refOMat

def _toWorld(referential, point):
	'''
	Transform 'point' into world space. 'point' must be specified in the
	coordinate space of 'referential'.
	
	Parameters:
	referential: The object that defines the coordinate space to transform from.
	             (KX_GameObject)
	point:       The point, in local space, to transform. (Mathutils.Vector)
	'''
	refP = Mathutils.Vector(referential.worldPosition)
	refOMat = referential.worldOrientation
	refOMat = Mathutils.Matrix(refOMat[0], refOMat[1], refOMat[2])
	refOMat.transpose()
	return (point * refOMat) + refP

def _SlowCopyRot(o, goal, factor):
	'''
	Slow parenting (Rotation only). 'o' will copy the rotation of the 'goal'.
	'o' must have a SlowFac property: 0 <= SlowFac <= 1. Low values will result
	in slower and smoother movement.
	'''
	goalOrn = goal.worldOrientation
	goalOrn = Mathutils.Matrix(
		goalOrn[0],
		goalOrn[1],
		goalOrn[2]
	)
	goalOrn.transpose()
	goalOrn = goalOrn.toQuat()
	orn = o.worldOrientation
	orn = Mathutils.Matrix(
		orn[0],
		orn[1],
		orn[2]
	)
	orn.transpose()
	orn = orn.toQuat()
	orn = Mathutils.Slerp(orn, goalOrn, factor)
	orn = orn.toMatrix()
	orn.transpose()
	
	o.localOrientation = orn

def SlowCopyRot(c):
	'''
	Slow parenting (Rotation only). The owner will copy the rotation of the
	'sGoal' sensor's owner. The owner must have a SlowFac property:
	0 <= SlowFac <= 1. Low values will result in slower and smoother movement.
	'''
	o = c.owner
	goal = c.sensors['sGoal'].owner
	_SlowCopyRot(o, goal, o['SlowFac'])

def _SlowCopyLoc(o, goal, factor):
	'''
	Slow parenting (Rotation only). 'o' will copy the position of the 'goal'.
	'o' must have a SlowFac property: 0 <= SlowFac <= 1. Low values will result
	in slower and smoother movement.
	'''
	goalPos = Mathutils.Vector(goal.worldPosition)
	pos = Mathutils.Vector(o.worldPosition)
	
	o.worldPosition = _lerp(pos, goalPos, factor)

def SlowCopyLoc(c):
	'''
	Slow parenting (Location only). The owner will copy the position of the
	'sGoal' sensor's owner. The owner must have a SlowFac property:
	0 <= SlowFac <= 1. Low values will result in slower and smoother movement.
	'''
	o = c.owner
	goal = c.sensors['sGoal'].owner
	_SlowCopyLoc(o, goal, o['SlowFac'])

def StorePos(c):
	'''Store the position and orientation of the owner.'''
	o = c.owner
	o['_storedPos'] = o.worldPosition
	o['_storedRot'] = o.worldOrientation

def RestorePos(c):
	'''Reset the position and orientation of the owner to what it was when
	StorePos was last called.'''
	o = c.owner
	o.worldPosition = o['_storedPos']
	o.worldOrientation = o['_storedRot']

def setRelOrn(ob, target, ref):
	'''
	Sets the orientation of 'ob' to match that of 'target' using 'ref' as the
	referential. The final orientation will be offset from 'target's by the
	difference between 'ob' and 'ref's orientations.
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

def setRelPos(ob, target, ref):
	'''
	Sets the position of 'ob' to match that of 'target' using 'ref' as the
	referential. The final position will be offset from 'target's by the
	difference between 'ob' and 'ref's positions.
	'''
	oPos = Mathutils.Vector(ob.worldPosition)
	rPos = Mathutils.Vector(ref.worldPosition)
	tPos = Mathutils.Vector(target.worldPosition)
	offset = rPos - oPos
	posFinal = tPos - offset
	
	ob.worldPosition = posFinal

def RayFollow(c):
	'''
	Position an object some distance along its parent's z-axis. The object will 
	be placed at the first intersection point, or RestDist units from the parent
	- whichever comes first.
	'''
	o = c.owner
	p = o.parent
	
	origin = Mathutils.Vector(p.worldPosition)
	direction = Mathutils.Vector(p.getAxisVect([0.0, 0.0, 1.0]))
	through = origin + direction
	
	hitOb, hitPoint, hitNorm = p.rayCast(
		through,		# obTo
		origin,			# obFrom
		o.RestDist, 	# dist
		'Ray',			# prop
		1,				# face normal
		1				# x-ray
	)
	
	targetDist = o.RestDist
	obscured = False
	if hitOb:
		hitPoint = Mathutils.Vector(hitPoint)
		hitNorm = Mathutils.Vector(hitNorm)
		dot = Mathutils.DotVecs(hitNorm, direction)
		if dot < 0:
			#
			# If dot > 0, the tracking object is inside another mesh.
			# It's not perfect, but better not bring the camera forward
			# in that case, or the camera will be inside too.
			#
			targetDist = (hitPoint - origin).magnitude
	
	targetDist = targetDist * o.DistBias
	
	try:
		if targetDist < o['_RF_Dist']:
			o['_RF_Dist'] = targetDist
		else:
			o['_RF_Dist'] = _lerp(targetDist, o['_RF_Dist'], o['Fact'])
	except KeyError:
			o['_RF_Dist'] = targetDist
	
	pos = origin + (direction * o['_RF_Dist'])
	
	o.worldPosition = pos

def OrbitFollow(c):
	'''
	Make an object follow another from a certain distance. Used to make a camera
	follow the player around without always sticking behind their back.
	'''
	
	MIN_DIST = 0.05
	target = c.sensors['sTarget'].owner
	o = c.owner
	
	#
	# Get the vector from the camera to the target.
	#
	tPos = Mathutils.Vector(target.worldPosition)
	pos = Mathutils.Vector(o.worldPosition)
	vec = pos - tPos
	
	#
	# Remove the z-component (position camera on XY plane).
	#
	vec.z = 0.0
	vec.normalize()
	
	#
	# Align the camera's Y-axis with the global Z, and align
	# its Z-axis with the direction to the target.
	#
	o.alignAxisToVect([0.0, 0.0, 1.0], 1)
	o.alignAxisToVect(vec, 2)
	
	#
	# Keep the camera a constant distance from the target.
	# Note that camera.MaxDist = sqrt(camera.XYDist^2 + camera.ZDist^2)
	#
	vec = vec * o['XYDist']
	vec.z = o['ZDist']
	pos = tPos + vec
	hitOb, hitPoint, hitNormal = o.rayCast(
		pos,          # to,
		tPos,         # from,
		o['MaxDist'], # dist,
		'Ray',        # prop,
		1,            # face,
		1,            # xray,
		0             # poly
	)
	if hitOb:
		hitPoint = Mathutils.Vector(hitPoint)
		vec = hitPoint - tPos
		vec = vec * o['DistBias']
		if vec.magnitude < o['MinDist']:
			#
			# Camera would be too close, so don't move it.
			# It has already tracked, though.
			#
			return
		pos = tPos + vec
	o.worldPosition = pos

class _Random:
	#
	# 100 random numbers (saves needing to import the 'random' module).
	#
	RANDOMS = [
		0.61542, 0.69297, 0.76860, 0.53475, 0.40886, 0.91689, 0.93900, 0.68926,
		0.13285, 0.06095, 0.48474, 0.72606, 0.08579, 0.86588, 0.51390, 0.49194,
		0.94516, 0.65302, 0.89945, 0.17170, 0.73977, 0.57983, 0.47412, 0.70460,
		0.57242, 0.84086, 0.59730, 0.21010, 0.62376, 0.03536, 0.04448, 0.59527,
		0.27221, 0.66046, 0.38000, 0.50336, 0.86750, 0.14385, 0.93692, 0.46126,
		0.81840, 0.15508, 0.64163, 0.34990, 0.14746, 0.40949, 0.85291, 0.05562,
		0.31280, 0.20150, 0.43594, 0.97547, 0.68338, 0.70483, 0.85266, 0.32621,
		0.18625, 0.86591, 0.20850, 0.73349, 0.87122, 0.16648, 0.48411, 0.23507,
		0.15775, 0.55275, 0.68549, 0.99837, 0.06443, 0.01583, 0.10712, 0.98735,
		0.02540, 0.11582, 0.14976, 0.89697, 0.24265, 0.85307, 0.24749, 0.62709,
		0.74986, 0.45483, 0.10935, 0.46603, 0.46222, 0.61726, 0.36655, 0.16848,
		0.35994, 0.71661, 0.18646, 0.81395, 0.56462, 0.36674, 0.00286, 0.31847,
		0.26284, 0.01141, 0.67497, 0.78098
	]
	
	def __init__(self):
		self.LastRandIndex = 0
	
	def next(self):
		'''
		Get a random number between 0.0 and 1.0. This is only vaguely random: each
		number is drawn from a finite set of numbers, and the sequence repeats.
		'''
		self.LastRandIndex = (self.LastRandIndex + 1) % len(self.RANDOMS)
		return self.RANDOMS[self.LastRandIndex]

Random = _Random()
