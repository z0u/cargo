#
# Copyright 2009-2010 Alex Fraser <alex@phatcore.com>
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
import bge
from bge import render
from bge import logic

import bxt

from . import director
from . import inventory
from Scripts import store, shells, camera, impulse

DEBUG = False

class Snail(impulse.Handler, director.VulnerableActor, bge.types.KX_GameObject):
	_prefix = ''

	# Snail states
	S_INIT     = 1
	S_CRAWLING = 2
	S_FALLING  = 3
	S_ACTIVE   = 4
	S_SHOCKED  = 5
	S_NOSHELL  = 16
	S_HASSHELL = 17
	S_INSHELL  = 18
	S_SHOCKWAVE = 20

	# Armature states
	S_ARM_CRAWL      = 1
	S_ARM_LOCOMOTION = 2
	S_ARM_POP        = 16
	S_ARM_ENTER      = 17
	S_ARM_EXIT       = 18
	# Armature animation layers
	L_ARM_IDLE		= 1 # Idle animations, like wriggling
	L_ARM_LOCO		= 2 # Locomation (walk cycle)
	L_ARM_SHELL		= 3 # Shell actions, like pop, enter, exit

	# Shockwave animation layers
	L_SW_GROW		= 0

	MAX_SPEED = 3.0
	MIN_SPEED = -3.0
	CAMERA_SAFE_DIST = 10.0
	SHELL_SCALE_FAC = 0.5
	EYE_LOOK_FAC = 0.5
	SHELL_POP_SPEED = 40.0
	WATER_DAMPING = 0.5

	shell = bxt.types.weakprop('shell')

	def __init__(self, old_owner):
		director.VulnerableActor.__init__(self, maxHealth=7)

		# Initialise state.
		self.rem_state(Snail.S_CRAWLING)
		self.add_state(Snail.S_FALLING)
		self.add_state(Snail.S_NOSHELL)
		self.rem_state(Snail.S_HASSHELL)
		self.rem_state(Snail.S_INSHELL)
		self.add_state(Snail.S_ACTIVE)
		self.rem_state(Snail.S_INIT)

		self.shell = None
		self.recentlyDroppedItems = bxt.types.SafeSet()
		# Not weak props, but it should be OK because they will die in the same
		# frame as the snail (this object).
		self.eyeRayL = self.childrenRecursive['EyeRay.L']
		self.eyeRayR = self.childrenRecursive['EyeRay.R']
		self.eyeLocL = self.childrenRecursive['EyeLoc.L']
		self.eyeLocR = self.childrenRecursive['EyeLoc.R']
		self.armature = self.children['SnailArmature']
		self.cargoHold = self.childrenRecursive['CargoHold']
		self.shockwave = self.childrenRecursive['Shockwave']
		self.cameraTrack = self.childrenRecursive['Head.2']
		self.focal_points = [self.eyeLocL, self.eyeLocR, self]

		# For path camera
		self.localCoordinates = True

		self.frameCounter = 0

		self.load_items()

		self['Oxygen'] = 1.0
		self.on_oxygen_set()

		bxt.types.EventBus().add_listener(self)
		bxt.types.EventBus().replay_last(self, 'GravityChanged')

		bxt.types.WeakEvent('MainCharacterSet', self).send()
		bxt.types.Event('SetCameraType', 'OrbitCamera').send()
		alignment = camera.OrbitCameraAlignment()
		bxt.types.Event('SetCameraAlignment', alignment).send()
		camera.AutoCamera().add_focus_point(self)

		self.DEBUGpositions = [self.worldPosition.copy()]
		impulse.Input().add_handler(self)
		impulse.Input().add_sequence("udlr12", bxt.types.Event("GiveAllShells"))
		bxt.types.EventBus().replay_last(self, 'TeleportSnail')

	def load_items(self):
		shellName = inventory.Shells().get_equipped()
		if shellName != None:
			shell = shells.factory(shellName)
			self.equip_shell(shell, False)

	@bxt.types.expose
	@bxt.utils.controller_cls
	def debug_collisions(self, c):
		if not DEBUG:
			return
		print(c.sensors[0].hitObjectList)

	@bxt.types.expose
	def update(self):
		self.orient()
		self.update_eye_length()
		self.size_shell()

	def orient(self):
		'''Adjust the orientation of the snail to match the nearest surface.'''
		counter = bxt.types.Counter()
		avNormal = bxt.bmath.ZEROVEC.copy()
		ob0, p0, n0 = self.children['ArcRay_Root.0'].getHitPosition()
		if ob0:
			avNormal += n0
			counter.add(ob0)
		ob1, p1, n1 = self.children['ArcRay_Root.1'].getHitPosition()
		if ob1:
			avNormal += n1
			counter.add(ob1)
		ob2, p2, n2 = self.children['ArcRay_Root.2'].getHitPosition()
		if ob2:
			avNormal += n2
			counter.add(ob2)
		ob3, p3, n3 = self.children['ArcRay_Root.3'].getHitPosition()
		if ob3:
			avNormal += n3
			counter.add(ob3)

		#
		# Inherit the angular velocity of a nearby surface. The object that was
		# hit by the most rays (above) is used.
		# TODO: The linear velocity should probably be set, too: fast-moving
		# objects can be problematic.
		#
		self.touchedObject = counter.mode
		if self.touchedObject != None:
			angV = self.touchedObject.getAngularVelocity()
			if angV.magnitude < bxt.bmath.EPSILON:
				angV = bxt.bmath.MINVECTOR
			self.setAngularVelocity(angV)

		#
		# Set property on object so it knows whether it's falling. This is used
		# to detect when to transition from S_FALLING to S_CRAWLING.
		#
		self['nHit'] = counter.n

		if counter.n > 0:
			avNormal /= counter.n

		if counter.n == 1:
			# Only one ray hit; use it to try to snap to a sane orientation.
			# Subsequent frames should then have more rays hit.
			self.alignAxisToVect(avNormal, 2)
		elif counter.n > 1:
			#
			# Derive normal from hit points and update orientation. This gives a
			# smoother transition than just averaging the normals returned by the
			# rays. Rays that didn't hit will use their last known value.
			#
			normal = bxt.bmath.quadNormal(p0, p1, p2, p3)
			if normal.dot(avNormal) < 0.0:
				normal.negate()
			self.alignAxisToVect(normal, 2)

		self.orient_segment(self.children['Head.0'])
		self.orient_segment(self.children['Tail.0'])
		self.armature.update()

		self.frameCounter += 1

	def orient_segment(self, parentSegment):
		name = parentSegment.name[:-2]
		i = int(parentSegment.name[-1:]) + 1

		pivotName = 'ChildPivot_%s.%d' % (name, i)
		if not pivotName in parentSegment.children:
			return

		pivot = parentSegment.children[pivotName]
		rayL = pivot.children['ArcRay_%s.%d.L' % (name, i)]
		rayR = pivot.children['ArcRay_%s.%d.R' % (name, i)]
		fulcrum = pivot.children['Fulcrum_%s.%d' % (name, i)]
		segment = pivot.children['%s.%d' % (name, i)]

		segment.alignAxisToVect(pivot.getAxisVect(bxt.bmath.XAXIS), 0)

		_, p1, _ = rayR.getHitPosition()
		_, p2, _ = rayL.getHitPosition()
		p3 = fulcrum.worldPosition
		normal = bxt.bmath.triangleNormal(p1, p2, p3)

		if normal.dot(pivot.getAxisVect(bxt.bmath.ZAXIS)) > 0.0:
			#
			# Normal is within 90 degrees of parent's normal -> segment not
			# doubling back on itself.
			#
			# Interpolate between normals for current and previous frames.
			# Don't use a factor of 0.5: potential for normal to average out
			# to be (0,0,0)
			#
			segment.alignAxisToVect(normal, 2, 0.4)

		#
		# Make orientation available to armature. Use the inverse of the
		# parent's orientation to find the local orientation.
		#
		parentInverse = parentSegment.worldOrientation.copy()
		parentInverse.invert()
		localOrnMat = parentInverse * segment.worldOrientation
		channel = self.armature.channels[segment['Channel']]
		channel.rotation_quaternion = localOrnMat.to_quaternion()

		# Recurse
		if len(segment.children) > 0:
			self.orient_segment(segment)

	def on_event(self, evt):
		if evt.message == 'ForceExitShell':
			self.exit_shell(evt.body)
		elif evt.message == 'ForceEnterShell':
			self.enter_shell(evt.body)
		elif evt.message == 'ForceDropShell':
			self.drop_shell(evt.body)
		elif evt.message == 'ForceReclaimShell':
			self.reclaim_shell()
		elif evt.message == 'GravityChanged':
			antiG = evt.body.copy()
			antiG.negate()
			# Anti-gravity is applied in world coordinates.
			self.actuators['aAntiGravity'].force = antiG
			# Artificial gravity is applied in local coordinates.
			self.actuators['aArtificialGravity'].force = evt.body
		elif evt.message == 'TeleportSnail':
			self.teleport(evt.body)
		elif evt.message == 'GiveAllShells':
			# Cheat ;)
			for name in inventory.Shells().get_all_shells():
				inventory.Shells().add(name)
				bxt.types.Event('ShellChanged', 'new').send()

	def teleport(self, spawn_point):
		print("Teleporting to %s." % spawn_point)
		self.exit_shell(False)
		if isinstance(spawn_point, str):
			try:
				spawn_point = self.scene.objects[spawn_point]
			except KeyError:
				print("Warning: can't find spawn point %s" % spawn_point)
				return
		bxt.bmath.copy_transform(spawn_point, self)
		self.save_location()
		self['BendAngleFore'] = 0.0
		self['BendAngleAft'] = 0.0

	def update_eye_length(self):
		def update_single(eyeRayOb):
			restLength = self['EyeRestLen']
			channel = self.armature.channels[eyeRayOb['channel']]

			vect = eyeRayOb.getAxisVect(bxt.bmath.ZAXIS) * restLength
			through = eyeRayOb.worldPosition + vect
			hitOb, hitPos, _ = bxt.bmath.ray_cast_p2p(through, eyeRayOb,
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
				targetProportion = bxt.bmath.lerp(currentProportion,
						targetProportion, self['EyeLenFac'])

			channel.scale = (1.0, targetProportion, 1.0)
		update_single(self.eyeRayL)
		update_single(self.eyeRayR)

	@bxt.types.expose
	@bxt.utils.controller_cls
	def look(self, c):
		'''
		Turn the eyes to face the nearest object in targetList. Objects with a
		higher priority will always be preferred. In practice, the targetList
		is provided by a Near sensor, so it won't include every object in the
		scene. Objects with a LookAt priority of less than zero will be ignored.
		'''

		def reset_orn(eye):
			channel = self.armature.channels[eye['channel']]
			orn = mathutils.Quaternion()
			orn.identity()
			oldOrn = mathutils.Quaternion(channel.rotation_quaternion)
			channel.rotation_quaternion = oldOrn.slerp(orn, Snail.EYE_LOOK_FAC)

		def look_single(eye, direction):
			channel = self.armature.channels[eye['channel']]
			eye.alignAxisToVect(eye.parent.getAxisVect(bxt.bmath.ZAXIS), 2)
			eye.alignAxisToVect(direction, 1)
			orn = eye.localOrientation.to_quaternion()
			oldOrn = mathutils.Quaternion(channel.rotation_quaternion)
			channel.rotation_quaternion = oldOrn.slerp(orn, Snail.EYE_LOOK_FAC)

		def get_direction(eye, target):
			_, gVec, _ = eye.getVectTo(target)
			return gVec

		def can_look(eye, direction):
			'''Don't allow looking behind; the eyes twist!'''
			dot = direction.dot(eye.parent.getAxisVect(bxt.bmath.YAXIS))
			return dot > -0.4

		targetList = c.sensors['sLookAt'].hitObjectList

		nearest = None
		minDist = None
		maxPriority = 0

		for target in targetList:
			if target['LookAt'] < maxPriority:
				continue
			dist = self.getDistanceTo(target)
			if nearest == None or dist < minDist:
				nearest = target
				minDist = dist
				maxPriority = target['LookAt']

		if not nearest:
			reset_orn(self.eyeLocL)
			reset_orn(self.eyeLocR)
			return

		dir_L = get_direction(self.eyeLocL, nearest)
		dir_R = get_direction(self.eyeLocR, nearest)
		if (can_look(self.eyeLocL, dir_L) and can_look(self.eyeLocR, dir_R)):
			look_single(self.eyeLocL, dir_L)
			look_single(self.eyeLocR, dir_R)
		else:
			reset_orn(self.eyeLocL)
			reset_orn(self.eyeLocR)

	def get_look_target(self):
		return self.childrenRecursive["SnailLookTarget"]

	def size_shell(self):
		'''Set the size of the carried shell based on the distance to the
		camera. This prevents the shell from filling the screen when in tight
		spaces.'''
		if not self.has_state(Snail.S_HASSHELL):
			return

		offset = camera.AutoCamera().camera.worldPosition - self.worldPosition
		dist = offset.magnitude
		targetScale = dist / Snail.CAMERA_SAFE_DIST
		if targetScale < 0:
			targetScale = 0
		if targetScale > 1:
			targetScale = 1
		scale = self.cargoHold.localScale.x
		scale = bxt.bmath.lerp(scale, targetScale, Snail.SHELL_SCALE_FAC)
		self.cargoHold.localScale = (scale, scale, scale)

	def _stow_shell(self, shell):
		# Similar to Bird.pick_up
		shell.localScale = (1.0, 1.0, 1.0)
		self.cargoHold.localScale = (1.0, 1.0, 1.0)
		referential = shell.cargoHook
		bxt.bmath.set_rel_orn(shell, self.cargoHold, referential)
		bxt.bmath.set_rel_pos(shell, self.cargoHold, referential)
		shell.setParent(self.cargoHold)

	@bxt.types.expose
	@bxt.utils.controller_cls
	def pick_up_item(self, controller):
		'''Picks up and equips nearby shells that don't already have an
		owner. Note: this must run with priority over functions that drop
		items!'''
		collectables = bxt.types.SafeSet(
				controller.sensors['sPickup'].hitObjectList)
		# Forget objects that are no longer in range.
		self.recentlyDroppedItems.intersection_update(collectables)
		# Ignore objects that were recently dropped.
		collectables.difference_update(self.recentlyDroppedItems)

		for ob in collectables:
			if isinstance(ob, shells.ShellBase):
				if not ob.is_carried() and not ob.is_grasped():
					self.equip_shell(ob, True)
					bxt.types.Event('ShellChanged', 'new').send()

	def switch_next(self):
		'''Equip the next-higher shell that the snail has.'''
		shellName = inventory.Shells().get_next(1)
		if shellName == None:
			return
		if self.shell and shellName == self.shell.name:
			return

		self._switch(shellName)
		bxt.types.Event('ShellChanged', 'next').send()

	def switch_previous(self):
		'''Equip the next-lower shell that the snail has.'''
		shellName = inventory.Shells().get_next(-1)
		if shellName == None:
			return
		if self.shell and shellName == self.shell.name:
			return

		self._switch(shellName)
		bxt.types.Event('ShellChanged', 'previous').send()

	def _switch(self, name):
		if name == None:
			return

		if self.shell and self.shell.name != name:
			oldShell = self.unequip_shell()
			oldShell.endObject()

		scene = bge.logic.getCurrentScene()
		if name in scene.objects:
			shell = scene.objects[name]
		else:
			shell = bxt.types.add_and_mutate_object(scene, name, self)
		self.equip_shell(shell, True)

	def equip_shell(self, shell, animate):
		'''
		Add the shell as a descendant of the snail. It will be
		made a child of the CargoHold. If the shell has a child
		of type "CargoHook", that will be used as the
		referential (offset). Otherwise, the shell will be
		positioned with its own origin at the same location as
		the CargoHold.

		Adding the shell as a child prevents collision with the
		parent. The shell's inactive state will also be set.

		If the snail already has a shell equipped, that shell will be unequipped
		and destroyed; but it will be kept in the snail's inventory.
		'''
		if self.shell:
			shell = self.unequip_shell()
			shell.endObject()

		self.rem_state(Snail.S_NOSHELL)
		self.add_state(Snail.S_HASSHELL)

		self._stow_shell(shell)

		self.shell = shell
		self['HasShell'] = 1
		self['DynamicMass'] = self['DynamicMass'] + shell['DynamicMass']
		self.shell.on_picked_up(self, animate)
		inventory.Shells().equip(shell.name)

		if animate:
			self.show_shockwave()

	def reclaim_shell(self):
		'''Reclaim a dropped shell.'''
		if not self.has_state(Snail.S_NOSHELL):
			return

		shellName = inventory.Shells.get_equipped(self)
		if shellName is not None:
			self._switch(shellName)

	def show_shockwave(self):
		self.shockwave.worldPosition = self.shell.worldPosition
		self.shockwave.worldOrientation = self.shell.worldOrientation
		self.shockwave.visible = True
		self.shockwave.playAction('ShockwaveGrow', 1, 20, layer=Snail.L_SW_GROW)
		self.add_state(Snail.S_SHOCKWAVE)

	@bxt.types.expose
	def poll_shockwave(self):
		if not self.shockwave.isPlayingAction(Snail.L_SW_GROW):
			self.rem_state(Snail.S_SHOCKWAVE)
			self.shockwave.visible = False

	def unequip_shell(self):
		self.rem_state(Snail.S_HASSHELL)
		self.add_state(Snail.S_NOSHELL)
		shell = self.shell
		shell.removeParent()
		self.shell = None
		self['HasShell'] = 0
		self['DynamicMass'] -= shell['DynamicMass']
		return shell

	def play_shell_action(self, actionName, endFrame, callback, animate=True,
				triggerFrame=None):
		'''Play a modal shell action. 'callback' will be executed either when
		the action finishes playing, or 'triggerFrame' is reached.'''

		self.armature.playAction(actionName, 1, endFrame, layer=Snail.L_ARM_SHELL)
		if not animate:
			self.armature.setActionFrame(endFrame, Snail.L_ARM_SHELL)

		if triggerFrame != None:
			bxt.anim.add_trigger_gte(self.armature, Snail.L_ARM_SHELL, triggerFrame, callback)
		else:
			bxt.anim.add_trigger_end(self.armature, Snail.L_ARM_SHELL, callback)

	def drop_shell(self, animate):
		'''Causes the snail to drop its shell, if it is carrying one.'''
		if not self.has_state(Snail.S_HASSHELL):
			return

		self.rem_state(Snail.S_HASSHELL)
		self.play_shell_action("PopShell", 18, self.on_drop_shell, animate, 15)
		bxt.sound.play_sample('//Sound/cc-by/BottleOpen.ogg')

	def on_drop_shell(self):
		'''Unhooks the current shell by un-setting its parent.'''
		velocity = bxt.bmath.ZAXIS.copy()
		velocity.x += 0.5 - bge.logic.getRandomFloat()
		velocity = self.getAxisVect(velocity)
		velocity *= Snail.SHELL_POP_SPEED
		shell = self.unequip_shell()

		shell.setLinearVelocity(velocity)
		shell.on_dropped()
		self.recentlyDroppedItems.add(shell)

		bxt.types.WeakEvent('ShellDropped', self).send()

	def enter_shell(self, animate):
		'''
		Starts the snail entering the shell. Shell.on_pre_enter will be called
		immediately; Snail.on_enter_shell and Shell.on_entered will be called
		later, at the appropriate point in the animation.
		'''
		if not self.has_state(Snail.S_HASSHELL):
			return

		self.rem_state(Snail.S_HASSHELL)
		bxt.utils.rem_state(self.armature, Snail.S_ARM_CRAWL)
		bxt.utils.rem_state(self.armature, Snail.S_ARM_LOCOMOTION)
		self.play_shell_action("Inshell", 18, self.on_enter_shell, animate)

		self.shell.on_pre_enter()

	def on_enter_shell(self):
		'''Transfers control of the character to the shell. The snail must have
		a shell.'''
		self.rem_state(Snail.S_CRAWLING)
		self.add_state(Snail.S_INSHELL)

		linV = self.getLinearVelocity()
		angV = self.getAngularVelocity()

		self.shell.removeParent()
		# Make sure the shell is the right size.
		self.shell.localScale = (1.0, 1.0, 1.0)
		self.armature.setVisible(False, True)
		self.localScale = (0.01, 0.01, 0.01)
		self.setParent(self.shell)

		self.shell.setLinearVelocity(linV)
		self.shell.setAngularVelocity(angV)

		#
		# Swap mass with shell so the shell can influence bendy leaves properly
		#
		dm = self.shell['DynamicMass']
		self.shell['DynamicMass'] = self['DynamicMass']
		self['DynamicMass'] = dm


		self['InShell'] = 1
		self.shell.on_entered()

		bxt.types.WeakEvent('ShellEntered', self).send()

	def exit_shell(self, animate):
		'''
		Tries to make the snail exit the shell. If possible, control will be
		transferred to the snail. The snail must currently be in a shell.
		'''
		if not self.has_state(Snail.S_INSHELL):
			return

		self.rem_state(Snail.S_INSHELL)
		self.add_state(Snail.S_FALLING)
		bxt.utils.add_state(self.armature, Snail.S_ARM_CRAWL)
		bxt.utils.add_state(self.armature, Snail.S_ARM_LOCOMOTION)
		self.play_shell_action("Outshell", 18, self.on_exit_shell, animate)

		linV = self.shell.getLinearVelocity()
		angV = self.shell.getAngularVelocity()

		self.removeParent()
		self.localScale = (1.0, 1.0, 1.0)
		if self.shell['ExitCentre']:
			self.worldPosition = self.shell.worldPosition
		self.armature.setVisible(True, True)
		self._stow_shell(self.shell)

		self.setLinearVelocity(linV)
		self.setAngularVelocity(angV)

		#
		# Swap mass with shell so the body can influence bendy leaves properly
		#
		dm = self.shell['DynamicMass']
		self.shell['DynamicMass'] = self['DynamicMass']
		self['DynamicMass'] = dm

		self['InShell'] = 0
		self.shell.on_exited()

		bxt.types.WeakEvent('MainCharacterSet', self).send()
		# Temporarily use a path camera while exiting the shell - it's smoother!
		bxt.types.Event('SetCameraType', 'PathCamera').send()
		bxt.types.Event('OxygenSet', self['Oxygen']).send()

	def on_exit_shell(self):
		'''Called when the snail has finished its exit shell
		animation (several frames after control has been
		transferred).'''

		self.add_state(Snail.S_HASSHELL)
		self.shell.on_post_exit()

		# Switch to orbit camera.
		bxt.types.Event('SetCameraType', 'OrbitCamera').send()
		alignment = camera.OrbitCameraAlignment()
		bxt.types.Event('SetCameraAlignment', alignment).send()

		bxt.types.WeakEvent('ShellExited', self).send()

	def record_velocity(self):
		# TODO: Remove this debugging code.
		super(Snail, self).record_velocity()
		self.DEBUGpositions.append(self.worldPosition.copy())
		if len(self.DEBUGpositions) > 20:
			self.DEBUGpositions.pop(0)

	def respawn(self, reason):
		if self.has_state(Snail.S_INSHELL):
			self.exit_shell(False)
		super(Snail, self).respawn(reason)

		print("Snail respawning. Previous positions were:")
		for pos in self.DEBUGpositions:
			print(pos)

	def set_health(self, value):
		super(Snail, self).set_health(value)
		evt = bxt.types.Event('HealthSet', value / self.maxHealth)
		bxt.types.EventBus().notify(evt)

	def shock(self):
		self.enter_shell(animate=True)

	def on_oxygen_set(self):
		if not self.has_state(Snail.S_INSHELL):
			bxt.types.Event('OxygenSet', self['Oxygen']).send()

	@bxt.types.expose
	@bxt.utils.controller_cls
	def power_up(self, c):
		for powerUp in c.sensors[0].hitObjectList:
			if powerUp['SpeedMultiplier']:
				self['SpeedMultiplier'] = powerUp['SpeedMultiplier']

			if powerUp['SingleUse']:
				powerUp.endObject()

	def on_float(self, water):
		# Assume water gives speed up unless otherwise specified (e.g. honey
		# slows you down).
		speed = 2.0
		if 'SpeedMultiplier' in water:
			speed = water['SpeedMultiplier']

		if speed > 1.0 and self['SpeedMultiplier'] < speed:
			self['SpeedMultiplier'] = speed
		elif speed < 1.0 and self['SpeedMultiplier'] > speed:
			self['SpeedMultiplier'] = speed

	@bxt.types.expose
	def start_crawling(self):
		'''Called when the snail enters its crawling state.'''
		#
		# Don't set it quite to zero: zero vectors are ignored!
		#
		self.setAngularVelocity(bxt.bmath.MINVECTOR, False)
		self.setLinearVelocity(bxt.bmath.MINVECTOR, False)

	def on_movement_impulse(self, f, b, l, r):
		return

	def handle_movement(self, state):
		'''
		Make the snail move. If moving forward or backward, this implicitly
		calls decaySpeed.
		'''
		if not self.has_state(Snail.S_CRAWLING):
			return True

		direction = state.direction
		#
		# Apply forward/backward motion.
		#
		speed = self['NormalSpeed'] * self['SpeedMultiplier'] * direction.y
		if 'SubmergedFactor' in self:
			# Don't go so fast when under water!
			speed *= 1.0 - Snail.WATER_DAMPING * self['SubmergedFactor']
		self.applyMovement((0.0, speed, 0.0), True)
		self.decay_speed()

		#
		# Decide which way to turn.
		#
		targetBendAngleAft = None
		targetBendAngleFore = self['MaxBendAngle'] * direction.x
		targetRot = self['MaxRot'] * -direction.x

		locomotionStep = self['SpeedMultiplier'] * 0.4
		if direction.y > 0.1:
			#
			# Moving forward.
			#
			targetBendAngleAft = targetBendAngleFore
			self.armature['LocomotionFrame'] = (
				self.armature['LocomotionFrame'] + locomotionStep)
		elif direction.y < -0.1:
			#
			# Reversing: invert rotation direction.
			#
			targetBendAngleAft = targetBendAngleFore
			targetRot = 0.0 - targetRot
			self.armature['LocomotionFrame'] = (
				self.armature['LocomotionFrame'] - locomotionStep)
		else:
			#
			# Stationary. Only bend the head.
			#
			targetBendAngleAft = 0.0
			targetRot = 0.0

		self.armature['LocomotionFrame'] = (
			self.armature['LocomotionFrame'] % 19)

		#
		# Rotate the snail.
		#
		self['Rot'] = bxt.bmath.lerp(self['Rot'], targetRot, self['RotFactor'])
		oRot = mathutils.Matrix.Rotation(self['Rot'], 3, bxt.bmath.ZAXIS)
		self.localOrientation = self.localOrientation * oRot

		#
		# Match the bend angle with the current speed.
		#
		if self['SpeedMultiplier'] > 1.0:
			targetBendAngleAft /= self['SpeedMultiplier']

		# These actually get applied in update.
		self['BendAngleFore'] = bxt.bmath.lerp(self['BendAngleFore'],
				targetBendAngleFore, self['BendFactor'])

		if abs(direction.y) > 0.1:
			self['BendAngleAft'] = bxt.bmath.lerp(self['BendAngleAft'],
					targetBendAngleAft, self['BendFactor'])

			# Moving forward or backward, so update trail.
			if self.touchedObject is not None:
				self.children['Trail'].moved(self['SpeedMultiplier'],
					self.touchedObject)

		return True

	def decay_speed(self):
		'''Bring the speed of the snail one step closer to normal speed.'''
		dr = self['SpeedDecayRate']
		mult = self['SpeedMultiplier']

		# Make noise when going fast.
		self.armature['Squeaking'] = mult > 1.0

		if mult == 1.0:
			return
		elif mult > 1.0:
			self['SpeedMultiplier'] = max(mult - dr, 1.0)
		else:
			self['SpeedMultiplier'] = min(mult + dr, 1.0)

	def handle_bt_1(self, state):
		'''
		Primary action: enter shell, or reclaim it if it is not being carried.
		Note: No special logic is required to NOT enter the shell; if it's not
		currently allowed (e.g. during dialogue), another input handler will be
		registered above this one.
		'''
		if state.activated:
			if self.has_state(Snail.S_INSHELL):
				self.exit_shell(animate = True)
			elif self.has_state(Snail.S_HASSHELL):
				self.enter_shell(animate = True)
			elif self.has_state(Snail.S_NOSHELL):
				self.reclaim_shell()
		return True

	def handle_bt_2(self, state):
		shells = inventory.Shells().get_shells()
		if len(shells) == 1 and shells[0] == "Shell":
			# Can't drop shell until a special point in the game.
			return True

		if state.activated:
			if self.has_state(Snail.S_HASSHELL):
				self.drop_shell(animate = True)
			elif self.has_state(Snail.S_NOSHELL):
				self.reclaim_shell()
		return True

	def handle_switch(self, state):
		'''Switch to next or previous shell.'''
		if state.triggered and (self.has_state(Snail.S_HASSHELL) or
				self.has_state(Snail.S_NOSHELL)):
			if state.direction > 0.1:
				self.switch_next()
			elif state.direction < -0.1:
				self.switch_previous()
		return True

	def handle_bt_camera(self, state):
		'''Move camera to be directly behind the snail.'''
		if state.activated:
			bxt.types.Event('ResetCameraPos', None).send()
		return True

	def get_camera_tracking_point(self):
		return self.cameraTrack

	def get_focal_points(self):
		return self.focal_points[:]

class Trail(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	S_NORMAL = 2
	S_SLOW = 3
	S_FAST = 4

	NUM_SPOTS = 16

	def __init__(self, old_owner):
		self.lastMinorPos = self.worldPosition.copy()
		self.lastMajorPos = self.lastMinorPos.copy()
		self.paused = False
		self.spotIndex = 0
		self.warned = False

	def add_spot(self, speedStyle, touchedObject):
		'''
		Add a spot where the snail is now. Actually, this only adds a spot half
		the time: gaps will be left in the trail, like so:
		    -----     -----     -----     -----     -----

		@param speedStyle: The style to apply to the new spot. One of [S_SLOW,
			S_NORMAL, S_FAST].
		'''
		self.spotIndex = (self.spotIndex + 1) % Trail.NUM_SPOTS

		spot_name = "Trail.{:03d}".format(self.spotIndex + 1)
		try:
			spot = self.scene.addObject(spot_name, self)
		except:
			if not self.warned:
				print("Couldn't find trail '%s' in scene '%s'" %
						(spot_name, self.scene))
			self.warned = True
			return

		#
		# Attach the spot to the object that the snail is crawling on.
		#
		if touchedObject != None:
			spot.setParent(touchedObject)

		bxt.utils.set_state(spot, speedStyle)

	def moved(self, speedMultiplier, touchedObject):
		pos = self.worldPosition

		distMajor = (pos - self.lastMajorPos).magnitude
		if distMajor > self['TrailSpacingMajor']:
			self.lastMajorPos = pos.copy()
			self.paused = not self.paused

		if self.paused:
			return

		distMinor = (pos - self.lastMinorPos).magnitude
		if distMinor > self['TrailSpacingMinor']:
			self.lastMinorPos = pos.copy()
			speedStyle = Trail.S_NORMAL
			if speedMultiplier > (1.0 + bxt.bmath.EPSILON):
				speedStyle = Trail.S_FAST
			elif speedMultiplier < (1.0 - bxt.bmath.EPSILON):
				speedStyle = Trail.S_SLOW
			self.add_spot(speedStyle, touchedObject)


class MinSnail(bxt.types.BX_GameObject, bge.types.BL_ArmatureObject):

	_prefix = 'MS_'

	LOOK_FAC = 0.2

	look_goal = bxt.types.weakprop('look_goal')

	def __init__(self, old_owner):
		con = self.constraints["LookTarget:Copy Location"]
		con.enforce = 1.0
		self.look_at(None)

	@bxt.types.expose
	def update_look(self):
		# Stop tracking goal if it is behind the head.
		con = self.constraints["LookTarget:Copy Location"]
		head = self.children["SlugLookTarget"]
		_, _, local_vec = head.getVectTo(self.look_goal)

		if local_vec.y > 0.0:
			con.active = True
			con.enforce = min(con.enforce + MinSnail.LOOK_FAC, 1.0)
			if con.target is not None:
				con.target.worldPosition = bxt.bmath.lerp(
					con.target.worldPosition, self.look_goal.worldPosition,
					MinSnail.LOOK_FAC)
		else:
			con.enforce = max(con.enforce - MinSnail.LOOK_FAC, 0.0)
			if con.enforce == 0.0:
				con.active = False

	def look_at(self, goal):
		'''Turn the eyes to face the goal.'''
		if isinstance(goal, str):
			goal = self.scene.objects[goal]

		if hasattr(goal, "get_look_target"):
			goal = goal.get_look_target()

		if goal is None:
			goal = self

		self.look_goal = goal
