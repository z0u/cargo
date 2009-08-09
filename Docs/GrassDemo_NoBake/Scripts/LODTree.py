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
import Utilities
from Blender import Mathutils

ACTIVATION_TIMEOUT = 120

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
	
	def __init__(self, objects, dimensions, leafSize = 4, parentOb = None):
		'''
		Create a new LODTree. The hierarchy will exist in Python, and will be
		reflected in the scene hierarchy using Empty objects for branches.
		
		Parameters:
		objects:    A list of all objects to store in the KD-tree.
		dimensions: The number of dimensions to use for searching.
		            1 = x-axis only; 2 = x and y axes; 3 = x, y and z.
		leafSize:   The maximum number of objects to hold in a leaf node.
		            Smaller values here mean deeper trees.
		parentOb:   The object to parent the root object of the tree to.
		'''
		self.LeafSize = leafSize
		self.Dimensions = dimensions
		self.MaxDepth = 0
		
		if len(objects) > leafSize:
			self.Root = LODBranch(objects, 0, self)
		else:
			self.Root = LODLeaf(objects, 0, self)
		
		if parentOb:
			self.Root.SetParent(parentOb)

		_lodManager.AddTree(self)
	
	def ActivateRange(self, bounds):
		'''
		Traverse the tree to make the leaves that are in range 'active'. Active
		leaves will have dynamic objects instantiated in place of each of the
		objects they control.
		
		Parameters:
		bounds: The bounding cube to search for elements in.
		'''
		self.Root.ActivateRange(bounds)
	
	def PrettyPrint(self):
		self.Root.PrettyPrint('')

def CreateLODTree(cont):
	o = cont.owner
	objects = []
	objects.extend(o.children)
	LODTree(objects, o['LODDimensions'], leafSize = o['LODLeafSize'], parentOb = o)

class LODNode:
	'''A node in an LODTree. This is an abstract class; see LODBranch and
	LODLeaf.'''
	
	def __init__(self):
		self.Active = False
	
	def ActivateRange(self, bounds):
		'''See LODNode.ActivateRange.'''
		pass
	
	def Pulse(self, maxAge):
		'''
		Traverse the tree to cause active subtrees to age.
		
		Parameters:
		maxAge: Any subtree that has been visible for longer than this number of
		        frames will be deactivated.
		'''
		pass
	
	def PrettyPrint(self, indent):
		print indent + ('          active=%s' % self.Active)

class LODBranch(LODNode):
	'''A branch in an LODTree. This type of node has two children: Left and
	Right. The left subtree contains all elements whose location on the Axis is
	less than the MedianValue. The right subtree contains all the other
	elements.'''
	
	def __init__(self, objects, depth, tree):
		'''
		Create an LOD sub-tree.
		
		Parameters:
		objects: A list of objects to place in this sub-tree.
		depth:   The number of ancestors that this node has.
		tree:    The tree that owns this subtree.
		'''
		
		LODNode.__init__(self)
		self.Axis = depth % tree.Dimensions
		
		scene = GameLogic.getCurrentScene()
		templateOb = scene.objectsInactive['OBLODBranchTemplate']
		self.Object = scene.addObject(templateOb, templateOb)
		
		#
		# Sort the objects along the current axis.
		#
		objects.sort(lambda a, b: cmp(a.worldPosition[self.Axis],
		                              b.worldPosition[self.Axis]))
		
		#
		# The median value is the location of the middle element on the current
		# axis.
		#
		medianIndex = len(objects) / 2
		self.MedianValue = objects[medianIndex].worldPosition[self.Axis]
		
		#
		# Create children.
		#
		nextDepth = depth + 1
		leftObjects = objects[0:medianIndex]
		if len(leftObjects) > tree.LeafSize:
			self.Left = LODBranch(leftObjects, nextDepth, tree)
		else:
			self.Left = LODLeaf(leftObjects, nextDepth, tree)
		
		rightObjects = objects[medianIndex:]
		if len(rightObjects) > tree.LeafSize:
			self.Right = LODBranch(rightObjects, nextDepth, tree)
		else:
			self.Right = LODLeaf(rightObjects, nextDepth, tree)
		
		#
		# Set the position of this branch's Empty object, and set it as the
		# parent of the child nodes.
		#
		self.MeanPosition = (self.Left.MeanPosition + self.Right.MeanPosition / 2.0)
		self.Object.worldPosition = self.MeanPosition
		self.Left.SetParent(self.Object)
		self.Right.SetParent(self.Object)
	
	def SetParent(self, parentOb):
		self.Object.setParent(parentOb)
	
	def ActivateRange(self, bounds):
		'''
		Activate the branches if they are not out of bounds on the current
		axis. If they are out of bounds but were previously active, descend in
		to them to increment their age.
		'''
		
		#
		# Explicitely-shown nodes are only ever hidden in Pulse. Implicit nodes
		# need to be hidden after Pulse is called if their sibling has since
		# become hidden.
		#
		if self.MedianValue > bounds.LowerBound[self.Axis]:
			self.Left.ActivateRange(bounds)
		elif self.Left.Active:
			self.Left.Pulse(ACTIVATION_TIMEOUT)
		
		if self.MedianValue < bounds.UpperBound[self.Axis]:
			self.Right.ActivateRange(bounds)
		elif self.Right.Active:
			self.Right.Pulse(ACTIVATION_TIMEOUT)
		
		#
		# Set own visibility based on descendants'.
		#
		self.Active = self.Left.Active or self.Right.Active
	
	def Pulse(self, maxAge):
		if self.Left.Active:
			self.Left.Pulse(maxAge)
		if self.Right.Active:
			self.Right.Pulse(maxAge)
		self.Active = self.Left.Active or self.Right.Active
	
	def PrettyPrint(self, indent):
		print indent + ('LODBranch: axis=%d, median=%f' % (self.Axis, self.MedianValue))
		
		LODNode.PrettyPrint(self, indent)
		
		self.Left.PrettyPrint(indent + ' L ')
		self.Right.PrettyPrint(indent + ' R ')

class LODLeaf(LODNode):
	'''A leaf node in an LODTree. A leaf is the bottom of the tree, but it can
	still have multiple children.'''
	
	def __init__(self, objects, depth, tree):
		'''
		Create a new LODLeaf node.
		
		Parameters:
		objects: A list of objects to place in this sub-tree.
		depth:   The number of ancestors that this node has.
		tree:    The tree that owns this subtree.
		'''
		LODNode.__init__(self)
		self.ObjectsPairs = []
		scene = GameLogic.getCurrentScene()
		self.MeanPosition = Mathutils.Vector(0.0, 0.0, 0.0)
		for o in objects:
			templateOb = scene.objectsInactive['OB' + o['LODObject']]
			self.ObjectsPairs.append((o, templateOb))
		self.MeanPosition = self.MeanPosition / float(len(objects))
		self.DynamicObjects = []
		
		self.NumFramesActive = -1
	
	def SetParent(self, parentOb):
		for (staticOb, _) in self.ObjectsPairs:
			staticOb.setParent(parentOb)
	
	def ActivateRange(self, bounds):
		'''
		Search the objects owned by this node. If any of them are within
		range, this node will be shown.
		'''
		inRange = False
		for (staticOb, _) in self.ObjectsPairs:
			if bounds.isInRange(staticOb.worldPosition):
				inRange = True
				break
		
		if inRange:
			self.Active = True
			self.NumFramesActive = 0
			self.Update()
		else:
			self.Pulse(ACTIVATION_TIMEOUT)
	
	def Pulse(self, maxAge):
		'''
		Make this node age by one frame. If it has been visible for too long
		it will be hidden.
		'''
		self.NumFramesActive = self.NumFramesActive + 1
		if self.NumFramesActive > maxAge:
			self.Active = False
		self.Update()
	
	def Update(self):
		'''
		Apply the visibility settings of this node to the underlying Game
		Objects.
		'''
		if self.Active:
			if len(self.DynamicObjects) == 0:
				scene = GameLogic.getCurrentScene()
				for (staticOb, templateOb) in self.ObjectsPairs:
					dynOb = scene.addObject(templateOb, staticOb)
					self.DynamicObjects.append(dynOb)
					staticOb.visible = False
		else:
			if len(self.DynamicObjects) > 0:
				for (staticOb, _) in self.ObjectsPairs:
					staticOb.visible = True
				for dynOb in self.DynamicObjects:
					dynOb.endObject()
				self.DynamicObjects = []
	
	def PrettyPrint(self, indent):
		print indent + 'LODLeaf: age=%d children=' % self.NumFramesActive,
		for (staticOb, templateOb) in self.ObjectsPairs:
			print "(%s, %s)" % (staticOb.name, templateOb.name),
		print
		LODNode.PrettyPrint(self, indent)
