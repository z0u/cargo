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

import GameLogic
import Mathutils
import Utilities
import Actor

# The angle to rotate successive ripples by (giving them a random appearance),
# in degrees.
ANGLE_INCREMENT = 81.0
# Extra spacing to bubble spawn points, in Blender units.
BUBBLE_BIAS = 0.4
ZAXIS = Mathutils.Vector((0.0, 0.0, 1.0))
ZERO = Mathutils.Vector((0.0, 0.0, 0.0))

class Water(Actor.ActorListener):
	S_INIT = 1
	S_IDLE = 2
	S_FLOATING = 3

	def __init__(self, owner):
		'''
		Create a water object that can respond to things touching it. The mesh
		is assumed to be a globally-aligned XY plane that passes through the
		object's origin.
		'''
		self.Owner = owner
		owner['Water'] = self
		
		Utilities.SetDefaultProp(self.Owner, 'RippleInterval', 20)
		Utilities.SetDefaultProp(self.Owner, 'DampingFactor', 0.2)
		
		self.InstanceAngle = 0.0
		self.CurrentFrame = 0
		
		scene = GameLogic.getCurrentScene()
		self.BubbleTemplate = scene.objectsInactive['OB' + self.Owner['BubbleTemplate']]
		self.RippleTemplate = scene.objectsInactive['OB' + self.Owner['RippleTemplate']]
		
		self.FloatingActors = set()
		
		Utilities.SceneManager.Subscribe(self)
	
	def OnSceneEnd(self):
		self.Owner['Water'] = None
		self.Owner = None
		self.BubbleTemplate = None
		self.RippleTemplate = None
		Utilities.SceneManager.Unsubscribe(self)
	
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
		scene.addObject(template, template)
	
	def spawnBubble(self, actor):
		global counter
		template = self.BubbleTemplate
		if actor.Owner.name == template.name:
			return
		
		#
		# Transform template.
		#
		vec = Mathutils.Vector(actor.Owner.getLinearVelocity(False))
		if vec.magnitude == 0.0:
			vec = Mathutils.Vector(0.0, 0.0, -1.0)
		else:
			vec.normalize()
		vec *= (actor.Owner['FloatRadius'] + BUBBLE_BIAS)
		pos = Mathutils.Vector(actor.Owner.worldPosition)
		pos -= vec
		template.worldPosition = pos
		
		#
		# Create object.
		#
		scene = GameLogic.getCurrentScene()
		bubOb = scene.addObject(template, template)
		bubOb['Bubble'] = True
		bubble = Actor.Actor(bubOb)
		self.FloatingActors.add(bubble)
		Utilities.setState(self.Owner, self.S_FLOATING)
	
	def getSubmergedFactor(self, actor):
		body = actor.Owner
		base = body.worldPosition[2] - body['FloatRadius']
		diam = body['FloatRadius'] * 2.0
		depth = self.Owner.worldPosition[2] - base
		return depth / diam
	
	def applyDamping(self, linV, submergedFactor):
		return Utilities._lerp(linV, ZERO, self.Owner['DampingFactor'] * submergedFactor)
	
	def Float(self, actor):
		'''
		Adjust the velocity of an object to make it float on the water.
		
		Returns: True if the object is floating; False otherwise (e.g. if it has
		sunk or emerged fully).
		'''
		#
		# Find the distance to the water from the UPPER END
		# of the object.
		#
		body = actor.Owner
		submergedFactor = self.getSubmergedFactor(actor)
		
		if submergedFactor > 0.9 and not self.isBubble(actor):
			# Object is almost fully submerged. Try to cause it to drown.
			o2 = actor.getOxygen()
			o22 = o2 - body['OxygenDepletionRate']
			actor.setOxygen(o22)
			if int(o2 * 10) != int(o22 * 10):
				self.spawnBubble(actor)
			
			if actor.getOxygen() <= 0.0:
				if actor.Drown():
					body['CurrentBuoyancy'] = body['Buoyancy']
					actor.setOxygen(1.0)
					return False
		
		elif submergedFactor < 0.9 and self.isBubble(actor):
			# Bubbles are the opposite: they lose 'oxygen' when they are not
			# fully submerged.
			actor.setOxygen(actor.getOxygen() - body['OxygenDepletionRate'])
			if actor.getOxygen() <= 0.0:
				self.SpawnSurfaceDecal(self.RippleTemplate, actor.Owner.worldPosition)
				actor.Destroy()
		
		else:
			actor.setOxygen(1.0)
		
		if submergedFactor <= 0.1:
			# Object has emerged.
			body['CurrentBuoyancy'] = body['Buoyancy']
			return False
		
		#
		# Object is partially submerged. Apply acceleration away from the
		# water (up). Acceleration increases linearly with the depth, until the
		# object is fully submerged.
		#
		submergedFactor = Utilities._clamp(0.0, 1.0, submergedFactor)
		accel = submergedFactor * body['CurrentBuoyancy']
		linV = Mathutils.Vector(body.getLinearVelocity(False))
		linV.z = linV.z + accel
		linV = self.applyDamping(linV, submergedFactor)
		body.setLinearVelocity(linV, False)
		
		#
		# Update buoyancy (take on water).
		#
		targetBuoyancy = (1.0 - submergedFactor) * body['Buoyancy']
		if targetBuoyancy > body['CurrentBuoyancy']:
			body['CurrentBuoyancy'] += body['SinkFactor']
		else:
			body['CurrentBuoyancy'] -= body['SinkFactor']
		
		return True
	
	def SpawnRipples(self, actor, force = False):
		if self.isBubble(actor):
			return
		
		ob = actor.Owner
		
		if not force and 'Water_LastFrame' in ob:
			# This is at least the first time the object has touched the water.
			# Make sure it has moved a minimum distance before adding a ripple.
			if ob['Water_LastFrame'] == self.CurrentFrame:
				ob['Water_CanRipple'] = True
			
			if not ob['Water_CanRipple']:
				# The object has rippled too recently.
				return
			
			linV = Mathutils.Vector(ob.getLinearVelocity(False))
			if linV.magnitude < ob['MinRippleSpeed']:
				# The object hasn't moved fast enough to cause another event.
				return
		
		ob['Water_LastFrame'] = self.CurrentFrame
		ob['Water_CanRipple'] = False
		self.SpawnSurfaceDecal(self.RippleTemplate, ob.worldPosition)
	
	def OnCollision(self, hitActors):
		'''
		Called when an object collides with the water. Creates ripples and
		causes objects to float or sink. Should only be called once per frame.
		'''
		for actor in hitActors:
			self.SpawnRipples(actor, False)
		
		self.FloatingActors.update(hitActors)
		for actor in self.FloatingActors.copy():
			try:
				floating = self.Float(actor)
				if not floating:
					self.FloatingActors.discard(actor)
					actor.removeListener(self)
				else:
					actor.addListener(self)
			except SystemError:
				# Shouldn't get here, but just in case!
				print "Error: tried to float dead actor", actor.name
				self.FloatingActors.discard(actor)
				actor.removeListener(self)
		
		if len(self.FloatingActors) > 0:
			Utilities.setState(self.Owner, self.S_FLOATING)
		else:
			Utilities.setState(self.Owner, self.S_IDLE)
		
		#
		# Increase the frame counter.
		#
		self.CurrentFrame = ((self.CurrentFrame + 1) %
			self.Owner['RippleInterval'])
	
	def actorDestroyed(self, actor):
		self.FloatingActors.discard(actor)
	
	def actorChildDetached(self, actor, oldChild):
		'''Actor's child has become a free body. Assume that it is now floating,
		and inherit the current buoyancy of its old parent.'''
		
		if actor in self.FloatingActors:
			oldChild.Owner['CurrentBuoyancy'] = actor.Owner['CurrentBuoyancy']
			oldChild.setOxygen(actor.getOxygen())
			self.FloatingActors.add(oldChild)
			oldChild.addListener(self)
	
	def actorAttachedToParent(self, actor, newParent):
		'''Actor has become attached to another. Re-set its buoyancy in case it
		emerges from the water while still attached to its new parent.'''
		
		actor.Owner['CurrentBuoyancy'] = actor.Owner['Buoyancy']
		actor.setOxygen(1.0)
		self.FloatingActors.discard(actor)
		actor.removeListener(self)
	
	def isBubble(self, actor):
		return 'Bubble' in actor.Owner

class Honey(Water):
	def __init__(self, owner):
		Water.__init__(self, owner)
		Utilities.parseChildren(self, owner)
	
	def parseChild(self, child, t):
		if t == 'ExternalTarget':
			self.rayTarget = child
			return True
		return False
	
	def applyDamping(self, linV, submergedFactor):
		return Utilities._lerp(linV, ZERO, self.Owner['DampingFactor'])
	
	def getSubmergedFactor(self, actor):
		'''Returns 1.0 if the centre of the actor is inside the honey; 0.0
		otherwise.'''
		
		# Cast a ray out from the actor. If it hits this honey object from
		# inside, the actor is considered to be fully submerged. Otherwise, it
		# is fully emerged.
		
		origin = Mathutils.Vector(actor.Owner.worldPosition)
		through = Mathutils.Vector(self.rayTarget.worldPosition)
		vec = Mathutils.Vector(through - origin)
		ob, _, normal = actor.Owner.rayCast(
			through,            # to
			origin,             # from
			vec.magnitude,      # dist
			'IsHoney',          # prop
			1,                  # face
			1                   # xray
		)
		
		if (ob):
			normal = Mathutils.Vector(normal)
			if (Mathutils.DotVecs(normal, vec) > 0.0):
				# Hit was from inside.
				return 1.0
			else:
				# Hit was from outside.
				return 0.0
		# No hit, therefore actor is outside.
		return 0.0
	
	def spawnBubble(self, actor):
		'''No bubbles in honey.'''
		pass
	
	def SpawnRipples(self, actor, force = False):
		'''No ripples on honey: too hard to find surface.'''
		pass

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

def CreateHoney(c):
	'''
	Create a new Honey object. The object does not have to be flat, but it has
	the following constraints. The object must:
	 - Have a manifold mesh with normals pointing out.
	 - Have a child outside the volume, with the property Type=ExternalTarget.
	 - Be a ghost.
	 - Detect collisions (e.g. Static mesh type).
	
	Controller properties:
	BubbleTemplate: The object to spawn as bubbles when another object drowns.
	                Must be on a hidden layer.
	'''
	Honey(c.owner)

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
			if not 'Actor' in ob:
				continue
			a = ob['Actor']
			if a.invalid:
				continue
			actors.add(ob['Actor'])
	
	#
	# Call Water.OnCollision regardless of collisions: this allows for one more
	# frame of processing to sink submerged objects.
	#
	water.OnCollision(actors)
