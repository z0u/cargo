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

'''Run this script from any object that moves. When dialogue is
displayed, registered objects will be suspended. This just stops
the main action of the level: minor animations should still play.

To kill an actor, call Actor.Destroy; don't call KX_GameObject.endObject
directly.'''

import LODTree
import Utilities

class ActorListener:
	def actorDestroyed(self, actor):
		'''Called when the actor is destroyed. See Actor.addListener and
		Actor.Destroy.'''
		pass
	
	def actorAttachedToParent(self, actor, newParent):
		'''
		Called just before the logical parent is set for the actor. The
		actual game object hierarchy may not exactly reflect this assignment.
		actor.Owner will have a new parent, but it will not necessarily be
		newParent.Owner: it may be any game object controlled by newParent.  
		
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

class Actor:
	'''A basic actor. Physics may be suspended, but nothing else.'''
	
	def __init__(self, owner):
		self.Owner = owner
		owner['Actor'] = self
		self.Suspended = False
		Director.AddActor(self)
		
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
		
		if owner.has_key('LODRadius'):
			LODTree.LODManager.AddCollider(self)
		
		#
		# Prepare the actor for floatation. This is used by Water.Water.Float.
		#
		Utilities.SetDefaultProp(self.Owner, 'Oxygen', 1.0)
		Utilities.SetDefaultProp(self.Owner, 'OxygenDepletionRate', 0.005)
		Utilities.SetDefaultProp(self.Owner, 'Buoyancy', 0.5)
		Utilities.SetDefaultProp(
			self.Owner, 'CurrentBuoyancy', self.Owner['Buoyancy'])
		Utilities.SetDefaultProp(self.Owner, 'FloatRadius', 1.1)
		Utilities.SetDefaultProp(self.Owner, 'FloatDamp', 0.2)
		Utilities.SetDefaultProp(self.Owner, 'SinkFactor', 0.01)
		Utilities.SetDefaultProp(self.Owner, 'MinRippleSpeed', 1.0)
		
		self.SaveLocation()
		
		Utilities.SceneManager.Subscribe(self)
	
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
		ghost: Whether the child should physically react to collisions.
		'''
		children = self.getChildren()
		if child in children:
			return
		children.add(child)
		
		attachObject = self.Owner
		if attachPoint != None:
			attachObject = self.getAttachPoints()[attachPoint]
		child.Owner.setParent(attachObject, compound, ghost)
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
		child.Owner.removeParent()
		for l in self.getListeners().copy():
			l.actorChildDetached(self, child)
	
	def OnSceneEnd(self):
		self.Owner['Actor'] = None
		self.Owner = None
		Utilities.SceneManager.Unsubscribe(self)
	
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
		'''Remove this actor from the scene. This destroys the actor's
		underlying KX_GameObject too.'''
		for listener in self.getListeners().copy():
			listener.actorDestroyed(self)
		self.getListeners().clear()
		
		Director.RemoveActor(self)
		if self.Owner.has_key('LODRadius'):
			LODTree.LODManager.RemoveCollider(self)
		self.Owner.endObject()
	
	def CanSuspend(self):
		'''Check whether the object can be suspended at this time.'''
		return True
	
	def OnSuspend(self):
		pass
	
	def OnResume(self):
		pass
	
	def _Suspend(self):
		if self.CanSuspend() and not self.Suspended:
			if not self.Owner.parent:
				self.Owner.suspendDynamics()
			self.OnSuspend()
			self.Suspended = True
	
	def _Resume(self):
		if self.CanSuspend() and self.Suspended:
			if not self.Owner.parent:
				self.Owner.restoreDynamics()
			self.OnResume()
			self.Suspended = False
	
	def Drown(self):
		'''
		Called when the Actor is fully submerged in water.
		
		Returns: True iff the actor drowned.
		'''
		self.RestoreLocation()
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
		self.Pos = self.Owner.worldPosition
		self.Orn = self.Owner.worldOrientation
	
	def RestoreLocation(self):
		self.Owner.worldPosition = self.Pos
		self.Owner.worldOrientation = self.Orn
		self.Owner.setLinearVelocity(Utilities.ALMOST_ZERO)
		self.Owner.setAngularVelocity(Utilities.ALMOST_ZERO)
	
	def RecordVelocity(self):
		'''Store the velocity of this object for one frame. See
		GetLastLinearVelocity.'''
		self.Velocity2 = self.Velocity1
		self.Velocity1 = self.Owner.getLinearVelocity()
	
	def GetLastLinearVelocity(self):
		'''Get the second-last velocity of this actor. This is useful in touch
		handlers, because the object's energy is absorbed by the time the
		handler is called.'''
		return self.Velocity2
	
	def getHealth(self):
		return self.Health
	
	def setHealth(self, value):
		self.Health = value
		for l in self.getListeners().copy():
			l.actorHealthChanged(self)
	
	def getOxygen(self):
		return self.Owner['Oxygen']
	
	def setOxygen(self, value):
		self.Owner['Oxygen'] = value
		for l in self.getListeners().copy():
			l.actorOxygenChanged(self)

def CreateActor(c):
	c.owner['Actor'] = Actor(c.owner)

def DestroyActor(c):
	c.owner['Actor'].Destroy()

def SaveLocation(c):
	c.owner['Actor'].SaveLocation()

def RestoreLocation(c):
	c.owner['Actor'].RestoreLocation()

class StatefulActor(Actor):
	'''In addition to physics suspension, the object transitions
	to state 10 while suspended.'''

	def __init__(self, owner):
		Actor.__init__(self, owner)
		self.State = None
	
	def OnSuspend(self):
		self.State = self.Owner.state
		Utilities.setState(self.Owner, 10)
	
	def OnResume(self):
		self.Owner.state = self.State

def CreateStatefulActor(c):
	StatefulActor(c.owner)

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

class _Director:
	def __init__(self):
		self.Suspended = False
		self.InputSuspended = False
		self.Actors = set()
		self.MainCharacter = None
		
		self.Listeners = set()
	
	def addListener(self, listener):
		self.Listeners.add(listener)
	
	def removeListener(self, listener):
		self.Listeners.discard(listener)
	
	def AddActor(self, actor):
		self.Actors.add(actor)
		if self.Suspended:
			actor._Suspend()
	
	def RemoveActor(self, actor):
		self.Actors.remove(actor)
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
		for actor in self.Actors:
			actor.RecordVelocity()
	
	def OnMovementImpulse(self, fwd, back, left, right):
		if self.MainCharacter and not self.InputSuspended:
			self.MainCharacter.OnMovementImpulse(fwd, back, left, right)
	
	def OnButton1(self, positive, triggered):
		if self.MainCharacter and not self.InputSuspended:
			self.MainCharacter.OnButton1(positive, triggered)
		
	def OnButton2(self, positive, triggered):
		if self.MainCharacter and not self.InputSuspended:
			self.MainCharacter.OnButton2(positive, triggered)

Director = _Director()

def Update(c):
	'''Call this once per frame to allow the Director to update the state of its
	Actors.'''
	Director.Update()

def SuspendAction():
	Director.SuspendAction()

def ResumeAction():
	Director.ResumeAction()

#
# Methods for dealing with user input.
#
def OnImpulse(c):
	fwd = c.sensors['sForward']
	back = c.sensors['sBackward']
	left = c.sensors['sLeft']
	right = c.sensors['sRight']
	btn1 = c.sensors['sButton1']
	btn2 = c.sensors['sButton2']
	Director.OnMovementImpulse(fwd.positive, back.positive, left.positive,
		right.positive)
	Director.OnButton1(btn1.positive, btn1.triggered)
	Director.OnButton2(btn2.positive, btn2.triggered)

