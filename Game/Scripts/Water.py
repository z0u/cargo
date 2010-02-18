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

ANGLE_INCREMENT = 81.0

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
		scene = GameLogic.getCurrentScene()
		self.Owner = owner
		owner['Water'] = self
		
		self.InstanceAngle = 0.0
		self.BubbleTemplate = scene.objectsInactive['OB' + owner['BubbleTemplate']]
		self.RippleTemplate = scene.objectsInactive['OB' + owner['RippleTemplate']]
		self.CurrentFrame = 0
		
		self.FloatingActors = set()
		
		Utilities.SceneManager.Subscribe(self)
	
	def OnSceneEnd(self):
		self.Owner['Water'] = None
		self.Owner = None
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
		base = body.worldPosition[2] - body['FloatRadius']
		diam = body['FloatRadius'] * 2.0
		depth = self.Owner.worldPosition[2] - base
		
		submergedFactor = depth / diam
		if submergedFactor > 0.9:
			# Object is almost fully submerged. Try to cause it to drown.
			actor.setOxygen(actor.getOxygen() - body['OxygenDepletionRate'])
			if actor.getOxygen() <= 0.0:
				pos = body.worldPosition
				if actor.Drown():
					body['CurrentBuoyancy'] = body['Buoyancy']
					actor.setOxygen(1.0)
					self.SpawnSurfaceDecal(self.BubbleTemplate, pos)
					return False
		else:
			actor.setOxygen(1.0)
		
		if submergedFactor < 0.0:
			# Object has emerged.
			body['CurrentBuoyancy'] = body['Buoyancy']
			return False
		
		#
		# Object is partially submerged. Apply acceleration away from the
		# water (up). Acceleration increases linearly with the depth, until the
		# object is fully submerged.
		#
		submergedFactor = Utilities._clamp(0.0, 1.0, submergedFactor)
		accel = depth * body['CurrentBuoyancy']
		linV = Mathutils.Vector(body.getLinearVelocity(False))
		linV.z = linV.z + accel
		linV = linV - (linV * body['FloatDamp'] * submergedFactor)
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
	
	def SpawnRipples(self, actor):
		ob = actor.Owner
		
		try:
			if ob['Water_LastFrame'] == self.CurrentFrame:
				ob['Water_CanRipple'] = True
			if not ob['Water_CanRipple']:
				#
				# The object has rippled too recently.
				#
				return
			linV = Mathutils.Vector(ob.getLinearVelocity(False))
			if linV.magnitude < ob['MinRippleSpeed']:
				#
				# The object hasn't moved fast enough to cause another event.
				#
				return
		except KeyError:
			#
			# This is the first time the object has touched the water.
			# Continue; the required key will be added below.
			#
			pass
		
		ob['Water_LastFrame'] = self.CurrentFrame
		ob['Water_CanRipple'] = False
		self.SpawnSurfaceDecal(self.RippleTemplate, ob.worldPosition)
	
	def OnCollision(self, hitActors):
		'''
		Called when an object collides with the water. Creates ripples and
		causes objects to float or sink. Should only be called once per frame.
		'''
		for actor in hitActors:
			self.SpawnRipples(actor)
		
		self.FloatingActors.update(hitActors)
		for actor in self.FloatingActors.copy():
			floating = self.Float(actor)
			if not floating:
				self.FloatingActors.remove(actor)
				actor.removeListener(self)
			else:
				actor.addListener(self)
		
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
