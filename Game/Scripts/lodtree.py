#
# Copyright 2009-2010 Alex Fraser <alex@phatcore.com>
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

from bge import logic

import bxt.types

from . import director

ACTIVATION_TIMEOUT = 120
DEBUG = False

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

class LODManager(metaclass=bxt.types.Singleton):
	'''A registrar of LODTrees. Each tree adds itself to this manager
	Other scripts then have a central place
	to access LODTrees, such as the module function activate_range, below.'''

	_prefix = ''

	def __init__(self):
		self.trees = set()

		if DEBUG:
			self.leavesVisible = 0
			self.branchesVisible = 0
			self.originalObjects = set(logic.getCurrentScene().objects)
			self.currentObjects = self.originalObjects.copy()

	def add_tree(self, tree):
		self.trees.add(tree)

	def remove_tree(self, tree):
		self.trees.discard(tree)

	@bxt.types.expose
	def update(self):
		'''Update which blades of grass are active. Call this once per frame.'''
		boundsList = []
		deadTrees = []

		# Collect colliders
		for actor in director.Director().actors:
			radius = 1.0
			try:
				radius = actor['LODRadius']
			except KeyError:
				actor['LODRadius'] = 1.0
			boundsList.append(KCube(actor.worldPosition, radius))

		# Collide with trees
		for t in self.trees:
			try:
				t.activate_range(boundsList)
			except SystemError:
				deadTrees.append(t)

		# Expunge dead trees
		for t in deadTrees:
			self.remove_tree(t)

		if DEBUG:
			currentObjects = set()
			currentObjects.update(logic.getCurrentScene().objects)
			newObjects = currentObjects.difference(self.currentObjects)
			deadObjects = self.currentObjects.difference(currentObjects)
			if len(newObjects) != 0 or len(deadObjects) != 0:
				print('Objects', len(logic.getCurrentScene().objects),
					'Leaves:', self.leavesVisible,
					'Branches:', self.branchesVisible)
				self.currentObjects = currentObjects

class KCube:
	'''A bounding cube with arbitrary dimensions, defined by its centre
	and radius.'''

	def __init__(self, centre, radius):
		self.lowerBound = []
		self.upperBound = []
		for component in centre:
			self.lowerBound.append(component - radius)
			self.upperBound.append(component + radius)

	def is_in_range(self, point):
		'''Tests whether a point is inside the cube.
		Returns: False if the point is outside; True otherwise.'''
		for i in range(len(point)):
			if point[i] < self.lowerBound[i]:
				return False
			elif point[i] > self.upperBound[i]:
				return False
		return True

class LODTree:
	'''A KD-tree of game objects for hierarchical LOD management.'''

	def __init__(self, root):
		'''Create a new LODTree.
		Parameters:
		root: The root LODNode of the tree.'''

		self.root = root
		LODManager().add_tree(self)

	def activate_range(self, boundsList):
		'''
		Traverse the tree to make the leaves that are in range 'active' - i.e.
		make their constituent parts visible, hiding the low-LOD clusters that
		would be shown otherwise.
		
		Parameters:
		bounds: The bounding cube to search for elements in.
		'''
		self.root.activate_range(boundsList)
		if not self.root.visible:
			self.root.visible = NS_IMPLICIT
		self.root.update()
	
	def pretty_print(self):
		self.root.pretty_print('', False)

class LODNode:
	'''A node in an LODTree. This is an abstract class; see LODBranch and
	LODLeaf.'''
	
	def __init__(self):
		self.visible = NS_HIDDEN
		self.name = None
	
	def activate_range(self, boundsList):
		pass
	
	def pulse(self, maxAge):
		'''
		Traverse the tree to cause active subtrees to age.
		
		Parameters:
		maxAge: Any subtree that has been visible for longer than this number of
		        frames will be deactivated.
		'''
		pass
	
	def update(self):
		'''Apply any changes that have been made to this node.'''
		pass
	
	def verify(self, anscestorVisible):
		if anscestorVisible:
			assert not bool(self.visible in (NS_VISIBLE, NS_IMPLICIT)), 'Error: path includes more than one visible node.'
	
	def deep_verify(self, anscestorVisible):
		self.verify(self, anscestorVisible)
	
	def pretty_print(self, indent, anscestorVisible):
		state = ""
		if self.visible == NS_HIDDEN:
			state = "NS_HIDDEN"
		elif self.visible == NS_VISIBLE_DESCENDANT:
			state = "NS_VISIBLE_DESCENDANT"
		elif self.visible == NS_VISIBLE:
			state = "NS_VISIBLE"
		elif self.visible == NS_IMPLICIT:
			state = "NS_IMPLICIT"
		print(indent + ('          state=%s' % state))
		
		try:
			self.verify(anscestorVisible)
		except AssertionError as e:
			print(indent + '          ' + str(e))

class LODBranch(LODNode):
	'''A branch in an LODTree. This type of node has two children: left and
	right. The left subtree contains all elements whose location on the axis is
	less than the medianValue. The right subtree contains all the other
	elements.'''

	# Don't really need a weakprop here, as these objects are carefully managed.
	#objectInstance = bxt.types.weakprop('objectInstance')
	
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
		
		self.owner = logic.getCurrentScene().objectsInactive[obName]
		#
		# Parents just cause problems with visibility.
		#
		self.owner.removeParent()
		self.objectInstance = None
		self.name = obName
		
		#
		# The number of dimensions do not need to be known, because each node
		# explicitely stores its axis.
		#
		self.medianValue = medianValue
		self.axis = axis
		self.left = left
		self.right = right
	
	def activate_range(self, boundsList):
		left = self.left
		right = self.right
		
		#
		# Activate the branches if they are not out of bounds on the current
		# axis. If they are out of bounds but were previously active, descend in
		# to them to increment their age.
		#
		# Explicitely-shown nodes are only ever hidden in pulse. Implicit nodes
		# need to be hidden after pulse is called if their sibling has since
		# become hidden.
		#
		leftInRange = [b for b in boundsList if self.medianValue > b.lowerBound[self.axis]]
		rightInRange = [b for b in boundsList if self.medianValue < b.upperBound[self.axis]]
		
		if len(leftInRange) > 0:
			left.activate_range(leftInRange)
		elif left.visible:
			left.pulse(ACTIVATION_TIMEOUT)
		
		if len(rightInRange) > 0:
			right.activate_range(rightInRange)
		elif right.visible:
			right.pulse(ACTIVATION_TIMEOUT)
		
		#
		# If either branch contains visible nodes, make sure the other branch is
		# shown too.
		#
		if left.visible and not right.visible:
			right.visible = NS_IMPLICIT
		if right.visible and not left.visible:
			left.visible = NS_IMPLICIT
		
		#
		# Set own visibility based on descendants'.
		#
		if left.visible:
			self.visible = NS_VISIBLE_DESCENDANT
		else:
			self.visible = NS_HIDDEN
		
		#
		# Render children.
		#
		left.update()
		right.update()
	
	def pulse(self, maxAge):
		if self.visible == NS_IMPLICIT:
			#
			# An implicit branch:
			# * Is visible.
			# * Has no visible descendants.
			# * Depends upon its sibling for visibility (has no age).
			# Therefore, remove the implicit flag from this node now: it will be
			# reinstated by the parent if need be.
			#
			self.visible = NS_HIDDEN
			return
		
		left = self.left
		right = self.right
		
		if left.visible:
			left.pulse(maxAge)
		if right.visible:
			right.pulse(maxAge)
		
		#
		# If either branch contains visible nodes, make sure the other branch is
		# shown too.
		#
		if left.visible and not right.visible:
			right.visible = NS_IMPLICIT
		if right.visible and not left.visible:
			left.visible = NS_IMPLICIT
		
		#
		# Set own visibility based on descendants'.
		#
		if left.visible:
			self.visible = NS_VISIBLE_DESCENDANT
		else:
			self.visible = NS_HIDDEN
		
		#
		# Render children.
		#
		left.update()
		right.update()
	
	def update(self):
		'''Apply any changes that have been made to this node.'''
		# A branch can only ever be implicitly visible, or hidden (i.e. only
		# leaves can be explicitly visible).
		if self.visible == NS_IMPLICIT:
			if self.objectInstance == None:
				self.objectInstance = logic.getCurrentScene().addObject(self.owner, self.owner)
				if DEBUG:
					LODManager().branchesVisible += 1
		else:
			if self.objectInstance != None:
				self.objectInstance.endObject()
				self.objectInstance = None
				if DEBUG:
					LODManager().branchesVisible -= 1
	
	def verify(self, anscestorVisible):
		LODNode.verify(self, anscestorVisible)
		assert bool(self.left.visible) == bool(self.right.visible), 'Children have unbalanced visibility.'
		assert bool(self.objectInstance) == (self.visible in (NS_VISIBLE, NS_IMPLICIT)), 'object visibility doesn\'t match node state.'
	
	def deep_verify(self, anscestorVisible):
		LODNode.verify(self, anscestorVisible)
		if self.visible in (NS_VISIBLE, NS_IMPLICIT):
			anscestorVisible = True
		self.left.deep_verify(anscestorVisible)
		self.right.deep_verify(anscestorVisible)
	
	def pretty_print(self, indent, anscestorVisible):
		print(indent + ('LODBranch: %s, axis=%d, median=%f' % (self.owner.name, self.axis, self.medianValue)))
		
		LODNode.pretty_print(self, indent, anscestorVisible)
		
		if self.visible > NS_VISIBLE_DESCENDANT:
			anscestorVisible = True
		self.left.pretty_print(indent + ' L ', anscestorVisible)
		self.right.pretty_print(indent + ' R ', anscestorVisible)

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
		
		#
		# objectPairs is a list of tuples: (positionObject, meshObject). When
		# this node is activated, meshObject will be instantiated in the same
		# position as positionObject. This allows the same meshObject (e.g. a
		# group) to be re-used for several elements in the tree.
		#
		self.objectPairs = []
		self.name = str(obNames)
		sceneObs = logic.getCurrentScene().objectsInactive
		for name in obNames:
			oPos = sceneObs[name]
			oMesh = oPos
			if 'LODObject' in oPos:
				oMesh = sceneObs[oPos['LODObject']]

			#
			# Parents just cause problems with visibility.
			#
			oPos.removeParent()
			self.objectPairs.append((oPos, oMesh))

		self.lastFrameVisible = False
		# No fancy sets here; just be really careful!
		#self.objectInstances = bxt.types.GameObjectSet()
		self.objectInstances = set()
		
		self.numFramesActive = -1
	
	def activate_range(self, boundsList):
		'''Search the objects owned by this node. If any of them are within
		range, this node will be shown.'''
		for (oPos, _) in self.objectPairs:
			for bounds in boundsList:
				if bounds.is_in_range(oPos.worldPosition):
					self.visible = NS_VISIBLE
					self.numFramesActive = 0
					return
	
	def pulse(self, maxAge):
		'''Make this node age by one frame. If it has been visible for too long
		it will be hidden.'''
		if self.visible == NS_IMPLICIT:
			#
			# An implicit leaf:
			# * Is visible.
			# * Depends upon its sibling for visibility (has no age).
			# Therefore, remove the implicit flag from this node now: it will be
			# reinstated by the parent if need be.
			#
			self.visible = NS_HIDDEN
			return
		
		self.numFramesActive = self.numFramesActive + 1
		if self.numFramesActive > maxAge:
			self.visible = NS_HIDDEN
	
	def update(self):
		'''Apply any changes that have been made to this node.'''
		if self.visible:
			if not self.lastFrameVisible:
				try:
					scene = logic.getCurrentScene()
					for (oPos, oMesh) in self.objectPairs:
						o = bxt.types.add_and_mutate_object(scene, oMesh, oPos)
						self.objectInstances.add(o)
				finally:
					self.lastFrameVisible = True
					if DEBUG:
						LODManager().leavesVisible += 1
		else:
			if self.lastFrameVisible:
				try:
					for oInst in self.objectInstances:
						oInst.endObject()
					self.objectInstances.clear()
				finally:
					self.lastFrameVisible = False
					if DEBUG:
						LODManager().leavesVisible -= 1
	
	def verify(self, anscestorVisible = None):
		LODNode.verify(self, anscestorVisible)
		assert (len(self.objectInstances) > 0) == (self.visible in (NS_VISIBLE, NS_IMPLICIT)), 'object visibility doesn\'t match node state.'
	
	def pretty_print(self, indent, anscestorVisible):
		print(indent + 'LODLeaf: age=%d children=' % self.numFramesActive, end=' ')
		print(self.name)
		LODNode.pretty_print(self, indent, anscestorVisible)
