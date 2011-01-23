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

'''Run this script from any object that moves. When dialogue is
displayed, registered objects will be suspended. This just stops
the main action of the level: minor animations should still play.

To kill an actor, call Actor.Destroy; don't call KX_GameObject.endObject
directly.'''

from . import LODTree
from . import Utilities
import bxt
import mathutils

SANITY_RAY_LENGTH = 10000

class ActorListener:
	def actorDestroyed(self, actor):
		'''Called when the actor is destroyed. See Actor.addListener and
		Actor.Destroy.'''
		pass
	
	def actorAttachedToParent(self, actor, newParent):
		'''
		Called just before the logical parent is set for the actor. The
		actual game object hierarchy may not exactly reflect this assignment.
		actor.owner will have a new parent, but it will not necessarily be
		newParent.owner: it may be any game object controlled by newParent.  
		
		Parameters:
		actor: The actor being made the child of another.
		newParent: The actor that will be the parent.
		'''
		pass
	
	def actorChildDetached(self, actor, oldChild):
		'''Called just before the actor is un-set as the parent of another.'''
		pass

	def actorHealthChanged(self, actor):
		'''Called when the health of the actor changes (e.g. when damaged).'''
		pass
	
	def actorOxygenChanged(self, actor):
		'''Called when the amount of oxygen the actor has changes (e.g. while
		under water).'''
		pass
	
	def actorRespawned(self, actor, reason):
		'''
		Called when the actor is respawned to the last safe point.
		
		Parameters:
		actor:  The actor being respawned.
		reason: A string explaining why the actor respawned, e.g. "Drowned", or
			None.
		'''
		pass

class Actor:
	'''A basic actor. Physics may be suspended, but nothing else.'''
	
	s_LocationIndex = 0
	
	def __init__(self, owner):
		self.owner = owner
		self.name = owner.name
		self.invalid = False
		
		owner['Actor'] = self
		self.Suspended = False
		Director().AddActor(self)
		
		#
		# Used to calculate the velocity on impact. Because the velocity is
		# changed by the time the impact is detected, these need to be updated
		# every frame.
		#
		self.Velocity1 = [0.0, 0.0, 0.0]
		self.Velocity2 = [0.0, 0.0, 0.0]
		
		self.Listeners = None # set
		self.AttachPoints = None # {}
		self.Children = None # set
		self.Parent = None
		
		if 'LODRadius' in owner:
			LODTree.LODManager().AddCollider(self)
		
		bxt.utils.set_default_prop(self.owner, 'Health', 1.0)
		
		#
		# Prepare the actor for floatation. This is used by Water.Water.Float.
		#
		bxt.utils.set_default_prop(self.owner, 'Oxygen', 1.0)
		bxt.utils.set_default_prop(self.owner, 'OxygenDepletionRate', 0.005)
		bxt.utils.set_default_prop(self.owner, 'Buoyancy', 1)
		bxt.utils.set_default_prop(
			self.owner, 'CurrentBuoyancy', self.owner['Buoyancy'])
		bxt.utils.set_default_prop(self.owner, 'FloatRadius', 1.1)
		bxt.utils.set_default_prop(self.owner, 'SinkFactor', 0.02)
		bxt.utils.set_default_prop(self.owner, 'MinRippleSpeed', 1.0)
		
		self.SaveLocation()
		
		Utilities.SceneManager().Subscribe(self)
	
	def AddChild(self, child, attachPoint = None, compound = True, ghost = True):
		'''
		Add a child to this actor. The child's listeners will be notified via an
		AttachedToParent event.
		
		Parameters:
		child: Another actor. Its owner will be made a child of this actor's
				owner or another object it controls (see attachPoint).
		attachPoint: The name of the object to attach to, or None to attach to
				this actor's owner.
		compound: Whether the child's bounds will be added to the attach point's
				bounds (for physics).
		ghost: False if the child should physically react to collisions.
		'''
		children = self.getChildren()
		if child in children:
			return
		children.add(child)
		child.Parent = self
		
		attachObject = self.owner
		if attachPoint != None:
			attachObject = self.getAttachPoints()[attachPoint]
		child.owner.setParent(attachObject, compound, ghost)
		for l in child.getListeners().copy():
			l.actorAttachedToParent(child, self)
	
	def RemoveChild(self, child):
		'''
		Remove a child from this actor. The child's owner will be freed from its
		parent. Listeners bound to this actor will be notified via a
		ChildDetached event.
		
		Parameters:
		child: The actor to remove from this actor's list of children. If it is
				not already a child of this actor, nothing will happen.
		'''
		children = self.getChildren()
		if not child in children:
			return
		
		children.discard(child)
		child.Parent = None
		child.owner.removeParent()
		for l in self.getListeners().copy():
			l.actorChildDetached(self, child)
	
	def OnSceneEnd(self):
		self.owner['Actor'] = None
		self.owner = None
		Utilities.SceneManager().Unsubscribe(self)
	
	def getChildren(self):
		if self.Children == None:
			self.Children = set()
		return self.Children
	
	def getAttachPoints(self):
		if self.AttachPoints == None:
			self.AttachPoints = {}
		return self.AttachPoints
	
	def getListeners(self):
		if self.Listeners == None:
			self.Listeners = set()
		return self.Listeners
	
	def addListener(self, listener):
		self.getListeners().add(listener)
	
	def removeListener(self, listener):
		self.getListeners().discard(listener)
	
	def Destroy(self):
		'''
		Remove this actor from the scene. This destroys the actor's underlying
		KX_GameObject too. All listeners will be notified by the actorDestroyed
		callback.
		
		Even after the game object (self.owner) has been destroyed, it hangs
		around for the rest of the frame. It may be passed in to other scripts
		via Near and Collision sensors. It is NOT safe to store an actor whose
		owner has been destroyed. Therefore, Actor.invalid should be checked
		before storing a reference.
		'''
		
		for child in self.getChildren():
			child.Destroy()
		
		for listener in self.getListeners().copy():
			listener.actorDestroyed(self)
		self.getListeners().clear()
		
		Director().RemoveActor(self)
		if 'LODRadius' in self.owner:
			LODTree.LODManager().RemoveCollider(self)
		self.owner.endObject()
		self.invalid = True
	
	def CanSuspend(self):
		'''Check whether the object can be suspended at this time.'''
		return True
	
	def OnSuspend(self):
		pass
	
	def OnResume(self):
		pass
	
	def _Suspend(self):
		if self.CanSuspend() and not self.Suspended:
			if not self.owner.parent:
				self.owner.suspendDynamics()
			self.OnSuspend()
			self.Suspended = True
	
	def _Resume(self):
		if self.CanSuspend() and self.Suspended:
			if not self.owner.parent:
				self.owner.restoreDynamics()
			self.OnResume()
			self.Suspended = False
	
	def Drown(self):
		'''
		Called when the Actor is fully submerged in water, and its Oxigen
		property reaches zero.
		
		Returns: True iff the actor drowned.
		'''
		if self.Parent != None:
			return False
		
		self.restore_location("You drowned! Try again.")
		self.damage(1.0, shock = False)
		return True
	
	def OnMovementImpulse(self, fwd, back, left, right):
		'''
		Called when the actor should move forward, e.g. when the user presses
		the up arrow. Usually only happens when the Actor is the the main
		subject of game play. This will be called once per frame, even if all
		inputs are False.
		
		Parameters:
		fwd:   True if the actor should move forward. If back is True, the net
		       movement should be zero.
		back:  True if the actor should move backward. If fwd is True, the net
		       movement should be zero.
		left:  True if the actor should move left. If right is True, the net
		       movement should be zero.
		right: True if the actor should move right. If left is True, the net
		       movement should be zero.
		'''
		pass
	
	def OnButton1(self, positive, triggered):
		pass
		
	def OnButton2(self, positive, triggered):
		pass
	
	def SaveLocation(self):
		'''Save the location of the owner for later. This may happen when the
		object touches a safe point.'''
		self.Pos = self.owner.worldPosition
		self.Orn = self.owner.worldOrientation
		for child in self.getChildren():
			child.SaveLocation()
	
	def restore_location(self, reason = None):
		self.owner.worldPosition = self.Pos
		self.owner.worldOrientation = self.Orn
		self.owner.setLinearVelocity(bxt.math.MINVECTOR)
		self.owner.setAngularVelocity(bxt.math.MINVECTOR)
		
		for l in self.getListeners().copy():
			l.actorRespawned(self, reason)
	
	def RecordVelocity(self):
		'''Store the velocity of this object for one frame. See
		GetLastLinearVelocity.'''
		self.Velocity2 = self.Velocity1
		self.Velocity1 = self.owner.getLinearVelocity()
	
	def GetLastLinearVelocity(self):
		'''Get the second-last velocity of this actor. This is useful in touch
		handlers, because the object's energy is absorbed by the time the
		handler is called.'''
		return self.Velocity2
	
	def getHealth(self):
		return self.owner['Health']
	
	def setHealth(self, value):
		self.owner['Health'] = value
		for l in self.getListeners().copy():
			l.actorHealthChanged(self)
		print(self.owner['Health'])
	
	def damage(self, amount, shock):
		self.setHealth(self.getHealth() - amount)
	
	def getOxygen(self):
		return self.owner['Oxygen']
	
	def setOxygen(self, value):
		self.owner['Oxygen'] = value
		for l in self.getListeners().copy():
			l.actorOxygenChanged(self)
	
	def isInsideWorld(self):
		'''
		Make sure the actor is in a sensible place. This searches for objects
		with the 'Ground' property directly above and directly below the actor.
		A free actor is considered to be outside the world if:
		 - No ground is found.
		 - Ground is found but the actor is on the wrong side of it, i.e. the
		   surface normal is facing away from the actor.
		Otherwise, the actor is inside the world.
		
		If the actor is the child of another, or if its owner is the child of
		another KX_GameObject, it is always considered to be inside the world.
		
		Returns True if the object seems to be inside the world; False
		otherwise.
		'''
		if self.Parent != None or self.owner.parent != None:
			# Responsibility delegated to parent.
			return True
		
		foundGround = False
		outsideGround = True
		
		# First, look up.
		origin = mathutils.Vector(self.owner.worldPosition)
		vec = bxt.math.ZAXIS.copy()
		through = origin + vec
		ob, _, normal = self.owner.rayCast(
			through,             # to
			origin,              # from
			SANITY_RAY_LENGTH,   # dist
			'Ground',            # prop
			1,                   # face
			1                    # xray
		)
		
		if ob != None:
			# Found some ground. Are we outside of it?
			foundGround = True
			if (ob):
				normal = mathutils.Vector(normal)
				if normal.dot(vec) > 0.0:
					# Hit was from inside.
					outsideGround = False
		
		# Now look down.
		vec = bxt.math.ZAXIS.copy()
		vec.negate()
		through = origin + vec
		ob, _, normal = self.owner.rayCast(
			through,             # to
			origin,              # from
			SANITY_RAY_LENGTH,   # dist
			'Ground',            # prop
			1,                   # face
			1                    # xray
		)
		
		if ob != None:
			# Found some ground. Are we outside of it?
			foundGround = True
			if (ob):
				normal = mathutils.Vector(normal)
				if normal.dot(vec) > 0.0:
					# Hit was from inside.
					outsideGround = False
		
		return foundGround and outsideGround
	
	def getTouchedObject(self):
		return None
	
	def useLocalCoordinates(self):
		'''True if the actor's local coordinates are meaningful to other systems
		such as the camera.'''
		return False
	
	def getCloseCamera(self):
		'''Returns the camera that should be used in 'close' mode, or None if
		the actor doesn't define one.'''
		return None

@bxt.utils.owner
def CreateActor(o):
	o['Actor'] = Actor(o)

@bxt.utils.owner
def DestroyActor(o):
	o['Actor'].Destroy()

@bxt.utils.owner
def SaveLocation(o):
	o['Actor'].SaveLocation()

@bxt.utils.owner
def restore_location(o):
	o['Actor'].restore_location()

@bxt.utils.controller
def Damage(c):
	print("damaged")
	for s in c.sensors:
		if (not s.positive) or (not s.triggered):
			continue
		shock = False
		if 'Shock' in s.owner:
			shock = s.owner['Shock'] == True
		for o in s.hitObjectList:
			if 'Actor' in o:
				o['Actor'].damage(c.owner['Damage'], shock)

class StatefulActor(Actor):
	'''In addition to physics suspension, the object transitions
	to state 10 while suspended.'''

	def __init__(self, owner):
		Actor.__init__(self, owner)
		self.State = None
	
	def OnSuspend(self):
		self.State = self.owner.state
		bxt.utils.set_state(self.owner, 10)
	
	def OnResume(self):
		self.owner.state = self.State

@bxt.utils.owner
def CreateStatefulActor(o):
	StatefulActor(o)

class DirectorListener:
	def directorMainCharacterChanged(self, oldActor, newActor):
		'''
		Called immediately after the main subject (i.e. the actor receiving user
		input) changes.
		
		Parameters:
		oldActor: The previous main subject. May be None.
		newActor: The new main subject. May be None.
		'''
		pass

@bxt.types.singleton()
class Director:
	def __init__(self):
		self.Suspended = False
		self.InputSuspended = False
		self.Actors = set()
		self.MainCharacter = None
		self.SanityCheckIndex = 0
		
		self.Listeners = set()
	
	def addListener(self, listener):
		self.Listeners.add(listener)
	
	def removeListener(self, listener):
		self.Listeners.discard(listener)
	
	def AddActor(self, actor):
		if actor in self.Actors:
			return
		
		self.Actors.add(actor)
		
		if self.Suspended:
			actor._Suspend()
	
	def RemoveActor(self, actor):
		if not actor in self.Actors:
			return
		
		self.Actors.discard(actor)
		
		if self.MainCharacter == actor:
			self.setMainCharacter(None)
		if self.Suspended:
			actor._Resume()
	
	def SuspendAction(self):
		'''Suspends dynamics of each actor. Calls each actor's _Suspend
		function.'''
		if self.Suspended:
			return
		for actor in self.Actors:
			actor._Suspend()
		self.Suspended = True
	
	def ResumeAction(self):
		'''Resumes dynamics of each actor. Calls each actor's _Resume function.
		'''
		if not self.Suspended:
			return
		for actor in self.Actors:
			actor._Resume()
		self.Suspended = False
	
	def getMainCharacter(self):
		return self.MainCharacter
	
	def setMainCharacter(self, actor):
		oldMainSubject = self.MainCharacter
		self.MainCharacter = actor
		for l in self.Listeners.copy():
			l.directorMainCharacterChanged(oldMainSubject, actor)
	
	def SuspendUserInput(self):
		self.InputSuspended = True
	
	def ResumeUserInput(self):
		self.InputSuspended = False
	
	def Update(self):
		'''Update the state of all the actors.'''
		if self.SanityCheckIndex >= len(self.Actors):
			self.SanityCheckIndex = 0
		
		i = 0
		for actor in self.Actors.copy():
			if actor == self.MainCharacter or i == self.SanityCheckIndex:
				if not actor.isInsideWorld():
					print("Actor %s was outside world!" % actor.name)
					actor.restore_location("Ouch! You got squashed.")
			
			actor.RecordVelocity()
			i += 1
		
		self.SanityCheckIndex += 1
	
	def OnMovementImpulse(self, fwd, back, left, right):
		if self.MainCharacter and not self.InputSuspended:
			self.MainCharacter.OnMovementImpulse(fwd, back, left, right)
	
	def OnButton1(self, positive, triggered):
		if self.MainCharacter and not self.InputSuspended:
			self.MainCharacter.OnButton1(positive, triggered)
		
	def OnButton2(self, positive, triggered):
		if self.MainCharacter and not self.InputSuspended:
			self.MainCharacter.OnButton2(positive, triggered)

def Update():
	'''Call this once per frame to allow the Director to update the state of its
	Actors.'''
	Director().Update()

def SuspendAction():
	Director().SuspendAction()

def ResumeAction():
	Director().ResumeAction()

@bxt.utils.controller
def _hitMainCharacter(c):
	'''
	Test whether the main character was hit.
	
	Sensors:
	<any>: Any touch sensors attached to this controller will be used to look
		for the main character.
	
	@return: True if the main character is hit; False otherwise.
	'''
	for s in c.sensors:
		if not hasattr(s, 'hitObjectList'):
			continue
		for o in s.hitObjectList:
			if 'Actor' in o:
				actor = o['Actor']
				if Director().getMainCharacter() == actor:
					return True
	return False

#
# Methods for dealing with user input.
#
@bxt.utils.controller
def OnImpulse(c):
	fwd = c.sensors['sForward']
	back = c.sensors['sBackward']
	left = c.sensors['sLeft']
	right = c.sensors['sRight']
	btn1 = c.sensors['sButton1']
	btn2 = c.sensors['sButton2']
	Director().OnMovementImpulse(fwd.positive, back.positive, left.positive,
		right.positive)
	Director().OnButton1(btn1.positive, btn1.triggered)
	Director().OnButton2(btn2.positive, btn2.triggered)

def isTouchingMainCharacter(touchSensor):
	for o in touchSensor.hitObjectList:
		if 'Actor' in o:
			a = o['Actor']
			if a == Director().getMainCharacter():
				return True
	return False
