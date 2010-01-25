import GameLogic
import Utilities
import Actor
import UI

S_RUNNING = 2

class Timer(Actor.Actor):
	def __init__(self, owner):
		Actor.Actor.__init__(self, owner)
		self.Tics = 0.0
		self.TargetTics = 1.0
		self.SuspendStart = None
		Utilities.SetDefaultProp(owner, 'Message', 'TimerFinished')
	
	def Start(self):
		self.Tics = 0.0
		self.TargetTics = self.Owner['Duration'] * GameLogic.getLogicTicRate()
		if self.TargetTics < 1.0:
			self.TargetTics = 1.0
		Utilities.addState(self.Owner, S_RUNNING)
		self.Pulse()

	def Stop(self):
		Utilities.remState(self.Owner, S_RUNNING)
		gauge = UI.HUD.GetGauge(self.Owner['Style'])
		if gauge:
			gauge.Hide()

	def Pulse(self):
		if self.Suspended:
			return
		
		gauge = UI.HUD.GetGauge(self.Owner['Style'])
		self.Tics = self.Tics + 1.0
		fraction = self.Tics / self.TargetTics
		if gauge:
			gauge.SetFraction(1.0 - fraction)
			gauge.Show()
		if fraction >= 1.0:
			self.Stop()
			self.OnFinished()
	
	def OnFinished(self):
		GameLogic.sendMessage(self.Owner['Message'])

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
	'''Advance the timer by one logic tic. This must be called once per frame
	while the timer is active.'''
	if Utilities.allSensorsPositive(c):
		c.owner['Actor'].Pulse()

