#
# Copyright 2009-2012 Alex Fraser <alex@phatcore.com>
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

import logging

import mathutils
import bge

import bat.bats
import bat.containers
import bat.event
import bat.bmath
import bat.utils
import bat.anim
import bat.sound
import bat.effectors

import Scripts.director
import Scripts.inventory
import Scripts.shells
import Scripts.camera
import Scripts.attitude
import bat.impulse


class Snail(bat.impulse.Handler, Scripts.director.VulnerableActor, bge.types.KX_GameObject):
	_prefix = ''

	log = logging.getLogger(__name__ + ".Snail")

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

	HEALTH_WARNING_DELAY = 180 # 3s
	SHOCK_DURATION = 30 # 2s

	# For shrooms
	MAX_INTOXICATION = 140
	INTOXICATION_HIT = 60

	shell = bat.containers.weakprop('shell')

	def __init__(self, old_owner):
		Scripts.director.VulnerableActor.__init__(self, maxHealth=7)
		Snail.log.info("Creating Snail in %s", self.scene)

		# Initialise state.
		self.rem_state(Snail.S_CRAWLING)
		self.add_state(Snail.S_FALLING)
		self.add_state(Snail.S_NOSHELL)
		self.rem_state(Snail.S_HASSHELL)
		self.rem_state(Snail.S_INSHELL)
		self.add_state(Snail.S_ACTIVE)
		self.rem_state(Snail.S_INIT)

		self.shell = None
		self.recentlyDroppedItems = bat.containers.SafeSet()
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

		self.attitude = Scripts.attitude.SurfaceAttitude(self,
				bat.bats.mutate(self.children['ArcRay_Root.0']),
				bat.bats.mutate(self.children['ArcRay_Root.1']),
				bat.bats.mutate(self.children['ArcRay_Root.2']),
				bat.bats.mutate(self.children['ArcRay_Root.3']))

		# Movement fields
		self.bend_angle_fore = 0.0
		self.bend_angle_aft = 0.0
		self.direction_mapper = bat.impulse.DirectionMapperLocal()
		self.engine = Scripts.attitude.Engine(self)

		# For path camera
		self.localCoordinates = True

		self.load_items()

		self['Oxygen'] = 1.0
		self.on_oxygen_set()

		self.intoxication_level = 0
		self.health_warn_tics = 0
		self.shock_tics = 0

		bat.event.EventBus().add_listener(self)
		bat.event.EventBus().replay_last(self, 'GravityChanged')

		bat.event.WeakEvent('MainCharacterSet', self).send()
		bat.event.Event('SetCameraType', 'OrbitCamera').send()
		alignment = Scripts.camera.OrbitCameraAlignment()
		bat.event.Event('SetCameraAlignment', alignment).send()
		Scripts.camera.AutoCamera().add_focus_point(self)

		self.DEBUGpositions = [self.worldPosition.copy()]
		bat.impulse.Input().add_handler(self)
		bat.impulse.Input().add_sequence("udlr12", bat.event.Event("GiveAllShells"))
		bat.event.EventBus().replay_last(self, 'TeleportSnail')

		self.shell_change_sound = bat.sound.Sample(
			'//Sound/cc-by/Swosh1.ogg',
			'//Sound/cc-by/Swosh2.ogg')
		self.shell_change_sound.volume = 0.5
		self.shell_change_sound.add_effect(bat.sound.Localise(self))

	def load_items(self):
		shellName = Scripts.inventory.Shells().get_equipped()
		if shellName != None:
			shell = Scripts.shells.factory(shellName)
			self.equip_shell(shell, False)

	@bat.bats.expose
	def alive(self):
		'''Miscellaneous things to update while alive.'''
		self.health_warning()

	@bat.bats.expose
	def crawl(self):
		self.orient()
		self.update_eye_length()
		self.size_shell()
		if self.intoxication_level > 0:
			self.intoxication_level -= 1

	def orient(self):
		'''Adjust the orientation of the snail to match the nearest surface.'''
		# Use attitude object to apply root orientation.
		# Set property on object so it knows whether it's falling. This is used
		# to detect when to transition from S_FALLING to S_CRAWLING.
		self.touchedObject, self['nHit'] = self.attitude.apply()

		mat_rot = mathutils.Matrix.Rotation(self.bend_angle_fore, 3, 'Z')
		self.orient_segment(self.children['Head.0'], mat_rot)
		mat_rot = mathutils.Matrix.Rotation(self.bend_angle_aft, 3, 'Z')
		self.orient_segment(self.children['Tail.0'], mat_rot)
		self.armature.update()

	def orient_segment(self, parentSegment, mat_rot):
		name = parentSegment.name[:-2]
		i = int(parentSegment.name[-1:]) + 1

		pivotName = 'ChildPivot_%s.%d' % (name, i)
		if not pivotName in parentSegment.children:
			return

		pivot = parentSegment.children[pivotName]
		pivot.localOrientation = mat_rot
		rayL = pivot.children['ArcRay_%s.%d.L' % (name, i)]
		rayR = pivot.children['ArcRay_%s.%d.R' % (name, i)]
		fulcrum = pivot.children['Fulcrum_%s.%d' % (name, i)]
		segment = pivot.children['%s.%d' % (name, i)]

		segment.alignAxisToVect(pivot.getAxisVect(bat.bmath.XAXIS), 0)

		_, p1, _ = rayR.getHitPosition()
		_, p2, _ = rayL.getHitPosition()
		p3 = fulcrum.worldPosition
		normal = bat.bmath.triangleNormal(p1, p2, p3)

		if normal.dot(pivot.getAxisVect(bat.bmath.ZAXIS)) > 0.0:
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
			self.orient_segment(segment, mat_rot)

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
			for name in Scripts.inventory.Shells().get_all_shells():
				Scripts.inventory.Shells().add(name)
				bat.event.Event('ShellChanged', 'new').send()
		elif evt.message == 'HitMushroom':
			self.hit_mushroom()

	def teleport(self, spawn_point):
		self.exit_shell(False)
		if isinstance(spawn_point, str):
			try:
				spawn_point = self.scene.objects[spawn_point]
			except KeyError:
				Snail.log.error("Can't find spawn point %s", spawn_point)
				return
		bat.bmath.copy_transform(spawn_point, self)
		self.bend_angle_fore = 0.0
		self.bend_angle_aft = 0.0

	def update_eye_length(self):
		def update_single(eyeRayOb):
			restLength = self['EyeRestLen']
			channel = self.armature.channels[eyeRayOb['channel']]

			vect = eyeRayOb.getAxisVect(bat.bmath.ZAXIS) * restLength
			through = eyeRayOb.worldPosition + vect
			hitOb, hitPos, _ = bat.bmath.ray_cast_p2p(through, eyeRayOb,
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
				targetProportion = bat.bmath.lerp(currentProportion,
						targetProportion, self['EyeLenFac'])

			channel.scale = (1.0, targetProportion, 1.0)
		update_single(self.eyeRayL)
		update_single(self.eyeRayR)

	def pull_eyes_in(self):
		'''
		Cause the eyes to shrink back. This is a manual control; usually, the
		eyes will be managed automatically in update_eye_length.
		'''
		def update_single(eyeRayOb):
			channel = self.armature.channels[eyeRayOb['channel']]
			channel.scale = (1.0, 0.1, 1.0)
		update_single(self.eyeRayL)
		update_single(self.eyeRayR)

	@bat.bats.expose
	@bat.utils.controller_cls
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
			eye.alignAxisToVect(eye.parent.getAxisVect(bat.bmath.ZAXIS), 2)
			eye.alignAxisToVect(direction, 1)
			orn = eye.localOrientation.to_quaternion()
			oldOrn = mathutils.Quaternion(channel.rotation_quaternion)
			channel.rotation_quaternion = oldOrn.slerp(orn, Snail.EYE_LOOK_FAC)

		def get_direction(eye, target):
			_, gVec, _ = eye.getVectTo(target)
			return gVec

		def can_look(eye, direction):
			'''Don't allow looking behind; the eyes twist!'''
			dot = direction.dot(eye.parent.getAxisVect(bat.bmath.YAXIS))
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

		offset = Scripts.camera.AutoCamera().camera.worldPosition - self.worldPosition
		dist = offset.magnitude
		targetScale = dist / Snail.CAMERA_SAFE_DIST
		if targetScale < 0:
			targetScale = 0
		if targetScale > 1:
			targetScale = 1
		scale = self.cargoHold.localScale.x
		scale = bat.bmath.lerp(scale, targetScale, Snail.SHELL_SCALE_FAC)
		self.cargoHold.localScale = (scale, scale, scale)

	def _stow_shell(self, shell):
		# Similar to Bird.pick_up
		shell.localScale = (1.0, 1.0, 1.0)
		self.cargoHold.localScale = (1.0, 1.0, 1.0)
		referential = shell.cargoHook
		bat.bmath.set_rel_orn(shell, self.cargoHold, referential)
		bat.bmath.set_rel_pos(shell, self.cargoHold, referential)
		shell.setParent(self.cargoHold)

	@bat.bats.expose
	@bat.utils.controller_cls
	def pick_up_item(self, controller):
		'''Picks up and equips nearby shells that don't already have an
		owner. Note: this must run with priority over functions that drop
		items!'''
		collectables = bat.containers.SafeSet(
				controller.sensors['sPickup'].hitObjectList)
		# Forget objects that are no longer in range.
		self.recentlyDroppedItems.intersection_update(collectables)
		# Ignore objects that were recently dropped.
		collectables.difference_update(self.recentlyDroppedItems)

		for ob in collectables:
			if isinstance(ob, Scripts.shells.ShellBase):
				if not ob.is_carried and not ob.is_grasped:
					self.equip_shell(ob, True)
					bat.event.Event('ShellChanged', 'new').send()

	def switch_next(self):
		'''Equip the next-higher shell that the snail has.'''
		shellName = Scripts.inventory.Shells().get_next(1)
		if shellName == None:
			return
		if self.shell and shellName == self.shell.name:
			return

		self._switch(shellName)
		bat.event.Event('ShellChanged', 'next').send()

	def switch_previous(self):
		'''Equip the next-lower shell that the snail has.'''
		shellName = Scripts.inventory.Shells().get_next(-1)
		if shellName == None:
			return
		if self.shell and shellName == self.shell.name:
			return

		self._switch(shellName)
		bat.event.Event('ShellChanged', 'previous').send()

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
			shell = bat.bats.add_and_mutate_object(scene, name, self)
		self.equip_shell(shell, True)
		self.shell_change_sound.play()

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

		bat.event.WeakEvent('ShellEquipped', shell).send()
		bat.event.Event('ShowDialogue', shell.equip_message).send(30)
		Scripts.inventory.Shells().equip(shell.name)

		if animate:
			self.show_shockwave()

	def reclaim_shell(self):
		'''Reclaim a dropped shell.'''
		if not self.has_state(Snail.S_NOSHELL):
			return

		shellName = Scripts.inventory.Shells.get_equipped(self)
		if shellName is not None:
			self._switch(shellName)

	def show_shockwave(self):
		self.shockwave.worldPosition = self.shell.worldPosition
		self.shockwave.worldOrientation = self.shell.worldOrientation
		self.shockwave.visible = True
		self.shockwave.playAction('ShockwaveGrow', 1, 20, layer=Snail.L_SW_GROW)
		self.add_state(Snail.S_SHOCKWAVE)

	@bat.bats.expose
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
			bat.anim.add_trigger_gte(self.armature, Snail.L_ARM_SHELL, triggerFrame, callback)
		else:
			bat.anim.add_trigger_end(self.armature, Snail.L_ARM_SHELL, callback)

	def drop_shell(self, animate):
		'''Causes the snail to drop its shell, if it is carrying one.'''
		if not self.has_state(Snail.S_HASSHELL):
			return

		self.rem_state(Snail.S_HASSHELL)
		self.play_shell_action("PopShell", 18, self.on_drop_shell, animate, 15)

		bat.sound.Sample('//Sound/cc-by/BottleOpen.ogg').play()

	def on_drop_shell(self):
		'''Unhooks the current shell by un-setting its parent.'''
		if not self.has_state(Snail.S_HASSHELL):
			return
		velocity = bat.bmath.ZAXIS.copy()
		velocity.x += 0.5 - bge.logic.getRandomFloat()
		velocity = self.getAxisVect(velocity)
		velocity *= Snail.SHELL_POP_SPEED
		shell = self.unequip_shell()

		shell.setLinearVelocity(velocity)
		shell.on_dropped()
		self.recentlyDroppedItems.add(shell)

		bat.event.WeakEvent('ShellDropped', shell).send()

	def enter_shell(self, animate):
		'''
		Starts the snail entering the shell. Shell.on_pre_enter will be called
		immediately; Snail.on_enter_shell and Shell.on_entered will be called
		later, at the appropriate point in the animation.
		'''
		if not self.has_state(Snail.S_HASSHELL):
			return

		self.rem_state(Snail.S_HASSHELL)
		bat.utils.rem_state(self.armature, Snail.S_ARM_CRAWL)
		bat.utils.rem_state(self.armature, Snail.S_ARM_LOCOMOTION)
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

		bat.event.WeakEvent('ShellEntered', self).send()

	def exit_shell(self, animate):
		'''
		Tries to make the snail exit the shell. If possible, control will be
		transferred to the snail. The snail must currently be in a shell.
		'''
		if not self.has_state(Snail.S_INSHELL):
			return

		self.rem_state(Snail.S_INSHELL)
		self.add_state(Snail.S_FALLING)
		bat.utils.add_state(self.armature, Snail.S_ARM_CRAWL)
		bat.utils.add_state(self.armature, Snail.S_ARM_LOCOMOTION)
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

		bat.event.WeakEvent('MainCharacterSet', self).send()
		# Temporarily use a path camera while exiting the shell - it's smoother!
		bat.event.Event('SetCameraType', 'PathCamera').send()
		bat.event.Event('OxygenSet', self['Oxygen']).send()

	def on_exit_shell(self):
		'''Called when the snail has finished its exit shell
		animation (several frames after control has been
		transferred).'''

		self.add_state(Snail.S_HASSHELL)
		self.shell.on_post_exit()

		# Switch to orbit camera.
		bat.event.Event('SetCameraType', 'OrbitCamera').send()
		alignment = Scripts.camera.OrbitCameraAlignment()
		bat.event.Event('SetCameraAlignment', alignment).send()

		bat.event.WeakEvent('ShellExited', self).send()

	def record_velocity(self):
		# TODO: Remove this debugging code.
		super(Snail, self).record_velocity()
		self.DEBUGpositions.append(self.worldPosition.copy())
		if len(self.DEBUGpositions) > 20:
			self.DEBUGpositions.pop(0)

	def respawn(self):
		if self.has_state(Snail.S_INSHELL):
			self.exit_shell(False)
		super(Snail, self).respawn()

		Snail.log.info("Respawning.")
		if Snail.log.isEnabledFor(10):
			Snail.log.debug("Previous positions:")
			for pos in self.DEBUGpositions:
				Snail.log.debug("%s", pos)

	def set_health(self, value):
		current = self.get_health()
		super(Snail, self).set_health(value)

		diff = self.get_health() - current
		body = self.childrenRecursive['SnailBody']
		if diff < 0:
			body.stopAction(0)
			body.playAction('SnailDamage_Body', 1, 100, 0)
			body.setActionFrame(1, 0)
			bat.sound.Sample(
					'//Sound/cc-by/HealthDown1.ogg', 
					'//Sound/cc-by/HealthDown2.ogg',
					'//Sound/cc-by/HealthDown3.ogg').play()
			self.pull_eyes_in()
		elif diff > 0:
			body.stopAction(0)
			body.playAction('SnailHeal_Body', 1, 100, 0)
			body.setActionFrame(1, 0)
			bat.sound.Sample('//Sound/cc-by/HealthUp.ogg').play()
		bat.event.Event('HealthSet', value / self.maxHealth).send()

	def heal(self, amount=1):
		self.damage(amount=-amount)

	def shock(self):
		self.add_state(Snail.S_SHOCKED)
		self.rem_state(Snail.S_CRAWLING)
		self.rem_state(Snail.S_FALLING)
		self.enter_shell(animate=True)
		self.shock_tics = Snail.SHOCK_DURATION
		self.localLinearVelocity.z += 10.0

	@bat.bats.expose
	def shock_update(self):
		'''Count down to become un-shocked.'''
		if self.shock_tics > 0:
			self.shock_tics -= 1
			return

		if not self.has_state(Snail.S_INSHELL):
			self.add_state(Snail.S_FALLING)
		self.rem_state(Snail.S_SHOCKED)

	def health_warning(self):
		'''Plays a sound every few seconds when health is low.'''
		if self.get_health() > 1:
			return

		if self.health_warn_tics == 1:
			sample = bat.sound.Sample('//Sound/cc-by/HealthWarning.ogg')
			sample.volume = 0.5
			sample.play()

		if self.health_warn_tics > 0:
			self.health_warn_tics -= 1
		else:
			self.health_warn_tics = Snail.HEALTH_WARNING_DELAY

	def die(self):
		if self.has_state(Snail.S_INSHELL):
			self.exit_shell(False)
		if self.has_state(Snail.S_HASSHELL):
			self.drop_shell(False)
		Scripts.director.VulnerableActor.die(self)

	def on_oxygen_set(self):
		if not self.has_state(Snail.S_INSHELL):
			bat.event.Event('OxygenSet', self['Oxygen']).send()

	@bat.bats.expose
	@bat.utils.controller_cls
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

	def hit_mushroom(self):
		bat.event.Event('BlurAdd', 0.5).send()
		self.intoxication_level += Snail.INTOXICATION_HIT
		if self.intoxication_level >= Snail.MAX_INTOXICATION:
			self.damage()
			self.intoxication_level = 0

	@bat.bats.expose
	def start_crawling(self):
		'''Called when the snail enters its crawling state.'''
		#
		# Don't set it quite to zero: zero vectors are ignored!
		#
		self.setAngularVelocity(bat.bmath.MINVECTOR, False)
		self.setLinearVelocity(bat.bmath.MINVECTOR, False)

	def can_handle_input(self, state):
		return state.name in ('Movement', '1', '2', 'Camera', 'Switch')

	def handle_input(self, state):
		if state.name == 'Movement':
			self.handle_movement(state)
		elif state.name == '1':
			self.handle_bt_1(state)
		elif state.name == '2':
			self.handle_bt_2(state)
		elif state.name == 'Switch':
			self.handle_switch(state)
		elif state.name == 'Camera':
			self.handle_bt_camera(state)

	NORMAL_SPEED = 0.08
	BEND_FACTOR = 0.03
	MAX_BEND_ANGLE = 0.7 # radians

	def handle_movement(self, state):
		'''
		Make the snail move. If moving forward or backward, this implicitly
		calls decaySpeed.
		'''

		user_speed = min(1.0, state.direction.magnitude)
		speed = Snail.NORMAL_SPEED * self['SpeedMultiplier'] * user_speed
		if 'SubmergedFactor' in self:
			# Don't go so fast when under water!
			speed *= 1.0 - Snail.WATER_DAMPING * self['SubmergedFactor']
		self.decay_speed()

		self.direction_mapper.update(self, state.direction)
		self.engine.apply(self.direction_mapper.direction, speed)

		self.armature['LocomotionFrame'] += 5 * self.engine.speed
		self.armature['LocomotionFrame'] %= 19

		# Bending
		target_bend_angle = Snail.MAX_BEND_ANGLE * self.engine.turn_factor
		if self.engine.speed < 0:
			target_bend_angle = -target_bend_angle

		if self['SpeedMultiplier'] > 1.0:
			target_bend_angle /= self['SpeedMultiplier']

		# These actually get applied in crawl.
		self.bend_angle_fore = bat.bmath.lerp(self.bend_angle_fore,
				-target_bend_angle, Snail.BEND_FACTOR)

		if abs(user_speed) > 0.1:
			self.bend_angle_aft = bat.bmath.lerp(self.bend_angle_aft,
					target_bend_angle, Snail.BEND_FACTOR)

			# Moving forward or backward, so update trail.
			if self.touchedObject is not None:
				self.children['Trail'].moved(self['SpeedMultiplier'],
					self.touchedObject)

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
				self.exit_shell(animate=True)
			elif self.has_state(Snail.S_HASSHELL):
				self.enter_shell(animate=True)
			elif self.has_state(Snail.S_NOSHELL):
				self.reclaim_shell()

	def handle_bt_2(self, state):
		if not state.activated:
			return

		shells = Scripts.inventory.Shells().get_shells()
		if len(shells) == 1 and shells[0] == "Shell":
			# Can't drop shell until a special point in the game.
			return

		if self.has_state(Snail.S_HASSHELL):
			self.drop_shell(animate=True)
		elif self.has_state(Snail.S_NOSHELL):
			self.reclaim_shell()

	def handle_switch(self, state):
		'''Switch to next or previous shell.'''
		if state.triggered and (self.has_state(Snail.S_HASSHELL) or
				self.has_state(Snail.S_NOSHELL)):
			if state.direction > 0.1:
				self.switch_next()
			elif state.direction < -0.1:
				self.switch_previous()

	def handle_bt_camera(self, state):
		'''Move camera to be directly behind the snail.'''
		if state.activated:
			bat.event.Event('ResetCameraPos', None).send()

	def get_camera_tracking_point(self):
		return self.cameraTrack

	def get_focal_points(self):
		return self.focal_points[:]

	@property
	def has_shell(self):
		return self.has_state(Snail.S_HASSHELL)

	@property
	def is_in_shell(self):
		return self.has_state(Snail.S_INSHELL)

class Trail(bat.bats.BX_GameObject, bge.types.KX_GameObject):
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

		self.sound = bat.sound.Sample(
			'//Sound/cc-by/Slither1.ogg',
			'//Sound/cc-by/Slither2.ogg',
			'//Sound/cc-by/Slither3.ogg')
		self.sound.pitchmin = 0.7
		self.sound.pitchmax = 1.2
		self.sound.add_effect(bat.sound.Localise(self))

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
				Snail.log.warn("Couldn't find trail '%s' in scene '%s'",
						spot_name, self.scene)
			self.warned = True
			return

		#
		# Attach the spot to the object that the snail is crawling on.
		#
		if touchedObject != None:
			spot.setParent(touchedObject)

		bat.utils.set_state(spot, speedStyle)

	def moved(self, speedMultiplier, touchedObject):
		pos = self.worldPosition

		triggered = False
		distMajor = (pos - self.lastMajorPos).magnitude
		if distMajor > self['TrailSpacingMajor']:
			self.lastMajorPos = pos.copy()
			self.paused = not self.paused
			triggered = True

		if self.paused:
			return

		distMinor = (pos - self.lastMinorPos).magnitude
		if distMinor > self['TrailSpacingMinor']:
			self.lastMinorPos = pos.copy()
			speedStyle = Trail.S_NORMAL
			if speedMultiplier > (1.0 + bat.bmath.EPSILON):
				speedStyle = Trail.S_FAST
			elif speedMultiplier < (1.0 - bat.bmath.EPSILON):
				speedStyle = Trail.S_SLOW
			self.add_spot(speedStyle, touchedObject)
			if triggered and speedStyle == Trail.S_FAST:
				self.sound.copy().play()

class PickupAttractor(bat.effectors.Repeller3D):
	S_INIT = 1
	S_ACTIVE = 2
	S_INACTIVE = 3

	def __init__(self, old_owner):
		bat.effectors.Repeller3D.__init__(self, old_owner)
		bat.event.EventBus().add_listener(self)

	def on_event(self, evt):
		if evt.message == 'ShellEntered':
			self.set_state(PickupAttractor.S_INACTIVE)
		elif evt.message == 'ShellExited':
			self.set_state(PickupAttractor.S_ACTIVE)

class MinSnail(bat.bats.BX_GameObject, bge.types.BL_ArmatureObject):

	_prefix = 'MS_'

	S_INIT = 1
	S_LOOKING = 2

	LOOK_FAC = 0.2

	look_goal = bat.containers.weakprop('look_goal')

	def __init__(self, old_owner):
		eye_l = self.children['SlugEye.L']
		eye_r = self.children['SlugEye.R']
		self.focal_points = [eye_l, eye_r, self]

		self.look_at(None)

	@bat.bats.expose
	def update_look(self):
		# Stop tracking goal if it is behind the head.
		con = self.constraints["LookTarget:Copy Location"]
		head = self.children["SlugLookTarget"]
		if self.look_goal is None:
			return

		_, _, local_vec = head.getVectTo(self.look_goal)
		if local_vec.y > 0.0:
			con.enforce = min(con.enforce + MinSnail.LOOK_FAC, 1.0)
			if con.target is not None:
				con.target.worldPosition = bat.bmath.lerp(
					con.target.worldPosition, self.look_goal.worldPosition,
					MinSnail.LOOK_FAC)
		else:
			con.enforce = max(con.enforce - MinSnail.LOOK_FAC, 0.0)

	def look_at(self, goal):
		'''Turn the eyes to face the goal.'''
		if isinstance(goal, str):
			goal = self.scene.objects[goal]

		if hasattr(goal, "get_look_target"):
			goal = goal.get_look_target()

		if goal is None:
			con = self.constraints["LookTarget:Copy Location"]
			con.enforce = 0.0
			self.rem_state(MinSnail.S_LOOKING)
		else:
			self.add_state(MinSnail.S_LOOKING)

		self.look_goal = goal

	def get_focal_points(self):
		return self.focal_points[:]
