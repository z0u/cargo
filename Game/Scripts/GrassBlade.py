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

import Mathutils
from Scripts import Utilities

class SBParticle:
	'''
	A 2D softbody particle. Always tries to return to (0, 0). Set the Frame
	property directly to displace the particle; then call UpdateDynamics to
	accelerate the particle back towards (0, 0).
	'''
	def __init__(self, spring, damp, index):
		self.Velocity = Mathutils.Vector(0.0, 0.0)
		self.Frame = Mathutils.Vector(0.0, 0.0)
		
		self.Spring = spring
		self.Damping = damp
		
		self.XProp = "BladeX%d" % index
		self.YProp = "BladeY%d" % index
	
	def UpdateDynamics(self):
		'''
		Accelerate the particle towards (0, 0)
		'''
		self.Velocity = self.Velocity - (self.Frame * self.Spring)
		self.Velocity = self.Velocity * (1.0 - self.Damping)
		self.Frame = self.Frame + self.Velocity

class GrassBlade:
	def __init__(self, owner):
		self.Owner = owner
		self.Owner['GrassBlade'] = self
		
		ry = self.Owner['GrassRadY']
		rz = self.Owner['GrassRadZ']
		self.BBox = Utilities.Box2D(0.0 - ry, 0.0 - rz, ry, rz)
		
		self.Segments = []
		for i in range(0, self.Owner['nSegments']):
			p = SBParticle(self.Owner['Spring'], self.Owner['Damping'], i)
			self.Segments.append(p)
		
		self.LastBaseFrame = Mathutils.Vector(0.0, 0.0)
		
		Utilities.SceneManager.Subscribe(self)
	
	def OnSceneEnd(self):
		self.Owner['GrassBlade'] = None
		self.Owner = None
		Utilities.SceneManager.Unsubscribe(self)

	def GetCollisionForce(self, collider):
		#
		# Transform collider into blade's coordinate system.
		#
		cPos = Mathutils.Vector(collider.worldPosition)
		cPos = Utilities._toLocal(self.Owner, cPos)
		
		#
		# The blades are rotated 90 degrees to work better as Blender particles.
		# But we're only interested in two axes. Re-map them to be X and Y.
		#
		cPos = cPos.yz
		
		#
		# Collider bounding box.
		#
		colRad = collider['LODRadius']
		colBox = Utilities.Box2D(cPos.x - colRad, cPos.y - colRad,
		                         cPos.x + colRad, cPos.y + colRad)
		
		#
		# Perform axis-aligned 2D bounding box collision.
		#
		colBox.Intersect(self.BBox)
		area = colBox.GetArea()
		
		if area < 0.0:
			#
			# Boxes aren't touching; no force.
			#
			return Mathutils.Vector(0.0, 0.0)
		
		areaFraction = area / self.BBox.GetArea()
		
		cPos.normalize()
		cPos = cPos * (areaFraction * 100.0)
		
		return cPos
	
	def Collide(self, colliders):
		#
		# Find the offset of the base.
		#
		vec = Mathutils.Vector(0.0, 0.0)
		for col in colliders:
			vec = vec + self.GetCollisionForce(col)
		self.Owner['BladeXBase'] = vec.x
		self.Owner['BladeYBase'] = vec.x
		
		linkDisplacement = vec - self.LastBaseFrame
		self.LastBaseFrame = vec
		
		#
		# Provide input to other logic paths (a sensor might watch this).
		#
		self.Owner['Acceleration'] = linkDisplacement.magnitude
		
		#
		# Move each link in the opposite direction to the preceding link.
		#
		for s in self.Segments:
			s.Frame = s.Frame - linkDisplacement
			s.UpdateDynamics()
			self.Owner[s.XProp] = s.Frame.x
			self.Owner[s.YProp] = s.Frame.y
			linkDisplacement = s.Velocity

def CreateGrassBlade(c):
	GrassBlade(c.owner)

def Collide(c):
	s = c.sensors['Near']
	c.owner['GrassBlade'].Collide(s.hitObjectList)
	for act in c.actuators:
		c.activate(act)
