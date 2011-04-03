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

import bpy
import Blender

#
# This is only for debugging: makes the tree print out with indentation, but
# it will not be parsable.
#
#INDENT_STEP = '    '
INDENT_STEP = ''

class StateError(Exception):
	pass

class Progress:
	def __init__(self, message, upperBound, updateStep = 0.001):
		self.upper = upperBound
		self.message = message
		self.currentValue = 0
		self.currentFraction = 0.0
		self.lastFraction = 0.0
		self.updateStep = updateStep
		self.set_value(0.0)

	def increment(self, value):
		self.set_value(self.currentValue + value)

	def set_value(self, value):
		self.currentValue = value
		self.currentFraction = float(value) / float(self.upper)
		if (self.currentFraction > (self.lastFraction + self.updateStep) or
		    self.currentFraction <= 0.0 or
		    self.currentFraction >= 1.0):
			self.update()

	def update(self):
		Blender.Window.DrawProgressBar(self.currentFraction, self.message)
		self.lastFraction = self.currentFraction

class KDTree:
	def __init__(self, objects, dimensions, leafSize = 4):
		self.leafSize = leafSize
		self.dimensions = dimensions
		self.maxDepth = 0
		self.debug = False
		self._depthIPOs = []
		self.nNodes = 0

		self.progress = Progress('1/3: Constructing KDTree', len(objects))

		if len(objects) > leafSize:
			self.root = KDBranch(objects, 0, self)
		else:
			self.root = KDLeaf(objects, 0, self)

	def on_node_created(self, node):
		self.nNodes = self.nNodes + 1

	def on_leaf_created(self, leaf):
		self.update_max_depth(leaf.depth)
		self.progress.increment(len(leaf.Objects))

	def GetIPO(self, level):
		try:
			return self._depthIPOs[level]
		except IndexError:
			# continued below
			pass

		for lvl in range(0, self.maxDepth):
			colour = float(lvl) / float(self.maxDepth)
			ipo = Blender.Ipo.New('owner', 'LOD_%d' % lvl)
			ic = ipo.addCurve('ColR')
			ic[1.0] = colour
			ic = ipo.addCurve('ColG')
			ic[1.0] = colour
			ic = ipo.addCurve('ColB')
			ic[1.0] = colour
			ic = ipo.addCurve('ColA')
			ic[1.0] = 1.0
			self._depthIPOs.append(ipo)

		return self._depthIPOs[level]

	def update_max_depth(self, depth):
		if depth > self.maxDepth:
			self.maxDepth = depth

	def on_cluster_created(self, node):
		self.progress.increment(1)

	def create_cluster_hierarchy(self):
		self.progress = Progress('2/3: Creating clusters', self.nNodes)
		self.root.create_cluster_hierarchy([], [])

	def on_node_serialised(self, node):
		self.progress.increment(1)

	def serialise_to_lod_tree(self, tBuf):
		'''
		Serialise to an LODTree. This is like the standard Python __repr__
		functions: the resulting text will be executable Python code that
		constructs a new tree. However deserialisation will result in a
		different type (LODTree instead of KDTree).

		To prevent nested instantiation like this:
		    branch = LODBranch(LODBranch(...), LODBranch(...))
		Two queues will be created: LQ and RQ (for the left and right branches,
		respectively):
		    LQ = []
			RQ = []
			LQ.append(LODLeaf())
			RQ.append(LODLeaf())
		    LQ.append(LODBranch(LQ.pop(), RQ.pop()))
			...

		Parameters:
		tBuf: The text buffer to write into (Blender.Text.Text).
		'''
		self.progress = Progress('3/3: Serialising KDTree', self.nNodes)

		#
		# Deselect the objects: they will be selected again on serialisation.
		#
		Blender.Scene.GetCurrent().objects.selected = []

		tBuf.write('#\n# A serialised LODTree, created by BlendKDTree in the Source/Scripts directory.\n#\n')
		tBuf.write('import Scripts.LODTree\n')
		tBuf.write('br = Scripts.LODTree.LODBranch\n')
		tBuf.write('lf = Scripts.LODTree.LODLeaf\n')
		tBuf.write('# Queues avoid nested instantiations.\n')
		tBuf.write('LQ = []\n')
		tBuf.write('RQ = []\n')
		self.root.serialise_to_lod_tree(tBuf, '', 'tree=Scripts.LODTree.LODTree(%s)')
		tBuf.write('assert(len(LQ) == 0)\n')
		tBuf.write('assert(len(RQ) == 0)\n')

class KDNode:
	def __init__(self, depth, tree):
		self.tree = tree
		self.depth = depth
		tree.on_node_created(self)

class KDBranch(KDNode):
	def __init__(self, objects, depth, tree):
		KDNode.__init__(self, depth, tree)
		self.axis = depth % self.tree.dimensions
		self.owner = None

		#
		# Sort the objects along the current axis.
		#
		objects.sort(lambda a, b: cmp(a.getLocation('localspace')[self.axis],
		                              b.getLocation('localspace')[self.axis]))

		#
		# The median value is the location of the middle element on the current
		# axis.
		#
		medianIndex = len(objects) / 2
		self.medianValue = objects[medianIndex].getLocation('worldspace')[self.axis]

		#
		# Create children.
		#
		nextDepth = self.depth + 1
		leftObjects = objects[0:medianIndex]
		if len(leftObjects) > self.tree.leafSize:
			self.left = KDBranch(leftObjects, nextDepth, tree)
		else:
			self.left = KDLeaf(leftObjects, nextDepth, tree)

		rightObjects = objects[medianIndex:]
		if len(rightObjects) > self.tree.leafSize:
			self.right = KDBranch(rightObjects, nextDepth, tree)
		else:
			self.right = KDLeaf(rightObjects, nextDepth, tree)

	def create_cluster_hierarchy(self, meshObs, posObs, side = ''):
		'''
		Create a mesh for this node. The mesh is the sum of all the descendants'
		meshes.

		Parameters:
		meshObs: Objects that represent the mesh of this node will be appended
		         to this list.
		posObs:  Objects that should be stored in the hierarchy will be appended
		         to this list. In the case of KDBranch, the same objects will be
		         added to both lists.
		'''
		if self.owner:
			raise StateError('Tried to create cluster twice.')

		childMeshObs = []
		childPosObs = []
		self.left.create_cluster_hierarchy(childMeshObs, childPosObs, 'L')
		self.right.create_cluster_hierarchy(childMeshObs, childPosObs, 'R')

		#
		# Create a new, empty object.
		#
		name = 'LOD_%d%s' % (self.depth, side)
		sce = Blender.Scene.GetCurrent()
		mesh = bpy.data.meshes.new(name)
		ob = sce.objects.new(mesh, name)

		#
		# Set the location. For setLocation, localspace == worldspace: the new
		# object has no parent yet.
		#
		meanLoc = Blender.Mathutils.Vector()
		for c in childPosObs:
			loc = Blender.Mathutils.Vector(c.getLocation('worldspace'))
			meanLoc = meanLoc + loc
		meanLoc = meanLoc / len(childPosObs)
		ob.setLocation(meanLoc)

		#
		# Create a new cluster from children.
		#
		ob.join(childMeshObs)

		if self.tree.debug:
			#
			# Colour the objects for debugging.
			#
			ob.setIpo(self.tree.GetIPO(self.depth))

		#
		# Parent children to new cluster. This relationship will be broken by
		# LODTree on deserialisation (when the game starts). In the mean time,
		# the relationships make the objects easier to manage.
		#
		ob.makeParent(childPosObs)

		#
		# Disable fancy collisions. Only the leaves retain their original
		# interactivity.
		#
		ob.rbFlags = Blender.Object.RBFlags['PROP']

		self.owner = ob
		self.tree.on_cluster_created(self)
		meshObs.append(ob)
		posObs.append(ob)

	def serialise_to_lod_tree(self, tBuf, indent, format):
		'''
		Serialise to an LODBranch.

		To be valid code, the supplied text buffer must already contain the
		variables 'br = LODBranch', LQ = [] and RQ = []. See LODTree.
		serialise_to_lod_tree for an example.

		Several lines may be required to represent the new object. The last will
		be an expression that returns an LODBranch, and will be formatted
		according to the 'format' parameter (see below).

		Parameters:
		tBuf:   The text buffer to write into (Blender.Text.Text).
		indent: The spacing to insert at the start of each line (string).
		format: Extra string formatting for the serialised object. This is used
		        to assign the new object to a variable. (string)
		'''
		if not self.owner:
			raise StateError('Serialisation requires clusters to have been created.')

		self.left.serialise_to_lod_tree(tBuf, indent + INDENT_STEP, 'LQ.append(%s)')
		self.right.serialise_to_lod_tree(tBuf, indent + INDENT_STEP, 'RQ.append(%s)')

		obName = self.owner.getName()
		expr = 'br(\'%s\',LQ.pop(),RQ.pop(),%d,%f)' % (obName, self.axis, self.medianValue)
		tBuf.write(indent + (format % expr) + (' # %d' % self.depth)  + '\n')
		self.owner.select(True)
		self.tree.on_node_serialised(self)

class KDLeaf(KDNode):
	def __init__(self, objects, depth, tree):
		KDNode.__init__(self, depth, tree)
		self.Objects = objects
		self.SerialisableObjects = []
		tree.on_leaf_created(self)

	def create_cluster_hierarchy(self, meshObs, posObs, side = ''):
		'''
		Create the meshes for this node.

		Parameters:
		meshObs: Objects that represent the mesh of this node will be appended
		         to this list.
		posObs:  Objects that should be stored in the hierarchy will be appended
		         to this list. In the case of KDLeaf, the objects will be
		         empties. Each empty will have a property that 
		'''
		if len(self.SerialisableObjects) > 0:
			raise StateError('Tried to create cluster twice.')

		for o in self.Objects:
			ps = o.getAllProperties()
			prop = None
			for p in ps:
				if p.name == 'LODObject':
					prop = p
					break
			if prop:
				#
				# If the object has an 'LODObject' property, create a new Empty
				# to stand in its place.
				#
				e = Blender.Scene.GetCurrent().objects.new('Empty', 'E' + prop.data)
				#e = Blender.Object.New('Empty', 'E' + o.getName())
				e.setLocation(o.getLocation('worldspace'))
				e.setEuler(o.getEuler('worldspace'))
				e.addProperty(prop.name, prop.data, prop.type)
				meshObs.append(o)
				posObs.append(e)
				self.SerialisableObjects.append(e)

			else:
				meshObs.append(o)
				posObs.append(o)
				self.SerialisableObjects.append(o)

		self.tree.on_cluster_created(self)

	def serialise_to_lod_tree(self, tBuf, indent, format):
		'''
		Serialise to an LODLeaf.

		To be valid code, the supplied text buffer must already contain the
		variables 'lf = LODLeaf'. See LODTree.serialise_to_lod_tree for an example.

		Several lines may be required to represent the object. The last will be
		an expression that returns an LODLeaf, and will be formatted according
		to the 'format' parameter (see below).

		Parameters:
		tBuf:   The text buffer to write into (Blender.Text.Text).
		indent: The spacing to insert at the start of each line (string).
		format: Extra string formatting for the serialised object. This is used
		        to assign the new object to a variable. (string)
		'''
		if len(self.SerialisableObjects) < len(self.Objects):
			raise StateError('Serialisation requires clusters to have been created.')

		elements = []
		for e in self.SerialisableObjects:
			elements.append(e.getName())
			e.select(True)
		expr = 'lf(%s)' % repr(elements)
		tBuf.write(indent + (format % expr) + (' # %d' % self.depth)  + '\n')
		self.tree.on_node_serialised(self)

if __name__ == '__main__':
	'''Create clusters and a serialised LOD tree from the selected objects.'''
	obs = Blender.Object.GetSelected()
	tree = KDTree(obs, dimensions = 2, leafSize = 4)
	tBuf = Blender.Text.New('LODTree_Serialised')
	tree.serialise_to_lod_tree(tBuf)
	Blender.Draw.PupMenu('Tree created.%t|' + ('Saved to text buffer %s.' % tBuf.getName()))
