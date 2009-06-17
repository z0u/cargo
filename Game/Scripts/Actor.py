'''Run this script from any object that moves. When dialogue is
displayed, registered objects will be suspended. This just stops
the main action of the level: minor animations should still play.

To kill an actor, call Actor.Destroy; don't call KX_GameObject.endObject
directly.'''

class Actor:
	'''A basic actor. Physics may be suspended, but nothing else.'''
	
	def __init__(self, owner):
		self.Owner = owner
		owner['Actor'] = self
		self.Suspended = 0
		Director.AddActor(self)
	
	def Destroy(self):
		'''Remove this actor from the scene. This destroys the actor's
		underlying KX_GameObject too.'''
		Director.RemoveActor(self)
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
			self.Owner.suspendDynamics()
			self.OnSuspend()
			self.Suspended = True
	
	def _Resume(self):
		if self.CanSuspend() and self.Suspended:
			self.Owner.restoreDynamics()
			self.OnResume()
			self.Suspended = False
	
	def Drown(self, water):
		'''Called when the Actor touches deep water.'''
		self.Owner.state = 1<<29 # state 30
		return True

def CreateActor(c):
	Actor(c.owner)

def DestroyActor(c):
	c.owner['Actor'].Destroy()

def DrownActor(c):
	c.owner['Actor'].Drown()

class StatefulActor(Actor):
	'''In addition to physics suspension, the object transitions
	to state 10 while suspended.'''

	def __init__(self, owner):
		Actor.__init__(self, owner)
		self.State = None
	
	def OnSuspend(self):
		self.State = self.Owner.state
		self.Owner.state = 1<<9 # state 10
	
	def OnResume(self):
		self.Owner.state = self.State

def CreateStatefulActor(c):
	StatefulActor(c.owner)

class _Director:
	def __init__(self):
		self.Suspended = False
		self.Actors = set()
	
	def AddActor(self, actor):
		self.Actors.add(actor)
		if self.Suspended:
			actor._Suspend()
	
	def RemoveActor(self, actor):
		self.Actors.remove(actor)
		if self.Suspended:
			actor._Resume()
	
	def SuspendAction(self):
		'''
		Suspends dynamics of each actor. Calls each actor's _Suspend function.
		'''
		if self.Suspended:
			return
		for actor in self.Actors:
			actor._Suspend()
		self.Suspended = True
	
	def ResumeAction(self):
		'''
		Resumes dynamics of each actor. Calls each actor's _Resume function.
		'''
		if not self.Suspended:
			return
		for actor in self.Actors:
			actor._Resume()
		self.Suspended = False

Director = _Director()

def SuspendAction():
	Director.SuspendAction()

def ResumeAction():
	Director.ResumeAction()
