import Utilities
from Blender import Mathutils

def BendLeaf(c):
	'''
	Cause a bendy leaf to react to objects touching it. The controller must
	belong to to the leaf. It must only be connected to a set of touch sensors
	belonging to segments of the leaf. These should only respond to objects
	that have a numeric DynamicMass property.
	'''
	o = c.owner
	sensors = c.sensors

	#
	# Pass one: Find out which objects are touching the leaf.
	#
	hitObs = set()
	for s in sensors:
		if not s.positive:
			continue
		for ob in s.hitObjectList:
			hitObs.add(ob)
	
	o['Hit'] = len(hitObs) > 0
	
	#
	# Pass two: add up the effect of all touching objects.
	#
	origin = Mathutils.Vector(o.worldPosition)
	distRange = o['MaxDist'] - o['MinDist']
	if len(hitObs) > 0:
		totalInfluence = 0.0
		for ob in hitObs:
			pos = Mathutils.Vector(ob.worldPosition)
			distance = (pos - origin).magnitude
			influence = (distance - o['MinDist']) / distRange
			influence = influence * ob['DynamicMass']
			totalInfluence = totalInfluence + influence
		totalInfluence = totalInfluence * o['InfluenceMultiplier']
		
		bendAngle = o['RestAngle'] + totalInfluence * o['MaxAngle']
		if bendAngle > o['MaxAngle']:
			bendAngle = o['MaxAngle']
		elif bendAngle < o['MinAngle']:
			bendAngle = o['MinAngle']
	else:
		bendAngle = o['RestAngle']
	
	#
	# Interpolate to target angle.
	#
	o['CurrentDelta'], o['BendAngle'] = Utilities._smerp(o['CurrentDelta'], o['BendAngle'], bendAngle, o['SpeedFactor'], o['Responsiveness'])
	
	#
	# Apply deformation.
	#
	actuator = c.actuators['aBend']
	c.activate(actuator)