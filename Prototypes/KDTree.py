#
# Copyright 2009 Alex Fraser <alex@phatcore.com>
# Copyright 2009 Mark Triggs <mst@dishevelled.net>
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

class Cube:
	'''A bounding cube with arbitrary dimensions, defined by its centre
	and radius.'''
	def __init__(self, centre, radius):
		self.LowerBound = []
		self.UpperBound = []
		for component in centre:
			self.LowerBound.append(component - radius)
			self.UpperBound.append(component + radius)

class KDNode:
	def __init__(self):
		self.Axis = None
		self.Value = None
		self.A = None
		self.B = None
		self.Elements = None

class KDTree:
	def __init__(self, elements, leafSize = 8):
		'''Create a new KDTree from a list of elements. leafSize determines the
		largest size a leaf can be. If a node would store more elements than
		this, it will be split in two. Setting this to be greater than 1 will
		reduce the depth of the tree, which can speed up traversal. Large values
		will result in a mostly flat list, which would also be slow.'''
		self.leafSize = leafSize
		
		#
		# maxDepth for diagnostics only.
		#
		self.maxDepth = 0
		
		if len(elements) > 0:
			self.setDimensions(elements[0])
			self.root = self.construct(elements, 0, None)
		else:
			self.dimensions = None
			self.root = None
	
	def setDimensions(self, element):
		'''Configures the KD tree to have the same number of dimensions as
		element. Overrid this if the elements are more than just points.'''
		self.dimensions = len(element)
	
	def elemCmp(self, axis):
		'''Returns a function that compares two elements based on the specified
		axis. Override this if the elements are more than just points.'''
		return lambda e1, e2: cmp(e1[axis], e2[axis])
	
	def getValue(self, e, axis):
		'''Get the value of an element for a given axis. Override this if the
		elements are more than just points.'''
		return e[axis]
		
	def construct(self, elements, depth, parent):
		'''Recursively create a KDTree from a list of elements. This isn't
		elegant, and is intended to be done only once.'''
		if depth > self.maxDepth:
			self.maxDepth = depth
		
		n = KDNode()
		n.Axis = depth % self.dimensions
		if len(elements) <= self.leafSize:
			n.Elements = elements
			return n
		
		elements.sort(self.elemCmp(n.Axis))
		medianIndex = len(elements) / 2
		n.Value = self.getValue(elements[medianIndex], n.Axis)
		n.A = self.construct(elements[0:medianIndex], depth + 1, n)
		n.B = self.construct(elements[medianIndex:], depth + 1, n)
		return n
	
	def isInRange(self, element, bounds):
		'''Tests whether an element is within bounds. This is the last step of
		the search.'''
		for axis in range(0, self.dimensions):
			val = self.getValue(element, axis)
			if  val <= bounds.LowerBound[axis] or val >= bounds.UpperBound[axis]:
				return False
		return True
	
	def getRange(self, centre, radius):
		'''Get a list of all the elements in the tree that are within the given
		bounds. This is an iterative depth-first search.'''
		bounds = Cube(centre, radius)
		elemInRange = []
		queue = [self.root]
		
		while queue != []:
			n = queue.pop()
			
			if n.Elements:
				#
				# Found a leaf node. Still need to test it properly.
				#
				for e in n.Elements:
					if self.isInRange(e, bounds):
						elemInRange.append(e)
			else:
				if n.Value > bounds.LowerBound[n.Axis]:
					#
					# Within lower bound on this axis. Check the left tree. We
					# know this isn't a leaf, so we can assume n.A exists.
					#
					queue.append(n.A)
				if n.Value < bounds.UpperBound[n.Axis]:
					#
					# Within upper bound on this axis. Check the right tree. We
					# know this isn't a leaf, so we can assume n.B exists.
					#
					queue.append(n.B)
		
		return elemInRange
	
	def getElementStr(self, e):
		'''Get the string form of an element. Used for printing.'''
		return str(e)
	
	def prettyPrint(self, n = None, indent = ""):
		'''Print the tree out.'''
		if n == None:
			n = self.root
		if n == None:
			return
		if n.Elements:
			for e in n.Elements:
				print "%s%s" % (indent, self.getElementStr(e))
		else:
			print "%s%s" % (indent, "A"),
			print "Axis:", n.A.Axis,
			print "Value:", n.A.Value
			self.prettyPrint(n.A, indent + "  ")
			
			print "%s%s" % (indent, "B"),
			print "Axis:", n.B.Axis,
			print "Value:", n.B.Value
			self.prettyPrint(n.B, indent + "  ")

class GameObjectXYTree(KDTree):
	'''A KDTree for Blender Game Engine objects that are roughly situated on an
	XY plane.'''
	def __init__(self, elements, leafSize = 32):
		KDTree.__init__(self, elements, leafSize)
	
	def setDimensions(self, element):
		'''Set the number of dimensions to two, as all objects are expected to
		be roughly on a plane.'''
		self.dimensions = 2
	
	def elemCmp(self, e1, e2, axis):
		'''Returns a function that compares two game objects based on the
		specified axis. axis will be 0 (x) or 1 (y), so it needs no
		modification.'''
		return lambda e1, e2: e1.getPosition()[axis] - e2.getPosition()[axis]
	
	def getValue(self, e, axis):
		'''Get the position of an element on a given axis.'''
		return e.getPosition()[axis]
	
	def getElementStr(self, e):
		'''Get the name of a game object. Used when printing the tree
		(debugging).'''
		return e.name

if __name__ == "__main__":
	'''Small self-test. Create random lists of 2D coordinates and create a tree
	for them. This validates the search function against a brute-force
	implementation, and times the execution of each method.'''
	import time
	import random
	
	def bruteForceGetRange(bounds, elements):
		'''Get a list of elements that are within rage. This method checks every
		element, and exists only to validate the getRange method in KDTree.'''
		elemInRange = []
		numAxes = len(elements[0])
		for e in elements:
			withinRange = True
			for axis in range(0, numAxes):
				if (e[axis] <= bounds.LowerBound[axis] or
				    e[axis] >= bounds.UpperBound[axis]):
					withinRange = False
					break
			if withinRange:
				elemInRange.append(e)
		return elemInRange
	
	def compareKD(e1, e2):
		'''Compare tuples, giving precedence to the first component.
		The following components are only tested if the earlier are equal. This
		is used to sort the resultant lists so they may be compared.'''
		diff = 0
		for i in range(0, len(e1)):
			diff = cmp(e1[i], e2[i])
			if diff != 0:
				return diff
		return diff
	
	def createRandomPoint(dimensions, lowerBound, upperBound):
		p = []
		bredth = upperBound - lowerBound
		for i in range(0, dimensions):
			p.append((random.random() * bredth) - lowerBound)
		return p
	
	def createRandomElements(dimensions, nElements, lowerBound, upperBound):
		'''Create a list of elements with random coordinates within the given
		range. The same upper and lower bounds are used for each axis.'''
		elements = []
		for i in range(0, nElements):
			e = createRandomPoint(dimensions, lowerBound, upperBound)
			elements.append(e)
		return elements
	
	def benchmark(elements, leafSize, lowerBound, upperBound):
		'''Time the execution of all the search algorithms.'''
		REPETITIONS = 20
		RADIUS = 10
		t1 = time.time()
		tree = KDTree(elements, leafSize)
		t2 = time.time()
		print ("%3d, %9d, %5d, %8d, %8.2f," %
		       (tree.dimensions,
		        len(elements),
		        tree.maxDepth,
		        tree.leafSize,
		        (t2 - t1) * 1000)),
		
		nElements = 0.0
		treeTimes = []
		treeTimesIter = []
		bfTimes = []
		for i in range(0, REPETITIONS):
			point = createRandomPoint(len(elements[0]), lowerBound, upperBound)
			
			#
			# KDTree version
			#
			t1 = time.time()
			elemInRange = tree.getRange(point, RADIUS)
			t2 = time.time()
			treeTimes.append(t2 - t1)
			
			#
			# Brute-force version
			#
			t1 = time.time()
			elemInRangeBF = bruteForceGetRange(Cube(point, RADIUS), elements)
			t2 = time.time()
			bfTimes.append(t2 - t1)
			
			nElements = nElements + len(elemInRangeBF)
			
			elemInRange.sort(compareKD)
			elemInRangeBF.sort(compareKD)
			if elemInRange != elemInRangeBF:
				print "ERROR: kd-tree results don't match brute-force method."
				print "Centre: %s; Radius: %d" % (str(point), RADIUS)
				print "kd-tree:    ", elemInRange
				print "brute-force:", elemInRangeBF
		nElements = nElements / REPETITIONS
		
		avTreeTimes = 0.0
		avBFTimes = 0.0
		for i in range(0, REPETITIONS):
			avTreeTimes = avTreeTimes + treeTimes[i]
			avBFTimes = avBFTimes + bfTimes[i]
		avTreeTimes = avTreeTimes / REPETITIONS
		avBFTimes = avBFTimes / REPETITIONS
		print ("%6.1f, %7.2f, %6.2f" %
		       (nElements,           # average number found
		        avBFTimes * 1000,    # average brute-force search time
		        avTreeTimes * 1000)) # average kd-tree search time
	
	print "dim, nElements, depth, leafSize,    cTime, nFound,  bfTime, kdTime"
	lowerBound = -50
	upperBound = 50
	for dimensions in [1, 2, 3, 4, 5]:
		for nElements in [100, 1000, 10000, 100000]:
			elements = createRandomElements(dimensions, nElements, lowerBound, upperBound)
			for leafSize in [1, 2, 4, 8, 16, 32, 64, 128, 256]:
				benchmark(elements, leafSize, lowerBound, upperBound)
	
