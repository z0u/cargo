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

import collections

import bge

import bxt

DEBUG = True

Track = collections.namedtuple('Track', ['files', 'volume', 'loop',
		'permute'])

class Jukebox(metaclass=bxt.types.Singleton):
	_prefix = ''

	def __init__(self):
		self.stack = bxt.types.SafePriorityStack()
		self.current_track = None

	@bxt.types.expose
	def update(self):
		if len(self.stack) == 0:
			top = None
		else:
			top = self.stack.top()

		if top is None:
			track = None
		else:
			track = top['_JukeboxTrack']

		if track is self.current_track:
			return

		if DEBUG:
			if track is None:
				print("Playing track:", track)
			else:
				print("Playing track:", track.files)
		if track is None:
			bxt.music.stop()
		elif track.permute:
			bxt.music.play_permutation(*track.files, volume=track.volume,
					loop=track.loop)
		else:
			bxt.music.play(*track.files, volume=track.volume,
					loop=track.loop)
		self.current_track = track

	def play(self, owner, priority, *files, volume=1.0):
		track = Track(files=files, volume=volume, loop=True, permute=False)
		owner['_JukeboxTrack'] = track
		self.stack.push(owner, priority)

	def play_permutation(self, owner, priority, *files, volume=1.0):
		track = Track(files=files, volume=volume, loop=True, permute=True)
		owner['_JukeboxTrack'] = track
		self.stack.push(owner, priority)

	def stop(self, owner):
		self.stack.discard(owner)
