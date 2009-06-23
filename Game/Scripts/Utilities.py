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
			
			except AttributeError:
				continue

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

def SlowCopyRot(c):
	'''
	Slow parenting (Rotation only). The owner will copy the rotation of the
	'sGoal' sensor's owner. The owner must have a SlowFac property:
	0 <= SlowFac <= 1. Low values will result in slower and smoother movement.
	'''
	o = c.owner
	goal = c.sensors['sGoal'].owner

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
	orn = Mathutils.Slerp(orn, goalOrn, o['SlowFac'])
	orn = orn.toMatrix()
	orn.transpose()

	o.localOrientation = orn

def SlowCopyLoc(c):
	'''
	Slow parenting (Location only). The owner will copy the position of the
	'sGoal' sensor's owner. The owner must have a SlowFac property:
	0 <= SlowFac <= 1. Low values will result in slower and smoother movement.
	'''
	o = c.owner
	goal = c.sensors['sGoal'].owner

	goalPos = Mathutils.Vector(goal.worldPosition)
	pos = Mathutils.Vector(o.worldPosition)

	o.worldPosition = _lerp(pos, goalPos, o['SlowFac'])

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
