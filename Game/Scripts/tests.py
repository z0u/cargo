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

import unittest
from bge import logic
import bxt
from . import Utilities
import weakref

class ProxyGameObjectTest(unittest.TestCase):
	'''bxt.types.ProxyGameObject'''

	def setUp(self):
		self.o1 = bxt.types.get_wrapper(logic.getCurrentScene().objects['pt.1'])
		self.o2 = bxt.types.get_wrapper(logic.getCurrentScene().objects['pt.2'])

	def test_0_unwrap(self):
		self.assertEquals(self.o1.unwrap().__class__.__name__, 'KX_GameObject')

	def test_function(self):
		vw = self.o1.getVelocity()
		v = self.o1.unwrap().getVelocity()
		self.assertEqual(vw, v)

	def test_property_get(self):
		pw = self.o1.worldPosition
		p = self.o1.unwrap().worldPosition
		self.assertEqual(pw, p)

	def test_property_set(self):
		wp = self.o1.unwrap().worldPosition.copy()
		wp.y = 5.0
		self.o1.worldPosition = wp
		
		pw = self.o1.worldPosition
		p = self.o1.unwrap().worldPosition
		self.assertEqual(pw, p)
		self.assertEqual(pw.y, 5.0)

	def test_game_property(self):
		self.o1['Foo'] = 'foo'
		self.assertTrue('foo' in self.o1.unwrap())
		self.assertEqual(self.o1['Foo'], 'foo')

	def test_parent(self):
		self.o1.setParent(self.o2)
		self.assertTrue(self.o1 in self.o2.children)
		self.assertTrue(self.o1.unwrap() in self.o2.unwrap().children)

class PriorityQueueTest(unittest.TestCase):
	'''bxt.utils.PriorityQueue'''

	def setUp(self):
		self.Q = bxt.utils.PriorityQueue()

	def test_add(self):
		self.Q.push('foo', 'fooI', 1)
		self.assertEquals(self.Q[-1], 'fooI')
		self.assertEquals(len(self.Q), 1)

	def test_add_several(self):
		self.Q.push('foo', 'fooI', 1)
		self.Q.push('bar', 'barI', 0)
		self.assertEquals(self.Q[-1], 'fooI')
		self.assertEquals(len(self.Q), 2)
		self.Q.push('baz', 'bazI', 1)
		self.assertEquals(self.Q[-1], 'bazI')
		self.assertEquals(len(self.Q), 3)

	def test_remove(self):
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

class FuzzySwitchTest(unittest.TestCase):
	'''bxt.utils.FuzzySwitch'''

	def test_init(self):
		self.sw = bxt.utils.FuzzySwitch(5, 10, False)
		self.assertFalse(self.sw.isOn())

	def test_on(self):
		self.sw = bxt.utils.FuzzySwitch(3, 4, False)
		self.sw.turnOn()
		self.assertFalse(self.sw.isOn())
		self.sw.turnOn()
		self.assertFalse(self.sw.isOn())
		self.sw.turnOn()
		self.assertTrue(self.sw.isOn())

	def test_off(self):
		self.sw = bxt.utils.FuzzySwitch(3, 4, True)
		self.sw.turnOff()
		self.assertTrue(self.sw.isOn())
		self.sw.turnOff()
		self.assertTrue(self.sw.isOn())
		self.sw.turnOff()
		self.assertTrue(self.sw.isOn())
		self.sw.turnOff()
		self.assertFalse(self.sw.isOn())

	def test_both(self):
		self.sw = bxt.utils.FuzzySwitch(2, 2, False)
		self.sw.turnOn()
		self.assertFalse(self.sw.isOn())
		self.sw.turnOff()
		self.assertFalse(self.sw.isOn())
		self.sw.turnOn()
		self.assertFalse(self.sw.isOn())
		
		self.sw.turnOn()
		self.assertTrue(self.sw.isOn())

def run_tests():
	suite = unittest.TestSuite()
	suite.addTests(unittest.TestLoader().loadTestsFromTestCase(ProxyGameObjectTest))
	suite.addTests(unittest.TestLoader().loadTestsFromTestCase(PriorityQueueTest))
	suite.addTests(unittest.TestLoader().loadTestsFromTestCase(FuzzySwitchTest))
	unittest.TextTestRunner(verbosity=2).run(suite)


#########################
# Non-standard unit tests
#########################

# Weak reference testing for ProxyGameObjects

wref = None
wrefCountdown = 3
wrefPass = True

def weakref_init():
	global wref

	def callback(ref):
		print("Info: Weak reference is dying.")

	o = bxt.types.get_wrapper(logic.getCurrentScene().objects['weakref'])
	wref = weakref.ref(o, callback)

def weakref_test():
	global wrefCountdown
	global wrefPass

	wrefCountdown -= 1

	if wrefCountdown > 0 and wref() == None:
		print("Info: Weak reference died before it was due to.")
		wrefPass = False
	elif wrefCountdown == 1:
		wref().endObject()
	elif wrefCountdown == 0:
		if wref() != None:
			wrefPass = False
			print("Info: Weak reference did not die on time.")

		if wrefPass:
			print("weakref_test ... ok")
			print("\n----------------------------------------------------------------------")
			print("OK")
		else:
			print("weakref_test ... FAIL")
			print("\n----------------------------------------------------------------------")
			print("FAIL")

################
# Demonstrations
################

@bxt.types.gameobject('update', prefix='ED_')
class ExtensionDemo(bxt.types.ProxyGameObject):
	'''Demonstrates:
	 - Input filtering (makes sure all sensors are positive).
	 - Promotion of methods to top-level functions, so they may be called from
	   a Python controller in the game engine.
	 - Using KX_GameObject attributes as though they belong to this class.'''

	@bxt.utils.all_sensors_positive
	def update(self):
		currentpos = self.worldPosition.x
		currentpos += 1.0
		currentpos %= 5.0
		self.worldPosition.x = currentpos
