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

from bge import logic
from . import Utilities
from . import Actor
from . import UI

class Timer(Actor.Actor):
	'''A countdown timer actor. Uses a regular pulse to count down to zero over
	a given duration. The remaining time may be shown on a gauge on-screen.
	
	Owner properties:
	 - Message: The subject of the message that will be sent to other objects
	            when the time is up. Defaults to 'TimerFinished' if not
	            specified.
	 - Duration: The time in seconds that the timer will run for.
	 - Style:   The name of the gauge to show in the UI. If this property is not
	            present, or if the gauge can't be found, no gauge will be shown.
	            The related property on the gauge is called 'Name'.
	
	Hierarchy:
	 - Owner: The base of the timer.
	'''
	
	S_RUNNING = 2

	def __init__(self, owner):
		'''Initialise a new timer.'''
		Actor.Actor.__init__(self, owner)
		self.Tics = 0.0
		self.TargetTics = 1.0
		self.SuspendStart = None
		Utilities.SetDefaultProp(owner, 'Message', 'TimerFinished')
	
	def Start(self):
		'''The the timer running for the duration specified by the owner.'''
		self.Tics = 0.0
		self.TargetTics = self.owner['Duration'] * logic.getLogicTicRate()
		if self.TargetTics < 1.0:
			self.TargetTics = 1.0
		Utilities.addState(self.owner, self.S_RUNNING)
		self.Pulse()

	def Stop(self):
		'''Cancel the timer. The gauge will be hidden. No message will be sent.
		'''
		Utilities.remState(self.owner, self.S_RUNNING)
		
		if 'Style' in self.owner:
			gauge = UI.HUD.GetGauge(self.owner['Style'])
			if gauge:
				gauge.Hide()

	def Pulse(self):
		'''Increase the elapsed time by one tic. This must be called once per
		logic frame (i.e. by using an Always sensor in pulse mode 0).'''
		if self.Suspended:
			return
		
		if 'Paused' in self.owner:
			if self.owner['Paused'] == 'Temporary':
				# Pause this frame, but resume on the next.
				self.owner['Paused'] = 'No'
				return
			elif self.owner['Paused'] == 'Yes':
				return
		
		self.Tics = self.Tics + 1.0
		fraction = self.Tics / self.TargetTics
		
		if 'Style' in self.owner:
			gauge = UI.HUD.GetGauge(self.owner['Style'])
			if gauge:
				gauge.SetFraction(1.0 - fraction)
				gauge.Show()
		
		if fraction >= 1.0:
			self.Stop()
			self.OnFinished()
	
	def OnFinished(self):
		'''Called when the timer has finished normally. This usually sends the
		message specified by the 'Message' property. Override to change this
		functionality.'''
		logic.sendMessage(self.owner['Message'])

def CreateTimer(c):
	'''Create a new timer from this controller's owner.'''
	if Utilities.allSensorsPositive(c):
		Timer(c.owner)

def Start(c):
	'''Start the timer that is attached to this controller.'''
	if Utilities.allSensorsPositive(c):
		c.owner['Actor'].Start()
def Stop(c):
	'''Cancel the timer that is attached to this controller.'''
	if Utilities.allSensorsPositive(c):
		c.owner['Actor'].Stop()
def Pulse(c):
	'''Advance the timer by one logic tic. This must be called once per logic
	frame while the timer is active.'''
	if Utilities.allSensorsPositive(c):
		c.owner['Actor'].Pulse()

