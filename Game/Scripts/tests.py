import unittest
from bge import logic
from . import bgeext
from . import Utilities

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

class PQTest(unittest.TestCase):
	'''Utilities.PriorityQueue'''

	def setUp(self):
		self.Q = Utilities.PriorityQueue()

	def testAdd(self):
		self.Q.push('foo', 'fooI', 1)
		self.assertEquals(self.Q[-1], 'fooI')
		self.assertEquals(len(self.Q), 1)

	def testAddSeveral(self):
		self.Q.push('foo', 'fooI', 1)
		self.Q.push('bar', 'barI', 0)
		self.assertEquals(self.Q[-1], 'fooI')
		self.assertEquals(len(self.Q), 2)
		self.Q.push('baz', 'bazI', 1)
		self.assertEquals(self.Q[-1], 'bazI')
		self.assertEquals(len(self.Q), 3)

	def testRemove(self):
		self.Q.push('foo', 'fooI', 1)
		self.Q.push('bar', 'barI', 0)
		self.Q.push('baz', 'bazI', 1)
		self.Q.pop()
		self.assertEquals(self.Q[-1], 'fooI')
		self.assertEquals(len(self.Q), 2)
		self.Q.pop()
		self.assertEquals(self.Q[-1], 'barI')
		self.assertEquals(len(self.Q), 1)
		self.Q.pop()
		self.assertEquals(len(self.Q), 0)

def generic_tests():
	suite = unittest.TestLoader().loadTestsFromTestCase(PQTest)
	unittest.TextTestRunner(verbosity=2).run(suite)
