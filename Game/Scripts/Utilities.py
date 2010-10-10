#
# Copyright 2009 Alex Fraser <alex@phatcore.com>
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

import mathutils
import GameLogic
import Rasterizer

XAXIS  = mathutils.Vector([1.0, 0.0, 0.0])
YAXIS  = mathutils.Vector([0.0, 1.0, 0.0])
ZAXIS  = mathutils.Vector([0.0, 0.0, 1.0])
ORIGIN = mathutils.Vector([0.0, 0.0, 0.0])
ZEROVEC = ORIGIN
ONEVEC = mathutils.Vector([1.0, 1.0, 1.0])
EPSILON = 0.000001
MINVECTOR = mathutils.Vector([0.0, 0.0, EPSILON])

RED   = mathutils.Vector([1.0, 0.0, 0.0, 1.0])
GREEN = mathutils.Vector([0.0, 1.0, 0.0, 1.0])
BLUE  = mathutils.Vector([0.0, 0.0, 1.0, 1.0])
YELLOW = RED + GREEN
CYAN  = GREEN + BLUE
MAGENTA = RED + BLUE
WHITE = mathutils.Vector([1.0, 1.0, 1.0, 1.0])
BLACK = mathutils.Vector([0.0, 0.0, 0.0, 1.0])

class _SceneManager:
	def __init__(self):
		self.Observers = set()
		self.NewScene = True
	
	def OnNewScene(self):
		GameLogic.setGravity([0.0, 0.0, -75.0])
		self.NewScene = False
	
	def Subscribe(self, observer):
		'''Subscribe to the set of listeners. It is OK to call this function
		twice for the same observer.'''
		if self.NewScene:
			self.OnNewScene()
		self.Observers.add(observer)
	
	def Unsubscribe(self, observer):
		self.Observers.remove(observer)
	
	def EndScene(self):
		'''Notifies observers that they should release all game objects.
		Observers should unsubscribe themselves if they are no longer interested
		in the scene.'''
		observers = self.Observers.copy()
		for o in observers:
			o.OnSceneEnd()
		self.NewScene = True

SceneManager = _SceneManager()

def EndScene(c):
	'''Releases all object references (e.g. Actors). Then, all actuators are
	activated. Call this from a Python controller attached to a switch scene
	actuator instead of using an AND controller.'''
	
	if not allSensorsPositive(c):
		return
		
	SceneManager.EndScene()
	for act in c.actuators:
		c.activate(act)

class SemanticException(Exception):
	pass

def parseChildren(self, o):
	for child in o.children:
		if 'Type' in child:
			if (not self.parseChild(child, child['Type'])):
				print("Warning: child %s of %s has unexpected type (%s)" % (
					child.name,
					o.name,
					child['Type']))

class Box2D:
	'''A 2D bounding box.'''
	def __init__(self, xLow, yLow, xHigh, yHigh):
		self.xLow = xLow
		self.yLow = yLow
		self.xHigh = xHigh
		self.yHigh = yHigh
	
	def Intersect(self, other):
		if other.xHigh < self.xHigh:
			self.xHigh = other.xHigh
		if other.yHigh < self.yHigh:
			self.yHigh = other.yHigh
		
		if other.xLow > self.xLow:
			self.xLow = other.xLow
		if other.yLow > self.yLow:
			self.yLow = other.yLow
		
		#
		# Ensure box is not inside-out.
		#
		if self.xLow > self.xHigh:
			self.xLow = self.xHigh
		if self.yLow > self.yHigh:
			self.yLow = self.yHigh
	
	def GetArea(self):
		w = self.xHigh - self.xLow
		h = self.yHigh - self.yLow
		return w * h

def _lerp(A, B, fac):
	'''
	Linearly interpolate between two values. Works for scalars and vectors.
	
	Parameters:
	A:   The value to interpolate from.
	B:   The value to interpolate to.
	fac: The amount that the result should resemble B.
	
	Returns: A if fac == 0.0; B if fac == 1.0; a value in between otherwise.
	'''
	return A + ((B - A) * fac)

def _smerp(CurrentDelta, CurrentValue, Target, SpeedFactor, Responsiveness):
	'''Smooth exponential average interpolation
	For each time step, try to move toward the target by some fraction of
	the distance (as is the case for normal exponential averages). If this
	would result in a positive acceleration, take a second exponential
	average of the acceleration. The resulting motion has smooth acceleration
	and smooth deceleration, with minimal oscillation.'''
	
	targetDelta = (Target - CurrentValue) * SpeedFactor
	if (targetDelta * targetDelta > CurrentDelta * CurrentDelta):
		CurrentDelta = CurrentDelta * (1.0 - Responsiveness) + targetDelta * Responsiveness
	else:
		CurrentDelta = targetDelta
	
	CurrentValue = CurrentValue + CurrentDelta
	return CurrentDelta, CurrentValue

def _approachOne(x, c):
	'''
	Shift a value to be in the range 0.0 - 1.0. The result increases
	monotonically. For low values, the result will be close to zero, and will
	increase quickly. High values will be close to one, and will increase
	slowly.
	
	To visualise this function, try it in gnuplot:
		f(x, c) =  1.0 - (1.0 / ((x + (1.0 / c)) * c))
		plot [0:100] f(x, 0.5)
	
	Parameters:
	x: The value to shift. 0.0 <= x.
	c: An amount to scale the result by.
	
	Returns: the shifted value, y. 0.0 <= y < 1.0.
	'''
	return 1.0 - (1.0 / ((x + (1.0 / c)) * c))

def _safeInvert(x, c = 2.0):
	'''
	Invert a value, but ensure that the result is not infinity.
	
	To visualise this function, try it in gnuplot:
		f(x, c) = 1.0 / ((x * c) + 1.0)
		plot [0:1] f(x, 2.0)
	
	Parameters:
	x: The value to invert. 0.0 <= x
	c: An amount to scale the result by.
	
	Returns: the inverted value, y. 0.0 < y <= 1.0.
	'''
	return 1.0 / ((x * c) + 1.0)

def _clamp(lower, upper, value):
	'''
	Ensure a value is within the given range.
	
	Parameters:
	lower: The lower bound.
	upper: The upper bound.
	value: The value to clamp.
	'''
	return min(upper, max(lower, value))

def _manhattanDist(pA, pB):
	'''Get the Manhattan distance between two points (the sum of the vector
	components).'''
	dx = abs(pA[0] - pB[0])
	dy = abs(pA[1] - pB[1])
	dz = abs(pA[2] - pB[2])
	
	return dx + dy + dz

def _toLocal(referential, point):
	'''
	Transform 'point' (specified in world space) into the coordinate space of
	the object 'referential'.
	
	Parameters:
	referential: The object that defines the coordinate space to transform to.
	             (KX_GameObject)
	point:       The point, in world space, to transform. (mathutils.Vector)
	'''
	refP = referential.worldPosition
	refOMat = referential.worldOrientation.copy()
	return (point - refP) * refOMat

def _toWorld(referential, point):
	'''
	Transform 'point' into world space. 'point' must be specified in the
	coordinate space of 'referential'.
	
	Parameters:
	referential: The object that defines the coordinate space to transform from.
	             (KX_GameObject)
	point:       The point, in local space, to transform. (mathutils.Vector)
	'''
	refP = referential.worldPosition
	refOMat = referential.worldOrientation.copy()
	refOMat.invert()
	return (point * refOMat) + refP

def _toWorldVec(referential, dir):
	'''
	Transform direction vector 'dir' into world space. 'dir' must be specified
	in the coordinate space of 'referential'.
	
	Parameters:
	referential: The object that defines the coordinate space to transform from.
	             (KX_GameObject)
	point:       The point, in local space, to transform. (mathutils.Vector)
	'''
	refOMat = referential.worldOrientation.copy()
	refOMat.invert()
	return dir * refOMat

def _toLocalVec(referential, dir):
	refOMat = referential.worldOrientation.copy()
	return dir * refOMat

def _copyTransform(source, target):
	target.worldPosition = source.worldPosition
	target.worldOrientation = source.worldOrientation

def _resetOrientation(ob):
	orn = mathutils.Quaternion()
	orn.identity()
	ob.worldOrientation = orn

def _rayCastP2P(objto, objfrom, dist = 0.0, prop = ''):
	face = 1
	xray = 1
	poly = 0
	return getCursor().rayCast(objto, objfrom, dist, prop, face, xray, poly)

def _SlowCopyRot(o, goal, factor):
	'''
	Slow parenting (Rotation only). 'o' will copy the rotation of the 'goal'.
	'o' must have a SlowFac property: 0 <= SlowFac <= 1. Low values will result
	in slower and smoother movement.
	'''
	goalOrn = goal.worldOrientation.to_quat()
	orn = o.worldOrientation.to_quat()
	orn = orn.slerp(goalOrn, factor)
	orn = orn.to_matrix()
	
	o.localOrientation = orn

def SlowCopyRot(c):
	'''
	Slow parenting (Rotation only). The owner will copy the rotation of the
	'sGoal' sensor's owner. The owner must have a SlowFac property:
	0 <= SlowFac <= 1. Low values will result in slower and smoother movement.
	'''
	o = c.owner
	goal = c.sensors['sGoal'].owner
	_SlowCopyRot(o, goal, o['SlowFac'])

def _SlowCopyLoc(o, goal, factor):
	'''
	Slow parenting (Rotation only). 'o' will copy the position of the 'goal'.
	'o' must have a SlowFac property: 0 <= SlowFac <= 1. Low values will result
	in slower and smoother movement.
	'''
	goalPos = goal.worldPosition
	pos = o.worldPosition
	
	o.worldPosition = _lerp(pos, goalPos, factor)

def SlowCopyLoc(c):
	'''
	Slow parenting (Location only). The owner will copy the position of the
	'sGoal' sensor's owner. The owner must have a SlowFac property:
	0 <= SlowFac <= 1. Low values will result in slower and smoother movement.
	'''
	o = c.owner
	goal = c.sensors['sGoal'].owner
	_SlowCopyLoc(o, goal, o['SlowFac'])

def setRelOrn(ob, target, ref):
	'''
	Sets the orientation of 'ob' to match that of 'target' using 'ref' as the
	referential. The final orientation will be offset from 'target's by the
	difference between 'ob' and 'ref's orientations.
	'''
	oOrn = ob.worldOrientation
	
	rOrn = mathutils.Matrix(ref.worldOrientation)
	rOrn.invert()
	
	localOrn = rOrn * oOrn
	
	ob.localOrientation = target.worldOrientation * localOrn

def setRelPos(ob, target, ref):
	'''
	Sets the position of 'ob' to match that of 'target' using 'ref' as the
	referential. The final position will be offset from 'target's by the
	difference between 'ob' and 'ref's positions.
	'''
	offset = ref.worldPosition - ob.worldPosition
	ob.worldPosition = target.worldPosition - offset

def RayFollow(c):
	'''
	Position an object some distance along its parent's z-axis. The object will 
	be placed at the first intersection point, or RestDist units from the parent
	- whichever comes first.
	'''
	o = c.owner
	p = o.parent
	
	origin = p.worldPosition
	direction = p.getAxisVect([0.0, 0.0, 1.0])
	through = origin + direction
	
	hitOb, hitPoint, hitNorm = p.rayCast(
		through,		# obTo
		origin,			# obFrom
		o['RestDist'], 	# dist
		'Ray',			# prop
		1,				# face normal
		1				# x-ray
	)
	
	targetDist = o['RestDist']
	if hitOb and (hitNorm.dot(direction) < 0):
		#
		# If dot > 0, the tracking object is inside another mesh.
		# It's not perfect, but better not bring the camera forward
		# in that case, or the camera will be inside too.
		#
		targetDist = (hitPoint - origin).magnitude
	
	targetDist = targetDist * o['DistBias']
	
	if targetDist < o['Dist']:
		o['Dist'] = targetDist
	else:
		o['Dist'] = _lerp(targetDist, o['Dist'], o['Fact'])
	
	pos = origin + (direction * o['Dist'])
	
	o.worldPosition = pos

def getCursor():
	return GameLogic.getCurrentScene().objects['Cursor']

def setCursorTransform(other):
	cursor = getCursor()
	cursor.worldPosition = other.worldPosition
	cursor.worldOrientation = other.worldOrientation

def addObject(name, time = 0):
	scene = GameLogic.getCurrentScene()
	return scene.addObject(name, getCursor(), time)

def SprayParticle(c):
	'''
	Instance one particle, and decrement the particle counter. The particle will
	move along the z-axis of the emitter. The emitter will then be repositioned.
	
	The intention is that one particle will be emitten on each frame. This
	should be fast enough for a spray effect. Staggering the emission reduces
	the liklihood that the frame rate will suffer.
	
	Actuators:
	aEmit:	A particle emitter, connected to its target object.
	aRot:	An actuator that moves the emitter by a fixed amount (e.g. movement
			or IPO).
	
	Controller properties:
	maxSpeed:	The maximum speed that a particle will have when it is created.
			Actually the particle will move at a random speed s, where 0.0 <= s
			<= maxSpeed.
	nParticles:	The number of particles waiting to be created. This will be
			reduced by 1. If less than or equal to 0, no particle will be
			created.
	'''
	if not allSensorsPositive(c):
		return
	
	o = c.owner
	if o['nParticles'] <= 0:
		return
	
	o['nParticles'] = o['nParticles'] - 1
	speed = o['maxSpeed'] * next(Random)
	c.actuators['aEmit'].linearVelocity = (0.0, 0.0, speed)
	c.activate('aEmit')
	c.activate('aRot')

def billboard(c):
	o = c.owner
	_, vec, _ = o.getVectTo(GameLogic.getCurrentScene().active_camera)
	o.alignAxisToVect(vec, 2)

def timeOffsetChildren(c):
	'''Copy the 'Frame' property to all children, incrementally adding an offset
	as defined by the 'Offset' property.'''
	o = c.owner
	a = c.actuators[0]
	range = a.frameEnd - a.frameStart
	increment = 0.0
	if len(o.children) > 0:
		increment = range / len(o.children)
	
	offset = 0.0
	for child in o.children:
		frame = o['Frame'] + offset
		frame -= a.frameStart
		frame %= range
		frame += a.frameStart
		child['Frame'] = frame
		offset += increment
	c.activate(a)
	
def SetDefaultProp(ob, propName, value):
	'''
	Ensure a game object has the given property.
	
	Parameters:
	ob:       A KX_GameObject.
	propName: The property to check.
	value:    The value to assign to the property if it dosen't exist yet.
	'''
	if propName not in ob:
		ob[propName] = value

def _parseColour(hexString):
	'''Parse a colour from a hexadecimal number; either "rrggbb" or
	"rrggbbaa". If no alpha is specified, a value of 1.0 will be used.
	
	Returns:
	A 4D vector compatible with object colour.
	'''
	if len(hexString) != 6 and len(hexString) != 8:
		raise ValueError('Hex colours need to be 6 or 8 characters long.')
	
	colour = BLACK.copy()
	
	components = [(x + y) for x,y in zip(hexString[0::2], hexString[1::2])]
	colour.x = int(components[0], 16)
	colour.y = int(components[1], 16)
	colour.z = int(components[2], 16)
	if len(components) == 4:
		colour.w = int(components[3], 16)
	
	colour /= 255.0
	return colour

def _colourToHex(colour):
	return "".join(map(lambda x: "%02x" % x, colour * 255.0))

def addState(ob, state):
	'''Add a set of states to this object's state.'''
	stateBitmask = 1 << (state - 1)
	ob.state |= stateBitmask

def remState(ob, state):
	'''Remove a state from this object's state.'''
	stateBitmask = 1 << (state - 1)
	ob.state &= (~stateBitmask)

def setState(ob, state):
	'''Set the object's state. All current states will be un-set and replaced
	with the one specified.'''
	stateBitmask = 1 << (state - 1)
	ob.state = stateBitmask

def hasState(ob, state):
	'''Test whether the object is in the specified state.'''
	stateBitmask = 1 << (state - 1)
	return (ob.state & stateBitmask) != 0

def allSensorsPositive(c):
	'''
	Test whether all sensors are positive.
	
	Parameters:
	c: A controller.
	
	Returns: true iff all sensors are positive.
	'''
	for s in c.sensors:
		if not s.positive:
			return False
	return True

def someSensorPositive(c):
	'''
	Test whether at least one sensor is positive.
	
	Parameters:
	c: A controller.
	
	Returns: true iff at least one sensor is positive.
	'''
	for s in c.sensors:
		if s.positive:
			return True
	return False

def makeScreenshot(c):
	if allSensorsPositive(c):
		Rasterizer.makeScreenshot('//Screenshot#.jpg')

class Counter:
	'''Counts the frequency of objects.'''
	def __init__(self):
		self.map = {}
		self.mode = None
		self.max = 0
		self.n = 0
	
	def add(self, ob):
		'''Add an object to this counter. If this object is the most frequent
		so far, it will be stored in the member variable 'mode'.'''
		count = 1
		if ob in self.map:
			count = self.map[ob] + 1
		self.map[ob] = count
		if count > self.max:
			self.max = count
			self.mode = ob
		self.n = self.n + 1

class _Random:
	#
	# 100 random numbers (saves needing to import the 'random' module).
	#
	RANDOMS = [
		0.61542, 0.69297, 0.76860, 0.53475, 0.40886, 0.91689, 0.93900, 0.68926,
		0.13285, 0.06095, 0.48474, 0.72606, 0.08579, 0.86588, 0.51390, 0.49194,
		0.94516, 0.65302, 0.89945, 0.17170, 0.73977, 0.57983, 0.47412, 0.70460,
		0.57242, 0.84086, 0.59730, 0.21010, 0.62376, 0.03536, 0.04448, 0.59527,
		0.27221, 0.66046, 0.38000, 0.50336, 0.86750, 0.14385, 0.93692, 0.46126,
		0.81840, 0.15508, 0.64163, 0.34990, 0.14746, 0.40949, 0.85291, 0.05562,
		0.31280, 0.20150, 0.43594, 0.97547, 0.68338, 0.70483, 0.85266, 0.32621,
		0.18625, 0.86591, 0.20850, 0.73349, 0.87122, 0.16648, 0.48411, 0.23507,
		0.15775, 0.55275, 0.68549, 0.99837, 0.06443, 0.01583, 0.10712, 0.98735,
		0.02540, 0.11582, 0.14976, 0.89697, 0.24265, 0.85307, 0.24749, 0.62709,
		0.74986, 0.45483, 0.10935, 0.46603, 0.46222, 0.61726, 0.36655, 0.16848,
		0.35994, 0.71661, 0.18646, 0.81395, 0.56462, 0.36674, 0.00286, 0.31847,
		0.26284, 0.01141, 0.67497, 0.78098
	]
	
	def __init__(self):
		self.LastRandIndex = 0
	
	def __next__(self):
		'''
		Get a random number between 0.0 and 1.0. This is only vaguely random: each
		number is drawn from a finite set of numbers, and the sequence repeats.
		'''
		self.LastRandIndex = (self.LastRandIndex + 1) % len(self.RANDOMS)
		return self.RANDOMS[self.LastRandIndex]

Random = _Random()

class FuzzySwitch:
	'''A boolean that only switches state after a number of consistent impulses.
	'''
	def __init__(self, delayOn, delayOff, startOn):
		self.delayOn = delayOn
		self.delayOff = 0 - delayOff
		self.on = startOn
		if startOn:
			self.current = self.delayOn
		else:
			self.current = self.delayOff
	
	def turnOn(self):
		self.current = max(0, self.current)
		if self.on:
			return
		
		self.current += 1
		if self.current == self.delayOn:
			self.on = True
		
	def turnOff(self):
		self.current = min(0, self.current)
		if not self.on:
			return
		
		self.current -= 1
		if self.current == self.delayOff:
			self.on = False
	
	def isOn(self):
		return self.on

class PriorityQueueItem:
	def __init__(self, key, item, priority):
		self.key = key
		self.item = item
		self.priority = priority
	
	def __repr__(self):
		return "(%s, %s, %d)" % (self.key, self.item, self.priority)

class PriorityQueue:
	'''
	A poor man's associative priority queue. All operations run in O(n) time.
	This is only meant to contain a small number of items.
	'''
	
	def __init__(self):
		'''Create a new, empty priority queue.'''
		self.Q = []
		self.ItemSet = set()
	
	def __len__(self):
		return len(self.Q)
	
	def __getitem__(self, y):
		'''
		Get the yth item from the queue. 0 is the bottom (oldest/lowest
		priority); -1 is the top (youngest/highest priority).
		'''
		return self.Q[y].item
	
	def push(self, key, item, priority):
		'''
		Add an item to the end of the queue. If the item is already in the
		queue, it is removed and added again using the new priority.
		
		Parameters:
		key:      The key to associate this item with.
		item:     The item to store in the queue.
		priority: Items with higher priority will be stored higher on the queue.
		          0 <= priority. (Integer)
		'''
		if key in self.ItemSet:
			self.discard(key)
		
		pqi = PriorityQueueItem(key, item, priority)
		
		added = False
		i = len(self.Q) - 1
		while i >= 0:
			if self.Q[i].priority <= priority:
				self.Q.insert(i + 1, pqi)
				added = True
				break
			i = i - 1
		if not added:
			self.Q.insert(0, pqi)
		
		self.ItemSet.add(key)
	
	def discard(self, key):
		'''
		Remove an item from the queue.
		
		Parameters:
		key: The key that was used to insert the item.
		'''
		i = len(self.Q) - 1
		while i >= 0:
			if self.Q[i].key == key:
				del self.Q[i]
				self.ItemSet.remove(key)
				return
			i = i - 1
	
	def pop(self):
		'''
		Remove the highest item in the queue.
		
		Returns: the item that is being removed.
		
		Raises:
		IndexError: if the queue is empty.
		'''
		pqi = self.Q.pop()
		self.ItemSet.remove(pqi.key)
		return pqi.item
	
	def top(self):
		return self[-1]

def RunTests():
	import unittest
	
	class PQTest(unittest.TestCase):
		def setUp(self):
			self.Q = PriorityQueue()
		
		def testAdd(self):
			self.Q.push('foo', 'fooI', 1)
			self.assertEquals(self.Q[-1], 'fooI')
			self.assertEquals(len(self.Q), 1)
		
		def testAddSeveral(self):
			self.Q.push('foo', 'fooI', 1)
			self.Q.push('bar', 'barI', 0)
			self.assertEquals(self.Q[-1], 'fooI')
			self.assertEquals(len(self.Q), 2)
			self.Q.push('baz', 'bazI', 1)
			self.assertEquals(self.Q[-1], 'bazI')
			self.assertEquals(len(self.Q), 3)
		
		def testRemove(self):
			self.Q.push('foo', 'fooI', 1)
			self.Q.push('bar', 'barI', 0)
			self.Q.push('baz', 'bazI', 1)
			self.Q.remove('foo')
			self.assertEquals(self.Q[-1], 'bazI')
			self.assertEquals(len(self.Q), 2)
			self.Q.remove('baz')
			self.assertEquals(self.Q[-1], 'barI')
			self.assertEquals(len(self.Q), 1)
			self.Q.remove('bar')
			self.assertEquals(len(self.Q), 0)
	
	suite = unittest.TestLoader().loadTestsFromTestCase(PQTest)
	unittest.TextTestRunner(verbosity=2).run(suite)

