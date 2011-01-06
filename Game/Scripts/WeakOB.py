from bge import types
import inspect
from . import Utilities

@Utilities.gameobject()
class ProxyGameObject:
	def __init__(self, owner):
		self._owner = owner

	def _get_owner(self):
		return self._owner

def import_member(clsT, name, member):
	if name.startswith('__'):
		# This is a private member. Don't wrap it - unless it's a
		# dictionary accessor, in which case we want it!
		if not (name in ('__getitem__', '__setitem__', '__delitem__',
						 '__contains__')):
			return

	if inspect.isroutine(member):
		def proxy_fun(slf, *argc, **argv):
			return member(slf._get_owner(), *argc, **argv)
		proxy_fun.__name__ = name
		proxy_fun.__doc__ = member.__doc__
		setattr(clsT, name, proxy_fun)

	elif inspect.isgetsetdescriptor(member):
		def get(slf):
			return getattr(slf._get_owner(), name)
		def set(slf, value):
			setattr(slf._get_owner(), name, value)
		p = property(get, set, doc=member.__doc__)
		setattr(clsT, name, p)

def import_members(clsT, clsS):
	for name, member in inspect.getmembers(clsS):
		import_member(clsT, name, member)

import_members(ProxyGameObject, types.KX_GameObject)

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
