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

import bge
import mathutils

import bxt

DEBUG = True

ZERO2 = mathutils.Vector((0.0, 0.0))

class SBParticle:
	'''A 2D softbody particle. Always tries to return to (0, 0). Set the Frame
	property directly to displace the particle; then call update_dynamics to
	accelerate the particle back towards (0, 0).
	'''
	def __init__(self, spring, damp, index):
		self.Velocity = ZERO2.copy()
		self.Frame = ZERO2.copy()

		self.Spring = spring
		self.Damping = damp

		self.XProp = "BladeX%d" % index
		self.YProp = "BladeY%d" % index

	def update_dynamics(self):
		'''Accelerate the particle towards (0, 0)'''
		self.Velocity = self.Velocity - (self.Frame * self.Spring)
		self.Velocity = self.Velocity * (1.0 - self.Damping)
		self.Frame = self.Frame + self.Velocity

class GrassBlade(bxt.types.BX_GameObject, bge.types.BL_ArmatureObject):
	_prefix = 'GB_'

	@bxt.types.profile('Scripts.foliage.GrassBlade.__init__')
	def __init__(self, old_owner):
		self.bbox = bxt.math.Box2D(
				0.0 - self['GrassRadY'], 0.0 - self['GrassRadZ'],
				self['GrassRadY'], self['GrassRadZ'])

		self.Segments = []
		for i in range(0, self['nSegments']):
			p = SBParticle(self['Spring'], self['Damping'], i)
			self.Segments.append(p)

		self.LastBaseFrame = ZERO2.copy()

		if DEBUG:
			for child in self.children:
				child.color = bxt.render.BLACK

	def get_collision_force(self, collider):
		#
		# Transform collider into blade's coordinate system.
		#
		cPos = bxt.math.to_local(self, collider.worldPosition)

		#
		# The blades are rotated 90 degrees to work better as Blender particles.
		# But we're only interested in two axes. Re-map them to be X and Y.
		#
		cPos = cPos.yz

		#
		# Collider bounding box.
		#
		colRad = collider['LODRadius']
		colBox = bxt.math.Box2D(cPos.x - colRad, cPos.y - colRad,
		                        cPos.x + colRad, cPos.y + colRad)

		#
		# Perform axis-aligned 2D bounding box collision.
		#
		colBox.intersect(self.bbox)
		area = colBox.get_area()

		if area < 0.0:
			#
			# Boxes aren't touching; no force.
			#
			return ZERO2.copy()

		areaFraction = area / self.bbox.get_area()

		cPos.normalize()
		cPos = cPos * (areaFraction * 100.0)

		return cPos

	@bxt.types.expose
	@bxt.utils.controller_cls
	def collide(self, c):
		#
		# Find the offset of the base.
		#
		s = c.sensors['Near']
		vec = ZERO2.copy()
		for col in s.hitObjectList:
			vec = vec + self.get_collision_force(col)
		self['BladeXBase'] = vec.x
		self['BladeYBase'] = vec.x

		linkDisplacement = vec - self.LastBaseFrame
		self.LastBaseFrame = vec

		#
		# Provide input to other logic paths (a sensor might watch this).
		#
		self['Acceleration'] = linkDisplacement.magnitude

		#
		# Move each link in the opposite direction to the preceding link.
		#
		for s in self.Segments:
			s.Frame = s.Frame - linkDisplacement
			s.update_dynamics()
			self[s.XProp] = s.Frame.x
			self[s.YProp] = s.Frame.y
			linkDisplacement = s.Velocity

		for act in c.actuators:
			c.activate(act)
