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
import math

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

class SnailSegment:
	def __init__(self, owner, parent):
		self.Parent  = parent # SnailSegment or None
		self.Child   = None   # SnailSegment or None
		self.Fulcrum = None   # KX_GameObject
		self.Rays    = {}     # Dictionary of SnailRays
		self.owner = owner
		Utilities.parseChildren(self, owner)

	def parseChild(self, child, type):
		if (type == "ArcRay"):
			self.Rays[child['Position']] = ArcRay(child)
			return True
		elif (type == "SnailSegment"):
			if (self.Child):
				print("Segment %s already has a child." % self.owner.name)
			self.Child = SnailSegment(child, self)
			return True
		elif (type == "SegmentChildPivot"):
			if (self.Child):
				print("Segment %s already has a child." % self.owner.name)
			self.Child = SegmentChildPivot(child)
			return True
		elif (type == "Fulcrum"):
			if (self.Fulcrum):
				print("Segment %s already has a fulcrum." % self.owner.name)
			self.Fulcrum = child
			return True
		else:
			return False

	def orient(self, parentOrnMat, armature):
		if (self.Parent):
			right = self.Parent.owner.getAxisVect(Utilities.XAXIS)
			self.owner.alignAxisToVect(right, 0)
		
		_, p1, _ = self.Parent.Rays['Right'].getHitPosition()
		_, p2, _ = self.Parent.Rays['Left'].getHitPosition()
		p3 = self.Parent.Fulcrum.worldPosition
		normal = geometry.TriangleNormal(p1, p2, p3)
		
		if normal.dot(self.Parent.owner.getAxisVect(Utilities.ZAXIS)) > 0.0:
			#
			# Normal is within 90 degrees of parent's normal -> segment not
			# doubling back on itself.
			#
			# Interpolate between normals for current and previous frames.
			# Don't use a factor of 0.5: potential for normal to average out
			# to be (0,0,0)
			#
			orientation = self.owner.getAxisVect(Utilities.ZAXIS)
			orientation = Utilities._lerp(normal, orientation, 0.4)
			self.owner.alignAxisToVect(orientation, 2)
		
		#
		# Make orientation available to armature. Use the inverse of the
		# parent's orientation to find the local orientation.
		#
		parentInverse = parentOrnMat.copy()
		parentInverse.invert()
		localOrnMat = parentInverse * self.owner.worldOrientation
		channel = armature.channels[self.owner['Channel']]
		channel.rotation_quaternion = localOrnMat.to_quat()
		
		if (self.Child):
			self.Child.orient(self.owner.worldOrientation, armature)
	
	def setBendAngle(self, angle):
		if self.Child:
			self.Child.setBendAngle(angle)

class AppendageRoot(SnailSegment):
	def __init__(self, owner):
		SnailSegment.__init__(self, owner, None)
		
	def orient(self, armature):
		self.Child.orient(self.owner.worldOrientation, armature)

class SegmentChildPivot(SnailSegment):
	def __init__(self, owner):
		SnailSegment.__init__(self, owner, None)
		
	def orient(self, parentOrnMat, armature):
		self.Child.orient(parentOrnMat, armature)
	
	def setBendAngle(self, angle):
		self.owner['BendAngle'] = angle
		self.Child.setBendAngle(angle)

class Snail(SnailSegment, Actor.Actor):
	def __init__(self, owner, cargoHold, eyeRayL, eyeRayR, eyeLocL, eyeLocR, camera):
		# FIXME: This derives from two classes, and both set the Owner property.
		Actor.Actor.__init__(self, owner)
		Actor.Director.setMainCharacter(self)
		
		self.Head = None
		self.Tail = None
		self.CargoHold = cargoHold
		self.getAttachPoints()['CargoHold'] = cargoHold
		self.EyeRayL = eyeRayL
		self.EyeRayR = eyeRayR
		self.EyeLocL = eyeLocL
		self.EyeLocR = eyeLocR
		self.NearestShell = None
		self.Shell = None
		self.Shockwave = None
		self.Trail = None
		self.Armature = None
		self.TouchedObject = None
		self.camera = camera
		SnailSegment.__init__(self, owner, None)
		if not self.Head:
			raise Exception("No head defined.")
		if not self.Tail:
			raise Exception("No tail defined.")
		if not self.Shockwave:
			raise Exception("No Shockwave defined.")
		self.setHealth(7.0)
		
		if DEBUG:
			self.eyeMarkerL = Utilities.addObject('AxisMarker', 0)
			Utilities._copyTransform(eyeLocL, self.eyeMarkerL)
			self.eyeMarkerL.setParent(eyeLocL)
			self.eyeMarkerR = Utilities.addObject('AxisMarker', 0)
			Utilities._copyTransform(eyeLocR, self.eyeMarkerR)
			self.eyeMarkerR.setParent(eyeLocR)
	
	def getTouchedObject(self):
		return self.TouchedObject
	
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
	
	def update(self):
		self.orient()
		self.updateEyeLength()
		
		# Don't update armature: this must be done last, and it's hard to
		# predict whether another function will want to modify the pose.
		# Just assume this will happen due to an action being played through an
		# actuator.
		#self.Armature.update()
	
	def orient(self):
		'''Adjust the orientation of the snail to match the nearest surface.'''
		counter = Utilities.Counter()
		avNormal = Utilities.ZEROVEC.copy()
		ob0, p0, n0 = self.Rays['0'].getHitPosition()
		avNormal += n0
		if ob0:
			counter.add(ob0)
		ob1, p1, n1 = self.Rays['1'].getHitPosition()
		avNormal += n1
		if ob1:
			counter.add(ob1)
		ob2, p2, n2 = self.Rays['2'].getHitPosition()
		avNormal += n2
		if ob2:
			counter.add(ob2)
		ob3, p3, n3 = self.Rays['3'].getHitPosition()
		avNormal += n3
		if ob3:
			counter.add(ob3)
		
		avNormal /= 4.0
		
		#
		# Inherit the angular velocity of a nearby surface. The object that was
		# hit by the most rays (above) is used.
		# TODO: The linear velocity should probably be set, too: fast-moving
		# objects can be problematic.
		#
		self.TouchedObject = counter.mode
		if self.TouchedObject != None:
			angV = counter.mode.getAngularVelocity()
			if angV.magnitude < Utilities.EPSILON:
				angV = Utilities.MINVECTOR
			self.owner.setAngularVelocity(angV)
		
		#
		# Set property on object so it knows whether it's falling. This is used
		# to detect when to transition from S_FALLING to S_CRAWLING.
		#
		self.owner['nHit'] = counter.n
		
		#
		# Derive normal from hit points and update orientation. Using QuadNormal
		# gives a smoother transition than just averaging the normals returned
		# by the rays.
		#
		orientation = geometry.QuadNormal(p0, p1, p2, p3)
		if orientation.dot(avNormal) < 0.0:
			orientation.negate()
		self.owner.alignAxisToVect(orientation, 2)
		
		self.Head.orient(self.Armature)
		self.Tail.orient(self.Armature)
	
	def _updateEyeLength(self, eyeRayOb):
		restLength = self.owner['EyeRestLen']
		channel = self.Armature.channels[eyeRayOb['channel']]
		
		vect = eyeRayOb.getAxisVect(Utilities.ZAXIS) * restLength
		through = eyeRayOb.worldPosition + vect
		hitOb, hitPos, _ = Utilities._rayCastP2P(through, eyeRayOb,
				prop = 'Ground')
		
		targetLength = vect.magnitude
		if hitOb:
			targetLength = (hitPos - eyeRayOb.worldPosition).magnitude
			targetLength *= 0.9
		targetProportion = (targetLength / restLength)
		
		currentProportion = channel.scale.y
		if (currentProportion >= targetProportion):
			targetProportion *= 0.5
		else:
			targetProportion = Utilities._lerp(currentProportion,
					targetProportion, self.owner['EyeLenFac'])
		
		channel.scale = (1.0, targetProportion, 1.0)
	
	def updateEyeLength(self):
		self._updateEyeLength(self.EyeRayL)
		self._updateEyeLength(self.EyeRayR)
	
	def lookAt(self, targetList):
		'''
		Turn the eyes to face the nearest object in targetList. Objects with a
		higher priority will always be preferred. In practice, the targetList
		is provided by a Near sensor, so it won't include every object in the
		scene. Objects with a LookAt priority of less than zero will be ignored.
		'''

		def look(eye, target):
			channel = self.Armature.channels[eye['channel']]
			_, gVec, _ = eye.getVectTo(target)
			eye.alignAxisToVect(eye.parent.getAxisVect(Utilities.ZAXIS), 2)
			eye.alignAxisToVect(gVec, 1)
			orn = eye.localOrientation.to_quat()
			oldOrn = mathutils.Quaternion(channel.rotation_quaternion)
			channel.rotation_quaternion = oldOrn.slerp(orn, 0.1)
		
		def resetOrn(eye):
			channel = self.Armature.channels[eye['channel']]
			orn = mathutils.Quaternion()
			orn.identity()
			oldOrn = mathutils.Quaternion(channel.rotation_quaternion)
			channel.rotation_quaternion = oldOrn.slerp(orn, 0.1)
			
		nearest = None
		minDist = None
		maxPriority = 0
		for target in targetList:
			if target['LookAt'] < maxPriority:
				continue
			dist = self.owner.getDistanceTo(target)
			if nearest == None or dist < minDist:
				nearest = target
				minDist = dist
				maxPriority = target['LookAt']
		
		if not nearest:
			resetOrn(self.EyeLocL)
			resetOrn(self.EyeLocR)
			return
		
		look(self.EyeLocL, nearest)
		look(self.EyeLocR, nearest)
	
	def _stowShell(self, shell):
		referential = shell.CargoHook
		
		Utilities.setRelOrn(shell.owner,
						    self.getAttachPoints()['CargoHold'],
						    referential)
		Utilities.setRelPos(shell.owner,
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
		Utilities.remState(self.owner, S_NOSHELL)
		Utilities.addState(self.owner, S_HASSHELL)
		
		self._stowShell(shell)
		
		self.Shell = shell
		self.owner['HasShell'] = 1
		self.owner['DynamicMass'] = self.owner['DynamicMass'] + self.Shell.owner['DynamicMass']
		self.Shell.OnPickedUp(self, animate)
		if animate:
			self.Shockwave.worldPosition = self.Shell.owner.worldPosition
			self.Shockwave.worldOrientation = self.Shell.owner.worldOrientation
			Utilities.setState(self.Shockwave, 2)
	
	def dropShell(self, animate):
		'''Causes the snail to drop its shell, if it is carrying one.'''
		if self.Suspended:
			return
		
		if not Utilities.hasState(self.owner, S_HASSHELL):
			return
		
		Utilities.remState(self.owner, S_HASSHELL)
		Utilities.addState(self.owner, S_POPPING)
		Utilities.addState(self.Armature, S_ARM_POP)
		self.Armature['NoTransition'] = not animate
	
	def onDropShell(self):
		'''Unhooks the current shell by un-setting its parent.'''
		if not Utilities.hasState(self.owner, S_POPPING):
			return
		
		Utilities.remState(self.owner, S_POPPING)
		Utilities.addState(self.owner, S_NOSHELL)
		
		self.RemoveChild(self.Shell)
		velocity = self.owner.getAxisVect(Utilities.ZAXIS)
		velocity = velocity * self.owner['ShellPopForce']
		self.Shell.owner.applyImpulse(self.Shell.owner.worldPosition, velocity)
		self.owner['HasShell'] = 0
		self.owner['DynamicMass'] = self.owner['DynamicMass'] - self.Shell.owner['DynamicMass']
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
		
		if not Utilities.hasState(self.owner, S_HASSHELL):
			return
		
		Utilities.remState(self.owner, S_HASSHELL)
		Utilities.addState(self.owner, S_ENTERING)
		Utilities.remState(self.Armature, S_ARM_CRAWL)
		Utilities.remState(self.Armature, S_ARM_LOCOMOTION)
		Utilities.addState(self.Armature, S_ARM_ENTER)
		self.Armature['NoTransition'] = not animate
		self.Shell.OnPreEnter()
	
	def onEnterShell(self):
		'''Transfers control of the character to the shell. The snail must have
		a shell.'''
		if not Utilities.hasState(self.owner, S_ENTERING):
			return
		
		Utilities.remState(self.owner, S_CRAWLING)
		Utilities.remState(self.owner, S_ENTERING)
		Utilities.addState(self.owner, S_INSHELL)
		
		linV = self.owner.getLinearVelocity()
		angV = self.owner.getAngularVelocity()
		
		self.RemoveChild(self.Shell)
		self.owner.setVisible(0, 1)
		self.owner.localScale = (0.01, 0.01, 0.01)
		self.Shell.AddChild(self)
		
		self.Shell.owner.setLinearVelocity(linV)
		self.Shell.owner.setAngularVelocity(angV)
	
		#
		# Swap mass with shell so the shell can influence bendy leaves properly
		#
		dm = self.Shell.owner['DynamicMass']
		self.Shell.owner['DynamicMass'] = self.owner['DynamicMass']
		self.owner['DynamicMass'] = dm
		
		self.owner['InShell'] = 1
		self.Shell.OnEntered()
		Actor.Director.setMainCharacter(self.Shell)
	
	def exitShell(self, animate):
		'''
		Tries to make the snail exit the shell. If possible, control will be
		transferred to the snail. The snail must currently be in a shell.
		'''
		if self.Suspended:
			return
		
		if not Utilities.hasState(self.owner, S_INSHELL):
			return
		
		Utilities.remState(self.owner, S_INSHELL)
		Utilities.addState(self.owner, S_EXITING)
		Utilities.addState(self.owner, S_FALLING)
		Utilities.addState(self.Armature, S_ARM_EXIT)
		Utilities.addState(self.Armature, S_ARM_CRAWL)
		Utilities.addState(self.Armature, S_ARM_LOCOMOTION)
		self.Armature['NoTransition'] = not animate
		
		linV = self.Shell.owner.getLinearVelocity()
		angV = self.Shell.owner.getAngularVelocity()
		
		self.Shell.RemoveChild(self)
		self.owner.localScale = (1.0, 1.0, 1.0)
		if self.Shell.owner['ExitCentre']:
			self.owner.worldPosition = self.Shell.owner.worldPosition
		self.owner.setVisible(1, 1)
		self._stowShell(self.Shell)
		
		self.owner.setLinearVelocity(linV)
		self.owner.setAngularVelocity(angV)
	
		#
		# Swap mass with shell so the body can influence bendy leaves properly
		#
		dm = self.Shell.owner['DynamicMass']
		self.Shell.owner['DynamicMass'] = self.owner['DynamicMass']
		self.owner['DynamicMass'] = dm
		
		self.owner['InShell'] = 0
		self.Shell.OnExited()
		Actor.Director.setMainCharacter(self)
	
	def onPostExitShell(self):
		'''Called when the snail has finished its exit shell
		animation (several frames after control has been
		transferred).'''
		if not Utilities.hasState(self.owner, S_EXITING):
			return
		
		Utilities.remState(self.owner, S_EXITING)
		Utilities.addState(self.owner, S_HASSHELL)
		self.Shell.OnPostExit()
	
	def onStartCrawling(self):
		'''Called when the snail enters its crawling state.'''
		#
		# Don't set it quite to zero: zero vectors are ignored!
		#
		self.owner.setAngularVelocity([0.0, 0.0, 0.0001], 0)
		self.owner.setLinearVelocity([0.0, 0.0, 0.0001], 0)
	
	def setSpeedMultiplier(self, mult):
		self.owner['SpeedMultiplier'] = max(min(mult, MAX_SPEED), MIN_SPEED)

	def decaySpeed(self):
		'''Bring the speed of the snail one step closer to normal speed.'''
		o = self.owner
		dr = o['SpeedDecayRate']
		mult = o['SpeedMultiplier']
		
		if mult == 1.0:
			return
		elif mult > 1.0:
			o['SpeedMultiplier'] = max(mult - dr, 1.0)
		else:
			o['SpeedMultiplier'] = min(mult + dr, 1.0)
	
	def crawling(self):
		return Utilities.hasState(self.owner, S_CRAWLING)
	
	def Drown(self):
		if not Utilities.hasState(self.owner, S_INSHELL):
			return Actor.Actor.Drown(self)
		else:
			return False
	
	def damage(self, amount, shock):
		if (Utilities.hasState(self.owner, S_ENTERING) or
		    Utilities.hasState(self.owner, S_EXITING)):
			return
		Actor.Actor.damage(self, amount, shock)
		if amount > 0.0:
			if shock and Utilities.hasState(self.owner, S_HASSHELL):
				self.enterShell(True)
	
	def OnMovementImpulse(self, fwd, back, left, right):
		'''
		Make the snail move. If moving forward or backward, this implicitely
		calls decaySpeed.
		'''
		if not self.crawling() or self.Suspended:
			return
		
		o = self.owner
		
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
		
		locomotionStep = self.owner['SpeedMultiplier'] * 0.4
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
		oRot = mathutils.Matrix.Rotation(o['Rot'], 3, Utilities.ZAXIS)
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
		
		if (fwd or back):
			self.Trail.onSnailMoved(self.owner['SpeedMultiplier'])
	
	def OnButton1(self, positive, triggered):
		if positive and triggered:
			if Utilities.hasState(self.owner, S_INSHELL):
				self.exitShell(animate = True)
			elif Utilities.hasState(self.owner, S_HASSHELL):
				self.enterShell(animate = True)
			elif Utilities.hasState(self.owner, S_NOSHELL):
				if self.NearestShell:
					self.setShell(self.NearestShell, animate = True)
	
	def OnButton2(self, positive, triggered):
		if positive and triggered:
			if Utilities.hasState(self.owner, S_HASSHELL):
				self.dropShell(animate = True)
	
	def useLocalCoordinates(self):
		# As the snail exits a shell, it might be upside down, which would
		# cause the camera to think it is in a very small tunnel.
		return not Utilities.hasState(self.owner, S_INSHELL)
	
	def getCloseCamera(self):
		return self.camera

class ArcRay:
	'''Like a Ray sensor, but the detection is done along an arc. The arc
	rotates around the y-axis, starting from the positive z-axis and sweeping
	around to the positive x-axis.'''
	
	RADIUS = 2.0
	ANGLE = 180.0
	RESOLUTION = 6
	PROP = 'Ground'
	
	def __init__(self, owner):
		self.owner = owner
		self._createPoints()
		self.lastHitPoint = Utilities.ORIGIN.copy()
		self.lastHitNorm = Utilities.ZAXIS.copy()
		self.prop = ArcRay.PROP
		if hasattr(owner, 'prop'):
			self.prop = owner['prop']
		
		if DEBUG:
			self.marker = Utilities.addObject('PointMarker', 0)
	
	def _createPoints(self):
		'''Generate an arc of line segments to cast rays along.'''
		self.path = []
		
		endAngle = ArcRay.ANGLE
		if hasattr(self.owner, 'angle'):
			endAngle = self.owner['angle']
		revolutions = endAngle / 360.0
		endAngle = math.radians(endAngle)
		
		res = ArcRay.RESOLUTION
		if hasattr(self.owner, 'resolution'):
			res = self.owner['resolution']
		numSegments = int(math.ceil(revolutions * res))
		
		increment = endAngle / numSegments
		
		radius = ArcRay.RADIUS
		if hasattr(self.owner, 'radius'):
			radius = self.owner['radius']
		
		for i in range(numSegments + 1):
			angle = increment * i
			point = mathutils.Vector()
			point.x = math.sin(angle) * radius
			point.z = math.cos(angle) * radius
			self.path.append(point)

	def getHitPosition(self):
		"""Return the hit point of the first child ray that hits.
		If none hit, the default value of the first ray is returned."""
		ob = None
		norm = None
		for A, B in zip(self.path, self.path[1:]):
			A = Utilities._toWorld(self.owner, A)
			B = Utilities._toWorld(self.owner, B)
			ob, p, norm = Utilities._rayCastP2P(B, A, prop = self.prop)
			if ob:
				self.lastHitPoint = Utilities._toLocal(self.owner, p)
				self.lastHitNorm = Utilities._toLocalVec(self.owner, norm)
				break
		
		wp = Utilities._toWorld(self.owner, self.lastHitPoint)
		wn = Utilities._toWorldVec(self.owner, self.lastHitNorm)
		if DEBUG:
			self.marker.worldPosition = wp
			
		return ob, wp, wn

class SnailTrail:
	S_NORMAL = 2
	S_SLOW = 3
	S_FAST = 4
	
	def __init__(self, owner, snail):
		self.LastMinorPos = owner.worldPosition.copy()
		self.LastMajorPos = self.LastMinorPos.copy()
		self.Paused = False
		self.TrailSpots = []
		self.SpotIndex = 0
		self.Snail = snail
		self.owner = owner
		Utilities.parseChildren(self, owner)
	
	def parseChild(self, child, type):
		if (type == "TrailSpot"):
			self.TrailSpots.append(child)
			child.removeParent()
			return True
	
	def addSpot(self, speedStyle):
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
		spotI = scene.addObject(spot, self.owner)
		
		#
		# Attach the spot to the object that the snail is crawling on.
		#
		if self.Snail.getTouchedObject() != None:
			spotI.setParent(self.Snail.getTouchedObject())
		
		Utilities.setState(spotI, speedStyle)
	
	def onSnailMoved(self, speedMultiplier):
		pos = self.owner.worldPosition
		
		distMajor = (pos - self.LastMajorPos).magnitude
		if distMajor > self.Snail.owner['TrailSpacingMajor']:
			self.LastMajorPos = pos.copy()
			self.Paused = not self.Paused
		
		if self.Paused:
			return
		
		distMinor = (pos - self.LastMinorPos).magnitude
		if distMinor > self.Snail.owner['TrailSpacingMinor']:
			self.LastMinorPos = pos.copy()
			speedStyle = SnailTrail.S_NORMAL
			if speedMultiplier > (1.0 + Utilities.EPSILON):
				speedStyle = SnailTrail.S_FAST
			elif speedMultiplier < (1.0 - Utilities.EPSILON):
				speedStyle = SnailTrail.S_SLOW
			self.addSpot(speedStyle)

#
# Module interface functions.
#

def init(cont):
	cargoHold = cont.sensors['sCargoHoldHook'].owner
	eyeRayL = cont.sensors['sEyeRayHook_L'].owner
	eyeRayR = cont.sensors['sEyeRayHook_R'].owner
	eyeLocL = cont.sensors['sEyeLocHookL'].owner
	eyeLocR = cont.sensors['sEyeLocHookR'].owner
	camera = cont.sensors['sCameraHook'].owner
	snail = Snail(cont.owner, cargoHold, eyeRayL, eyeRayR, eyeLocL, eyeLocR, camera)
	cont.owner['Snail'] = snail

def update(c):
	snail = c.owner['Snail']
	snail.orient()
	snail.updateEyeLength()

def look(c):
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
