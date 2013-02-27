#
# Copyright 2012 Alex Fraser <alex@phatcore.com>
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

import bat.bmath
import bat.bats
import bat.containers
import bat.event
import bat.utils

DEBUG = False

def spawn(c):
	sce = bge.logic.getCurrentScene()
	bee = factory(sce)
	bat.bmath.copy_transform(c.owner, bee)
	path = sce.objects[c.owner['path']]
	bee.path = bat.bats.mutate(path)

def factory(scene):
	if not "WorkerBee" in scene.objectsInactive:
		try:
			bge.logic.LibLoad('//Bee_loader.blend', 'Scene', load_actions=True)
		except ValueError as e:
			print('Warning: could not load bee:', e)

	return bat.bats.add_and_mutate_object(scene, "WorkerBee")

class WorkerBee(bat.bats.BX_GameObject, bge.types.KX_GameObject):
	_prefix = 'WB_'

	LIFT_FAC = 1.0
	ACCEL = 0.1
	DAMP = 0.1
	RELAX_DIST = 5.0
	NOISE_FAC = 0.05
	NOISE_SCALE = 0.1

	path = bat.containers.weakprop('path')

	def __init__(self, old_owner):
		self.path = None
		self.hint = 0
		self.set_lift(mathutils.Vector((0.0, 0.0, -9.8)))

		bat.event.EventBus().add_listener(self)
		bat.event.EventBus().replay_last(self, 'GravityChanged')

	def on_event(self, evt):
		if evt.message == 'GravityChanged':
			self.set_lift(evt.body)

	def set_lift(self, gravity):
		lift = gravity.copy()
		lift.negate()
		lift = (lift / bge.logic.getLogicTicRate()) * WorkerBee.LIFT_FAC
		self.lift = lift

	@bat.bats.expose
	def fly(self):
		if self.path is None:
			print("Warning: bee has no path.")
			return

		# Find target: either enemy or waypoint.
		snail = self.get_nearby_snail()
		if snail is not None:
			next_point = snail.worldPosition
		else:
			next_point = self.get_next_waypoint()

		# Approach target
		cpos = self.worldPosition.copy()
		base_accel = (next_point - cpos).normalized()
		accel =  (base_accel * WorkerBee.ACCEL) + self.lift
#		accel += mathutils.noise.random_unit_vector() * WorkerBee.RANDOM_FAC
		noise_vec = mathutils.noise.noise_vector(cpos * WorkerBee.NOISE_SCALE)
		accel += noise_vec * WorkerBee.NOISE_FAC
		pos, vel = bat.bmath.integrate(cpos, self.worldLinearVelocity,
			accel, WorkerBee.DAMP)

		if DEBUG:
			bge.render.drawLine(pos, next_point, (0, 0, 1))
			bge.render.drawLine(pos, pos + noise_vec * 20, (1, 0, 0))
			bge.render.drawLine(pos, pos + vel * 20, (0, 1, 0))

		self.worldPosition = pos
		self.worldLinearVelocity = vel

		# Orientation: z-up, y-back
		upvec = noise_vec * 0.5 + bat.bmath.ZAXIS
		self.alignAxisToVect(upvec, 2)
		vel.negate()
		self.alignAxisToVect(vel, 1, 0.3)

	@bat.utils.controller_cls
	def get_nearby_snail(self, c):
		s = c.sensors[0]
		if not s.positive:
			return None

		snail = s.hitObject
		if snail.is_in_shell:
			return None
		else:
			return snail

	def get_next_waypoint(self):
		cpos = self.worldPosition
		next_point, self.hint = self.path.get_next(cpos, WorkerBee.RELAX_DIST,
				self.hint)
		return next_point

class DirectedPath(bat.bats.BX_GameObject, bge.types.KX_GameObject):

	MIN_DIST = 2

	def __init__(self, old_owner):
		pass

	def init_path(self):
		mat = self.worldTransform.copy()
#		path = [mat * v.XYZ for v in bat.utils.iterate_all_verts_by_poly(self)]
		path = [mat * v.XYZ for v in bat.utils.iterate_verts(self)]
		self.path = []
		for v1 in path:
			dup = False
			for v2 in self.path:
				if (v1 - v2).magnitude < DirectedPath.MIN_DIST:
					dup = True
					break

			if not dup:
				self.path.append(v1)
		self.path = self.path[1:]

	def get_next(self, pos, relax_dist, hint=0):
		try:
			self.path
		except AttributeError:
			self.init_path()

		if DEBUG:
			bat.render.draw_polyline(self.path, (1,0,1), cyclic=True)

		# Find the first node beyond the relax length
		nnodes = len(self.path)
		for i in range(0, nnodes):
			index = (i + hint) % nnodes
			vert = self.path[index]
			dist = (vert - pos).magnitude
			if dist > relax_dist:
				#print(index, dist)
				return vert, index

		return self.path[0], 0
