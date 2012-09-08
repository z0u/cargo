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

import bxt.types

class PriorityStackTest(unittest.TestCase):
	'''bxt.types.SafePriorityStack'''

	class Dummy:
		def __init__(self):
			self.invalid = False

	def setUp(self):
		self.foo = PriorityStackTest.Dummy()
		self.bar = PriorityStackTest.Dummy()
		self.baz = PriorityStackTest.Dummy()
		self.queue = bxt.types.SafePriorityStack()

	def test_add(self):
		self.queue.push(self.foo, 1)
		self.assertIs(self.queue[-1], self.foo)
		self.assertEquals(len(self.queue), 1)

	def test_order(self):
		items = [self.foo, self.bar, self.baz]

		# Last item pushed on is at the front of the list.
		self.queue.push(self.foo, 1)
		self.queue.push(self.baz, 0)
		self.queue.push(self.bar, 0)

		for a, b in zip(self.queue, items):
			self.assertIs(a, b)

	def test_add_several(self):
		self.queue.push(self.foo, 1)
		self.queue.push(self.bar, 0)
		self.assertIs(self.queue.top(), self.foo)
		self.assertEquals(len(self.queue), 2)
		self.queue.push(self.baz, 1)
		self.assertIs(self.queue.top(), self.baz)
		self.assertEquals(len(self.queue), 3)

	def test_remove(self):
		self.queue.push(self.foo, 1)
		self.queue.push(self.bar, 0)
		self.queue.push(self.baz, 1)
		self.queue.pop()
		self.assertIs(self.queue.top(), self.foo)
		self.assertEquals(len(self.queue), 2)
		self.queue.pop()
		self.assertIs(self.queue.top(), self.bar)
		self.assertEquals(len(self.queue), 1)
		self.queue.pop()
		self.assertEquals(len(self.queue), 0)

	def test_weak(self):
		self.queue.push(self.foo, 1)
		self.queue.push(self.bar, 0)
		self.queue.push(self.baz, 1)
		self.baz.invalid = True
		self.assertIs(self.queue.top(), self.foo)
		self.assertEquals(len(self.queue), 2)
		self.foo.invalid = True
		self.assertIs(self.queue.top(), self.bar)
		self.assertEquals(len(self.queue), 1)
		self.bar.invalid = True
		self.assertEquals(len(self.queue), 0)

class FuzzySwitchTest(unittest.TestCase):
	'''bxt.types.FuzzySwitch'''

	def test_init(self):
		self.sw = bxt.types.FuzzySwitch(5, 10, False)
		self.assertFalse(self.sw.is_on())

	def test_on(self):
		self.sw = bxt.types.FuzzySwitch(3, 4, False)
		self.sw.turn_on()
		self.assertFalse(self.sw.is_on())
		self.sw.turn_on()
		self.assertFalse(self.sw.is_on())
		self.sw.turn_on()
		self.assertTrue(self.sw.is_on())

	def test_off(self):
		self.sw = bxt.types.FuzzySwitch(3, 4, True)
		self.sw.turn_off()
		self.assertTrue(self.sw.is_on())
		self.sw.turn_off()
		self.assertTrue(self.sw.is_on())
		self.sw.turn_off()
		self.assertTrue(self.sw.is_on())
		self.sw.turn_off()
		self.assertFalse(self.sw.is_on())

	def test_both(self):
		self.sw = bxt.types.FuzzySwitch(2, 2, False)
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
	suite.addTests(unittest.TestLoader().loadTestsFromTestCase(PriorityStackTest))
	suite.addTests(unittest.TestLoader().loadTestsFromTestCase(FuzzySwitchTest))
	unittest.TextTestRunner(verbosity=2).run(suite)
