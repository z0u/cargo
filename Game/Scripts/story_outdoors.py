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
import mathutils

import bxt

from .story import *
from . import shaders
from . import inventory
from . import jukebox

class LevelOut(GameLevel):
	def __init__(self, oldOwner):
		GameLevel.__init__(self, oldOwner)

		jukebox.Jukebox().play_permutation(self, 0,
				"//Sound/cc-by/PondAmbience1.ogg",
				"//Sound/cc-by/PondAmbience2.ogg",
				"//Sound/cc-by/PondAmbience3.ogg",
				volume=0.7)

		# Load additional files
		self.load_foaliage()
		self.load_npcs()

		shaders.ShaderCtrl().set_mist_colour(
				mathutils.Vector((0.565, 0.572, 0.578)))

	def load_foaliage(self):
		'''Load extra files'''
		try:
			bge.logic.LibLoad('//OutdoorsBase_flowers.blend', 'Scene',
					load_actions=True)
		except ValueError:
			print('Warning: could not load foliage.')

		if store.get('/opt/foliage', True):
			try:
				bge.logic.LibLoad('//OutdoorsBase_grass.blend', 'Scene',
						load_actions=True)
			except ValueError:
				print('Warning: could not load foliage.')

	def load_npcs(self):
		try:
			bge.logic.LibLoad('//OutdoorsNPCLoader.blend', 'Scene',
					load_actions=True)
		except ValueError:
			print('Warning: could not load characters.')

