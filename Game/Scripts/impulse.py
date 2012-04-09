#
# Copyright 2012 Alex Fraser <alex@phatcore.com>
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

import bxt

class Input(metaclass=bxt.types.Singleton):
	_prefix = ""

	def __init__(self):
		self.handlers = bxt.types.SafeList()

		# Acquire movement from a 2D directional pad.
		self.dp_move = DPad2D("Movement")

		# The switch command can be "next" or "previous"; use a 1D pad to filter
		# out multiple conflicting button presses.
		self.dp_switch = DPad1D("Switch")

		# Standard buttons.
		self.btn1 = Button("1")
		self.btn2 = Button("2")
		self.btn_cam = Button("Camera")

		self.buttons = [self.dp_move, self.btn1, self.btn2, self.dp_switch,
				self.btn_cam]

		self.load_config()

	@bxt.types.expose
	@bxt.utils.controller_cls
	def process(self, c):
		#joy_axis = c.sensors['Joystick_axis']
		#joy_btn = c.sensors['Joystick_btn']

		for btn in self.buttons:
			btn.update()

		# Run through the handlers separately for each event type, because a
		# handler may accept some events and not others.

		# Movement
		for h in self.handlers:
			if h.handle_movement(self.dp_move):
				# This handler has claimed ownership, so stop processing.
				break

		# Inventory switch
		for h in self.handlers:
			if h.handle_switch(self.dp_switch):
				break

		# Other buttons
		for h in self.handlers:
			if h.handle_bt_1(self.btn1):
				break
		for h in self.handlers:
			if h.handle_bt_2(self.btn2):
				break
		for h in self.handlers:
			if h.handle_bt_camera(self.btn_cam):
				break

	def load_config(self):
		self.dp_move.up.keyboard_keys.append(bge.events.UPARROWKEY)
		self.dp_move.up.keyboard_keys.append(bge.events.WKEY)
		self.dp_move.down.keyboard_keys.append(bge.events.DOWNARROWKEY)
		self.dp_move.down.keyboard_keys.append(bge.events.SKEY)
		self.dp_move.left.keyboard_keys.append(bge.events.LEFTARROWKEY)
		self.dp_move.left.keyboard_keys.append(bge.events.AKEY)
		self.dp_move.right.keyboard_keys.append(bge.events.RIGHTARROWKEY)
		self.dp_move.right.keyboard_keys.append(bge.events.DKEY)

		self.dp_switch.next.keyboard_keys.append(bge.events.EKEY)
		self.dp_switch.prev.keyboard_keys.append(bge.events.QKEY)

		self.btn1.keyboard_keys.append(bge.events.SPACEKEY)
		self.btn1.keyboard_keys.append(bge.events.ENTERKEY)
		self.btn2.keyboard_keys.append(bge.events.XKEY)
		self.btn_cam.keyboard_keys.append(bge.events.CKEY)

	def add_handler(self, handler):
		self.handlers.insert(0, handler)

	def remove_handler(self, handler):
		self.handlers.remove(handler)

class Button:
	def __init__(self, name):
		self.name = name
		self.keyboard_keys = []
		#self.joystick_buttons = []

		self.positive = False
		self.triggered = False

	def update(self):
		positive = False
		for key in self.keyboard_keys:
			if key in bge.logic.keyboard.active_events:
				positive = True
				break

		if positive != self.positive:
			self.triggered = True
			self.positive = positive
		else:
			self.triggered = False

	def __str__(self):
		return "Button %s - positive: %s, triggered: %s" % (self.name, 
				self.positive, self.triggered)

class DPad1D:
	'''
	Accumulates directional input (one dimension).
	'''

	def __init__(self, name):
		self.name = name
		self.next = Button("next")
		self.prev = Button("prev")
		self.direction = 0.0
		self.triggered = False

	def update(self):
		self.next.update()
		self.prev.update()

		x = 0.0
		if self.next.positive:
			x += 1.0
		if self.prev.positive:
			x -= 1.0

		self.direction = x
		self.triggered = self.next.triggered or self.prev.triggered

	def __str__(self):
		return "Button %s - direction: %s" % (self.name, self.direction)

class DPad2D:
	'''
	Accumulates directional input (two dimensions) - from directional pads,
	joysticks, and nominated keyboard keys.
	'''

	def __init__(self, name):
		self.name = name
		self.up = Button("up")
		self.down = Button("down")
		self.left = Button("left")
		self.right = Button("right")
		self.direction = mathutils.Vector((0.0, 0.0))
		self.triggered = False

	def update(self):
		self.up.update()
		self.down.update()
		self.left.update()
		self.right.update()

		y = 0.0
		if self.up.positive:
			y += 1.0
		if self.down.positive:
			y -= 1.0

		x = 0.0
		if self.right.positive:
			x += 1.0
		if self.left.positive:
			x -= 1.0

		self.direction.x = x
		self.direction.y = y
		self.triggered = (self.up.triggered or self.down.triggered or
				self.left.triggered or self.right.triggered)

	def __str__(self):
		return "Button %s - direction: %s" % (self.name, self.direction)

class Handler:
	def handle_movement(self, state):
		'''
		Handle a movement request from the user.
		@param direction: The direction to move in (2D vector; +y is up).
		@return: True if the input has been consumed.
		'''
		return True

	def handle_switch(self, state):
		return True

	def handle_bt_1(self, state):
		'''
		Handle a button press.
		@param state: The state of the button. state.positive, state.triggered
		@return: True if the input has been consumed.
		'''
		return True

	def handle_bt_2(self, state):
		return True

	def handle_bt_camera(self, state):
		return True

class TestHandler(Handler):
	def handle_movement(self, state):
		print(state)
		return True

	def handle_bt_1(self, state):
		print(state)
		return True

#Input().add_handler(TestHandler())
