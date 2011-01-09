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

'''Wraps some useful features of the game engine API to allow it to be extended.
'''

from bge import types
from bge import logic

import sys
import inspect
from functools import wraps

############
# Decorators
############

def owner(f):
	'''Passes a single argument to a function: the owner of the current
	controller.'''
	@wraps(f)
	def f_new():
		c = logic.getCurrentController()
		return f(c.owner)
	return f_new

def controller(f):
	'''Passes a single argument to a function: the current controller.'''
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

class gameobject:
	'''Extends a class to wrap KX_GameObjects. This decorator accepts any number
	of strings as arguments. Each string should be the name of a member to
	expose as a top-level function - this makes it available to logic bricks in
	the BGE. The class name is used as a function prefix. For example, consider
	the following class definition in a module called 'Module':

	@gameobject('update', prefix='f_')
	class Foo(ProxyGameObject):
		def __init__(self, owner):
			ProxyGameObject.__init__(self, owner)
		def update(self):
			self.worldPosition.z += 1.0

	A game object can be bound to the 'Foo' class by calling, from a Python
	controller, 'Module.Foo'. The 'update' function can then be called with
	'Module.f_update'. The 'prefix' argument is optional; if omitted, the
	functions will begin with <class name>_, e.g. 'Foo_update'.

	This decorator requires arguments; i.e. use '@gameobject()' instead of
	'@gameobject'.'''

	def __init__(self, *externs, prefix=None):
		self.externs = externs
		self.converted = False
		self.prefix = prefix

	@all_sensors_positive
	def __call__(self, cls):
		if not self.converted:
			self.create_interface(cls)
			self.converted = True

		old_init = cls.__init__
		def new_init(self, owner=None):
			if owner == None:
				owner = logic.getCurrentController().owner
			if 'template' in owner:
				owner = replaceObject(owner['template'], owner)
			old_init(self, owner)
			owner['__wrapper__'] = self
		cls.__init__ = new_init

		return cls

	def create_interface(self, cls):
		'''Expose the nominated methods as top-level functions in the containing
		module.'''
		module = sys.modules[cls.__module__]
		prefix = self.prefix
		if prefix == None:
			prefix = cls.__name__ + '_'

		for methodName in self.externs:
			f = cls.__dict__[methodName]

			def method_function(*args, **kwargs):
				o = logic.getCurrentController().owner
				instance = get_wrapper(o)
				args = list(args)
				args.insert(0, instance)
				return f(*args, **kwargs)

			method_function.__name__ = '%s%s' % (prefix, methodName)
			method_function.__doc__ = f.__doc__
			setattr(module, method_function.__name__, method_function)

def dereference_arg1(f):
	'''Function decorator: un-wraps the first argument of a function if
	possible. If the argument is not wrapped, it is passed through unchanged.'''
	@wraps(f)
	def f_new(*args, **kwargs):
		if is_wrapper(args[1]):
			args = list(args)
			args[1] = args[1].unwrap()
		return f(*args, **kwargs)
	return f_new

def get_reference(f):
	'''Function decorator: Changes the function to return the wrapper of a
	wrapped object. If the object has no wrapper, the return value is
	unchanged.'''
	@wraps(f)
	def f_new(*args, **kwargs):
		res = f(*args, **kwargs)
		if has_wrapper(res):
			return get_wrapper(res)
		else:
			return res
	return f_new

# Functions that are used in list manipulation.
LIST_FUNCTIONS = ['__getitem__', '__setitem__', '__delitem__', '__contains__',
				'__len__']

class mixin:
	'''Wraps all the functions of one class so that they may be called from
	another. The class that this is applied to must provide a link back to the
	wrapped object via a unwrap method.'''

	def __init__(self, base, privates=[], refs=[], derefs=[]):
		'''
		@param base The base class to mix-in.
		@param privates Normally, private members are not mixed-in. This
			parameter is a whitelist of private member names to mix in anyway.
		@param refs Names of members that can return a wrapped object.
		@param derefs Names of members that can accept a wrapped object as their
			first argument, or as the value to assign (in the case of
			properties).
		'''
		self.base = base
		self.privates = privates
		self.refs = refs
		self.derefs = derefs
		self.converted = False

	def __call__(self, cls):
		for name, member in inspect.getmembers(self.base):
			self.import_member(cls, name, member)

		def new_repr(slf):
			return "%s(%s)" % (slf.__class__.__name__, repr(slf.unwrap()))
		new_repr.__name__ = '__repr__'
		setattr(cls, '__repr__', new_repr)

		return cls

	def import_member(self, cls, name, member):
		'''Wrap a single member.'''
		if name.startswith('__'):
			if not name in self.privates:
				# This is a private member. Don't wrap it - unless it's a
				# dictionary accessor, in which case we want it!
				return

		if hasattr(cls, name):
			# Assume the class intended to override the attribute.
			return

		if inspect.isroutine(member):
			self.import_method(cls, name, member)
		elif inspect.isgetsetdescriptor(member):
			self.import_property(cls, name, member)

	def import_method(self, cls, name, member):
		'''Wrap a method. This creates a function of the same name in the target
		class.'''
		def proxy_fn(slf, *argc, **argv):
			ret = member(slf.unwrap(), *argc, **argv)
			return ret

		# Wrap/unwrap args and return values.
		if name in self.derefs:
			proxy_fn = dereference_arg1(proxy_fn)
		if name in self.refs:
			proxy_fn = get_reference(proxy_fn)

		proxy_fn.__doc__ = member.__doc__
		proxy_fn.__name__ = name

		setattr(cls, name, proxy_fn)

	def import_property(self, cls, name, member):
		'''Wrap a property or member variable. This creates a property in the
		target class; calling the property's get and set methods operate on the
		attribute with the same name in the wrapped object.'''
		def get(slf):
			return getattr(slf.unwrap(), name)
		def set(slf, value):
			setattr(slf.unwrap(), name, value)

		# Wrap/unwrap args and return values.
		if name in self.derefs:
			set = dereference_arg1(set)
		if name in self.refs:
			get = get_reference(get)

		p = property(get, set, doc=member.__doc__)
		setattr(cls, name, p)

@mixin(types.CListValue,
	privates=LIST_FUNCTIONS,
	refs=['__getitem__', 'from_id', 'get'],
	derefs=['__contains__', 'append', 'count', 'index'])
class ProxyCListValue:
	'''Wraps a bge.types.CListValue. When getting a value from the list, its
	wrapper (e.g. a ProxyGameObject) will be returned if one is available.'''
	def __init__(self, owner):
		self._owner = owner

	def unwrap(self):
		return self._owner

@gameobject()
@mixin(types.KX_GameObject,
	privates=LIST_FUNCTIONS,
	refs=['parent', 'rayCastTo'],
	derefs=['getDistanceTo', 'getVectTo', 'setParent', 'rayCastTo', 'reinstancePhysicsMesh'])
class ProxyGameObject:
	'''Wraps a bge.types.KX_GameObject. You can directly use any attributes
	defined by KX_GameObject, e.g. self.worldPosition.z += 1.0.'''

	def __init__(self, owner):
		self._owner = owner

	def unwrap(self):
		return self._owner

	# CListValues need to be wrapped every time, because every time it's a new
	# instance.
	def _getChildren(self):
		return ProxyCListValue(self.unwrap().children)
	children = property(_getChildren)

	# CListValues need to be wrapped every time, because every time it's a new
	# instance.
	def _getChildrenRecursive(self):
		return ProxyCListValue(self.unwrap().childrenRecursive)
	childrenRecursive = property(_getChildrenRecursive)

	# This function is special: the returned object may be wrapped, but it is
	# inside a tuple.
	@dereference_arg1
	def rayCast(self, *args, **kwargs):
		ob, p, n = self.unwrap().rayCast(*args, **kwargs)
		if ob != None and has_wrapper(ob):
			ob = get_wrapper(ob)
		return ob, p, n

def has_wrapper(owner):
	return '__wrapper__' in owner

def get_wrapper(owner):
	return owner['__wrapper__']

def is_wrapper(ob):
	return hasattr(ob, 'unwrap')
