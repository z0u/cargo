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
from . import director
from . import store
from Scripts import shells
from . import shaders

class LevelOut(GameLevel):
	def __init__(self, oldOwner):
		GameLevel.__init__(self, oldOwner)

		#bxt.music.play("//Sound/Music/explore.ogg", volume=0.3)
		bxt.music.play_permutation(
				"//Sound/cc-by/PondAmbience1.ogg",
				"//Sound/cc-by/PondAmbience2.ogg",
				"//Sound/cc-by/PondAmbience3.ogg",
				volume=0.7)

		# Load additional files
		self.load_foaliage()
		self.load_npcs()
		self.init_worm()

		shaders.ShaderCtrl().set_mist_colour(
				mathutils.Vector((0.749020, 0.737255, 0.745098)))

	def load_foaliage(self):
		'''Load extra files'''
		err = False

		try:
			bge.logic.LibLoad('//OutdoorsBase_flowers.blend', 'Scene',
					load_actions=True)
		except ValueError:
			err = True

		if store.get('/opt/foliage', True):
			try:
				bge.logic.LibLoad('//OutdoorsBase_grass.blend', 'Scene',
						load_actions=True)
			except ValueError:
				err = True

		if err:
			print('Error: Could not load foliage. Try reinstalling the game.')
			evt = bxt.types.Event('ShowDialogue',
				'Error: Could not load foliage. Try reinstalling the game.')
			bxt.types.EventBus().notify(evt)

	def load_npcs(self):
		try:
			bge.logic.LibLoad('//OutdoorsNPCLoader.blend', 'Scene',
					load_actions=True)
		except ValueError:
			print('Could not load characters. Try reinstalling the game.')
			evt = bxt.types.Event('ShowDialogue',
				'Could not load characters. Try reinstalling the game.')
			bxt.types.EventBus().notify(evt)

	def init_worm(self):
		sce = bge.logic.getCurrentScene()
		if not store.get('/game/level/wormMissionStarted', False):
			sce.addObject("G_Worm", "WormSpawn")
			bxt.bmath.copy_transform(sce.objects['WormSpawn'], sce.objects['Worm'])

class TestLevelCargoHouse(LevelOut):
	'''A level loader for Cargo's house - local testing only (not used by
	Outdoors.blend)'''

	def __init__(self, oldOwner):
		GameLevel.__init__(self, oldOwner)
		self.load_npcs()
		self.init_worm()
