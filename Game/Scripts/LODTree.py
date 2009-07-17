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

import GameLogic

ACTIVATION_TIMEOUT = 1

class LODManager:
	def __init__(self):
		self.Trees = []
	
	def AddTree(self, tree):
		self.Trees.append(tree)
	
	def ActivateRange(self, centre, radius):
		bounds = Cube(centre, radius)
		for t in self.Trees:
			t.ActivateRange(bounds)

_lodManager = LODManager()

def ActivateRange(cont):
	ob = cont.owner
	_lodManager.ActivateRange(ob.worldPosition, ob['LODRadius'])

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
		Returns: False if the point is outside; True otherwise.'''
		for i in xrange(len(point)):
			if point[i] < self.LowerBound[i]:
				return False
			elif point[i] > self.UpperBound[i]:
				return False
		return True

class LODTree:
	'''A KD-tree of game objects for hierarchical LOD management.'''
	
	def __init__(self, root):
		'''Create a new LODTree.
		Parameters:
		root: The root LODNode of the tree.'''
		
		self.Root = root
		_lodManager.AddTree(self)
	
	def ActivateRange(self, bounds):
		'''
		Traverse the tree to make the leaves that are in range 'active' - i.e.
		make their constituent parts visible, hiding the low-LOD clusters that
		would be shown otherwise.
		
		Parameters:
		bounds: The bounding cube to search for elements in.
		'''
		self.Root.ActivateRange(bounds)
		if not self.Root.SubtreeVisible:
			self.Root.Implicate()
			self.Root.Update()
	
	def PrettyPrint(self):
		self.Root.PrettyPrint('')

class LODNode:
	'''A node in an LODTree. This is an abstract class; see LODBranch and
	LODLeaf.'''
	
	def __init__(self):
		#
		# In a path from the root to any leaf, only one node can be active.
		# Visible:        This node is visible. None of its descendants or
		#                 anscestors are.
		# SubtreeVisible: Some part of the sub-tree is visible (this node or
		#                 some of its descendants).
		# Implicit:       This node has no descendants in range, but it is
		#                 visible because its sibling has been activated.
		#
		self.Visible = False
		self.SubtreeVisible = False
		self.Implicit = False
	
	def ActivateRange(self, bounds):
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
		'''Make this node visible. Rendering is deferred: call Update to apply
		the changes.'''
		if self.Visible:
			return
		
		assert(not self.SubtreeVisible)
		
		self.Visible = True
		self.SubtreeVisible = True
	
	def Hide(self):
		'''Make this node invisible. Rendering is deferred: call Update to apply
		the changes.'''
		self.Implicit = False
		
		if not self.Visible:
			return
		
		self.Visible = False
		self.SubtreeVisible = False
	
	def Implicate(self):
		'''Make this node visible even though no descendant leaves are within
		range. This is called when a sibling is visible.'''
		self.Show()
		self.Implicit = True
	
	def Update(self):
		'''Apply any changes that have been made to this node.'''
		pass
	
	def PrettyPrint(self, indent):
		print indent + ('          vis=%s, subVis=%s, imp=%s' %
		                (self.Visible, self.SubtreeVisible, self.Implicit))

class LODBranch(LODNode):
	'''A branch in an LODTree. This type of node has two children: Left and
	Right. The left subtree contains all elements whose location on the Axis is
	less than the MedianValue. The right subtree contains all the other
	elements.'''
	
	def __init__(self, obName, left, right, axis, medianValue):
		'''
		Create a new LODBranch node.
		
		Parameters:
		obName:      The name of the object that represents this node. It should
		             be the sum of all the descendants. It must be on a hidden
		             layer.
		left:        The left LODNode.
		right:       The right LODNode.
		axis:        The axis to search on.
		medianValue: The location of the median element (of all the leaves) on
		             the given axis.
		'''
		
		LODNode.__init__(self)
		
		self.Object = GameLogic.getCurrentScene().objectsInactive['OB' + obName]
		self.ObjectInstance = None
		
		#
		# The number of dimensions do not need to be known, because each node
		# explicitely stores its axis.
		#
		self.MedianValue = medianValue
		self.Axis = axis
		self.Left = left
		self.Right = right
	
	def ActivateRange(self, bounds):
		left = self.Left
		right = self.Right
		
		#
		# Activate the branches if they are not out of bounds on the current
		# axis. If they are out of bounds but were previously active, descend in
		# to them to increment their age.
		#
		# Explicitely-shown nodes are only ever hidden in Pulse. Implicit nodes
		# need to be hidden after Pulse is called if their sibling has since
		# become hidden.
		#
		if self.MedianValue > bounds.LowerBound[self.Axis]:
			left.ActivateRange(bounds)
		elif left.SubtreeVisible and not left.Implicit:
			left.Pulse(ACTIVATION_TIMEOUT)
			if (not left.SubtreeVisible) and right.Implicit:
				right.Hide()
		
		if self.MedianValue < bounds.UpperBound[self.Axis]:
			right.ActivateRange(bounds)
		elif right.SubtreeVisible and not right.Implicit:
			right.Pulse(ACTIVATION_TIMEOUT)
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
		
		if right.Implicit and left.Implicit:
			print 'Error: %s: Both children are implicit.' % self.Object.name
		
		#
		# No more operations will occur on child nodes for this frame, so render
		# them now.
		#
		left.Update()
		right.Update()
		
		self.SubtreeVisible = left.SubtreeVisible or right.SubtreeVisible
	
	def Pulse(self, maxAge):
		if self.Implicit:
			#
			# An implicit branch:
			# * Is visible.
			# * Has no visible descendants.
			# * Depends upon its sibling for visibility (has no age).
			# Therefore, there is nothing to do here.
			#
			return
		
		left = self.Left
		right = self.Right
		
		if left.SubtreeVisible:
			left.Pulse(maxAge)
			if (not left.SubtreeVisible) and right.Implicit:
				right.Hide()
		
		if right.SubtreeVisible:
			right.Pulse(maxAge)
			if (not right.SubtreeVisible) and left.Implicit:
				left.Hide()
		
		#
		# No more operations will occur on child nodes for this frame, so render
		# them now.
		#
		left.Update()
		right.Update()
		
		self.SubtreeVisible = left.SubtreeVisible or right.SubtreeVisible
	
	def Update(self):
		'''Apply any changes that have been made to this node.'''
		return
		if self.Visible:
			if not self.ObjectInstance:
				self.ObjectInstance = GameLogic.getCurrentScene().addObject(self.Object, self.Object)
		else:
			if self.ObjectInstance:
				self.ObjectInstance.endObject()
				self.ObjectInstance = None
	
	def PrettyPrint(self, indent):
		print indent + ('LODBranch: %s, axis=%d, median=%f' % (self.Object.name, self.Axis, self.MedianValue))
		LODNode.PrettyPrint(self, indent)
		self.Left.PrettyPrint(indent + ' L ')
		self.Right.PrettyPrint(indent + ' R ')

class LODLeaf(LODNode):
	'''A leaf node in an LODTree. A leaf is the bottom of the tree, but it can
	still have multiple children.'''
	
	def __init__(self, obNames):
		'''
		Create a new LODLeaf node.
		
		Parameters:
		obNames: A list of objects that this node represents. These must be on
		         a hidden layer.
		'''
		LODNode.__init__(self)
		
		self.Objects = []
		sceneObs = GameLogic.getCurrentScene().objectsInactive
		for name in obNames:
			o = sceneObs['OB' + name]
			self.Objects.append(o)
		self.ObjectInstances = []
		
		self.NumFramesActive = -1
	
	def ActivateRange(self, bounds):
		'''Search the objects owned by this node. If any of them are within
		range, this node will be shown.'''
		for o in self.Objects:
			if bounds.isInRange(o.worldPosition):
				self.Show()
				return
	
	def Pulse(self, maxAge):
		'''Make this node age by one frame. If it has been visible for too long
		it will be hidden.'''
		self.NumFramesActive = self.NumFramesActive + 1
		if self.NumFramesActive > maxAge:
			self.Hide()
	
	def Show(self):
		LODNode.Show(self)
		self.NumFramesActive = 0
	
	def Hide(self):
		LODNode.Hide(self)
		self.NumFramesActive = -1
	
	def Update(self):
		'''Apply any changes that have been made to this node.'''
		if self.Visible:
			if len(self.ObjectInstances) == 0:
				scene = GameLogic.getCurrentScene()
				for o in self.Objects:
					self.ObjectInstances.append(scene.addObject(o, o))
		else:
			for o in self.ObjectInstances:
				o.endObject()
			self.ObjectInstances = []
	
	def PrettyPrint(self, indent):
		print indent + 'LODLeaf:',
		for o in self.Objects:
			print o.name,
		print
		LODNode.PrettyPrint(self, indent)
