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
import bge
import bxt
import weakref

class PriorityQueueTest(unittest.TestCase):
	'''bxt.utils.PriorityQueue'''

	class Dummy:
		pass

	def setUp(self):
		self.foo = PriorityQueueTest.Dummy()
		self.bar = PriorityQueueTest.Dummy()
		self.baz = PriorityQueueTest.Dummy()
		self.queue = bxt.utils.WeakPriorityQueue()

	def test_add(self):
		self.queue.push(self.foo, 1)
		self.assertEquals(self.queue[-1], self.foo)
		self.assertEquals(len(self.queue), 1)

	def test_add_several(self):
		self.queue.push(self.foo, 1)
		self.queue.push(self.bar, 0)
		self.assertEquals(self.queue[-1], self.foo)
		self.assertEquals(len(self.queue), 2)
		self.queue.push(self.baz, 1)
		self.assertEquals(self.queue[-1], self.baz)
		self.assertEquals(len(self.queue), 3)

	def test_remove(self):
		self.queue.push(self.foo, 1)
		self.queue.push(self.bar, 0)
		self.queue.push(self.baz, 1)
		self.queue.pop()
		self.assertEquals(self.queue[-1], self.foo)
		self.assertEquals(len(self.queue), 2)
		self.queue.pop()
		self.assertEquals(self.queue[-1], self.bar)
		self.assertEquals(len(self.queue), 1)
		self.queue.pop()
		self.assertEquals(len(self.queue), 0)

	def test_weak(self):
		self.queue.push(self.foo, 1)
		self.queue.push(self.bar, 0)
		self.queue.push(self.baz, 1)
		self.baz = None
		self.assertEquals(self.queue[-1], self.foo)
		self.assertEquals(len(self.queue), 2)
		self.foo = None
		self.assertEquals(self.queue[-1], self.bar)
		self.assertEquals(len(self.queue), 1)
		self.bar = None
		self.assertEquals(len(self.queue), 0)

class FuzzySwitchTest(unittest.TestCase):
	'''bxt.utils.FuzzySwitch'''

	def test_init(self):
		self.sw = bxt.utils.FuzzySwitch(5, 10, False)
		self.assertFalse(self.sw.is_on())

	def test_on(self):
		self.sw = bxt.utils.FuzzySwitch(3, 4, False)
		self.sw.turn_on()
		self.assertFalse(self.sw.is_on())
		self.sw.turn_on()
		self.assertFalse(self.sw.is_on())
		self.sw.turn_on()
		self.assertTrue(self.sw.is_on())

	def test_off(self):
		self.sw = bxt.utils.FuzzySwitch(3, 4, True)
		self.sw.turn_off()
		self.assertTrue(self.sw.is_on())
		self.sw.turn_off()
		self.assertTrue(self.sw.is_on())
		self.sw.turn_off()
		self.assertTrue(self.sw.is_on())
		self.sw.turn_off()
		self.assertFalse(self.sw.is_on())

	def test_both(self):
		self.sw = bxt.utils.FuzzySwitch(2, 2, False)
		self.sw.turn_on()
		self.assertFalse(self.sw.is_on())
		self.sw.turn_off()
		self.assertFalse(self.sw.is_on())
		self.sw.turn_on()
		self.assertFalse(self.sw.is_on())
		
		self.sw.turn_on()
		self.assertTrue(self.sw.is_on())

def run_tests():
	suite = unittest.TestSuite()
	suite.addTests(unittest.TestLoader().loadTestsFromTestCase(PriorityQueueTest))
	suite.addTests(unittest.TestLoader().loadTestsFromTestCase(FuzzySwitchTest))
	unittest.TextTestRunner(verbosity=2).run(suite)


#########################
# Non-standard unit tests
#########################

@bxt.types.weakprops('wp')
class WeakrefTest:
	pass

# Weak reference testing for GameObjects

wt = WeakrefTest()
wrefCountdown = 3
wrefPass = True

def weakref_init():
	o = bge.logic.getCurrentScene().objects['weakref']
	# This is actually stored as a weakref, due to the weakprops decorator.
	wt.wp = o

def weakref_test():
	global wrefCountdown
	global wrefPass

	wrefCountdown -= 1

	if wrefCountdown > 0 and wt.wp == None:
		print("Info: Weak reference died before it was due to.")
		wrefPass = False
	elif wrefCountdown == 1:
		wt.wp.endObject()
	elif wrefCountdown == 0:
		if wt.wp != None:
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
