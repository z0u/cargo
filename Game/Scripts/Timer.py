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

import bge

import bxt
from . import ui

class Timer(bxt.types.BX_GameObject, bge.types.KX_GameObject):
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

	_prefix = ''

	S_RUNNING = 2

	def __init__(self, old_owner):
		'''Initialise a new timer.'''
		self.tics = 0.0
		self.targetTics = 1.0
		self.suspendStart = None
		self.set_default_prop('Message', 'TimerFinished')
		self.set_default_prop('Duration', 1.0)

	@bxt.types.expose_fun
	@bxt.utils.all_sensors_positive
	def start(self):
		'''The the timer running for the duration specified by the owner.'''
		self.tics = 0.0
		self.targetTics = self['Duration'] * bge.logic.getLogicTicRate()
		if self.targetTics < 1.0:
			self.targetTics = 1.0
		self.add_state(self.S_RUNNING)
		self.pulse()

	@bxt.types.expose_fun
	@bxt.utils.all_sensors_positive
	def stop(self):
		'''Cancel the timer. The gauge will be hidden. No message will be sent.
		'''
		self.rem_state(self.S_RUNNING)
		
		if 'Style' in self:
			gauge = ui.HUD().GetGauge(self['Style'])
			if gauge:
				gauge.Hide()

	@bxt.types.expose_fun
	@bxt.utils.all_sensors_positive
	def pulse(self):
		'''Increase the elapsed time by one tic. This must be called once per
		logic frame (i.e. by using an Always sensor in pulse mode 0).'''
		if 'Paused' in self:
			if self['Paused'] == 'Temporary':
				# Pause this frame, but resume on the next.
				self['Paused'] = 'No'
				return
			elif self['Paused'] == 'Yes':
				return
		
		self.tics = self.tics + 1.0
		fraction = self.tics / self.targetTics
		
		if 'Style' in self:
			gauge = ui.HUD().GetGauge(self['Style'])
			if gauge:
				gauge.SetFraction(1.0 - fraction)
				gauge.Show()
		
		if fraction >= 1.0:
			self.stop()
			self.OnFinished()
	
	def OnFinished(self):
		'''Called when the timer has finished normally. This usually sends the
		message specified by the 'Message' property. Override to change this
		functionality.'''
		bge.logic.sendMessage(self['Message'])
