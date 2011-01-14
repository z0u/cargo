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

import mathutils
import bxt
from . import Utilities

ZERO2 = mathutils.Vector((0.0, 0.0))

class SBParticle:
	'''
	A 2D softbody particle. Always tries to return to (0, 0). Set the Frame
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
		'''
		Accelerate the particle towards (0, 0)
		'''
		self.Velocity = self.Velocity - (self.Frame * self.Spring)
		self.Velocity = self.Velocity * (1.0 - self.Damping)
		self.Frame = self.Frame + self.Velocity

class GrassBlade:
	def __init__(self, owner):
		self.owner = owner
		self.owner['GrassBlade'] = self
		
		ry = self.owner['GrassRadY']
		rz = self.owner['GrassRadZ']
		self.bbox = bxt.utils.Box2D(0.0 - ry, 0.0 - rz, ry, rz)
		
		self.Segments = []
		for i in range(0, self.owner['nSegments']):
			p = SBParticle(self.owner['Spring'], self.owner['Damping'], i)
			self.Segments.append(p)
		
		self.LastBaseFrame = ZERO2.copy()
		
		Utilities.SceneManager().Subscribe(self)
	
	def OnSceneEnd(self):
		self.owner['GrassBlade'] = None
		self.owner = None
		Utilities.SceneManager().Unsubscribe(self)

	def get_collision_force(self, collider):
		#
		# Transform collider into blade's coordinate system.
		#
		cPos = bxt.math.to_local(self.owner, collider.worldPosition)
		
		#
		# The blades are rotated 90 degrees to work better as Blender particles.
		# But we're only interested in two axes. Re-map them to be X and Y.
		#
		cPos = cPos.yz
		
		#
		# Collider bounding box.
		#
		colRad = collider['LODRadius']
		colBox = bxt.utils.Box2D(cPos.x - colRad, cPos.y - colRad,
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
	
	def collide(self, colliders):
		#
		# Find the offset of the base.
		#
		vec = ZERO2.copy()
		for col in colliders:
			vec = vec + self.get_collision_force(col)
		self.owner['BladeXBase'] = vec.x
		self.owner['BladeYBase'] = vec.x
		
		linkDisplacement = vec - self.LastBaseFrame
		self.LastBaseFrame = vec
		
		#
		# Provide input to other logic paths (a sensor might watch this).
		#
		self.owner['Acceleration'] = linkDisplacement.magnitude
		
		#
		# Move each link in the opposite direction to the preceding link.
		#
		for s in self.Segments:
			s.Frame = s.Frame - linkDisplacement
			s.update_dynamics()
			self.owner[s.XProp] = s.Frame.x
			self.owner[s.YProp] = s.Frame.y
			linkDisplacement = s.Velocity

@bxt.utils.owner
def CreateGrassBlade(o):
	GrassBlade(o)

@bxt.utils.controller
def Collide(c):
	s = c.sensors['Near']
	c.owner['GrassBlade'].collide(s.hitObjectList)
	for act in c.actuators:
		c.activate(act)
