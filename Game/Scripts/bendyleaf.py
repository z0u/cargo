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
import mathutils

@bxt.utils.controller
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
	origin = mathutils.Vector(o.worldPosition)
	distRange = o['MaxDist'] - o['MinDist']
	targetCol = 1.0
	if len(hitObs) > 0:
		totalInfluence = 0.0
		for ob in hitObs:
			pos = mathutils.Vector(ob.worldPosition)
			distance = (pos - origin).magnitude
			influence = (distance - o['MinDist']) / distRange
			influence = influence * ob['DynamicMass']
			totalInfluence = totalInfluence + influence
		totalInfluence = totalInfluence * o['InfluenceMultiplier']

		bendAngle = o['RestAngle'] + totalInfluence * o['MaxAngle']
		bendAngle = bxt.math.clamp(o['MinAngle'], o['MaxAngle'], bendAngle)
		targetCol = bxt.math.clamp(0.0, 1.0, 1.0 - totalInfluence)
	else:
		bendAngle = o['RestAngle']

	#
	# Interpolate to target angle.
	#
	o['CurrentDelta'], o['BendAngle'] = bxt.math.smerp(o['CurrentDelta'],
		o['BendAngle'], bendAngle, o['SpeedFactor'], o['Responsiveness'])
	currentCol = o.children['BendyLeafSkin'].color.y
	currentCol = bxt.math.lerp(currentCol, targetCol, o['SpeedFactor'])
	o.children['BendyLeafSkin'].color.y = currentCol
	o.children['BendyLeafSkin'].color.z = currentCol

	#
	# Apply deformation.
	#
	actuator = c.actuators['aBend']
	c.activate(actuator)
