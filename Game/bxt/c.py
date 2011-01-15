#
# Copyright 2009-2011 Alex Fraser <alex@phatcore.com>
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

from bge import logic, render

import bxt.math

@bxt.utils.controller
def slow_copy_rot(c):
	'''Slow parenting (Rotation only). The owner will copy the rotation of the
	'sGoal' sensor's owner. The owner must have a SlowFac property:
	0 <= SlowFac <= 1. Low values will result in slower and smoother movement.
	'''

	o = c.owner
	goal = c.sensors['sGoal'].owner
	bxt.math.slow_copy_rot(o, goal, o['SlowFac'])

@bxt.utils.controller
def slow_copy_loc(c):
	'''Slow parenting (Location only). The owner will copy the position of the
	'sGoal' sensor's owner. The owner must have a SlowFac property:
	0 <= SlowFac <= 1. Low values will result in slower and smoother movement.
	'''

	o = c.owner
	goal = c.sensors['sGoal'].owner
	bxt.math.slow_copy_loc(o, goal, o['SlowFac'])

@bxt.utils.all_sensors_positive
@bxt.utils.controller
def copy_trans(c):
	'''Copy the transform from a linked sensor's object to this object.'''
	bxt.math.copy_transform(c.sensors[0].owner, c.owner)

@bxt.utils.owner
def ray_follow(o):
	'''Position an object some distance along its parent's z-axis. The object
	will be placed at the first intersection point, or RestDist units from the
	parent - whichever comes first.
	'''

	p = o.parent

	origin = p.worldPosition
	direction = p.getAxisVect([0.0, 0.0, 1.0])
	through = origin + direction

	hitOb, hitPoint, hitNorm = p.rayCast(
		through,		# obTo
		origin,			# obFrom
		o['RestDist'], 	# dist
		'Ray',			# prop
		1,				# face normal
		1				# x-ray
	)

	targetDist = o['RestDist']
	if hitOb and (hitNorm.dot(direction) < 0):
		#
		# If dot > 0, the tracking object is inside another mesh.
		# It's not perfect, but better not bring the camera forward
		# in that case, or the camera will be inside too.
		#
		targetDist = (hitPoint - origin).magnitude

	targetDist = targetDist * o['DistBias']

	if targetDist < o['Dist']:
		o['Dist'] = targetDist
	else:
		o['Dist'] = bxt.math.lerp(targetDist, o['Dist'], o['Fact'])

	pos = origin + (direction * o['Dist'])

	o.worldPosition = pos

@bxt.utils.all_sensors_positive
@bxt.utils.controller
def spray_particle(c):
	'''
	Instance one particle, and decrement the particle counter. The particle will
	move along the z-axis of the emitter. The emitter will then be repositioned.

	The intention is that one particle will be emitten on each frame. This
	should be fast enough for a spray effect. Staggering the emission reduces
	the liklihood that the frame rate will suffer.

	Actuators:
	aEmit:	A particle emitter, connected to its target object.
	aRot:	An actuator that moves the emitter by a fixed amount (e.g. movement
			or IPO).

	Controller properties:
	maxSpeed:	The maximum speed that a particle will have when it is created.
			Actually the particle will move at a random speed s, where 0.0 <= s
			<= maxSpeed.
	nParticles:	The number of particles waiting to be created. This will be
			reduced by 1. If less than or equal to 0, no particle will be
			created.
	'''

	o = c.owner
	if o['nParticles'] <= 0:
		return

	o['nParticles'] = o['nParticles'] - 1
	speed = o['maxSpeed'] * logic.getRandomFloat()
	c.actuators['aEmit'].linearVelocity = (0.0, 0.0, speed)
	c.activate('aEmit')
	c.activate('aRot')

@bxt.utils.owner
def billboard(o):
	'''Track the camera - the Z-axis of the current object will be point towards
	the camera.'''

	_, vec, _ = o.getVectTo(logic.getCurrentScene().active_camera)
	o.alignAxisToVect(vec, 2)

@bxt.utils.all_sensors_positive
def makeScreenshot():
	render.makeScreenshot('//Screenshot#.jpg')

@bxt.utils.controller
def time_offset_children(c):
	'''Copy the 'Frame' property to all children, incrementally adding an offset
	as defined by the 'Offset' property.
	'''

	o = c.owner
	a = c.actuators[0]
	range = a.frameEnd - a.frameStart
	increment = 0.0
	if len(o.children) > 0:
		increment = range / len(o.children)

	offset = 0.0
	for child in o.children:
		frame = o['Frame'] + offset
		frame -= a.frameStart
		frame %= range
		frame += a.frameStart
		child['Frame'] = frame
		offset += increment
	c.activate(a)
