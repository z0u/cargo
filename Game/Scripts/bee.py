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
import bat.utils

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
	ACCEL = 0.05
	DAMP = 0.05
	RELAX_DIST = 10.0

	path = bat.bats.weakprop('path')

	def __init__(self, old_owner):
		self.path = None
		self.hint = 0
		self.set_lift(mathutils.Vector((0.0, 0.0, -9.8)))

		bat.bats.EventBus().add_listener(self)
		bat.bats.EventBus().replay_last(self, 'GravityChanged')

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
		cpos = self.worldPosition
		accel = (next_point - cpos).normalized() * WorkerBee.ACCEL
		accel += self.lift
		pos, vel = bat.bmath.integrate(cpos, self.worldLinearVelocity,
			accel, WorkerBee.DAMP)
		self.worldPosition = pos
		self.worldLinearVelocity = vel

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

	DEFAULT_STRIDE = 2

	def __init__(self, old_owner):
		self.set_default_prop('stride', DirectedPath.DEFAULT_STRIDE)

	def init_path(self):
		mat = self.worldTransform
		self.path = [mat * v.XYZ for v in bat.utils.iterate_verts(self)]

	def get_next(self, pos, relax_dist, hint=0):
		try:
			self.path
		except AttributeError:
			self.init_path()

		# Find the first node beyond the relax length
		nnodes = len(self.path)
		for i in range(0, nnodes, self['stride']):
			index = (i + hint) % nnodes
			vert = self.path[index]
			dist = (vert - pos).magnitude
			if dist > relax_dist:
				#print(index, dist)
				return vert, index

		return self.path[0], 0
