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

'''
Create the structure required to control a snail. Python objects
will be created to match the types of Blender objects in the
hierarchy, with the owner as the root.

Call this script once. The rest of the processing should be done
by fetching the resulting object from the GameLogic.Snails
dictionary.
'''

import mathutils
import geometry
import Utilities
import Actor
import GameLogic

MAX_SPEED = 3.0
MIN_SPEED = -3.0
DEBUG = False

# FIXME: This is used for Euler bone transforms - but we should be able to
# transform the bones using a matrix. See ActionActuator.setChannel
PI = 3.14159
def radToDegrees(angle):
	return (angle / PI) * 180

#
# States for main snail object. The commented-out ones aren't currently used
# in the code, and are only set by logic bricks.
#
#S_INIT     = 1
S_CRAWLING = 2
S_FALLING  = 3
#S_ACTIVE   = 4
S_SHOCKED  = 5
S_NOSHELL  = 16
S_HASSHELL = 17
S_POPPING  = 18
S_INSHELL  = 19
S_EXITING  = 20
S_ENTERING = 21
#S_REINCARNATE = 29
#S_DROWNING    = 30

S_ARM_CRAWL      = 1
S_ARM_LOCOMOTION = 2
S_ARM_POP        = 16
S_ARM_ENTER      = 17
S_ARM_EXIT       = 18


ZAXIS  = mathutils.Vector([0.0, 0.0, 1.0])
XAXIS  = mathutils.Vector([1.0, 0.0, 0.0])
ORIGIN = mathutils.Vector([0.0, 0.0, 0.0])
EPSILON = 0.000001
MINVECTOR = mathutils.Vector([0.0, 0.0, EPSILON])

class SnailSegment:
	def __init__(self, owner, parent):
		self.Parent  = parent # SnailSegment or None
		self.Child   = None   # SnailSegment or None
		self.Fulcrum = None   # KX_GameObject
		self.Rays    = {}     # Dictionary of SnailRays
		self.Owner = owner
		Utilities.parseChildren(self, owner)

	def parseChild(self, child, type):
		if (type == "SnailRay"):
			self.Rays[child.Position] = SnailRay(child)
			return True
		elif (type == "SnailRayCluster"):
			self.Rays[child['Position']] = SnailRayCluster(child)
			return True
		elif (type == "SnailSegment"):
			if (self.Child):
				print("Segment %s already has a child." % self.Owner.name)
			self.Child = SnailSegment(child, self)
			return True
		elif (type == "SegmentChildPivot"):
			if (self.Child):
				print("Segment %s already has a child." % self.Owner.name)
			self.Child = SegmentChildPivot(child)
			return True
		elif (type == "Fulcrum"):
			if (self.Fulcrum):
				print("Segment %s already has a fulcrum." % self.Owner.name)
			self.Fulcrum = child
			return True
		else:
			return False

	def orient(self, parentOrnMat):
		if (self.Parent):
			right = self.Parent.Owner.getAxisVect(XAXIS)
			self.Owner.alignAxisToVect(right, 0)
		
		_, p1 = self.Parent.Rays['Right'].getHitPosition()
		_, p2 = self.Parent.Rays['Left'].getHitPosition()
		p3 = self.Parent.Fulcrum.worldPosition
		normal = geometry.TriangleNormal(p1, p2, p3)
		
		if normal.dot(self.Parent.Owner.getAxisVect(ZAXIS)) > 0.0:
			#
			# Normal is within 90 degrees of parent's normal -> segment not
			# doubling back on itself.
			#
			# Interpolate between normals for current and previous frames.
			# Don't use a factor of 0.5: potential for normal to average out
			# to be (0,0,0)
			#
			orientation = self.Owner.getAxisVect(ZAXIS)
			orientation = Utilities._lerp(normal, orientation, 0.4)
			self.Owner.alignAxisToVect(orientation, 2)
		
		#
		# Make orientation available to armature. Use the inverse of the
		# parent's orientation to find the local orientation.
		#
		parentInverse = parentOrnMat.copy()
		parentInverse.invert()
		localOrnMat = parentInverse * self.Owner.worldOrientation
		euler = localOrnMat.to_euler()
		self.Owner['Heading'] = radToDegrees(euler.x)
		self.Owner['Pitch'] = radToDegrees(euler.y)
		self.Owner['Roll'] = radToDegrees(euler.z)
		
		if (self.Child):
			self.Child.orient(self.Owner.worldOrientation)
	
	def setBendAngle(self, angle):
		if self.Child:
			self.Child.setBendAngle(angle)

class AppendageRoot(SnailSegment):
	def __init__(self, owner):
		SnailSegment.__init__(self, owner, None)
		
	def orient(self):
		self.Child.orient(self.Owner.worldOrientation)

class SegmentChildPivot(SnailSegment):
	def __init__(self, owner):
		SnailSegment.__init__(self, owner, None)
		
	def orient(self, parentOrnMat):
		self.Child.orient(parentOrnMat)
	
	def setBendAngle(self, angle):
		self.Owner['BendAngle'] = angle
		self.Child.setBendAngle(angle)

class Snail(SnailSegment, Actor.Actor):
	def __init__(self, owner, cargoHold, eyeLocL, eyeLocR):
		# FIXME: This derives from two classes, and both set the Owner property.
		Actor.Actor.__init__(self, owner)
		Actor.Director.setMainCharacter(self)
		
		self.Head = None
		self.Tail = None
		self.CargoHold = cargoHold
		self.getAttachPoints()['CargoHold'] = cargoHold
		self.EyeLocL = eyeLocL
		self.EyeLocR = eyeLocR
		self.NearestShell = None
		self.Shell = None
		self.Shockwave = None
		self.Trail = None
		self.Armature = None
		self.TouchedObject = None
		SnailSegment.__init__(self, owner, None)
		if not self.Head:
			raise Exception("No head defined.")
		if not self.Tail:
			raise Exception("No tail defined.")
		if not self.Shockwave:
			raise Exception("No Shockwave defined.")
		self.setHealth(7.0)
		
		global DEBUG
		if DEBUG:
			scene = GameLogic.getCurrentScene()
			marker = scene.addObject("SnailMarker", self.Owner)
			marker.setParent(self.Owner)
	
	def parseChild(self, child, type):
		if type == "AppendageRoot":
			if child['Location'] == 'Fore':
				self.Head = AppendageRoot(child)
			elif child['Location'] == 'Aft':
				self.Tail = AppendageRoot(child)
			else:
				print("Unknown appendage type %s on %s." % (
				    (child['Location'], child.name)))
			return True
		elif type == "Shockwave":
			self.Shockwave = child
			#
			# Remove this from the hierarchy: the shockwave only needs to be
			# positioned when it fires; other than that, it doesn't matter where
			# it is. Removing it from the hierarchy prevents it from being
			# implicitely and incorrectly made visible.
			#
			child.removeParent()
			child.setVisible(True, True)
			return True
		elif type == "SnailTrail":
			self.Trail = SnailTrail(child, self)
			return True
		elif type == 'Armature':
			self.Armature = child
			return True
		else:
			return SnailSegment.parseChild(self, child, type)
	
	def orient(self):
		'''Adjust the orientation of the snail to match the nearest surface.'''
		counter = Utilities.Counter()
		ob0, p0 = self.Rays['0'].getHitPosition()
		if ob0:
			counter.add(ob0)
		ob1, p1 = self.Rays['1'].getHitPosition()
		if ob1:
			counter.add(ob1)
		ob2, p2 = self.Rays['2'].getHitPosition()
		if ob2:
			counter.add(ob2)
		ob3, p3 = self.Rays['3'].getHitPosition()
		if ob3:
			counter.add(ob3)
		
		#
		# Inherit the angular velocity of a nearby surface. The object that was
		# hit by the most rays (above) is used.
		# TODO: The linear velocity should probably be set, too: fast-moving
		# objects can be problematic.
		#
		if counter.mode:
			angV = counter.mode.getAngularVelocity()
			if angV.magnitude < EPSILON:
				angV = MINVECTOR
			self.Owner.setAngularVelocity(angV)
		self.TouchedObject = counter.mode
		
		#
		# Set property on object so it knows whether it's falling. This is used
		# to detect when to transition from S_FALLING to S_CRAWLING.
		#
		self.Owner['nHit'] = counter.n
		
		#
		# Derive normal from hit points and update orientation.
		#
		orientation = geometry.QuadNormal(p0, p1, p2, p3)
		self.Owner.alignAxisToVect(orientation, 2)
		
		self.Head.orient()
		self.Tail.orient()
	
	def lookAt(self, targetList):
		'''
		Turn the eyes to face the nearest object in targetList. Objects with a
		higher priority will always be preferred. In practice, the targetList
		is provided by a Near sensor, so it won't include every object in the
		scene. Objects with a LookAt priority of less than zero will be ignored.
		'''
		def getAngleIndices(vec):
			MULT = 100.0
			vec = vec.copy()
			vec.normalize()
			angZIndex = 0.0
			if vec.y >= 0:
				angZIndex = vec.x * MULT
			else:
				if vec.x >= 0:
					angZIndex = ((1.0 - vec.x) * MULT) + MULT
				else:
					angZIndex = ((-1.0 - vec.x) * MULT) - MULT
			angZIndex = Utilities._clamp(-150, 150, angZIndex)
			angXIndex = vec.z * MULT
			return angXIndex, angZIndex
		
		def setEyeRot(ob, XL, ZL, XR, ZR, fac):
			ob['Eye_X_L'] = Utilities._lerp(ob['Eye_X_L'], XL, fac)
			ob['Eye_Z_L'] = Utilities._lerp(ob['Eye_Z_L'], ZL, fac)
			ob['Eye_X_R'] = Utilities._lerp(ob['Eye_X_R'], XR, fac)
			ob['Eye_Z_R'] = Utilities._lerp(ob['Eye_Z_R'], ZR, fac)
		
		nearest = None
		minDist = None
		maxPriority = 0
		for target in targetList:
			if target['LookAt'] < maxPriority:
				continue
			dist = self.Owner.getDistanceTo(target)
			if nearest == None or dist < minDist:
				nearest = target
				minDist = dist
				maxPriority = target['LookAt']
		
		if not nearest:
			setEyeRot(self.Armature, 0.0, 0.0, 0.0, 0.0, 
			          self.Owner['EyeRotFac'])
			return
		
		#
		# Normally we would need to find cos(x) to get the angle on the Z-axis.
		# But here, x drives an IPO curve with the cosine wave baked into it.
		#
		p = Utilities._toLocal(self.EyeLocL, nearest.worldPosition)
		angXIndexL, angZIndexL = getAngleIndices(p)
		
		p = Utilities._toLocal(self.EyeLocR, nearest.worldPosition)
		angXIndexR, angZIndexR = getAngleIndices(p)
		
		setEyeRot(self.Armature, angXIndexL, angZIndexL, angXIndexR, angZIndexR,
		          self.Owner['EyeRotFac'])
	
	def _stowShell(self, shell):
		referential = shell.CargoHook
		
		Utilities.setRelOrn(shell.Owner,
						    self.getAttachPoints()['CargoHold'],
						    referential)
		Utilities.setRelPos(shell.Owner,
						    self.getAttachPoints()['CargoHold'],
						    referential)
		self.AddChild(shell, 'CargoHold', compound = False)
	
	def setShell(self, shell, animate):
		'''
		Add the shell as a descendant of the snail. It will be
		made a child of the CargoHold. If the shell has a child
		of type "CargoHook", that will be used as the
		referential (offset). Otherwise, the shell will be
		positioned with its own origin at the same location as
		the CargoHold.
		
		Adding the shell as a child prevents collision with the
		parent. The shell's inactive state will also be set.
		'''
		Utilities.remState(self.Owner, S_NOSHELL)
		Utilities.addState(self.Owner, S_HASSHELL)
		
		self._stowShell(shell)
		
		self.Shell = shell
		self.Owner['HasShell'] = 1
		self.Owner['DynamicMass'] = self.Owner['DynamicMass'] + self.Shell.Owner['DynamicMass']
		self.Shell.OnPickedUp(self, animate)
		if animate:
			self.Shockwave.worldPosition = self.Shell.Owner.worldPosition
			self.Shockwave.worldOrientation = self.Shell.Owner.worldOrientation
			Utilities.setState(self.Shockwave, 2)
	
	def dropShell(self, animate):
		'''Causes the snail to drop its shell, if it is carrying one.'''
		if self.Suspended:
			return
		
		if not Utilities.hasState(self.Owner, S_HASSHELL):
			return
		
		Utilities.remState(self.Owner, S_HASSHELL)
		Utilities.addState(self.Owner, S_POPPING)
		Utilities.addState(self.Armature, S_ARM_POP)
		self.Armature['NoTransition'] = not animate
	
	def onDropShell(self):
		'''Unhooks the current shell by un-setting its parent.'''
		if not Utilities.hasState(self.Owner, S_POPPING):
			return
		
		Utilities.remState(self.Owner, S_POPPING)
		Utilities.addState(self.Owner, S_NOSHELL)
		
		self.RemoveChild(self.Shell)
		velocity = self.Owner.getAxisVect(ZAXIS)
		velocity = velocity * self.Owner['ShellPopForce']
		self.Shell.Owner.applyImpulse(self.Shell.Owner.worldPosition, velocity)
		self.Owner['HasShell'] = 0
		self.Owner['DynamicMass'] = self.Owner['DynamicMass'] - self.Shell.Owner['DynamicMass']
		self.Shell.OnDropped()
		self.Shell = None
	
	def enterShell(self, animate):
		'''
		Starts the snail entering the shell. Shell.OnPreEnter will be called
		immediately; Snail.onShellEnter and Shell.OnEntered will be called
		later, at the appropriate point in the animation.
		'''
		if self.Suspended:
			return
		
		if not Utilities.hasState(self.Owner, S_HASSHELL):
			return
		
		Utilities.remState(self.Owner, S_HASSHELL)
		Utilities.addState(self.Owner, S_ENTERING)
		Utilities.remState(self.Armature, S_ARM_CRAWL)
		Utilities.remState(self.Armature, S_ARM_LOCOMOTION)
		Utilities.addState(self.Armature, S_ARM_ENTER)
		self.Armature['NoTransition'] = not animate
		self.Shell.OnPreEnter()
	
	def onEnterShell(self):
		'''Transfers control of the character to the shell. The snail must have
		a shell.'''
		if not Utilities.hasState(self.Owner, S_ENTERING):
			return
		
		Utilities.remState(self.Owner, S_CRAWLING)
		Utilities.remState(self.Owner, S_ENTERING)
		Utilities.addState(self.Owner, S_INSHELL)
		
		linV = self.Owner.getLinearVelocity()
		angV = self.Owner.getAngularVelocity()
		
		self.RemoveChild(self.Shell)
		self.Owner.setVisible(0, 1)
		self.Owner.localScale = (0.01, 0.01, 0.01)
		self.Shell.AddChild(self)
		
		self.Shell.Owner.setLinearVelocity(linV)
		self.Shell.Owner.setAngularVelocity(angV)
	
		#
		# Swap mass with shell so the shell can influence bendy leaves properly
		#
		dm = self.Shell.Owner['DynamicMass']
		self.Shell.Owner['DynamicMass'] = self.Owner['DynamicMass']
		self.Owner['DynamicMass'] = dm
		
		self.Owner['InShell'] = 1
		self.Shell.OnEntered()
		Actor.Director.setMainCharacter(self.Shell)
	
	def exitShell(self, animate):
		'''
		Tries to make the snail exit the shell. If possible, control will be
		transferred to the snail. The snail must currently be in a shell.
		'''
		if self.Suspended:
			return
		
		if not Utilities.hasState(self.Owner, S_INSHELL):
			return
		
		Utilities.remState(self.Owner, S_INSHELL)
		Utilities.addState(self.Owner, S_EXITING)
		Utilities.addState(self.Owner, S_FALLING)
		Utilities.addState(self.Armature, S_ARM_EXIT)
		Utilities.addState(self.Armature, S_ARM_CRAWL)
		Utilities.addState(self.Armature, S_ARM_LOCOMOTION)
		self.Armature['NoTransition'] = not animate
		
		linV = self.Shell.Owner.getLinearVelocity()
		angV = self.Shell.Owner.getAngularVelocity()
		
		self.Shell.RemoveChild(self)
		self.Owner.localScale = (1.0, 1.0, 1.0)
		self.Owner.worldPosition = self.Shell.Owner.worldPosition
		self.Owner.setVisible(1, 1)
		self._stowShell(self.Shell)
		
		self.Owner.setLinearVelocity(linV)
		self.Owner.setAngularVelocity(angV)
	
		#
		# Swap mass with shell so the body can influence bendy leaves properly
		#
		dm = self.Shell.Owner['DynamicMass']
		self.Shell.Owner['DynamicMass'] = self.Owner['DynamicMass']
		self.Owner['DynamicMass'] = dm
		
		self.Owner['InShell'] = 0
		self.Shell.OnExited()
		Actor.Director.setMainCharacter(self)
	
	def onPostExitShell(self):
		'''Called when the snail has finished its exit shell
		animation (several frames after control has been
		transferred).'''
		if not Utilities.hasState(self.Owner, S_EXITING):
			return
		
		Utilities.remState(self.Owner, S_EXITING)
		Utilities.addState(self.Owner, S_HASSHELL)
		self.Shell.OnPostExit()
	
	def onStartCrawling(self):
		'''Called when the snail enters its crawling state.'''
		#
		# Don't set it quite to zero: zero vectors are ignored!
		#
		self.Owner.setAngularVelocity([0.0, 0.0, 0.0001], 0)
		self.Owner.setLinearVelocity([0.0, 0.0, 0.0001], 0)
	
	def setSpeedMultiplier(self, mult):
		self.Owner['SpeedMultiplier'] = max(min(mult, MAX_SPEED), MIN_SPEED)

	def decaySpeed(self):
		'''Bring the speed of the snail one step closer to normal speed.'''
		o = self.Owner
		dr = o['SpeedDecayRate']
		mult = o['SpeedMultiplier']
		
		if mult == 1.0:
			return
		elif mult > 1.0:
			o['SpeedMultiplier'] = max(mult - dr, 1.0)
		else:
			o['SpeedMultiplier'] = min(mult + dr, 1.0)
	
	def crawling(self):
		return Utilities.hasState(self.Owner, S_CRAWLING)
	
	def Drown(self):
		if not Utilities.hasState(self.Owner, S_INSHELL):
			return Actor.Actor.Drown(self)
		else:
			return False
	
	def damage(self, amount, shock):
		if (Utilities.hasState(self.Owner, S_ENTERING) or
		    Utilities.hasState(self.Owner, S_EXITING)):
			return
		Actor.Actor.damage(self, amount, shock)
		if amount > 0.0:
			if shock and Utilities.hasState(self.Owner, S_HASSHELL):
				self.enterShell(True)
	
	def OnMovementImpulse(self, fwd, back, left, right):
		'''
		Make the snail move. If moving forward or backward, this implicitely
		calls decaySpeed.
		'''
		if not self.crawling() or self.Suspended:
			return
		
		o = self.Owner
		
		#
		# Decide which direction to move in on the Y-axis.
		#
		fwdSign = 0
		if fwd:
			fwdSign = fwdSign + 1
		if back:
			fwdSign = fwdSign - 1
		
		#
		# Apply forward/backward motion.
		#
		speed = o['NormalSpeed'] * o['SpeedMultiplier'] * float(fwdSign)
		o.applyMovement((0.0, speed, 0.0), True)
		self.decaySpeed()
		
		#
		# Decide which way to turn.
		#
		targetBendAngleFore = 0.0
		targetRot = 0.0
		targetBendAngleAft = None
		if left:
			#
			# Bend left.
			#
			targetBendAngleFore = targetBendAngleFore - o['MaxBendAngle']
			targetRot = targetRot + o['MaxRot']
		if right:
			#
			# Bend right. If bending left too, the net result will be
			# zero.
			#
			targetBendAngleFore = targetBendAngleFore + o['MaxBendAngle']
			targetRot = targetRot - o['MaxRot']
		
		locomotionStep = self.Owner['SpeedMultiplier'] * 0.4
		if fwdSign > 0:
			#
			# Moving forward.
			#
			targetBendAngleAft = targetBendAngleFore
			self.Armature['LocomotionFrame'] = (
				self.Armature['LocomotionFrame'] + locomotionStep)
		elif fwdSign < 0:
			#
			# Reversing: invert rotation direction.
			#
			targetBendAngleAft = targetBendAngleFore
			targetRot = 0.0 - targetRot
			self.Armature['LocomotionFrame'] = (
				self.Armature['LocomotionFrame'] - locomotionStep)
		else:
			#
			# Stationary. Only bend the head.
			#
			targetBendAngleAft = 0.0
			targetRot = 0.0
		
		self.Armature['LocomotionFrame'] = (
			self.Armature['LocomotionFrame'] % 19)
		
		#
		# Rotate the snail.
		#
		o['Rot'] = Utilities._lerp(o['Rot'], targetRot, o['RotFactor'])
		oRot = mathutils.Matrix.Rotation(o['Rot'], 3, ZAXIS)
		o.localOrientation = o.localOrientation * oRot
		
		#
		# Match the bend angle with the current speed.
		#
		targetBendAngleAft = targetBendAngleAft / o['SpeedMultiplier']
		
		o['BendAngleFore'] = Utilities._lerp(o['BendAngleFore'],
		                                     targetBendAngleFore,
		                                     o['BendFactor'])
		if fwdSign != 0:
			o['BendAngleAft'] = Utilities._lerp(o['BendAngleAft'],
		                                        targetBendAngleAft,
		                                        o['BendFactor'])
		
		#
		# Bend the snail. This will be applied by other logic bricks, so it may
		# happen one frame later.
		#
		self.Head.setBendAngle(o['BendAngleFore'])
		self.Tail.setBendAngle(o['BendAngleAft'])
		
		self.Trail.onSnailMoved(self.Owner['SpeedMultiplier'])
	
	def OnButton1(self, positive, triggered):
		if positive and triggered:
			if Utilities.hasState(self.Owner, S_INSHELL):
				self.exitShell(animate = True)
			elif Utilities.hasState(self.Owner, S_HASSHELL):
				self.enterShell(animate = True)
			elif Utilities.hasState(self.Owner, S_NOSHELL):
				if self.NearestShell:
					self.setShell(self.NearestShell, animate = True)
	
	def OnButton2(self, positive, triggered):
		if positive and triggered:
			if Utilities.hasState(self.Owner, S_HASSHELL):
				self.dropShell(animate = True)

class SnailRayCluster:
	'''A collection of SnailRays. These will cast a ray once per frame in the
	order defined by their Priority property (ascending order). The first one
	that hits is used.'''
	
	def __init__(self, owner):
		self.Rays = []
		self.Marker = None
		self.Owner = owner
		self.DebugMesh = None
		Utilities.parseChildren(self, owner)
		if (len(self.Rays) <= 0):
			raise Exception("Ray cluster %s has no ray children." % self.Owner.name)
		self.Rays.sort(key=lambda ray: ray.Owner['Priority'])
		self.LastHitPoint = ORIGIN
		
		global DEBUG
		if DEBUG:
			self.DebugMesh.setVisible(True, True)
			scene = GameLogic.getCurrentScene()
			self.Marker = scene.addObject("RayMarker", self.Owner)
		else:
			self.DebugMesh.endObject()
	
	def parseChild(self, child, type):
		global DEBUG
		
		if (type == "SnailRay"):
			self.Rays.append(SnailRay(child))
			return True
		elif (type == "SnailRayCluster"):
			self.Rays.append(SnailRayCluster(child))
			return True
		elif type == 'Debug':
			self.DebugMesh = child
			return True
		else:
			return False

	def getHitPosition(self):
		"""Return the hit point of the first child ray that hits.
		If none hit, the default value of the first ray is returned."""
		p = None
		ob = None
		for ray in self.Rays:
			ob, p = ray.getHitPosition()
			if ob:
				self.LastHitPoint = Utilities._toLocal(self.Owner, p)
				break
		
		wp = Utilities._toWorld(self.Owner, self.LastHitPoint)
		if (self.Marker):
			self.Marker.worldPosition = wp
			
		return ob, wp

class SnailRay:
	LastPoint = None

	def __init__(self, owner):
		self.Marker = None
		self.Owner = owner
		Utilities.parseChildren(self, owner)
		self.LastPoint = self.Owner.worldPosition
	
	def parseChild(self, child, type):
		if (type == "Marker"):
			self.Marker = child
			child.removeParent()
			return True

	def getHitPosition(self):
		origin = self.Owner.worldPosition
		vec = self.Owner.getAxisVect(ZAXIS)
		through = origin + vec
		ob, hitPoint, normal = self.Owner.rayCast(
			through,            # to
			origin,             # from
			self.Owner['Length'],  # dist
			'Ground',           # prop
			1,                  # face
			1                   # xray
		)
		
		if (ob):
			#
			# Ensure the hit was not from inside an object.
			#
			if normal.dot(vec) > 0.0:
				ob = None
			else:
				self.LastPoint = hitPoint
		
		if (self.Marker):
			self.Marker.worldPosition = self.LastPoint
		
		return ob, self.LastPoint

class SnailTrail:
	S_NORMAL = 2
	S_SLOW = 3
	S_FAST = 4
	SPEED_EPSILON = 0.2
	
	def __init__(self, owner, snail):
		self.LastMinorPos = owner.worldPosition.copy()
		self.LastMajorPos = self.LastMinorPos.copy()
		self.Paused = False
		self.TrailSpots = []
		self.SpotIndex = 0
		self.Snail = snail
		self.Owner = owner
		Utilities.parseChildren(self, owner)
	
	def parseChild(self, child, type):
		if (type == "TrailSpot"):
			self.TrailSpots.append(child)
			child.removeParent()
			return True
	
	def AddSpot(self, speedStyle):
		'''
		Add a spot where the snail is now. Actually, this only adds a spot half
		the time: gaps will be left in the trail, like so:
		    -----     -----     -----     -----     -----
		
		@param speedStyle: The style to apply to the new spot. One of [S_SLOW,
			S_NORMAL, S_FAST].
		'''
		self.SpotIndex = (self.SpotIndex + 1) % len(self.TrailSpots)
		
		scene = GameLogic.getCurrentScene()
		spot = self.TrailSpots[self.SpotIndex]
		spotI = scene.addObject(spot, self.Owner)
		
		#
		# Attach the spot to the object that the snail is crawling on.
		#
		if self.Snail.TouchedObject:
			spotI.setParent(self.Snail.TouchedObject)
		
		Utilities.setState(spotI, speedStyle)
	
	def onSnailMoved(self, speedMultiplier):
		pos = self.Owner.worldPosition
		
		distMajor = (pos - self.LastMajorPos).magnitude
		if distMajor > self.Snail.Owner['TrailSpacingMajor']:
			self.LastMajorPos = pos.copy()
			self.Paused = not self.Paused
		
		if self.Paused:
			return
		
		distMinor = (pos - self.LastMinorPos).magnitude
		if distMinor > self.Snail.Owner['TrailSpacingMinor']:
			self.LastMinorPos = pos.copy()
			speedStyle = SnailTrail.S_NORMAL
			if speedMultiplier > (1.0 + SnailTrail.SPEED_EPSILON):
				speedStyle = SnailTrail.S_FAST
			elif speedMultiplier < (1.0 - SnailTrail.SPEED_EPSILON):
				speedStyle = SnailTrail.S_SLOW
			self.AddSpot(speedStyle)

#
# Module interface functions.
#

def Init(cont):
	cargoHold = cont.sensors['sCargoHoldHook'].owner
	eyeLocL = cont.sensors['sEyeLocHookL'].owner
	eyeLocR = cont.sensors['sEyeLocHookR'].owner
	snail = Snail(cont.owner, cargoHold, eyeLocL, eyeLocR)
	cont.owner['Snail'] = snail

def Orient(c):
	c.owner['Snail'].orient()

def Look(c):
	sLookAt = c.sensors['sLookAt']
	c.owner['Snail'].lookAt(sLookAt.hitObjectList)

def _GetNearestShell(snailOb, shellObs):
	nearest = None
	dist = None
	for shellOb in shellObs:
		shell = shellOb['Actor']
		if shell.IsCarried():
			continue
		if not nearest:
			nearest = shellOb
			continue
		d = shellOb.getDistanceTo(snailOb)
		if not nearest or d < dist:
			nearest = shellOb
			dist = d
	
	if not nearest:
		return None
	else:
		return nearest['Actor']

def SetShellImmediate(c):
	if not Utilities.allSensorsPositive(c):
		return
	
	snail = c.owner['Snail']
	closeShells = c.sensors['sShellPickup'].hitObjectList
	snail.setShell(_GetNearestShell(c.owner, closeShells), False)

def OnShellTouched(c):
	snail = c.owner['Snail']
	closeShells = c.sensors['sShellPickup'].hitObjectList
	snail.NearestShell = _GetNearestShell(c.owner, closeShells)

def OnDropShell(c):
	'''
	Called when the snail should drop its shell. This happens on a certain frame
	of the drop animation, as triggered by DropShell.
	'''
	if Utilities.allSensorsPositive(c):
		c.owner['Snail'].onDropShell()

def OnShellPostExit(c):
	'''Called when the shell has been fully exited.'''
	if Utilities.allSensorsPositive(c):
		c.owner['Snail'].onPostExitShell()

def OnShellEnter(c):
	'''
	Transfers control of the snail to its shell. Allows for things like
	steering a rolling shell. This must be run from a controller on the
	snail. The snail must be carrying a shell. To reverse this, run
	OnShellExit from a controller on the snail.
	'''
	if Utilities.allSensorsPositive(c):
		c.owner['Snail'].onEnterShell()

def OnStartCrawling(c):
	c.owner['Snail'].onStartCrawling()

def OnTouchSpeedModifier(c):
	mult = 0.0
	hitObs = c.sensors[0].hitObjectList
	
	if len(hitObs) == 0:
		return
	
	for hitOb in hitObs:
		mult = mult + hitOb['SetSpeedMultiplier']
		if 'SingleUse' in hitOb:
			hitOb.endObject()
	
	mult = mult / float(len(hitObs))
	c.owner['Snail'].setSpeedMultiplier(mult)

#
# Independent functions.
#

def EyeLength(c):
	'''Sets the length of the eyes. To be called by the snail.'''
	def getRayLength(sensor):
		origin = sensor.owner.worldPosition
		through = mathutils.Vector(sensor.hitPosition)
		return (through - origin).magnitude
	
	def getEyeLength(currentProportion, maxLen, sensor, factorUp):
		targetLength = 0.0
		if (sensor.positive):
			targetLength = getRayLength(sensor) * 0.9
		else:
			targetLength = maxLen
		targetProportion = (targetLength / maxLen) * 100
		
		if (currentProportion >= targetProportion):
			return targetProportion * 0.5
		else:
			return Utilities._lerp(currentProportion, targetProportion, factorUp)
	
	o = c.owner
	sRayL = c.sensors['sEyeRay_L']
	sRayR = c.sensors['sEyeRay_R']
	aActionL = c.actuators['aEyeLen_L']
	aActionR = c.actuators['aEyeLen_R']
	
	o['EyeProp_L'] = getEyeLength(o['EyeProp_L'], o['EyeRestLen'], sRayL, o['EyeLenFac'])
	o['EyeProp_R'] = getEyeLength(o['EyeProp_R'], o['EyeRestLen'], sRayR, o['EyeLenFac'])
	
	c.activate(aActionL)
	c.activate(aActionR)

def CopyRotToArmature(c):
	'''
	Copies the orientation of each snail segment to attributes in its
	corresponding bone in the armature. To be called by the armature. The
	controller must have sensors ('hooks', below) attached to the segments.
	'''
	o = c.owner
	
	h1 = c.sensors['sHook_H1'].owner
	h2 = c.sensors['sHook_H2'].owner
	t1 = c.sensors['sHook_T1'].owner
	t2 = c.sensors['sHook_T2'].owner
	
	o['Heading_H1'] = h1['Heading']
	o['Pitch_H1'] = h1['Pitch']
	o['Roll_H1'] = h1['Roll']
	
	o['Heading_H2'] = h2['Heading']
	o['Pitch_H2'] = h2['Pitch']
	o['Roll_H2'] = h2['Roll']
	
	o['Heading_T1'] = t1['Heading']
	o['Pitch_T1'] = t1['Pitch']
	o['Roll_T1'] = t1['Roll']
	
	o['Heading_T2'] = t2['Heading']
	o['Pitch_T2'] = t2['Pitch']
	o['Roll_T2'] = t2['Roll']

