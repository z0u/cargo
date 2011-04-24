#
# Copyright 2009-2011 Alex Fraser <alex@phatcore.com>
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

from optparse import OptionParser
from sys import stdout
import sys
import time
import traceback

import bpy
import mathutils

#
# This is only for debugging: makes the tree print out with indentation, but
# it will not be parsable.
#
#INDENT_STEP = '    '
INDENT_STEP = ''

class StateError(Exception):
	pass

class Progress:
	def __init__(self, message, upperBound, updateStep = 0.01):
		self.upper = upperBound
		self.message = message
		self.currentValue = 0
		self.currentFraction = 0.0
		self.updateStep = updateStep
		self.startTime = time.time()
		self.lastTime = self.startTime
		self.set_value(0.0)

	def increment(self, value):
		self.set_value(self.currentValue + value)

	def set_value(self, value):
		self.currentValue = value
		try:
			self.currentFraction = float(value) / float(self.upper)
		except ZeroDivisionError:
			self.currentFraction = 0.0
		currentTime = time.time()

		if (self.currentFraction <= 0.0 or
		    self.currentFraction >= 1.0 or
		    currentTime > (self.lastTime + 1.0)):

			self.update()
			self.lastTime = currentTime

	def update(self):
		'''Show the status to the user.'''
		pass

class ConsoleProgress(Progress):
	def format_time(self):
		if self.currentFraction <= 0.0 or self.currentFraction >= 1.0:
			return '               '

		elapsedTime = time.time() - self.startTime
		estimatedDuration = elapsedTime / self.currentFraction
		remainingTime = estimatedDuration - elapsedTime

		if remainingTime > 60 * 60:
			return '(T-%2.1fh)     ' % (remainingTime / (60 * 60))
		elif remainingTime > 60:
			return '(T-%2.1fmin)   ' % (remainingTime / 60)
		else:
			return '(T-%2.0fs)     ' % remainingTime

	def update(self):
		stdout.write('\r%s: %3.0f%%' % (self.message, self.currentFraction * 100))
		stdout.write(' ' + self.format_time())
		stdout.flush()

		if self.currentFraction >= 1.0:
			print()

class WindowProgress(Progress):
	def update(self):
		pass
		# Needs to be updated for Blender 2.5x
#		Blender.Window.DrawProgressBar(self.currentFraction, self.message)
#		self.lastFraction = self.currentFraction

progressFactory = ConsoleProgress

class KDTree:
	def __init__(self, objects, groupName, shortName, dimensions, leafSize=4):
		self.leafSize = leafSize
		self.dimensions = dimensions
		self.maxDepth = 0
		self._depthIPOs = []
		self.nNodes = 0
		self.nObs = len(objects)
		self.groupName = groupName
		self.shortName = shortName

		self.progress = progressFactory('1/3: Constructing KDTree', len(objects))

		if len(objects) > leafSize:
			self.root = KDBranch(objects, 0, self)
		else:
			self.root = KDLeaf(objects, 0, self)

	def on_node_created(self, node):
		self.nNodes = self.nNodes + 1

	def on_leaf_created(self, leaf):
		self.update_max_depth(leaf.depth)
		self.progress.increment(len(leaf.obs))

	def update_max_depth(self, depth):
		if depth > self.maxDepth:
			self.maxDepth = depth

	def on_cluster_created(self, node):
		self.progress.increment(1)

	def create_cluster_hierarchy(self):
		self.progress = progressFactory('2/3: Creating clusters', self.nNodes)
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
		tBuf: The text buffer to write into (bpy.types.text).
		'''
		self.progress = progressFactory('3/3: Serialising KDTree', self.nNodes)

		tBuf.write('#\n# A serialised LODTree, created by BlendKDTree in the BScripts directory.\n#\n')
		tBuf.write('# This tree contains %d leaf objects, supported by %d KD-tree nodes in %d levels\n#\n' %
				(self.nObs, self.nNodes, self.maxDepth))
		tBuf.write('import Scripts.lodtree\n')
		tBuf.write('br = Scripts.lodtree.LODBranch\n')
		tBuf.write('lf = Scripts.lodtree.LODLeaf\n')
		tBuf.write('# Queues avoid nested instantiations.\n')
		tBuf.write('LQ = []\n')
		tBuf.write('RQ = []\n')
		self.root.serialise_to_lod_tree(tBuf, '', 'tree=Scripts.lodtree.LODTree(%s)')
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
		def dimension_key(ob):
			return ob.location[self.axis]

		os = objects.sort(key=dimension_key)

		#
		# The median value is the location of the middle element on the current
		# axis.
		#
		medianIndex = int(len(objects) / 2)
		self.medianValue = objects[medianIndex].location[self.axis]

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
		name = 'LOD_%s%d%s' % (self.tree.shortName, self.depth, side)
		bpy.ops.object.add(type='MESH')
		ob = bpy.context.object
		ob.name = name
		ob.data.name = name

		#
		# Add to nominated group
		#
		if self.tree.groupName != None:
			if not self.tree.groupName in bpy.data.groups:
				bpy.data.groups.new(self.tree.groupName)
			bpy.ops.object.select_all(action='DESELECT')
			bpy.context.scene.objects.active = ob
			ob.select = True
			bpy.ops.object.group_link(group=self.tree.groupName)

		#
		# Set the location. For location, localspace == worldspace: the new
		# object has no parent yet.
		#
		meanLoc = mathutils.Vector((0,0,0))
		for c in childPosObs:
			meanLoc = meanLoc + c.location
		meanLoc = meanLoc / len(childPosObs)
		ob.location = meanLoc

		#
		# Create a new cluster from children. First, make linked duplicates of
		# the children so the old objects are retained.
		#
		bpy.ops.object.select_all(action='DESELECT')
		for child in childMeshObs:
			child.select = True
		bpy.ops.object.duplicate(linked=True)
		ob.select = True
		bpy.context.scene.objects.active = ob
		bpy.ops.object.join()

		#
		# Parent children to new cluster. This relationship will be broken by
		# LODTree on deserialisation (when the game starts). In the mean time,
		# the relationships make the objects easier to manage.
		#
		for child in childPosObs:
			child.select = True
		bpy.ops.object.parent_set()

		#
		# Disable fancy collisions. Only the leaves retain their original
		# interactivity.
		#
		ob.game.physics_type = 'NO_COLLISION'

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
		tBuf:   The text buffer to write into (bpy.types.text).
		indent: The spacing to insert at the start of each line (string).
		format: Extra string formatting for the serialised object. This is used
		        to assign the new object to a variable. (string)
		'''
		if not self.owner:
			raise StateError('Serialisation requires clusters to have been created.')

		self.left.serialise_to_lod_tree(tBuf, indent + INDENT_STEP, 'LQ.append(%s)')
		self.right.serialise_to_lod_tree(tBuf, indent + INDENT_STEP, 'RQ.append(%s)')

		obName = self.owner.name
		expr = 'br(\'%s\',LQ.pop(),RQ.pop(),%d,%f)' % (obName, self.axis, self.medianValue)
		tBuf.write(indent + (format % expr) + (' # %d' % self.depth)  + '\n')
		self.tree.on_node_serialised(self)

class KDLeaf(KDNode):
	def __init__(self, objects, depth, tree):
		KDNode.__init__(self, depth, tree)
		self.obs = objects
		self.serialisableObs = []
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
		if len(self.serialisableObs) > 0:
			raise StateError('Tried to create cluster twice.')

		for o in self.obs:
			if 'LODObject' in o.game.properties:
				#
				# If the object has an 'LODObject' property, create a new Empty
				# to stand in its place.
				#
				bpy.ops.object.add(type='EMPTY')
				e = bpy.context.object
				e.name = 'E%s%s' % (self.tree.shortName, o.game.properties['LODObject'].value)

				e.matrix_world = o.matrix_world

				#
				# Copy the name of the LOD object into a property on the new
				# empty object.
				# 
				bpy.ops.object.select_all(action='DESELECT')
				o.select = True
				e.select = True
				bpy.context.scene.objects.active = o
				bpy.ops.object.game_property_copy(property='LODObject')

				meshObs.append(o)
				posObs.append(e)
				self.serialisableObs.append(e)

			else:
				meshObs.append(o)
				posObs.append(o)
				self.serialisableObs.append(o)

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
		tBuf:   The text buffer to write into (bpy.types.text).
		indent: The spacing to insert at the start of each line (string).
		format: Extra string formatting for the serialised object. This is used
		        to assign the new object to a variable. (string)
		'''
		if len(self.serialisableObs) < len(self.obs):
			raise StateError('Serialisation requires clusters to have been created.')

		elements = []
		for e in self.serialisableObs:
			elements.append(e.name)
			e.select = True
		expr = 'lf(%s)' % repr(elements)
		tBuf.write(indent + (format % expr) + (' # %d' % self.depth)  + '\n')
		self.tree.on_node_serialised(self)

def parse_options():
	splitterIndex = -1
	for i, arg in enumerate(sys.argv):
		if arg == '--':
			splitterIndex = i
			break

	options = {}
	try:
		options['outfile'] = sys.argv[splitterIndex + 1]
	except IndexError:
		raise Exception('Invalid arguments.')

	return options

def set_layers_visible(layers):
	for i, value in enumerate(layers):
		bpy.context.scene.layers[i] = value

def make_lod_trees():
	'''Create clusters and a serialised LOD tree from marked objects. To mark an
	object as a source for an LOD tree, add two game properties to it:
	 - LODDupli (any type), and
	 - LODGroup (string; all derived objects will be added to a group with this
	   name).'''

	original_layers = list(bpy.context.scene.layers)

	def is_lodsource(ob):
		return ('LODDupli' in ob.game.properties and
			'LODGroup' in ob.game.properties)
	sourceObs = list(filter(is_lodsource, bpy.context.scene.objects))
	for sourceOb in sourceObs:
		groupName = sourceOb.game.properties['LODGroup'].value
		print('Creating LOD tree "%s"' % groupName)

		# Make dupli-objects (e.g. particle instances) real, and select them.
		set_layers_visible(sourceOb.layers)
		bpy.ops.object.select_all(action='DESELECT')
		bpy.context.scene.objects.active = sourceOb
		sourceOb.select = True
		bpy.ops.object.duplicates_make_real()
		sourceOb.select = False

		# Make KD tree and clusters from duplicated objects.
		lodObs = list(bpy.context.selected_objects)
		tree = KDTree(lodObs, groupName, groupName[0:2], dimensions=2, leafSize=4)
		tree.create_cluster_hierarchy()

		# Delete original duplis.
		for lodOb in lodObs:
			bpy.context.scene.objects.unlink(lodOb)
		lodObs = []

		# Serialise to text buffer.
		tBuf = bpy.data.texts.new(name='LODTree_%s' % groupName)
		tree.serialise_to_lod_tree(tBuf)

		print('Tree created. Saved to text buffer %s.' % tBuf.name)

	set_layers_visible(original_layers)

def save_file(fileName):
	print('Saving file to', fileName)
	bpy.ops.wm.save_as_mainfile(filepath=fileName)

if __name__ == '__main__':
	try:
		options = parse_options()
		make_lod_trees()
		save_file(options['outfile'])
	except Exception:
		traceback.print_exc()
		print('Usage:\n\tblender -P BScripts/BlendKDTree.py <infile.blend> -- <outfile.blend>')
		sys.exit(1)
