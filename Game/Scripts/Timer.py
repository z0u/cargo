import GameLogic
import Utilities
import Actor
import time

S_RUNNING = 2

class Timer(Actor.Actor):
	def __init__(self, owner):
		Actor.Actor.__init__(self, owner)
		self.StartTime = time.time()
		self.SuspendStart = None
		Utilities.SetDefaultProp(owner, 'Message', 'TimerFinished')
	
	def Start(self):
		self.StartTime = time.time()
		Utilities.addState(self.Owner, S_RUNNING)
		print "Timer started."
		self.Pulse()

	def Stop(self):
		print "Timer stopped."
		Utilities.remState(self.Owner, S_RUNNING)

	def Pulse(self):
		if self.Suspended:
			return
		
		if time.time() > (self.StartTime + self.Owner['Duration']):
			self.Stop()
			self.OnFinished()
	
	def OnFinished(self):
		GameLogic.sendMessage(self.Owner['Message'])
	
	def OnSuspend(self):
		self.SuspendStart = time.time()
	
	def OnResume(self):
		suspendDuration = time.time() - self.SuspendStart
		self.StartTime = self.StartTime + suspendDuration

def CreateTimer(c):
	if Utilities.allSensorsPositive(c):
		Timer(c.owner)

def Start(c):
	if Utilities.allSensorsPositive(c):
		c.owner['Actor'].Start()
def Stop(c):
	if Utilities.allSensorsPositive(c):
		c.owner['Actor'].Stop()
def Pulse(c):
	if Utilities.allSensorsPositive(c):
		c.owner['Actor'].Pulse()

