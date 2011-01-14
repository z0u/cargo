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

from bge import logic

from functools import wraps

###########
# Utilities
###########

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
