from bge import types
from bge import logic
from . import Utilities
import inspect
from functools import wraps

LIST_FUNCTIONS = ['__getitem__', '__setitem__', '__delitem__', '__contains__',
				'__len__']

def dereference_arg1(f):
	@wraps(f)
	def f_new(*args, **kwargs):
		if hasattr(args[1], '_get_owner'):
			args = list(args)
			args[1] = args[1]._get_owner()
		return f(*args, **kwargs)
	return f_new

def get_reference(f):
	@wraps(f)
	def f_new(*args, **kwargs):
		res = f(*args, **kwargs)
		if '__wrapper__' in res:
			return res['__wrapper__']
		else:
			return res
	return f_new

class Mixin:
	def __init__(self, base, privates):
		self.base = base
		self.privates = privates
		self.converted = False

	def __call__(self, cls):
		for name, member in inspect.getmembers(self.base):
			self.import_member(cls, name, member)

		def new_repr(slf):
			return "%s(%s)" % (slf.__class__.__name__, repr(slf._get_owner()))
		new_repr.__name__ = '__repr__'
		setattr(cls, '__repr__', new_repr)

		return cls

	def import_member(self, cls, name, member):
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
		def proxy_fun(slf, *argc, **argv):
			ret = member(slf._get_owner(), *argc, **argv)
			return ret
		proxy_fun.__name__ = name
		proxy_fun.__doc__ = member.__doc__
		setattr(cls, name, proxy_fun)

	def import_property(self, cls, name, member):
		def get(slf):
			return getattr(slf._get_owner(), name)
		def set(slf, value):
			setattr(slf._get_owner(), name, value)
		p = property(get, set, doc=member.__doc__)
		setattr(cls, name, p)

@Mixin(types.CListValue, LIST_FUNCTIONS)
class ProxyCListValue:
	def __init__(self, owner):
		self._owner = owner

	def _get_owner(self):
		return self._owner

	@get_reference
	def __getitem__(self, *args, **kwargs):
		return self._get_owner().__getitem__(*args, **kwargs)

@Utilities.gameobject()
@Mixin(types.KX_GameObject, LIST_FUNCTIONS)
class ProxyGameObject:

	def __init__(self, owner):
		self._owner = owner

	def _get_owner(self):
		return self._owner

	@dereference_arg1
	def setParent(self, *args, **kwargs):
		self._get_owner().setParent(*args, **kwargs)

	@get_reference
	def _getParent(self):
		return self._get_owner().parent
	parent = property(_getParent, doc=types.KX_GameObject.parent)

	# The CListValues need to be wrapped every time, because every time it's a
	# new instance.
	def _getChildren(self):
		return ProxyCListValue(self._get_owner().children)
	children = property(_getChildren, doc=types.KX_GameObject.children)

	# The CListValues need to be wrapped every time, because every time it's a
	# new instance.
	def _getChildrenRecursive(self):
		return ProxyCListValue(self._get_owner().childrenRecursive)
	childrenRecursive = property(_getChildrenRecursive,
								doc=types.KX_GameObject.childrenRecursive)

	@dereference_arg1
	def getDistanceTo(self, *args, **kwargs):
		return self._get_owner().getDistanceTo(*args, **kwargs)

	@dereference_arg1
	def getVectTo(self, *args, **kwargs):
		return self._get_owner().getVectTo(*args, **kwargs)

	@dereference_arg1
	def rayCastTo(self, *args, **kwargs):
		return self._get_owner().rayCastTo(*args, **kwargs)

	@dereference_arg1
	def rayCast(self, *args, **kwargs):
		return self._get_owner().rayCast(*args, **kwargs)

	@dereference_arg1
	def reinstancePhysicsMesh(self, *args, **kwargs):
		return self._get_owner().reinstancePhysicsMesh(*args, **kwargs)

@Utilities.owner
def test(o):
	proxy = o['__wrapper__']
	print(proxy.getVelocity())
	print(proxy.worldPosition)
	proxy.worldPosition.y += 5
	print(proxy.worldPosition)
	print(proxy['foo'])
	proxy['bar'] = 26
	print('bar' in proxy)
	print(proxy['bar'])
	del proxy['bar']

	other = logic.getCurrentScene().objects['other']['__wrapper__']
	proxy.setParent(other)
	for child in other.children:
		print(child)
	print(list(other._get_owner().children))
