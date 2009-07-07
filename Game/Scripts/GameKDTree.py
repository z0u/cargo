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

class LODTree:
	'''A KD-tree of game objects for hierarchical LOD management.'''
	def __init__(self, root):
		'''Create a new LODTree from an existing hierarchy of game objects.
		Each object in the tree should have the following parameters:
		enum  KDType        { KDLeftBranch, KDRightBranch, KDLeaf }
		float KDAxis
		float KDMedianValue'''
		
		self.Root = LODNode(root)
	
	def getRange(self, centre, radius):
		'''Get a list of all the leaves in the tree that have objects that are
		within the given bounds. This is an iterative depth-first search.'''
		bounds = Cube(centre, radius)
		leavesInRange = []
		queue = [self.Root]
		
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

class LODNode:
	def __init__(self, owner):
		'''Populate this tree with a hierarchy. The hierarchy should have been
		created previously using the BlenderObjectXYTree.Serialise method.'''
		self.Owner = owner
		
		#
		# In a path from the root to any leaf, only one node can be active.
		# Visible:        This node is visible. None of its descendants or
		#                 anscestors are.
		# SubtreeVisible: Some part of the sub-tree is visible (this node or
		#                 some of its descendants).
		# Implicit:       This node has no descendants in range, but it is
		#                 visible because its sibling has been activated.
		#
		self.Visible = false
		self.SubtreeVisible = false
		self.Implicit = false
	
	def ActivateRange(self, bounds):
		'''
		Traverse the tree to make the leaves that are in range 'active' - i.e.
		make their constituent parts visible, hiding the low-LOD clusters that
		would be shown otherwise.
		
		Parameters:
		bounds: The bounding cube to search for elements in.
		'''
		pass
	
	def Pulse(self, maxAge):
		'''
		Traverse the tree to cause active subtrees to age.
		
		Parameters:
		maxAge: Any subtree that has been visible for longer than this number of
		        frames will be deactivated.
		'''
		pass
	
	def Show(self):
		if self.Visible:
			return
		
		assert(not self.SubtreeVisible)
		
		self.Owner.visible = true
		self.Visible = true
		self.SubtreeVisible = true
	
	def Hide(self):
		if not self.Visible:
			return
		self.Owner.visible = false
		self.Visible = false
		self.SubtreeVisible = false
		self.Implicit = false
	
	def Implicate(self):
		'''Make this node visible even though no descendant leaves are within
		range.'''
		self.Show()
		self.Implicit = true

class LODBranch(LODNode):
	def __init__(self, owner):
		LODNode.__init__(self, owner)
		
		#
		# The number of dimensions are not needed to be known, because each node
		# explicitely stores its axis.
		#
		
		self.MedianValue = owner['KDMedianValue']
		self.Axis = owner['KDAxis']
		self.Left = None
		self.Right = None
		
		for child in owner.children:
			if not child.has_key('KDType'):
				continue
			
			childNode = None
			if child['KDType'] == 'Branch':
				childNode = LODBranch(child)
			elif child['KDType'] == 'Leaf':
				childNode = LODLeaf(child)
				
			if child['KDSide'] == 'Left':
				if self.Left:
					raise StructureError, "%s has two left branches." % owner.name
				self.Left = childNode
			elif child['KDSide'] == 'Right':
				if self.Right:
					raise StructureError, "%s has two right branches." % owner.name
				self.Right = childNode
			else:
				raise StructureError, "%s has unknown KDType: %s" % (child.name, child['KDType'])
			
		if not self.Left or not self.Right:
			raise StructureError, "Node is not a leaf, but is missing a branch."
	
	def ActivateRange(self, bounds):
		#
		# Activate the branches if they are not out of bounds on the current
		# axis. If they are out of bounds but were previously active, descend in
		# to them to increment their age.
		#
		left = self.Left
		right = self.Right
		
		if self.MedianValue > bounds.LowerBound[n.Axis]:
			left.ActivateRange(bounds)
		elif left.SubtreeVisible:
			left.Pulse()
			if (not left.SubtreeVisible) and right.Implicit:
				right.Hide()
		
		if self.MedianValue < bounds.UpperBound[n.Axis]:
			right.ActivateRange(bounds)
		elif right.SubtreeVisible:
			right.Pulse()
			if (not right.SubtreeVisible) and left.Implicit:
				left.Hide()
		
		#
		# If either branch contains visible nodes, make sure the other branch is
		# shown too.
		#
		if left.SubtreeVisible and not right.SubtreeVisible:
			right.Implicate()
		if right.SubtreeVisible and not left.SubtreeVisible:
			left.Implicate()
		
		self.SubtreeVisible = self.Visible or left.SubtreeVisible or right.SubtreeVisible
	
	def Pulse(self, maxAge):
		left = self.Left
		right = self.Right
		
		if left.SubtreeVisible:
			left.Pulse()
			if (not left.SubtreeVisible) and right.Implicit:
				right.Hide()
		
		if right.SubtreeVisible:
			right.Pulse()
			if (not right.SubtreeVisible) and left.Implicit:
				left.Hide()
		
		self.SubtreeVisible = self.Visible or left.SubtreeVisible or right.SubtreeVisible

class LODLeaf(LODNode):
	def __init__(self, owner):
		LODNode.__init__(self, owner)
		self.NumFramesActive = -1
	
	def ActivateRange(self, bounds, implicitNodes):
		for o in self.Owner.children:
			if bounds.isInRange(o.getWorldPosition()):
				self.Show()
				return
	
	def Pulse(self, maxAge):
		self.NumFramesActive = self.NumFramesActive + 1
		if self.NumFramesActive > maxAge:
			self.Hide()
	
	def Show(self):
		LODNode.Show(self)
		self.NumFramesActive = 0
	
	def Hide(self):
		LODNode.Hide(self)
		self.NumFramesActive = -1
