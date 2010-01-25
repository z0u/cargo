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

class Button:
	'''A generic 3D button that can be activated by objects in the scene. No
	special object hierarchy is required. The button sends messages when it is
	touched.'''
	
	def __init__(self, owner):
		'''Create a new button and attach it to 'owner'.'''
		self.Owner = owner
		owner['Button'] = self
		self.Down = False
		Utilities.SceneManager.Subscribe(self)
	
	def OnSceneEnd(self):
		self.Owner['Button'] = None
		self.Owner = None
		Utilities.SceneManager.Unsubscribe(self)

	def Accept(self, ob):
		'''Test whether this button will react to being touched by 'ob'.
		Override this to filter out other objects.'''
		return True

	def OnTouched(self, obsTouch, obsReset):
		'''Called when this button is touched.
		
		Parameters:
		 - obsTouch: The objects touching this button.
		 - obsReset: The objects that are close enough to keep the button
		             pressed, but not close enough to push it down.'''
		down = False
		
		obs = set(obsTouch)
		if self.Down:
			obs.update(obsReset)
		
		for ob in obs:
			if self.Accept(ob):
				down = True
				break
		
		if self.Down == down:
			return
		
		self.Down = down
		if down:
			self.OnDown()
		else:
			self.OnUp()
	
	def OnDown(self):
		'''Called when at least one object has triggered this button. Sends a
		message to the scene with the subject 'ButtonDown'.'''
		GameLogic.sendMessage('ButtonDown', '', '', self.Owner.name)
	
	def OnUp(self):
		'''Called when no objects are triggering the button. Sends a message to
		the scene with the subject 'ButtonUp'. This only happens after OnDown is
		called.'''
		GameLogic.sendMessage('ButtonUp', '', '', self.Owner.name)

class ToughButton(Button):
	'''A button that filters objects by their speed: only fast objects will
	trigger this button.'''
	
	def Accept(self, ob):
		vel = Mathutils.Vector(ob.getLinearVelocity())
		print vel.magnitude 
		return vel.magnitude >= self.Owner['MinSpeed']

def CreateButton(c):
	'''Create a new generic button.'''
	Button(c.owner)

def CreateToughButton(c):
	'''Create a new tough button.'''
	ToughButton(c.owner)

def OnTouched(c):
	'''Call this when the objects touching a button change.
	
	Sensors:
	 - sTouch:      A KX_TouchSensor that indicates all the objects that are
	                touching. An object sensed here may push the button down.
	 - sTouchReset: A KX_TouchSensor that indicates are still within range, but
	                not close enough to push the button down. When this sensor
	                detects no objects, the button may be reset.'''
	s1 = c.sensors['sTouch']
	s2 = c.sensors['sTouchReset']
	c.owner['Button'].OnTouched(s1.hitObjectList, s2.hitObjectList)

