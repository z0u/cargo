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

import bxt

import bge

class StoryLight(bxt.types.BX_GameObject, bge.types.KX_LightObject):
	'''
	This light is used to add special lighting to the cut-scenes. To use it:
	 - Ensure Utilities -> BasicKit is in the current scene.
	 - Send a 'SetStoryLight' message, containing an object as its body.
	The light will then mimic the orientation of the given object, and will
	adjust its energy to match the object's 'energy' property.
	'''

	_prefix = 'SL_'

	SPEEDFAC = 0.1
	TOLERANCE = 0.01
	S_UPDATING = 2

	goal = bxt.types.weakprop('goal')

	def __init__(self, old_owner):
		self.set_goal(None)
		bxt.types.EventBus().add_listener(self)
		bxt.types.EventBus().replay_last(self, 'SetStoryLight')

	def on_event(self, evt):
		if evt.message == 'SetStoryLight':
			if isinstance(evt.body, str):
				self.set_goal(self.scene.objects[evt.body])
			else:
				self.set_goal(evt.body)

	def set_goal(self, goal):
		if goal is not None:
			bxt.utils.set_default_prop(goal, 'energy', 1.0)
			bxt.utils.set_default_prop(goal, 'spotsize', 45.0)
			bxt.utils.set_default_prop(goal, 'spotblend', 1.0)
			bxt.utils.set_default_prop(goal, 'distance', 50.0)
		self.goal = goal
		self.add_state(StoryLight.S_UPDATING)

	@bxt.types.expose
	def update(self):
		if self.goal is None:
			target_energy = 0.0
			target_size = 45.0
			target_blend = 1.0
			target_distance = 50.0
			goal = self
		else:
			target_energy = self.goal['energy']
			target_size = self.goal['spotsize']
			target_blend = self.goal['spotblend']
			target_distance = self.goal['distance']
			goal = self.goal

		self.energy = bxt.bmath.lerp(self.energy, target_energy,
				StoryLight.SPEEDFAC)
		self.spotsize = bxt.bmath.lerp(self.spotsize, target_size,
				StoryLight.SPEEDFAC)
		self.spotblend = bxt.bmath.lerp(self.spotblend, target_blend,
				StoryLight.SPEEDFAC)
		self.distance = bxt.bmath.lerp(self.distance, target_distance,
				StoryLight.SPEEDFAC)
		bxt.bmath.slow_copy_rot(self, goal, StoryLight.SPEEDFAC)
		bxt.bmath.slow_copy_loc(self, goal, StoryLight.SPEEDFAC)

		# Check tolerance, and stop updating if close enough.
		if abs(self.energy - target_energy) > StoryLight.TOLERANCE:
			return
		if abs(self.spotsize - target_size) > StoryLight.TOLERANCE:
			return
		if abs(self.spotblend - target_blend) > StoryLight.TOLERANCE:
			return
		if abs(self.distance - target_distance) > StoryLight.TOLERANCE:
			return

		vec1 = self.getAxisVect(bxt.bmath.ZAXIS)
		vec2 = goal.getAxisVect(bxt.bmath.ZAXIS)
		orn_diff = 1.0 - vec1.dot(vec2)
		if orn_diff > StoryLight.TOLERANCE:
			return
		loc_diff = (self.worldPosition - goal.worldPosition).magnitude
		if loc_diff > StoryLight.TOLERANCE:
			return

		self.energy = target_energy
		self.worldOrientation = goal.worldOrientation
		self.rem_state(StoryLight.S_UPDATING)