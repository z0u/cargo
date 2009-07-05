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

class StructureError(Exception):
	def __init__(self, value):
		self.value = value
	
	def __str__(self):
		return repr(self.value)

class Cube:
	'''A bounding cube with arbitrary dimensions, defined by its centre
	and radius.'''
	def __init__(self, centre, radius):
		self.LowerBound = []
		self.UpperBound = []
		for component in centre:
			self.LowerBound.append(component - radius)
			self.UpperBound.append(component + radius)
	
	def isInRange(self, point):
	'''Tests whether a point is inside the cube.
	Returns: false if the point is outside; true otherwise.'''
		for i in xrange(len(point)):
			if point[i] < self.LowerBound[i]:
				return false
			elif point[i] > self.UpperBound[i]:
				return false
		return true

class GOKDTree():
	'''A KD-tree of game objects for hierarchical LOD management.'''
	
	def __init__(self, owner):
		'''Populate this tree with a hierarchy. The hierarchy should have been
		created previously using the BlenderObjectXYTree.Serialise method.'''
		
		#
		# The number of dimensions are not needed to be known, because each node
		# explicitely stores its axis.
		#
		
		self.Owner = owner
		self.MedianValue = owner['KDMedianValue']
		self.Axis = owner['KDAxis']
		self.Left = None
		self.Right = None
		
		if owner['KDType'] == 'Leaf':
			return
		
		for child in owner.children:
			if not child.has_key('KDType'):
				continue
			if child['KDType'] == 'LeftBranch':
				if self.Left:
					raise StructureError, "%s has two left branches." % owner.name
				self.Left = GOXYTree(child)
			elif child['KDType'] == 'RightBranch':
				if self.Right:
					raise StructureError, "%s has two right branches." % owner.name
				self.Right = GOXYTree(child)
			else:
				raise StructureError, "%s has unknown KDType: %s" % (child.name, child['KDType'])
		if not self.Left or not self.Right:
			raise StructureError, "Node is not a leaf, but is missing a branch."
	
	def show(self):
		#
		# Activate self, and recursively hide any children that are visible. But
		# the children might need to time out first. Maybe we should keep a set:
		# currentlyVisible = {nodes}. Increment the frame counter for each node.
		# If a node is in range, it frame counter is reset to 0. If the counter
		# reaches (say) 100, it is deactivated...
		#
		pass
	
	def getRange(self, centre, radius):
		'''Get a list of all the leaves in the tree that have objects that are
		within the given bounds. This is an iterative depth-first search.'''
		bounds = Cube(centre, radius)
		leavesInRange = []
		queue = [self]
		
		while queue != []:
			n = queue.pop()
			
			if n.Left: # implies n.Right
				if n.MedianValue > bounds.LowerBound[n.Axis]:
					#
					# Within lower bound on this axis. Check the left tree. We
					# know this isn't a leaf, so we can assume n.Left exists.
					#
					queue.append(n.Left)
				if n.MedianValue < bounds.UpperBound[n.Axis]:
					#
					# Within upper bound on this axis. Check the right tree. We
					# know this isn't a leaf, so we can assume n.Right exists.
					#
					queue.append(n.Right)
			else:
				#
				# Found a leaf node. Still need to test it properly.
				#
				for o in n.Owner.children:
					if bounds.isInRange(o.getWorldPosition()):
						leavesInRange.append(n)
						break
		
		return leavesInRange
	