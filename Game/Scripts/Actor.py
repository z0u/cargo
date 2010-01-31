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

class Actor:
	'''A basic actor. Physics may be suspended, but nothing else.'''
	
	def __init__(self, owner):
		self.Owner = owner
		owner['Actor'] = self
		self.Suspended = False
		Director.AddActor(self)
		self.Velocity1 = [0.0, 0.0, 0.0]
		self.Velocity2 = [0.0, 0.0, 0.0]
		if owner.has_key('LODRadius'):
			LODTree.LODManager.AddCollider(self)
		
		#
		# Prepare the actor for floatation. This is used by Water.Water.Float.
		#
		Utilities.SetDefaultProp(self.Owner, 'Buoyancy', 0.1)
		Utilities.SetDefaultProp(
			self.Owner, 'CurrentBuoyancy', self.Owner['Buoyancy'])
		Utilities.SetDefaultProp(self.Owner, 'FloatRadius', 1.1)
		Utilities.SetDefaultProp(self.Owner, 'FloatDamp', 0.1)
		Utilities.SetDefaultProp(self.Owner, 'SinkFactor', 0.01)
		Utilities.SetDefaultProp(self.Owner, 'MinRippleSpeed', 1.0)
		
		self.SaveLocation()
		
		Utilities.SceneManager.Subscribe(self)
	
	def OnSceneEnd(self):
		self.Owner['Actor'] = None
		self.Owner = None
		Utilities.SceneManager.Unsubscribe(self)
	
	def Destroy(self):
		'''Remove this actor from the scene. This destroys the actor's
		underlying KX_GameObject too.'''
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

class _Director:
	def __init__(self):
		self.Suspended = False
		self.InputSuspended = False
		self.Actors = set()
		self.MainSubject = None
	
	def AddActor(self, actor):
		self.Actors.add(actor)
		if self.Suspended:
			actor._Suspend()
	
	def RemoveActor(self, actor):
		self.Actors.remove(actor)
		if self.MainSubject == actor:
			self.MainSubject = None
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
	
	def SetMainSubject(self, actor):
		self.MainSubject = actor
	
	def SuspendUserInput(self):
		self.InputSuspended = True
	
	def ResumeUserInput(self):
		self.InputSuspended = False
	
	def Update(self):
		'''Update the state of all the actors.'''
		for actor in self.Actors:
			actor.RecordVelocity()
	
	def OnMovementImpulse(self, fwd, back, left, right):
		if self.MainSubject and not self.InputSuspended:
			self.MainSubject.OnMovementImpulse(fwd, back, left, right)
	
	def OnButton1(self, positive, triggered):
		if self.MainSubject and not self.InputSuspended:
			self.MainSubject.OnButton1(positive, triggered)
		
	def OnButton2(self, positive, triggered):
		if self.MainSubject and not self.InputSuspended:
			self.MainSubject.OnButton2(positive, triggered)

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

