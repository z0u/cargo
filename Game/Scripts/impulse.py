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

import bat.bats
import bat.containers
import bat.utils

DEBUG = False

INITIAL_REPEAT_DELAY = 30
REPEAT_DELAY = 5

class Input(metaclass=bat.bats.Singleton):
	'''
	Provides a unified interface to input devices such as keyboard and
	joysticks.
	'''
	_prefix = ""

	PRI = {'PLAYER': 0, 'STORY': 1, 'DIALOGUE': 2, 'MENU': 3}

	def __init__(self):
		self.handlers = bat.containers.SafePriorityStack()

		# Acquire movement from a 2D directional pad.
		self.dp_move = DPad2D("Movement", 'u', 'd', 'l', 'r')

		# The switch command can be "next" or "previous"; use a 1D pad to filter
		# out multiple conflicting button presses.
		self.dp_switch = DPad1D("Switch", 'n', 'p')

		# Standard buttons.
		self.btn1 = Button("1", '1')
		self.btn2 = Button("2", '2')
		self.btn_cam = Button("Camera", 'c')

		self.buttons = [self.dp_move, self.btn1, self.btn2, self.dp_switch,
				self.btn_cam]

		self.load_config()

		self.sequence_map = {}
		self.max_seq_len = 0
		self.sequence = ""

	@bat.bats.expose
	@bat.utils.controller_cls
	def process(self, c):
		'''Distribute all events to the listeners.'''
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

		self.check_sequences()

	def check_sequences(self):
		'''
		Build up strings of button presses, looking for known combinations.
		Primarily for things like cheats, but could be used for combo moves too.
		'''
		# Add all pressed buttons to the sequence.
		new_char = False
		for btn in self.buttons:
			if btn.triggered:
				char = btn.get_char()
				if char is None:
					continue
				self.sequence += char
				new_char = True

		if not new_char:
			return

		# Scan for acceptable cheats. We don't bother doing this inside the loop
		# above, because this is all happening in one frame: if multiple buttons
		# are pressed in one frame, the order that they are added to the
		# sequence is undefined anyway, so there's no point checking after each
		# character.
		for seq in self.sequence_map.keys():
			if self.sequence.endswith(seq):
				self.sequence_map[seq].send()

		# Truncate
		if len(self.sequence) > self.max_seq_len:
			self.sequence = self.sequence[-self.max_seq_len:]

	def load_config(self):
		'''Bind keys and buttons to the interfaces.'''
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

	def add_handler(self, handler, priority='PLAYER'):
		self.handlers.push(handler, Input.PRI[priority])
		if DEBUG:
			print("Handlers:", self.handlers)

	def remove_handler(self, handler):
		self.handlers.discard(handler)
		if DEBUG:
			print("Handlers:", self.handlers)

	def add_sequence(self, sequence, event):
		"""
		Adds a sequence that will cause an event to be fired. Should be in the
		form for a string using characters that would be returned from
		Button.get_char - e.g. "ud1" would be Up, Down, Button1.
		"""
		self.sequence_map[sequence] = event
		if self.max_seq_len < len(sequence):
			self.max_seq_len = len(sequence)

class Button:
	'''A simple button (0 dimensions).'''

	def __init__(self, name, char):
		self.name = name
		self.char = char
		self.keyboard_keys = []
		#self.joystick_buttons = []

		self.positive = False
		self.triggered = False

	@property
	def activated(self):
		'''
		True if the button is down on this frame, for the first time. On the
		following frame, this will be false even if the button is still held
		down.
		'''
		return self.positive and self.triggered

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

	def get_char(self):
		if self.activated:
			return self.char
		else:
			return None

	def __str__(self):
		return "Button %s - positive: %s, triggered: %s" % (self.name, 
				self.positive, self.triggered)

class DPad1D:
	'''
	Accumulates directional input (1 dimension). Useful for things like L/R
	shoulder buttons.
	'''

	def __init__(self, name, char_next, char_prev):
		self.name = name
		self.char_next = char_next
		self.char_prev = char_prev
		self.next = Button("next", char_next)
		self.prev = Button("prev", char_prev)
		self.direction = 0.0
		self.bias = 0.0
		self.dominant = None
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

		self.find_dominant_direction()

	def find_dominant_direction(self):
		"""
		Find which direction is dominant. Uses a bit of fuzzy logic to prevent
		this from switching rapidly.
		"""
		biased_direction = self.direction + self.bias * 0.1
		x = biased_direction
		bias = 0.0
		dominant = None
		if x > 0.5:
			dominant = self.char_next
			bias = 1.0
		elif x < -0.5:
			dominant = self.char_prev
			bias = -1.0

		if dominant != self.dominant:
			self.dominant = dominant
			self.bias = bias
			self.triggered = True
		else:
			self.triggered = False

	def get_char(self):
		return self.dominant

	def __str__(self):
		return "Button %s - direction: %s" % (self.name, self.direction)

class DPad2D:
	'''
	Accumulates directional input (2 dimensions) - from directional pads,
	joysticks, and nominated keyboard keys.
	'''

	def __init__(self, name, char_up, char_down, char_left, char_right):
		self.name = name
		self.char_up = char_up
		self.char_down = char_down
		self.char_left = char_left
		self.char_right = char_right
		self.up = Button("up", char_up)
		self.down = Button("down", char_down)
		self.left = Button("left", char_left)
		self.right = Button("right", char_right)
		self.direction = mathutils.Vector((0.0, 0.0))
		self.bias = mathutils.Vector((0.0, 0.0))
		self.dominant = None
		self.triggered = False
		self.triggered_repeat = False
		self.repeat_delay = 0

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

		self.find_dominant_direction()

	def find_dominant_direction(self):
		"""
		Find the dominant direction (up, down, left or right). Uses a bit of
		fuzzy logic to prevent this from switching rapidly.
		"""
		biased_direction = self.direction + self.bias * 0.1
		x = biased_direction.x
		y = biased_direction.y

		dominant = None
		bias = mathutils.Vector((0.0, 0.0))
		if abs(x) > 0.5 + abs(y):
			if x > 0.5:
				dominant = self.char_right
				bias = mathutils.Vector((1.0, 0.0))
			elif x < -0.5:
				dominant = self.char_left
				bias = mathutils.Vector((-1.0, 0.0))
		elif abs(y) > 0.5 + abs(x):
			if y > 0.5:
				dominant = self.char_up
				bias = mathutils.Vector((0.0, 1.0))
			elif y < -0.5:
				dominant = self.char_down
				bias = mathutils.Vector((0.0, -1.0))

		if dominant != self.dominant:
			self.dominant = dominant
			self.bias = bias
			self.triggered = True
			self.triggered_repeat = True
			self.repeat_delay = INITIAL_REPEAT_DELAY
		elif self.repeat_delay <= 0:
			self.triggered = False
			self.triggered_repeat = True
			self.repeat_delay = REPEAT_DELAY
		else:
			self.triggered = False
			self.triggered_repeat = False
			self.repeat_delay -= 1

	def get_char(self):
		"""
		Get the character of the dominant axis (used for sequences). If both
		axes are roughly equal, neither is dominant and this method will return
		None.
		"""
		return self.dominant

	def __str__(self):
		return "Button %s - direction: %s" % (self.name, self.direction)

class Handler:
	'''
	Use as a mixin to handle input from the user. Any methods that are not
	overridden will do nothing. By default, non-overridden functions will
	capture the event (preventing further processing from lower-priority
	handlers). To allow such events to pass through, set
	self.default_handler_response = False.
	'''

	def handle_movement(self, state):
		'''
		Handle a movement request from the user.
		@param direction: The direction to move in (2D vector; +y is up).
		@return: True if the input has been consumed.
		'''
		return self.default_handler_response

	def handle_switch(self, state):
		return self.default_handler_response

	def handle_bt_1(self, state):
		'''
		Handle a button press.
		@param state: The state of the button. state.positive, state.triggered
		@return: True if the input has been consumed.
		'''
		return self.default_handler_response

	def handle_bt_2(self, state):
		return self.default_handler_response

	def handle_bt_camera(self, state):
		return self.default_handler_response

	@property
	def default_handler_response(self):
		try:
			return self._default_handler_response
		except AttributeError:
			self._default_handler_response = True
			return self._default_handler_response
	@default_handler_response.setter
	def default_handler_response(self, value):
		self._default_handler_response = value

class TestHandler(Handler):
	'''Prints input state changes.'''
	def handle_movement(self, state):
		print(state)
		return True

	def handle_bt_1(self, state):
		print(state)
		return True

#Input().add_handler(TestHandler(), 'PLAYER')
