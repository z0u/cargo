import GameLogic
from Blender import Mathutils
import Utilities

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
		owner['Water'] = self
		
		self.InstanceAngle = 0.0
		self.BubbleTemplate = scene.objectsInactive['OB' + owner['BubbleTemplate']]
		self.RippleTemplate = scene.objectsInactive['OB' + owner['RippleTemplate']]
		self.MinDist = self.Owner['MinDist']
		
		self.LastHitActors = set()
	
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
	
	def Float(self, actor, hit):
		#
		# Find the distance to the water from the UPPER END
		# of the object.
		#
		body = actor.Owner
		base = body.worldPosition[2] - body['FloatRadius']
		diam = body['FloatRadius'] * 2.0
		depth = self.Owner.worldPosition[2] - base
		
		submergedFactor = depth / diam
		if hit:
			submergedFactor = Utilities._clamp(0.0, 1.0, submergedFactor)
			
			#
			# Object is partially submerged. Apply acceleration away from the
			# water (up). Acceleration increases linearly with the depth.
			#
			accel = depth * body['CurrentBuoyancy']
			linV = Mathutils.Vector(body.getLinearVelocity(False))
			linV.z = linV.z + accel
			linV = linV - (linV * body['FloatDamp'])
			body.setLinearVelocity(linV, False)
			
			#
			# Update buoyancy (take on water).
			#
			targetBuoyancy = 1.0 / ((5.0 * submergedFactor) + 1.0)
			body['CurrentBuoyancy'] = Utilities._lerp(
				body['CurrentBuoyancy'], targetBuoyancy, body['SinkFactor'])
		
		else:
			if submergedFactor < 0.5:
				#
				# Object is probably no longer touching; reset buoyancy.
				#
				body['CurrentBuoyancy'] = body['Buoyancy']
			
			else:
				#
				# Object is fully submerged. Cause it to drown.
				#
				self.SpawnSurfaceDecal(self.BubbleTemplate, body.worldPosition)
				actor.Drown()
	
	def SpawnRipples(self, actor):
		ob = actor.Owner
		pos = Mathutils.Vector(ob.worldPosition)
		
		try:
			if (pos - ob['Water_LastPos']).magnitude < self.MinDist:
				#
				# The object hasn't moved far enough to cause another event.
				#
				return
		except KeyError:
			#
			# This is the first time the object has touched the water.
			# Continue; the required key will be added below.
			#
			pass
		
		ob['Water_LastPos'] = pos
		self.SpawnSurfaceDecal(self.RippleTemplate, ob.worldPosition)
	
	def OnCollision(self, hitActors):
		'''
		Called when an object collides with the water. Creates ripples and
		causes objects to float or sink.
		'''
		for actor in hitActors:
			self.SpawnRipples(actor)
			self.Float(actor, True)
		
		for actor in (self.LastHitActors - hitActors):
			self.Float(actor, False)
		
		self.LastHitActors = hitActors

def CreateWater(c):
	'''
	Create a new Water object. The object should be perfectly flat, with all
	verices at z = 0 (localspace). Make sure the object is a Ghost.
	
	Controller properties:
	RippleTemplate: The object to spawn as a ripple on collision. Must be on a
	                hidden layer.
	BubbleTemplate: The object to spawn as bubbles when another object drowns.
	                Must be on a hidden layer.
	MinDist:        The distance an object has to move before it spawn a ripple.
	'''
	
	Water(c.owner)

def OnCollision(c):
	'''
	Respond to collisions with Actors. Ripples will be created, and 
	
	Sensors:
	<one+>: Near (e.g. Collision) sensors that detect when the water is hit by
	        an object. They should respond to any object, but only Actors will
	        be processed. Set it to positive pulse mode, f:0.
	'''
	water = c.owner['Water']
	
	#
	# Create a list of all colliding objects.
	#
	actors = set()
	for s in c.sensors:
		if not s.positive:
			continue
		for ob in s.hitObjectList:
			if ob.has_key('Actor'):
				actors.add(ob['Actor'])
	
	#
	# Call Water.OnCollision regardless of collisions: this allows for one more
	# frame of processing to sink submerged objects.
	#
	water.OnCollision(actors)
