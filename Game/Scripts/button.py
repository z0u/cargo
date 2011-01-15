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
import mathutils
from . import Utilities
import bxt

@bxt.types.gameobject('on_touched', prefix='btn_')
class Button(bxt.types.ProxyGameObject):
	'''A generic 3D button that can be activated by objects in the scene. No
	special object hierarchy is required. The button sends messages when it is
	touched.'''
	
	def __init__(self, owner):
		'''Create a new button and attach it to 'owner'.'''
		bxt.types.ProxyGameObject.__init__(self, owner)
		self.down = False

	def accept(self, ob):
		'''Test whether this button will react to being touched by 'ob'.
		Override this to filter out other objects.'''
		return True

	def on_touched(self):
		'''Called when this button is touched.
		
		Parameters:
		 - obsTouch: The objects touching this button.
		 - obsReset: The objects that are close enough to keep the button
		             pressed, but not close enough to push it down.'''

		c = logic.getCurrentController()
		obsTouch = c.sensors['sTouch'].hitObjectList
		obsReset = c.sensors['sTouchReset'].hitObjectList

		down = False
		
		obs = set(obsTouch)
		if self.down:
			obs.update(obsReset)
		
		for ob in obs:
			if self.accept(ob):
				down = True
				break
		
		if self.down == down:
			return
		
		self.down = down
		if down:
			self.on_down()
		else:
			self.on_up()
	
	def on_down(self):
		'''Called when at least one object has triggered this button. Sends a
		message to the scene with the subject 'ButtonDown'.'''
		logic.sendMessage('ButtonDown', '', '', self.name)
	
	def on_up(self):
		'''Called when no objects are triggering the button. Sends a message to
		the scene with the subject 'ButtonUp'. This only happens after on_down is
		called.'''
		logic.sendMessage('ButtonUp', '', '', self.name)

@bxt.types.gameobject()
class ToughButton(Button):
	'''A button that filters objects by their speed: only fast objects will
	trigger this button. This button only works with Actors.'''
	
	def accept(self, ob):
		if 'Actor' not in ob:
			return False
		
		actor = ob['Actor']
		vel = mathutils.Vector(actor.GetLastLinearVelocity())
		return vel.magnitude >= self['MinSpeed']
