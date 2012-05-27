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

import bge

import bxt

from . import shells
from . import inventory
from .story import *

def factory():
	scene = bge.logic.getCurrentScene()
	if not "Ant" in scene.objectsInactive:
		try:
			bge.logic.LibLoad('//Ant_loader.blend', 'Scene', load_actions=True)
		except ValueError as e:
			print('Warning: could not load ant:', e)

	return bxt.types.add_and_mutate_object(scene, "Ant", "Ant")

class Ant(Chapter, bxt.types.BX_GameObject, bge.types.BL_ArmatureObject):
	L_IDLE = 0
	L_ANIM = 1

	def __init__(self, old_owner):
		Chapter.__init__(self, old_owner)
		bxt.types.WeakEvent("StartLoading", self).send()
		self.create_state_graph()

	def create_state_graph(self):
		pass
