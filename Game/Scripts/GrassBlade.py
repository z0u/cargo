
from Blender import Mathutils
from Scripts import Utilities

class GrassBlade:
	def __init__(self, owner):
		self.Owner = owner
		self.Owner['GrassBlade'] = self
		
		ry = owner['LODRadY']
		rz = owner['LODRadZ']
		self.BBox = Utilities.Box2D(0.0 - ry, 0.0 - rz, ry, rz)
		
		self.TipVelocity = Mathutils.Vector(0.0, 0.0)
		self.TipFrame = Mathutils.Vector(0.0, 0.0)
		self.LastBaseFrame = Mathutils.Vector(0.0, 0.0)

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
	
	def WobbleTip(self, baseFrame):
		#
		# Move the tip in the opposite direction to the base, so it appears to
		# have not moved.
		#
		delta = baseFrame - self.LastBaseFrame
		tipFrame = self.TipFrame - delta
		
		#
		# Now accelerate the tip towards the rest position (0.0, 0.0).
		#
		self.TipVelocity = self.TipVelocity - (tipFrame * self.Owner['Spring'])
		self.TipVelocity = self.TipVelocity * (1.0 - self.Owner['Damping'])
		
		self.TipFrame = tipFrame + self.TipVelocity
		self.Owner['BladeZ2'] = self.TipFrame.x
		self.Owner['BladeY2'] = self.TipFrame.y
		
		self.LastBaseFrame = baseFrame
	
	def Collide(self, colliders):
		vec = Mathutils.Vector(0.0, 0.0)
		for col in colliders:
			vec = vec + self.GetCollisionForce(col)
		self.Owner['BladeZ1'] = vec.x
		self.Owner['BladeY1'] = vec.y
		self.WobbleTip(vec)

def CreateGrassBlade(c):
	GrassBlade(c.owner)

def Collide(c):
	s = c.sensors['Near']
	c.owner['GrassBlade'].Collide(s.hitObjectList)
	for act in c.actuators:
		c.activate(act)
