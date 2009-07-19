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

ACTIVATION_TIMEOUT = 120

#
# Node states, from weakest to strongest. In a path from the root to any leaf,
# only one node can be active. These states capture that fact.
# NS_HIDDEN evaluates to False (hidden); all other states evaluate to True
# (visible in some manner).
#
# NS_HIDDEN:   No part of this subtree is visible: an anscestor must be visible
#              instead.
# NS_VISIBLE_DESCENDANT: A leaf of this subtree is active.
# NS_VISIBLE:  This node is visible.
# NS_IMPLICIT: This node is visible because its sibling is not hidden.
#
NS_HIDDEN             = 0
NS_VISIBLE_DESCENDANT = 1
NS_VISIBLE            = 2
NS_IMPLICIT           = 3

class LODManager:
	'''A registrar of LODTrees. Each tree adds itself to this manager
	(singleton; instance created below). Other scripts then have a central place
	to access LODTrees, such as the module function ActivateRange, below.'''
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
	'''
	Activate all leaves in all trees that are close to the current controller's
	owner. The object should have a property called 'LODRadius': Any leaf closer
	than 'LODRadius' will be activated, along with its siblings.
	
	This should only be called once per frame; therefore, only one object can be
	the centre of activity at a time.
	'''
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
		self.ErrorState = False
	
	def ActivateRange(self, bounds):
		'''
		Traverse the tree to make the leaves that are in range 'active' - i.e.
		make their constituent parts visible, hiding the low-LOD clusters that
		would be shown otherwise.
		
		Parameters:
		bounds: The bounding cube to search for elements in.
		'''
		if self.ErrorState:
			return
		
		self.Root.ActivateRange(bounds)
		if not self.Root.Visibility:
			self.Root.Visibility = NS_IMPLICIT
		self.Root.Update()
	
	def PrettyPrint(self):
		self.Root.PrettyPrint('', False)

class LODNode:
	'''A node in an LODTree. This is an abstract class; see LODBranch and
	LODLeaf.'''
	
	def __init__(self):
		self.Visibility = NS_HIDDEN
		self.Name = None
	
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
	
	def Update(self):
		'''Apply any changes that have been made to this node.'''
		pass
	
	def Verify(self, anscestorVisible):
		if anscestorVisible:
			assert not bool(self.Visibility in (NS_VISIBLE, NS_IMPLICIT)), 'Error: path includes more than one visible node.'
	
	def DeepVerify(self, anscestorVisible):
		self.Verify(self, anscestorVisible)
	
	def PrettyPrint(self, indent, anscestorVisible):
		state = ""
		if self.Visibility == NS_HIDDEN:
			state = "NS_HIDDEN"
		elif self.Visibility == NS_VISIBLE_DESCENDANT:
			state = "NS_VISIBLE_DESCENDANT"
		elif self.Visibility == NS_VISIBLE:
			state = "NS_VISIBLE"
		elif self.Visibility == NS_IMPLICIT:
			state = "NS_IMPLICIT"
		print indent + ('          state=%s' % state)
		
		try:
			self.Verify(anscestorVisible)
		except AssertionError, e:
			print indent + '          ' + str(e)

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
		#
		# Parents just cause problems with visibility.
		#
		self.Object.removeParent()
		self.ObjectInstance = None
		self.Name = obName
		
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
		elif left.Visibility:
			left.Pulse(ACTIVATION_TIMEOUT)
		
		if self.MedianValue < bounds.UpperBound[self.Axis]:
			right.ActivateRange(bounds)
		elif right.Visibility:
			right.Pulse(ACTIVATION_TIMEOUT)
		
		#
		# If either branch contains visible nodes, make sure the other branch is
		# shown too.
		#
		if left.Visibility and not right.Visibility:
			right.Visibility = NS_IMPLICIT
		if right.Visibility and not left.Visibility:
			left.Visibility = NS_IMPLICIT
		
		#
		# Set own visibility based on descendants'.
		#
		if left.Visibility:
			self.Visibility = NS_VISIBLE_DESCENDANT
		else:
			self.Visibility = NS_HIDDEN
		
		#
		# Render children.
		#
		left.Update()
		right.Update()
	
	def Pulse(self, maxAge):
		if self.Visibility == NS_IMPLICIT:
			#
			# An implicit branch:
			# * Is visible.
			# * Has no visible descendants.
			# * Depends upon its sibling for visibility (has no age).
			# Therefore, remove the implicit flag from this node now: it will be
			# reinstated by the parent if need be.
			#
			self.Visibility = NS_HIDDEN
			return
		
		left = self.Left
		right = self.Right
		
		if left.Visibility:
			left.Pulse(maxAge)
		if right.Visibility:
			right.Pulse(maxAge)
		
		#
		# If either branch contains visible nodes, make sure the other branch is
		# shown too.
		#
		if left.Visibility and not right.Visibility:
			right.Visibility = NS_IMPLICIT
		if right.Visibility and not left.Visibility:
			left.Visibility = NS_IMPLICIT
		
		#
		# Set own visibility based on descendants'.
		#
		if left.Visibility:
			self.Visibility = NS_VISIBLE_DESCENDANT
		else:
			self.Visibility = NS_HIDDEN
		
		#
		# Render children.
		#
		left.Update()
		right.Update()
	
	def Update(self):
		'''Apply any changes that have been made to this node.'''
		if self.Visibility == NS_IMPLICIT:
			if not self.ObjectInstance:
				self.ObjectInstance = GameLogic.getCurrentScene().addObject(self.Object, self.Object)
		else:
			if self.ObjectInstance:
				self.ObjectInstance.endObject()
				self.ObjectInstance = None
	
	def Verify(self, anscestorVisible):
		LODNode.Verify(self, anscestorVisible)
		assert bool(self.Left.Visibility) == bool(self.Right.Visibility), 'Children have unbalanced visibility.'
		assert bool(self.ObjectInstance) == (self.Visibility in (NS_VISIBLE, NS_IMPLICIT)), 'Object visibility doesn\'t match node state.'
	
	def DeepVerify(self, anscestorVisible):
		LODNode.Verify(self, anscestorVisible)
		if self.Visibility in (NS_VISIBLE, NS_IMPLICIT):
			anscestorVisible = True
		self.Left.DeepVerify(anscestorVisible)
		self.Right.DeepVerify(anscestorVisible)
	
	def PrettyPrint(self, indent, anscestorVisible):
		print indent + ('LODBranch: %s, axis=%d, median=%f' % (self.Object.name, self.Axis, self.MedianValue))
		
		LODNode.PrettyPrint(self, indent, anscestorVisible)
		
		if self.Visibility > NS_VISIBLE_DESCENDANT:
			anscestorVisible = True
		self.Left.PrettyPrint(indent + ' L ', anscestorVisible)
		self.Right.PrettyPrint(indent + ' R ', anscestorVisible)

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
		self.Name = str(obNames)
		sceneObs = GameLogic.getCurrentScene().objectsInactive
		for name in obNames:
			o = sceneObs['OB' + name]
			#
			# Parents just cause problems with visibility.
			#
			o.removeParent()
			self.Objects.append(o)
		self.ObjectInstances = []
		
		self.NumFramesActive = -1
	
	def ActivateRange(self, bounds):
		'''Search the objects owned by this node. If any of them are within
		range, this node will be shown.'''
		for o in self.Objects:
			if bounds.isInRange(o.worldPosition):
				self.Visibility = NS_VISIBLE
				self.NumFramesActive = 0
				return
	
	def Pulse(self, maxAge):
		'''Make this node age by one frame. If it has been visible for too long
		it will be hidden.'''
		if self.Visibility == NS_IMPLICIT:
			#
			# An implicit leaf:
			# * Is visible.
			# * Depends upon its sibling for visibility (has no age).
			# Therefore, remove the implicit flag from this node now: it will be
			# reinstated by the parent if need be.
			#
			self.Visibility = NS_HIDDEN
			return
		
		self.NumFramesActive = self.NumFramesActive + 1
		if self.NumFramesActive > maxAge:
			self.Visibility = NS_HIDDEN
	
	def Update(self):
		'''Apply any changes that have been made to this node.'''
		if self.Visibility:
			if len(self.ObjectInstances) == 0:
				scene = GameLogic.getCurrentScene()
				for o in self.Objects:
					self.ObjectInstances.append(scene.addObject(o, o))
		else:
			if len(self.ObjectInstances) > 0:
				for o in self.ObjectInstances:
					o.endObject()
				self.ObjectInstances = []
	
	def Verify(self, anscestorVisible = None):
		LODNode.Verify(self, anscestorVisible)
		assert (len(self.ObjectInstances) > 0) == (self.Visibility in (NS_VISIBLE, NS_IMPLICIT)), 'Object visibility doesn\'t match node state.'
	
	def PrettyPrint(self, indent, anscestorVisible):
		print indent + 'LODLeaf: age=%d children=' % self.NumFramesActive,
		print self.Name
		LODNode.PrettyPrint(self, indent, anscestorVisible)
