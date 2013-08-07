#
# Copyright 2009-2011 Alex Fraser <alex@phatcore.com>
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
import mathutils

import bat.bats

class Button(bat.bats.BX_GameObject, bge.types.KX_GameObject):
	'''A generic 3D button that can be activated by objects in the scene. No
	special object hierarchy is required. The button sends messages when it is
	touched.'''

	_prefix = 'btn_'

	def __init__(self, old_owner):
		self.down = False

	def accept(self, ob):
		'''Test whether this button will react to being touched by 'ob'.
		Override this to filter out other objects.'''
		return True

	@bat.bats.expose
	def on_touched(self):
		'''Called when this button is touched.

		Parameters:
		 - obsTouch: The objects touching this button.
		 - obsReset: The objects that are close enough to keep the button
		             pressed, but not close enough to push it down.'''

		c = bge.logic.getCurrentController()
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
		bge.logic.sendMessage('ButtonDown', '', '', self.name)

	def on_up(self):
		'''Called when no objects are triggering the button. Sends a message to
		the scene with the subject 'ButtonUp'. This only happens after on_down is
		called.'''
		bge.logic.sendMessage('ButtonUp', '', '', self.name)

class ToughButton(Button):
	'''A button that filters objects by their speed: only fast objects will
	trigger this button. This button only works with Actors.'''

	def accept(self, ob):
		try:
			vel = mathutils.Vector(ob.lastLinV)
			return vel.magnitude >= self['MinSpeed']
		except AttributeError:
			return False
