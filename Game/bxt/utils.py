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

from functools import wraps

from bge import logic

def singleton(cls):
	'''Class decorator: turns a class into a Singleton. When applied, all
	class instantiations return the same instance.'''

	# Adapted from public domain code in Python docs:
	# http://www.python.org/dev/peps/pep-0318/#examples
	instance = None
	def get():
		nonlocal instance
		if instance == None:
			instance = cls()
		return instance
	return get

def replaceObject(name, original, time = 0):
	'''Like bge.types.scene.addObject, but:
	 - Transfers the properies of the original to the new object, and
	 - Deletes the original after the new one is created.'''
	scene = logic.getCurrentScene()
	newObj = scene.addObject(name, original, time)
	for prop in original.getPropertyNames():
		newObj[prop] = original[prop]
	original.endObject()
	return newObj

def owner(f):
	'''Decorator. Passes a single argument to a function: the owner of the
	current controller.'''
	@wraps(f)
	def f_new():
		c = logic.getCurrentController()
		return f(c.owner)
	return f_new

def controller(f):
	'''Decorator. Passes a single argument to a function: the current
	controller.'''
	@wraps(f)
	def f_new():
		c = logic.getCurrentController()
		return f(c)
	return f_new

@controller
def allSensorsPositive(c):
	'''Test whether all sensors are positive.
	
	Parameters:
	c: A controller.
	
	Returns: True if all sensors are positive.'''
	for s in c.sensors:
		if not s.positive:
			return False
	return True

@controller
def someSensorPositive(c):
	'''Test whether at least one sensor is positive.
	
	Parameters:
	c: A controller.
	
	Returns: True if at least one sensor is positive.'''
	for s in c.sensors:
		if s.positive:
			return True
	return False

def all_sensors_positive(f):
	'''Decorator. Only calls the function if all sensors are positive.'''
	@wraps(f)
	def f_new(*args, **kwargs):
		if not allSensorsPositive():
			return
		return f(*args, **kwargs)
	return f_new

def some_sensors_positive(f):
	'''Decorator. Only calls the function if one ore more sensors are
	positive.'''
	@wraps(f)
	def f_new(*args, **kwargs):
		if not someSensorPositive():
			return
		return f(*args, **kwargs)
	return f_new

def get_cursor():
	'''Gets the 'Cursor' object in the current scene. This object can be used
	when you need to call a method on a KX_GameObject, but you don't care which
	object it gets called on.
	'''

	return logic.getCurrentScene().objects['Cursor']

def add_object(name, time = 0):
	'''Like KX_Scene.addObject, but doesn't need an existing object to position
	it. This uses the scene's cursor object (see get_cursor).
	'''

	scene = logic.getCurrentScene()
	return scene.addObject(name, get_cursor(), time)

def set_default_prop(ob, propName, value):
	'''Ensure a game object has the given property.

	Parameters:
	ob:       A KX_GameObject.
	propName: The property to check.
	value:    The value to assign to the property if it dosen't exist yet.
	'''
	if propName not in ob:
		ob[propName] = value

def add_state(ob, state):
	'''Add a set of states to the object's state.'''
	stateBitmask = 1 << (state - 1)
	ob.state |= stateBitmask

def rem_state(ob, state):
	'''Remove a state from the object's state.'''
	stateBitmask = 1 << (state - 1)
	ob.state &= (~stateBitmask)

def set_state(ob, state):
	'''Set the object's state. All current states will be un-set and replaced
	with the one specified.'''
	stateBitmask = 1 << (state - 1)
	ob.state = stateBitmask

def has_state(ob, state):
	'''Test whether the object is in the specified state.'''
	stateBitmask = 1 << (state - 1)
	return (ob.state & stateBitmask) != 0

class Counter:
	'''Counts the frequency of objects. This should only be used temporarily and
	then thrown away, as it keeps hard references to objects.
	'''

	def __init__(self):
		self.map = {}
		self.mode = None
		self.max = 0
		self.n = 0

	def add(self, ob):
		'''Add an object to this counter. If this object is the most frequent
		so far, it will be stored in the member variable 'mode'.'''
		count = 1
		if ob in self.map:
			count = self.map[ob] + 1
		self.map[ob] = count
		if count > self.max:
			self.max = count
			self.mode = ob
		self.n = self.n + 1

class FuzzySwitch:
	'''A boolean that only switches state after a number of consistentimpulses.
	'''

	def __init__(self, delayOn, delayOff, startOn):
		self.delayOn = delayOn
		self.delayOff = 0 - delayOff
		self.on = startOn
		if startOn:
			self.current = self.delayOn
		else:
			self.current = self.delayOff

	def turnOn(self):
		self.current = max(0, self.current)
		if self.on:
			return

		self.current += 1
		if self.current == self.delayOn:
			self.on = True

	def turnOff(self):
		self.current = min(0, self.current)
		if not self.on:
			return

		self.current -= 1
		if self.current == self.delayOff:
			self.on = False

	def isOn(self):
		return self.on

class PriorityQueue:
	'''A poor man's associative priority queue. All operations run in O(n) time.
	This is only meant to contain a small number of items.
	'''

	class Item:
		def __init__(self, key, item, priority):
			self.key = key
			self.item = item
			self.priority = priority

		def __repr__(self):
			return "(%s, %s, %d)" % (self.key, self.item, self.priority)

	def __init__(self):
		'''Create a new, empty priority queue.'''

		self.Q = []
		self.ItemSet = set()

	def __len__(self):
		return len(self.Q)

	def __getitem__(self, y):
		'''Get the yth item from the queue. 0 is the bottom (oldest/lowest
		priority); -1 is the top (youngest/highest priority).
		'''

		return self.Q[y].item

	def push(self, key, item, priority):
		'''Add an item to the end of the queue. If the item is already in the
		queue, it is removed and added again using the new priority.
		
		Parameters:
		key:      The key to associate this item with.
		item:     The item to store in the queue.
		priority: Items with higher priority will be stored higher on the queue.
		          0 <= priority. (Integer)
		'''

		if key in self.ItemSet:
			self.discard(key)

		pqi = PriorityQueue.Item(key, item, priority)

		added = False
		i = len(self.Q) - 1
		while i >= 0:
			if self.Q[i].priority <= priority:
				self.Q.insert(i + 1, pqi)
				added = True
				break
			i = i - 1
		if not added:
			self.Q.insert(0, pqi)

		self.ItemSet.add(key)

	def discard(self, key):
		'''Remove an item from the queue.

		Parameters:
		key: The key that was used to insert the item.
		'''

		i = len(self.Q) - 1
		while i >= 0:
			if self.Q[i].key == key:
				del self.Q[i]
				self.ItemSet.remove(key)
				return
			i = i - 1

	def pop(self):
		'''Remove the highest item in the queue.

		Returns: the item that is being removed.

		Raises:
		IndexError: if the queue is empty.
		'''

		pqi = self.Q.pop()
		self.ItemSet.remove(pqi.key)
		return pqi.item

	def top(self):
		return self[-1]

class Box2D:
	'''A 2D bounding box.'''

	def __init__(self, xLow, yLow, xHigh, yHigh):
		self.xLow = xLow
		self.yLow = yLow
		self.xHigh = xHigh
		self.yHigh = yHigh

	def intersect(self, other):
		if other.xHigh < self.xHigh:
			self.xHigh = other.xHigh
		if other.yHigh < self.yHigh:
			self.yHigh = other.yHigh
		
		if other.xLow > self.xLow:
			self.xLow = other.xLow
		if other.yLow > self.yLow:
			self.yLow = other.yLow

		#
		# Ensure box is not inside-out.
		#
		if self.xLow > self.xHigh:
			self.xLow = self.xHigh
		if self.yLow > self.yHigh:
			self.yLow = self.yHigh

	def get_area(self):
		w = self.xHigh - self.xLow
		h = self.yHigh - self.yLow
		return w * h
