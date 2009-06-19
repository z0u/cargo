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
	
	o['Hit'] = False
	hitObs = {}

	#
	# Find out the bending force of all objects touching the leaf. The further
	# an object is from the leaf's origin, the greater its effect. This is done
	# in two passes: the first stores the objects in a set to ensure they aren't
	# counted twice.
	#
	origin = Mathutils.Vector(o.worldPosition)
	distRange = o['MaxDist'] - o['MinDist']
	for s in sensors:
		if not s.positive:
			continue
		o['Hit'] = True
		for ob in s.hitObjectList:
			pos = Mathutils.Vector(ob.worldPosition)
			distance = (pos - origin).magnitude
			influence = (distance - o['MinDist']) / distRange
			hitObs[ob] = (influence, ob['DynamicMass'])
	
	#
	# Pass two: add up the effect of all touching objects.
	#
	if len(hitObs) > 0:
		totalInfluence = 0.0
		for influence, dynMass in hitObs.values():
			totalInfluence = totalInfluence + influence * dynMass
		totalInfluence = totalInfluence * o['InfluenceMultiplier']
		
		bendAngle = o['RestAngle'] + totalInfluence * o['MaxAngle']
		if bendAngle > o['MaxAngle']: bendAngle = o['MaxAngle']
		elif bendAngle < o['MinAngle']: bendAngle = o['MinAngle']
	else:
		bendAngle = o['RestAngle']

	o['CurrentDelta'], o['BendAngle'] = Utilities._smerp(o['CurrentDelta'], o['BendAngle'], bendAngle, o['SpeedFactor'], o['Responsiveness'])

	actuator = c.actuators['aBend']
	c.activate(actuator)