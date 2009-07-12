#INDENT_STEP = '    '
INDENT_STEP = ''

class KDTree:
	def __init__(self, objects, dimensions, leafSize = 8):
		if len(objects) > leafSize:
			self.Root = KDBranch(objects, 0, dimensions, leafSize)
		else:
			self.Root = KDLeaf(objects)
	
	def SerialiseToLODTree(self):
		print '#\n# A serialised LODTree, created by BlendKDTree in the Source/Scripts directory.\n#'
		print 'import Scripts.LODTree'
		print 'br = Scripts.LODTree.LODBranch'
		print 'lf = Scripts.LODTree.LODLeaf'
		print '# Queues are used to avoid the need for nested instantiations.'
		print 'LQ = []'
		print 'RQ = []'
		self.Root.SerialiseToLODTree('', 'root = %s')
		print 'assert(len(LQ) == 0)'
		print 'assert(len(RQ) == 0)'

class KDBranch:
	def __init__(self, objects, axis, dimensions, leafSize):
		self.Axis = axis
		
		#
		# Sort the objects along the current axis.
		#
		objects.sort(lambda a, b: cmp(a.getLocation('localspace')[axis], b.getLocation('localspace')[axis]))
		
		#
		# The median value is the location of the middle element on the current
		# axis.
		#
		medianIndex = len(objects) / 2
		self.MedianValue = objects[medianIndex].getLocation('worldspace')[axis]
		
		#
		# Create children.
		#
		nextAxis = (axis + 1) % dimensions
		leftObjects = objects[0:medianIndex]
		if len(leftObjects) > leafSize:
			self.Left = KDBranch(leftObjects, nextAxis, dimensions, leafSize)
		else:
			self.Left = KDLeaf(leftObjects)
		
		rightObjects = objects[medianIndex:]
		if len(rightObjects) > leafSize:
			self.Right = KDBranch(rightObjects, nextAxis, dimensions, leafSize)
		else:
			self.Right = KDLeaf(rightObjects)
	
	def SerialiseToLODTree(self, indent, format):
		self.Left.SerialiseToLODTree(indent + INDENT_STEP, 'LQ.append(%s)')
		self.Right.SerialiseToLODTree(indent + INDENT_STEP, 'RQ.append(%s)')
		
		expr = 'br(LQ.pop(),RQ.pop(),%d,%f)' % (self.Axis, self.MedianValue)
		print indent + (format % expr)

class KDLeaf:
	def __init__(self, objects):
		self.Objects = objects
	
	def SerialiseToLODTree(self, indent, format):
		elements = []
		for o in self.Objects:
			elements.append(o.getName())
		expr = 'lf(%s)' % repr(elements)
		print indent + (format % expr)

if __name__ == '__main__':
	import Blender.Object
	obs = Blender.Object.GetSelected()
	tree = KDTree(obs, dimensions = 2, leafSize = 8)
	tree.SerialiseToLODTree()
