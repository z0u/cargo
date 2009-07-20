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

class Progress:
	def __init__(self, message, upperBound, updateStep = 0.01):
		self.Upper = upperBound
		self.Message = message
		self.CurrentValue = 0
		self.CurrentFraction = 0.0
		self.LastFraction = 0.0
		self.UpdateStep = updateStep
		self.SetValue(0.0)
	
	def Increment(self, value):
		self.SetValue(self.CurrentValue + value)
	
	def SetValue(self, value):
		self.CurrentValue = value
		self.CurrentFraction = float(value) / float(self.Upper)
		if (self.CurrentFraction > (self.LastFraction + self.UpdateStep) or
		    self.CurrentFraction <= 0.0 or
		    self.CurrentFraction >= 1.0):
			self.Update()
	
	def Update(self):
		Blender.Window.DrawProgressBar(self.CurrentFraction, self.Message)
		self.LastFraction = self.CurrentFraction

class KDTree:
	def __init__(self, objects, dimensions, leafSize = 4):
		self.LeafSize = leafSize
		self.Dimensions = dimensions
		self.MaxDepth = 0
		self._debug = False
		self._depthIPOs = []
		self.NNodes = 0
		
		self.Progress = Progress('1/3: Constructing KDTree', len(objects))
		
		if len(objects) > leafSize:
			self.Root = KDBranch(objects, 0, self)
		else:
			self.Root = KDLeaf(objects, 0, self)
	
	def _getDebug(self): return self._debug
	def _setDebug(self, value): self._debug = value
	Debug = property(_getDebug, _setDebug,
		'''
		Whether the tree should produce debugging information. This will cause
		the objects to be re-coloured. Objects near the root (far from the
		player) will be black; the objects near the leaves (close to the player)
		will be white. The leaves themselves will be their original colours.
		'''
	)
	
	def OnNodeCreated(self, node):
		self.NNodes = self.NNodes + 1
	
	def OnLeafCreated(self, leaf):
		self.UpdateMaxDepth(leaf.Depth)
		self.Progress.Increment(len(leaf.Objects))
	
	def GetIPO(self, level):
		try:
			return self._depthIPOs[level]
		except IndexError:
			# continued below
			pass
		
		for lvl in range(0, self.MaxDepth):
			colour = float(lvl) / float(self.MaxDepth)
			ipo = Blender.Ipo.New('Object', 'LOD_%d' % lvl)
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
	
	def UpdateMaxDepth(self, depth):
		if depth > self.MaxDepth:
			self.MaxDepth = depth
	
	def OnClusterCreated(self, node):
		self.Progress.Increment(1)
	
	def CreateClusterHierarchy(self):
		self.Progress = Progress('2/3: Creating clusters', self.NNodes)
		self.Root.CreateClusterHierarchy()
	
	def OnNodeSerialised(self, node):
		self.Progress.Increment(1)
	
	def SerialiseToLODTree(self, tBuf):
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
		self.Progress = Progress('3/3: Serialising KDTree', self.NNodes)
		
		tBuf.write('#\n# A serialised LODTree, created by BlendKDTree in the Source/Scripts directory.\n#\n')
		tBuf.write('import Scripts.LODTree\n')
		tBuf.write('br = Scripts.LODTree.LODBranch\n')
		tBuf.write('lf = Scripts.LODTree.LODLeaf\n')
		tBuf.write('# Queues avoid nested instantiations.\n')
		tBuf.write('LQ = []\n')
		tBuf.write('RQ = []\n')
		self.Root.SerialiseToLODTree(tBuf, '', 'tree=Scripts.LODTree.LODTree(%s)')
		tBuf.write('assert(len(LQ) == 0)\n')
		tBuf.write('assert(len(RQ) == 0)\n')

class KDNode:
	def __init__(self, depth, tree):
		self.Tree = tree
		self.Depth = depth
		tree.OnNodeCreated(self)

class KDBranch(KDNode):
	def __init__(self, objects, depth, tree):
		KDNode.__init__(self, depth, tree)
		self.Axis = depth % self.Tree.Dimensions
		self.Object = None
		
		#
		# Sort the objects along the current axis.
		#
		objects.sort(lambda a, b: cmp(a.getLocation('localspace')[self.Axis],
		                              b.getLocation('localspace')[self.Axis]))
		
		#
		# The median value is the location of the middle element on the current
		# axis.
		#
		medianIndex = len(objects) / 2
		self.MedianValue = objects[medianIndex].getLocation('worldspace')[self.Axis]
		
		#
		# Create children.
		#
		nextDepth = self.Depth + 1
		leftObjects = objects[0:medianIndex]
		if len(leftObjects) > self.Tree.LeafSize:
			self.Left = KDBranch(leftObjects, nextDepth, tree)
		else:
			self.Left = KDLeaf(leftObjects, nextDepth, tree)
		
		rightObjects = objects[medianIndex:]
		if len(rightObjects) > self.Tree.LeafSize:
			self.Right = KDBranch(rightObjects, nextDepth, tree)
		else:
			self.Right = KDLeaf(rightObjects, nextDepth, tree)
	
	def CreateClusterHierarchy(self, side = ''):
		children = self.Left.CreateClusterHierarchy('L')
		children = children + self.Right.CreateClusterHierarchy('R')
		
		#
		# Create a new, empty object.
		#
		name = 'LOD_%d%s' % (self.Depth, side)
		sce = Blender.Scene.GetCurrent()
		mesh = bpy.data.meshes.new(name)
		ob = sce.objects.new(mesh, name)
		
		#
		# Set the location. For setLocation, localspace == worldspace: the new
		# object has no parent yet.
		#
		meanLoc = Blender.Mathutils.Vector()
		for c in children:
			loc = Blender.Mathutils.Vector(c.getLocation('worldspace'))
			meanLoc = meanLoc + loc
		meanLoc = meanLoc / len(children)
		ob.setLocation(meanLoc)
		
		#
		# Create a new cluster from children.
		#
		ob.join(children)
		
		if self.Tree.Debug:
			#
			# Colour the objects for debugging.
			#
			#relDepth = float(self.Depth) / float(self.Tree.MaxDepth)
			#print relDepth
			#ob.color = (relDepth, relDepth, relDepth, 1.0)
			ob.setIpo(self.Tree.GetIPO(self.Depth))
		
		#
		# Parent children to new cluster. This relationship will be broken by
		# LODTree on deserialisation (when the game starts). In the mean time,
		# the relationships make the objects easier to manage.
		#
		ob.makeParent(children)
		
		#
		# Disable fancy collisions. Only the leaves retain their original
		# interactivity.
		#
		ob.rbFlags = Blender.Object.RBFlags['PROP']
		
		self.Object = ob
		self.Tree.OnClusterCreated(self)
		return [ob]
	
	def SerialiseToLODTree(self, tBuf, indent, format):
		'''
		Serialise to an LODBranch.
		
		To be valid code, the supplied text buffer must already contain the
		variables 'br = LODBranch', LQ = [] and RQ = []. See LODTree.
		SerialiseToLODTree for an example.
		
		Several lines may be required to represent the new object. The last will
		be an expression that returns an LODBranch, and will be formatted
		according to the 'format' parameter (see below).
		
		Parameters:
		tBuf:   The text buffer to write into (Blender.Text.Text).
		indent: The spacing to insert at the start of each line (string).
		format: Extra string formatting for the serialised object. This is used
		        to assign the new object to a variable. (string)
		'''
		self.Left.SerialiseToLODTree(tBuf, indent + INDENT_STEP, 'LQ.append(%s)')
		self.Right.SerialiseToLODTree(tBuf, indent + INDENT_STEP, 'RQ.append(%s)')
		
		obName = self.Object.getName()
		expr = 'br(\'%s\',LQ.pop(),RQ.pop(),%d,%f)' % (obName, self.Axis, self.MedianValue)
		tBuf.write(indent + (format % expr) + (' # %d' % self.Depth)  + '\n')
		self.Tree.OnNodeSerialised(self)

class KDLeaf(KDNode):
	def __init__(self, objects, depth, tree):
		KDNode.__init__(self, depth, tree)
		self.Objects = objects
		tree.OnLeafCreated(self)
	
	def CreateClusterHierarchy(self, side = ''):
		self.Tree.OnClusterCreated(self)
		return self.Objects
	
	def SerialiseToLODTree(self, tBuf, indent, format):
		'''
		Serialise to an LODLeaf.
		
		To be valid code, the supplied text buffer must already contain the
		variables 'lf = LODLeaf'. See LODTree.SerialiseToLODTree for an example.
		
		Several lines may be required to represent the object. The last will be
		an expression that returns an LODLeaf, and will be formatted according
		to the 'format' parameter (see below).
		
		Parameters:
		tBuf:   The text buffer to write into (Blender.Text.Text).
		indent: The spacing to insert at the start of each line (string).
		format: Extra string formatting for the serialised object. This is used
		        to assign the new object to a variable. (string)
		'''
		elements = []
		for o in self.Objects:
			elements.append(o.getName())
		expr = 'lf(%s)' % repr(elements)
		tBuf.write(indent + (format % expr) + (' # %d' % self.Depth)  + '\n')
		self.Tree.OnNodeSerialised(self)

if __name__ == '__main__':
	'''Create clusters and a serialised LOD tree from the selected objects.'''
	obs = Blender.Object.GetSelected()
	tree = KDTree(obs, dimensions = 2, leafSize = 4)
	tBuf = Blender.Text.New('LODTree_Serialised')
	tree.SerialiseToLODTree(tBuf)
	Blender.Draw.PupMenu('Tree created.%t|' + ('Saved to text buffer %s.' % tBuf.getName()))
