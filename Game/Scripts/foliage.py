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

import bge
import mathutils

import bat.bats
import bat.event
import bat.utils
import bat.bmath
import bat.render
import bat.sound

DEBUG = False

ZERO2 = mathutils.Vector((0.0, 0.0))

class Clover(bat.bats.BX_GameObject, bge.types.KX_GameObject):
	'''A health powerup.'''

	_prefix = 'CL_'

	def __init__(self, old_owner):
		pass

	@bat.bats.expose
	@bat.utils.controller_cls
	def touched(self, c):
		s = c.sensors[0]
		if s.hitObject is not None and hasattr(s.hitObject, "heal"):
			s.hitObject.heal()
			self.scene.addObject("Clover_dynamic", self)
			self.endObject()

class SBParticle:
	'''A 2D softbody particle. Always tries to return to (0, 0). Set the Frame
	property directly to displace the particle; then call update_dynamics to
	accelerate the particle back towards (0, 0).
	'''
	def __init__(self, spring, damp, index):
		self.Velocity = ZERO2.copy()
		self.Frame = ZERO2.copy()

		self.Spring = spring
		self.Damping = damp

		self.XProp = "BladeX%d" % index
		self.YProp = "BladeY%d" % index

	def update_dynamics(self):
		'''Accelerate the particle towards (0, 0)'''
		accel = self.Frame * -self.Spring
		self.Frame, self.Velocity = bat.bmath.integrate(
				self.Frame, self.Velocity,
				accel, self.Damping)

class FlexibleObject(bat.bats.BX_GameObject, bge.types.BL_ArmatureObject):
	_prefix = 'GB_'

	S_INIT = 1
	S_UPDATE = 2

	def __init__(self, old_owner):
		self.Segments = []
		for i in range(0, self['nSegments']):
			p = SBParticle(self['Spring'], self['Damping'], i)
			self.Segments.append(p)

		self.jolt_frames = 0
		self.intrusion = ZERO2.copy()
		self.LastBaseFrame = ZERO2.copy()

		if DEBUG:
			for child in self.children:
				child.color = bat.render.BLACK

	@bat.bats.expose
	@bat.utils.controller_cls
	def collide(self, c):
		#
		# Find the offset of the base.
		#
		s = c.sensors['Near']
		vec = ZERO2.copy()
		for col in s.hitObjectList:
			vec = vec + self.get_collision_force(col)
		self['BladeXBase'] = vec.x
		self['BladeYBase'] = vec.y
		self.intrusion = vec
		if vec.magnitude > 0.0:
			self.add_state(FlexibleObject.S_UPDATE)

	@bat.bats.expose
	@bat.utils.controller_cls
	def update(self, c):
		linkDisplacement = self.intrusion - self.LastBaseFrame
		self.LastBaseFrame = self.intrusion.copy()

		#
		# Provide input to other logic paths (a sensor might watch this).
		#
		if self.jolt_frames == 0 and linkDisplacement.magnitude > 15.0:
			self['Jolted'] = True
			self.jolt_frames = 100
			if 'JoltMessage' in self:
				evt = bat.event.Event(self['JoltMessage'])
				if 'JoltBody' in self:
					evt.body = self['JoltBody']
				evt.send()
		elif self.jolt_frames > 0:
			self['Jolted'] = False
			self.jolt_frames -= 1

		#
		# Move each link in the opposite direction to the preceding link.
		#
		max_offset = 0.0
		for s in self.Segments:
			s.Frame = s.Frame - linkDisplacement
			s.update_dynamics()
			self[s.XProp] = s.Frame.x
			self[s.YProp] = s.Frame.y
			max_offset = max(max_offset, abs(s.Frame.x), abs(s.Frame.y),
					abs(s.Velocity.x), abs(s.Velocity.y))
			linkDisplacement = s.Velocity

		if max_offset < 0.1:
			self.rem_state(FlexibleObject.S_UPDATE)

		for act in c.actuators:
			c.activate(act)

class GrassBlade(FlexibleObject):

	@bat.bats.profile('Scripts.foliage.GrassBlade.__init__')
	def __init__(self, old_owner):
		FlexibleObject.__init__(self, old_owner)
		self.bbox = bat.bmath.Box2D(
				0.0 - self['GrassRadY'], 0.0 - self['GrassRadZ'],
				self['GrassRadY'], self['GrassRadZ'])

	def get_collision_force(self, collider):
		#
		# Transform collider into blade's coordinate system.
		#
		cPos = bat.bmath.to_local(self, collider.worldPosition)

		#
		# The blades are rotated 90 degrees to work better as Blender particles.
		# But we're only interested in two axes. Re-map them to be X and Y.
		#
		cPos = cPos.yz

		#
		# Collider bounding box.
		#
		colRad = collider['LODRadius']
		colBox = bat.bmath.Box2D(cPos.x - colRad, cPos.y - colRad,
		                        cPos.x + colRad, cPos.y + colRad)

		#
		# Perform axis-aligned 2D bounding box collision.
		#
		colBox.intersect(self.bbox)
		area = colBox.get_area()

		if area < 0.0:
			#
			# Boxes aren't touching; no force.
			#
			return ZERO2.copy()

		areaFraction = area / self.bbox.get_area()

		cPos.normalize()
		cPos = cPos * (areaFraction * 100.0)

		return cPos

def flower_sound(c):
	sample = bat.sound.Sample(
		'//Sound/cc-by/Bell2.ogg',
		'//Sound/cc-by/Bell3.ogg',
		'//Sound/cc-by/Bell4.ogg',
		'//Sound/cc-by/Bell1.ogg')
	sample.volume = 0.7
	sample.add_effect(bat.sound.Localise(c.owner))
	sample.play()

def mushroom_sound(c):
	sample = bat.sound.Sample(
		'//Sound/cc-by/jaw-harp21.ogg',
		'//Sound/cc-by/jaw-harp4.ogg',
		'//Sound/cc-by/jaw-harp3.ogg',
		'//Sound/cc-by/jaw-harp19.ogg',
		'//Sound/cc-by/jaw-harp2.ogg',
		'//Sound/cc-by/jaw-harp20.ogg')
	sample.volume = 0.7
	sample.add_effect(bat.sound.Localise(c.owner))
	sample.play()

class Web(FlexibleObject):
	def __init__(self, old_owner):
		FlexibleObject.__init__(self, old_owner)

	def get_collision_force(self, collider):
		cPos = bat.bmath.to_local(self, collider.worldPosition)
		colRad = collider['LODRadius']
		if cPos.z < 0:
			intrusion = cPos.z + colRad
		else:
			intrusion = cPos.z - colRad
		intrusion = bat.bmath.clamp(-colRad, colRad, intrusion) * 100.0
		return mathutils.Vector((intrusion, intrusion))

def salt_crystal_destroy(c):
	ob = c.owner
	sce = bge.logic.getCurrentScene()

	# Transform name "Salt_X.Y_T" -> "Salt_X.Y_Fractured"
	name = ob.name[:-1] + "Fractured"

	# Replace current object with fractured object
	MAX_LIFE = 300
	new_ob = sce.addObject(name, ob, MAX_LIFE)
	ob.endObject()

	sample = bat.sound.Sample(
		'//Sound/cc-by/CrashBoom1.ogg',
		'//Sound/cc-by/CrashBoom2.ogg',
		'//Sound/cc-by/CrashBoom3.ogg')
	sample.volume = 0.7
	sample.pitchmin = 0.9
	sample.pitchmax = 1.4
	sample.add_effect(bat.sound.Localise(new_ob))
	sample.play()

	sce.addObject('Salt_Dust', ob, MAX_LIFE)
