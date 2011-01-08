import unittest
from bge import logic
from . import bgeext

class ProxyTest(unittest.TestCase):
	'''bgeext.ProxyGameObject'''

	def setUp(self):
		self.o1 = bgeext.get_proxy(logic.getCurrentScene().objects['pt.1'])
		self.o2 = bgeext.get_proxy(logic.getCurrentScene().objects['pt.2'])

	def test_0_unwrap(self):
		self.assertEquals(self.o1._get_owner().__class__.__name__, 'KX_GameObject')

	def test_function(self):
		vw = self.o1.getVelocity()
		v = self.o1._get_owner().getVelocity()
		self.assertEqual(vw, v)

	def test_property_get(self):
		pw = self.o1.worldPosition
		p = self.o1._get_owner().worldPosition
		self.assertEqual(pw, p)

	def test_property_set(self):
		wp = self.o1._get_owner().worldPosition.copy()
		wp.y = 5.0
		self.o1.worldPosition = wp
		
		pw = self.o1.worldPosition
		p = self.o1._get_owner().worldPosition
		self.assertEqual(pw, p)
		self.assertEqual(pw.y, 5.0)

	def test_game_property(self):
		self.o1['Foo'] = 'foo'
		self.assertTrue('foo' in self.o1._get_owner())
		self.assertEqual(self.o1['Foo'], 'foo')

	def test_parent(self):
		self.o1.setParent(self.o2)
		self.assertTrue(self.o1 in self.o2.children)
		self.assertTrue(self.o1._get_owner() in self.o2._get_owner().children)

def proxy_test():
	suite = unittest.TestLoader().loadTestsFromTestCase(ProxyTest)
	unittest.TextTestRunner(verbosity=2).run(suite)
