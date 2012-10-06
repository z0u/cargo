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

import bat.bats
import bat.event
import bat.utils

import bat.store

class Tree(bat.bats.BX_GameObject, bge.types.KX_GameObject):
	def __init__(self, oldOwner):
		if not bat.store.get('/game/level/treeDoorBroken', False):
			self.create_door()

	def create_door(self):
		hook = self.children['T_Door_Hook']
		scene = bge.logic.getCurrentScene()
		door = scene.addObject('T_Door', hook)
		door.worldPosition = hook.worldPosition
		door.worldOrientation = hook.worldOrientation

class TreeDoor(bat.bats.BX_GameObject, bge.types.KX_GameObject):
	_prefix = 'TD_'

	def __init__(self, oldOnwer):
		pass

	def destruct(self):
		scene = bge.logic.getCurrentScene()
		for hook in self.children:
			i = hook.name[-3:]
			pieceName = 'T_Door_Broken.%s' % i
			try:
				scene.addObject(pieceName, hook)
			except ValueError:
				print('Failed to add object %s' % pieceName)
		self.endObject()
		bat.event.Event('treeDoorBroken').send()
		bat.store.put('/game/level/treeDoorBroken', True)

	@bat.bats.expose
	@bat.utils.controller_cls
	def collide(self, c):
		for shell in c.sensors[0].hitObjectList:
			if shell.name != 'Wheel':
				continue
			if not shell.can_destroy_stuff():
				continue
			evt = bat.event.Event('ForceExitShell', True)
			bat.event.EventBus().notify(evt)
			self.destruct()
