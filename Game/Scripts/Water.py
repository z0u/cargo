import GameLogic
from Blender import Mathutils

ANGLE_INCREMENT = 81.0

class Water:
	def __init__(self, owner):
		'''
		Create a water object that can respond to things touching it. The mesh
		is assumed to be a globally-aligned XY plane that passes through the
		object's origin.
		'''
		scene = GameLogic.getCurrentScene()
		self.Owner = owner
		owner['_Water'] = self
		
		self.InstanceAngle = 0.0
		self.BubbleTemplate = scene.objectsInactive['OB' + owner['BubbleTemplate']]
		self.RippleTemplate = scene.objectsInactive['OB' + owner['RippleTemplate']]
		self.MinDist = self.Owner['MinDist']
	
	def SpawnSurfaceDecal(self, template, position):
		pos = position
		pos[2] = self.Owner.worldPosition[2]
		
		#
		# Transform template.
		#
		elr = Mathutils.Euler(0.0, 0.0, self.InstanceAngle)
		self.InstanceAngle = self.InstanceAngle + ANGLE_INCREMENT
		oMat = elr.toMatrix()
		oMat.transpose()
		template.worldOrientation = oMat
		template.worldPosition = pos
		
		#
		# Create object.
		#
		scene = GameLogic.getCurrentScene()
		instance = scene.addObject(template, template)
	
	def OnSink(self, ob):
		self.SpawnSurfaceDecal(self.BubbleTemplate, ob.worldPosition)
	
	def OnCollision(self, ob):
		'''
		Called when an object collides with the water. Creates an instance of a
		ripple (as defined by the TemplateOb property) at the location on the
		surface that is nearest to the colliding object.
		'''
		pos = Mathutils.Vector(ob.worldPosition)
		
		try:
			if (pos - ob['Water_LastPos']).magnitude < self.MinDist:
				#
				# The object hasn't moved far enough to cause another event.
				#
				return
		except KeyError:
			#
			# This is the first time the object has touched the water. Continue;
			# the required key will be added below.
			#
			pass
		
		ob['Water_LastPos'] = pos
		self.SpawnSurfaceDecal(self.RippleTemplate, ob.worldPosition)

def CreateWater(c):
	Water(c.owner)

def OnCollision(c):
	'''
	Respond to collisions.
	
	Parameters:
	c: A Controller, owned by a water object, connected only to Near sensors.
	'''
	water = c.owner['_Water']
	
	for s in c.sensors:
		if not s.positive:
			continue
		
		for ob in s.hitObjectList:
			water.OnCollision(ob)
