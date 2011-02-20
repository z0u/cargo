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

import math

import mathutils
from bge import render
from bge import logic

import bxt
from . import director

@bxt.types.gameobject('orient', 'look', 'save_location', 'modify_speed',
		'start_crawling', prefix='')
class Snail(bxt.types.ProxyGameObject, director.Actor):
	#S_INIT     = 1
	S_CRAWLING = 2
	S_FALLING  = 3
	#S_ACTIVE   = 4
	S_SHOCKED  = 5
	S_NOSHELL  = 16
	S_HASSHELL = 17
	S_POPPING  = 18
	S_INSHELL  = 19
	S_EXITING  = 20
	S_ENTERING = 21
	#S_REINCARNATE = 29
	#S_DROWNING    = 30

	MAX_SPEED = 3.0
	MIN_SPEED = -3.0

	def __init__(self, owner):
		bxt.types.ProxyGameObject.__init__(self, owner)
		self.touchedObject = None

		evt = bxt.utils.WeakEvent('MainCharacterSet', self)
		bxt.utils.EventBus().notify(evt)

	def orient(self):
		'''Adjust the orientation of the snail to match the nearest surface.'''
		counter = bxt.utils.Counter()
		avNormal = bxt.math.ZEROVEC.copy()
		ob0, p0, n0 = self.children['ArcRay_Root.0'].getHitPosition()
		avNormal += n0
		if ob0:
			counter.add(ob0)
		ob1, p1, n1 = self.children['ArcRay_Root.1'].getHitPosition()
		avNormal += n1
		if ob1:
			counter.add(ob1)
		ob2, p2, n2 = self.children['ArcRay_Root.2'].getHitPosition()
		avNormal += n2
		if ob2:
			counter.add(ob2)
		ob3, p3, n3 = self.children['ArcRay_Root.3'].getHitPosition()
		avNormal += n3
		if ob3:
			counter.add(ob3)

		avNormal /= 4.0
		
		#
		# Inherit the angular velocity of a nearby surface. The object that was
		# hit by the most rays (above) is used.
		# TODO: The linear velocity should probably be set, too: fast-moving
		# objects can be problematic.
		#
		self.touchedObject = counter.mode
		if self.touchedObject != None:
			angV = self.touchedObject.getAngularVelocity()
			if angV.magnitude < bxt.math.EPSILON:
				angV = bxt.math.MINVECTOR
			self.setAngularVelocity(angV)
		
		#
		# Set property on object so it knows whether it's falling. This is used
		# to detect when to transition from S_FALLING to S_CRAWLING.
		#
		self['nHit'] = counter.n
		
		#
		# Derive normal from hit points and update orientation. This gives a
		# smoother transition than just averaging the normals returned by the
		# rays.
		#
		normal = bxt.math.quadNormal(p0, p1, p2, p3)
		if normal.dot(avNormal) < 0.0:
			normal.negate()
		self.alignAxisToVect(normal, 2)
		
		self.orient_segment(self.children['Head.0'])
		self.orient_segment(self.children['Tail.0'])

	def orient_segment(self, parentSegment):
		name = parentSegment.name[:-2]
		i = int(parentSegment.name[-1:]) + 1

		pivot = parentSegment.children[0]
		rayL = pivot.children['ArcRay_%s.%d.L' % (name, i)]
		rayR = pivot.children['ArcRay_%s.%d.R' % (name, i)]
		fulcrum = pivot.children['Fulcrum_%s.%d' % (name, i)]
		segment = pivot.children['%s.%d' % (name, i)]

		#segment.alignAxisToVect(parentSegment.getAxisVect(bxt.math.XAXIS), 0)

		_, p1, _ = rayR.getHitPosition()
		_, p2, _ = rayL.getHitPosition()
		p3 = fulcrum.worldPosition
		normal = bxt.math.triangleNormal(p1, p2, p3)

		if normal.dot(pivot.getAxisVect(bxt.math.ZAXIS)) > 0.0:
			#
			# Normal is within 90 degrees of parent's normal -> segment not
			# doubling back on itself.
			#
			# Interpolate between normals for current and previous frames.
			# Don't use a factor of 0.5: potential for normal to average out
			# to be (0,0,0)
			#
			orientation = segment.getAxisVect(bxt.math.ZAXIS)
			orientation = bxt.math.lerp(normal, orientation, 0.4)
			segment.alignAxisToVect(orientation, 2)

		#
		# Make orientation available to armature. Use the inverse of the
		# parent's orientation to find the local orientation.
		#
		parentInverse = parentSegment.worldOrientation.copy()
		parentInverse.invert()
		localOrnMat = parentInverse * segment.worldOrientation
		channel = self.children['SnailArmature'].channels[segment['Channel']]
		channel.rotation_quaternion = localOrnMat.to_quat()

		# Recurse
		if len(segment.children) > 0:
			self.orient_segment(segment)

	def _get_touched_object(self):
		if self._touchedObject == None:
			return None
		elif self._touchedObject.invalid:
			self._touchedObject = None
			return None
		else:
			return self._touchedObject
	def _set_touched_object(self, object):
		self._touchedObject = object
	touchedObject = property(_get_touched_object, _set_touched_object)

	def look(self):
		pass

	def save_location(self):
		pass

	def modify_speed(self):
		pass

	def start_crawling(self):
		'''Called when the snail enters its crawling state.'''
		#
		# Don't set it quite to zero: zero vectors are ignored!
		#
		self.setAngularVelocity(bxt.math.MINVECTOR, False)
		self.setLinearVelocity(bxt.math.MINVECTOR, False)

	def on_movement_impulse(self, fwd, back, left, right):
		'''Make the snail move. If moving forward or backward, this implicitly
		calls decaySpeed.
		'''
		if not self.has_state(Snail.S_CRAWLING):
			return

		armature = self.children['SnailArmature']

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
		speed = self['NormalSpeed'] * self['SpeedMultiplier'] * float(fwdSign)
		self.applyMovement((0.0, speed, 0.0), True)
		self.decay_speed()

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
			targetBendAngleFore = targetBendAngleFore - self['MaxBendAngle']
			targetRot = targetRot + self['MaxRot']
		if right:
			#
			# Bend right. If bending left too, the net result will be
			# zero.
			#
			targetBendAngleFore = targetBendAngleFore + self['MaxBendAngle']
			targetRot = targetRot - self['MaxRot']

		locomotionStep = self['SpeedMultiplier'] * 0.4
		if fwdSign > 0:
			#
			# Moving forward.
			#
			targetBendAngleAft = targetBendAngleFore
			armature['LocomotionFrame'] = (
				armature['LocomotionFrame'] + locomotionStep)
		elif fwdSign < 0:
			#
			# Reversing: invert rotation direction.
			#
			targetBendAngleAft = targetBendAngleFore
			targetRot = 0.0 - targetRot
			armature['LocomotionFrame'] = (
				armature['LocomotionFrame'] - locomotionStep)
		else:
			#
			# Stationary. Only bend the head.
			#
			targetBendAngleAft = 0.0
			targetRot = 0.0

		armature['LocomotionFrame'] = (
			armature['LocomotionFrame'] % 19)

		#
		# Rotate the snail.
		#
		self['Rot'] = bxt.math.lerp(self['Rot'], targetRot, self['RotFactor'])
		oRot = mathutils.Matrix.Rotation(self['Rot'], 3, bxt.math.ZAXIS)
		self.localOrientation = self.localOrientation * oRot

		#
		# Match the bend angle with the current speed.
		#
		targetBendAngleAft = targetBendAngleAft / self['SpeedMultiplier']

		# These actually get applied in update.
		self['BendAngleFore'] = bxt.math.lerp(self['BendAngleFore'],
		                                     targetBendAngleFore,
		                                     self['BendFactor'])
		if fwdSign != 0:
			self['BendAngleAft'] = bxt.math.lerp(self['BendAngleAft'],
		                                        targetBendAngleAft,
		                                        self['BendFactor'])

		if (fwd or back):
			self.children['Trail'].moved(self['SpeedMultiplier'], self.touchedObject)

	def set_speed_multiplier(self, mult):
		self['SpeedMultiplier'] = max(min(mult, Snail.MAX_SPEED), Snail.MIN_SPEED)

	def decay_speed(self):
		'''Bring the speed of the snail one step closer to normal speed.'''
		dr = self['SpeedDecayRate']
		mult = self['SpeedMultiplier']
		
		if mult == 1.0:
			return
		elif mult > 1.0:
			self['SpeedMultiplier'] = max(mult - dr, 1.0)
		else:
			self['SpeedMultiplier'] = min(mult + dr, 1.0)
	
	def on_button1(self, positive, triggered):
		if positive and triggered:
			
			if self.has_state(Snail.S_INSHELL):
				self.exitShell(animate = True)
			elif self.has_state(Snail.S_HASSHELL):
				self.enterShell(animate = True)
			elif self.has_state(Snail.S_NOSHELL):
				if self.NearestShell:
					self.setShell(self.NearestShell, animate = True)
	
	def on_button2(self, positive, triggered):
		if positive and triggered:
			if self.has_state(Snail.S_HASSHELL):
				self.dropShell(animate = True)

@bxt.types.gameobject()
class Trail(bxt.types.ProxyGameObject):
	S_NORMAL = 2
	S_SLOW = 3
	S_FAST = 4
	
	def __init__(self, owner):
		bxt.types.ProxyGameObject.__init__(self, owner)
		self.lastMinorPos = self.worldPosition.copy()
		self.lastMajorPos = self.lastMinorPos.copy()
		self.paused = False
		self.spotIndex = 0
	
	def add_spot(self, speedStyle, touchedObject):
		'''
		Add a spot where the snail is now. Actually, this only adds a spot half
		the time: gaps will be left in the trail, like so:
		    -----     -----     -----     -----     -----
		
		@param speedStyle: The style to apply to the new spot. One of [S_SLOW,
			S_NORMAL, S_FAST].
		'''
		self.spotIndex = (self.spotIndex + 1) % len(self.children)
		
		scene = logic.getCurrentScene()
		spot = self.children[self.spotIndex]
		spotI = scene.addObject(spot, self.unwrap())
		
		#
		# Attach the spot to the object that the snail is crawling on.
		#
		if touchedObject != None:
			spotI.setParent(touchedObject)
		
		bxt.utils.set_state(spotI, speedStyle)
	
	def moved(self, speedMultiplier, touchedObject):
		pos = self.worldPosition
		
		distMajor = (pos - self.lastMajorPos).magnitude
		if distMajor > self['TrailSpacingMajor']:
			self.lastMajorPos = pos.copy()
			self.paused = not self.paused
		
		if self.paused:
			return
		
		distMinor = (pos - self.lastMinorPos).magnitude
		if distMinor > self['TrailSpacingMinor']:
			self.lastMinorPos = pos.copy()
			speedStyle = Trail.S_NORMAL
			if speedMultiplier > (1.0 + bxt.math.EPSILON):
				speedStyle = Trail.S_FAST
			elif speedMultiplier < (1.0 - bxt.math.EPSILON):
				speedStyle = Trail.S_SLOW
			self.add_spot(speedStyle, touchedObject)
