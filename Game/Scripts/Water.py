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
from . import Utilities
from . import Actor
from . import ForceFields

# The angle to rotate successive ripples by (giving them a random appearance),
# in degrees.
ANGLE_INCREMENT = 81.0
# Extra spacing to bubble spawn points, in Blender units.
BUBBLE_BIAS = 0.4

DEBUG = False

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
		self.owner = owner
		owner['Water'] = self
		owner['IsWater'] = True
		
		Utilities.SetDefaultProp(self.owner, 'RippleInterval', 20)
		Utilities.SetDefaultProp(self.owner, 'DampingFactor', 0.2)
		# Colour to use as filter when camera is under water
		# (see Camera.CameraCollider)
		Utilities.SetDefaultProp(self.owner, 'VolumeCol', '#22448880')
		
		self.InstanceAngle = 0.0
		self.CurrentFrame = 0
		
		if DEBUG:
			self.floatMarker = Utilities.addObject('VectorMarker', 0)
		
		self.FloatingActors = set()
		self.ForceFields = []
		
		Utilities.parseChildren(self, owner)
		Utilities.SceneManager().Subscribe(self)
		Utilities.setState(self.owner, self.S_IDLE)
	
	def parseChild(self, child, t):
		if t == 'ForceField':
			self.ForceFields.append(ForceFields.create(child))
			return True
		else:
			return False
	
	def OnSceneEnd(self):
		self.owner['Water'] = None
		self.owner = None
		self.FloatingActors = None
		self.ForceFields = None
		Utilities.SceneManager().Unsubscribe(self)
	
	def SpawnSurfaceDecal(self, name, position):
		pos = position.copy()
		pos.z = self.owner.worldPosition.z
		
		#
		# Transform template.
		#
		elr = mathutils.Euler()
		elr.z = self.InstanceAngle
		self.InstanceAngle = self.InstanceAngle + ANGLE_INCREMENT
		oMat = elr.to_matrix()
		
		decal = Utilities.addObject(name, 0)
		decal.worldPosition = pos
		decal.worldOrientation = oMat
		decal.setParent(self.owner)
	
	def spawnBubble(self, actor):
		if self.isBubble(actor):
			return
		
		#
		# Transform template.
		#
		vec = actor.owner.getLinearVelocity(False)
		if vec.magnitude <= 0.1:
			vec = mathutils.Vector((0.0, 0.0, -1.0))
		else:
			vec.normalize()
		vec = vec * (actor.owner['FloatRadius'] + BUBBLE_BIAS)
		pos = actor.owner.worldPosition.copy()
		pos = pos - vec
		
		#
		# Create object.
		#
		bubble = Bubble(pos)
		self.FloatingActors.add(bubble)
		Utilities.setState(self.owner, self.S_FLOATING)
	
	def getSubmergedFactor(self, actor):
		'''Determine the fraction of the object that is inside the water. This
		works vertically only: if the object touches the water from the side
		(shaped water such as honey), and the centre is outside, the factor will
		be zero.'''
		
		# Cast a ray out from the actor. If it hits this water object from
		# inside, the actor is considered to be fully submerged. Otherwise, it
		# is fully emerged.
		
		origin = actor.owner.worldPosition.copy()
		origin.z = origin.z - actor.owner['FloatRadius']
		through = self.owner.worldPosition.copy()
		# Force ray to be vertical.
		through.xy = origin.xy
		through.z += 1.0
		vec = through - origin
		ob, hitPoint, normal = actor.owner.rayCast(
			through,             # to
			origin,              # from
			0.0,                 # dist
			'IsWater',           # prop
			1,                   # face
			1                    # xray
		)
		
		if ob == None:
			# No hit; object is not submerged.
			return 0.0
		
		inside = False
		if (ob):
			if normal.dot(vec) > 0.0:
				# Hit was from inside.
				inside = True
		
		depth = hitPoint.z - origin.z
		submergedFactor = depth / (actor.owner['FloatRadius'] * 2.0)
		submergedFactor = Utilities._clamp(0.0, 1.0, submergedFactor)
		
		if not inside:
			# The object is submerged, but its base is outside the water object.
			# Invert the submergedFactor, since it is the object's top that is
			# protruding into the water.
			# This must be a shaped water object (such as honey).
			submergedFactor = 1.0 - submergedFactor
		
		return submergedFactor
	
	def applyDamping(self, linV, submergedFactor):
		return Utilities._lerp(linV, Utilities.ZEROVEC, self.owner['DampingFactor'] * submergedFactor)
	
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
		body = actor.owner
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
				self.SpawnSurfaceDecal('Ripple', actor.owner.worldPosition)
				actor.Destroy()
		
		else:
			actor.setOxygen(1.0)
		
		if submergedFactor <= 0.1 and not self.isBubble(actor):
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
		linV = body.getLinearVelocity(False)
		linV.z = linV.z + accel
		linV = self.applyDamping(linV, submergedFactor)
		body.setLinearVelocity(linV, False)
		
		angV = body.getAngularVelocity(False)
		angV = self.applyDamping(angV, submergedFactor)
		body.setAngularVelocity(angV, False)
		
		if DEBUG:
			self.floatMarker.worldPosition = body.worldPosition
			self.floatMarker.localScale = Utilities.ONEVEC * accel
		
		#
		# Update buoyancy (take on water).
		#
		targetBuoyancy = (1.0 - submergedFactor) * body['Buoyancy']
		if targetBuoyancy > body['CurrentBuoyancy']:
			body['CurrentBuoyancy'] += body['SinkFactor']
		else:
			body['CurrentBuoyancy'] -= body['SinkFactor']
		
		for ff in self.ForceFields:
			ff.touched(actor, submergedFactor)
		
		return True
	
	def SpawnRipples(self, actor, force = False):
		if self.isBubble(actor):
			return
		
		ob = actor.owner
		
		if not force and 'Water_LastFrame' in ob:
			# This is at least the first time the object has touched the water.
			# Make sure it has moved a minimum distance before adding a ripple.
			if ob['Water_LastFrame'] == self.CurrentFrame:
				ob['Water_CanRipple'] = True
			
			if not ob['Water_CanRipple']:
				# The object has rippled too recently.
				return
			
			linV = ob.getLinearVelocity(False)
			if linV.magnitude < ob['MinRippleSpeed']:
				# The object hasn't moved fast enough to cause another event.
				return
		
		ob['Water_LastFrame'] = self.CurrentFrame
		ob['Water_CanRipple'] = False
		self.SpawnSurfaceDecal('Ripple', ob.worldPosition)
	
	def onCollision(self, hitActors):
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
				print("Error: tried to float dead actor", actor.name)
				self.FloatingActors.discard(actor)
				actor.removeListener(self)
		
		if len(self.FloatingActors) > 0:
			Utilities.setState(self.owner, self.S_FLOATING)
		else:
			Utilities.setState(self.owner, self.S_IDLE)
		
		#
		# Increase the frame counter.
		#
		self.CurrentFrame = ((self.CurrentFrame + 1) %
			self.owner['RippleInterval'])
	
	def actorDestroyed(self, actor):
		self.FloatingActors.discard(actor)
	
	def actorChildDetached(self, actor, oldChild):
		'''Actor's child has become a free body. Assume that it is now floating,
		and inherit the current buoyancy of its old parent.'''
		
		if actor in self.FloatingActors:
			oldChild.owner['CurrentBuoyancy'] = actor.owner['CurrentBuoyancy']
			oldChild.setOxygen(actor.getOxygen())
			self.FloatingActors.add(oldChild)
			oldChild.addListener(self)
	
	def actorAttachedToParent(self, actor, newParent):
		'''Actor has become attached to another. Re-set its buoyancy in case it
		emerges from the water while still attached to its new parent.'''
		
		actor.owner['CurrentBuoyancy'] = actor.owner['Buoyancy']
		actor.setOxygen(1.0)
		self.FloatingActors.discard(actor)
		actor.removeListener(self)
	
	def isBubble(self, actor):
		return actor.owner.name == 'Bubble'

class ShapedWater(Water):
	'''Special water that does not need to be flat.'''
	
	def __init__(self, owner):
		Water.__init__(self, owner)
	
	def applyDamping(self, linV, submergedFactor):
		return Utilities._lerp(linV, Utilities.ZEROVEC, self.owner['DampingFactor'])
	
	def spawnBubble(self, actor):
		'''No bubbles in shaped water.'''
		pass
	
	def SpawnRipples(self, actor, force = False):
		'''No ripples in shaped water: too hard to find surface.'''
		pass

class Bubble(Actor.Actor):
	def __init__(self, pos):
		owner = Utilities.addObject('Bubble', 0)
		owner.worldPosition = pos
		owner['Bubble'] = True
		Actor.Actor.__init__(self, owner)
	
	def RestoreLocation(self, reason = None):
		'''Bubbles aren't important enough to respawn. Just destroy them.'''
		self.Destroy()

@bxt.utils.owner
def createWater(o):
	'''
	Create a new Water object. The object should be perfectly flat, with all
	verices at z = 0 (localspace). Make sure the object is a Ghost.
	
	Controller properties:
	MinDist:        The distance an object has to move before it spawn a ripple.
	'''
	
	Water(o)

@bxt.utils.owner
def createShapedWater(o):
	'''
	Create a new ShapedWater object. The object does not have to be flat, but it
	has the following constraints. The object must:
	 - Have a manifold mesh with normals pointing out.
	 - Have a child outside the volume, with the property Type=ExternalTarget.
	 - Be a ghost.
	 - Detect collisions (e.g. Static mesh type).
	'''
	ShapedWater(o)

@bxt.utils.controller
def onCollision(c):
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
	# Call Water.onCollision regardless of collisions: this allows for one more
	# frame of processing to sink submerged objects.
	#
	water.onCollision(actors)
