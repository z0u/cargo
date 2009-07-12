class KDTree:
	def __init__(self, objects, dimensions, leafSize = 8):
		if len(objects) > leafSize:
			self.Root = KDBranch(objects, 0, dimensions, leafSize)
		else:
			self.Root = KDLeaf(objects)
	
	def SerialiseToGameKDTree(self):
		self.Root.SerialiseToGameKDTree('')

class KDNode:
	def SerialiseToLODTree(self, indent):
		pass

class KDBranch(KDNode):
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
		self.MedianValue = objects[medianIndex].getLocation('localspace')[axis]
		
		#
		# Create children.
		#
		leftObjects = objects[0:medianIndex]
		if len(leftObjects) > leafSize:
			self.Left = KDBranch(leftObjects, (axis + 1) % dimensions, leafSize)
		else:
			self.Left = KDLeaf(leftObjects)
		
		rightObjects = objects[medianIndex:]
		if len(rightObjects) > leafSize:
			self.Right = KDBranch(rightObjects, (axis + 1) % dimensions, leafSize)
		else:
			self.Right = KDLeaf(rightObjects)
	
	def SerialiseToLODTree(self, indent):
		print indent + 'left = ' + self.Left.SerialiseToGameKDTree(indent + ' ')
		print indent + 'right = ' + self.Right.SerialiseToGameKDTree(indent + ' ')
		print indent + 'LODBranch(left, right)'

class KDLeaf(KDNode):
	def __init__(self, objects):
		self.Objects = objects
	
	def SerialiseToLODTree(self, indent):
		elements = []
		for o in self.Objects:
			elements.add(o.getName())
		print indent + 'elements = ' + repr(elements)
		print indent + 'LODLeaf(elements)'
	