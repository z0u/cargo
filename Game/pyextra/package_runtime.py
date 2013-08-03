#!/usr/bin/env python3

#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# Data concatenation
# Copyright Mitchell Stokes
#
# Zip file manipulation
# Copyright 2013 Alex Fraser
#

import argparse
import io
import re
import struct
import tarfile
import zipfile



def package_for_osx(game_name, blend_dist, mainfile):
	# Work directly with zip file contents to avoid changing OSX file metadata.

	PLAYER_PATTERN = re.compile('^Blender/blenderplayer.app(.*)$')
	ROOT_PATTERN = re.compile('^Blender(/[^/]*)$')

	with zipfile.ZipFile(blend_dist, 'r') as blender, \
			zipfile.ZipFile(game_name + '.zip', 'w') as game:

		# First, copy over blenderplayer contents, but rename to game name
		for zi in blender.infolist():
			original_filename = zi.filename
			if original_filename == 'Blender/copyright.txt':
				zi.filename = '{0}/Blender-copyright.txt'.format(game_name)
			elif PLAYER_PATTERN.match(original_filename) is not None:
				match = PLAYER_PATTERN.match(original_filename)
				zi.filename = '{0}/{0}.app{1}'.format(game_name, match.group(1))
			elif ROOT_PATTERN.match(original_filename) is not None:
				match = ROOT_PATTERN.match(original_filename)
				zi.filename = '{0}{1}'.format(game_name, match.group(1))
			else:
				# Don't copy main blender app directory.
				continue

			print(zi.filename)
			data = blender.read(original_filename)
			game.writestr(zi, data)

		arcname = '{0}/{0}.app/Contents/Resources/game.blend'.format(game_name)
		game.write(mainfile, arcname=arcname)


def package_for_win(game_name, blend_dist, mainfile):
	# Work directly with the zip file, because we can.
	pass


def package_for_lin(game_name, blend_dist, mainfile):
	# Copy from tar to zip.

	PATTERN = re.compile('^[^/]+(.*)$')

	def get_target_path(src_path):
		match = PATTERN.match(src_path)
		if match is None:
			return None
		sub_path = match.group(1)
		if sub_path in {'/blender', '/blender-softwaregl', '/blender-thumbnailer.py'}:
			# Don't copy main blender app
			path = None
		elif sub_path == '/blenderplayer':
			path = '{0}/{0}'.format(game_name)
		elif sub_path == '/copyright.txt':
			path = '{0}/Blender-copyright.txt'.format(game_name)
		else:
			path = '{0}{1}'.format(game_name, sub_path)
		return sub_path, path

	with tarfile.open(blend_dist, 'r') as blender, \
			tarfile.open(game_name + '.tar.bz2', 'w:bz2') as game:

		# First, copy over blenderplayer contents, but rename to game name
		for ti in blender:
			# Rename file.
			sub_path, name = get_target_path(ti.name)
			if name is None:
				continue

			# Special handling for links
			if ti.type in {tarfile.LNKTYPE, tarfile.SYMTYPE}:
				ti.name = name
				print('%s -> %s' % (ti.name, ti.linkname))
				game.addfile(ti)

			else:
				# For some entries buf will be None, but that's OK
				buf = blender.extractfile(ti)
				if sub_path == '/blenderplayer':
					print('old size', ti.size)
					with open(mainfile, 'rb') as mf:
						buf, ti.size = concat_game(buf, mf)
					print('new size', ti.size)
	
				ti.name = name
				print(ti.name)
				game.addfile(ti, fileobj=buf)


def concat_game(playerfile, mainfile):
	'''
	Concatenate the primary game data file onto the blenderplayer executable.
	'''
	buf = io.BytesIO()
	size = offset = buf.write(playerfile.read())
	size += buf.write(mainfile.read())

	# Store the offset (an int is 4 bytes, so we split it up into 4 bytes and save it)
	size += buf.write(struct.pack('B', (offset>>24)&0xFF))
	size += buf.write(struct.pack('B', (offset>>16)&0xFF))
	size += buf.write(struct.pack('B', (offset>>8)&0xFF))
	size += buf.write(struct.pack('B', (offset>>0)&0xFF))
	size += buf.write(b'BRUNTIME')
	buf.seek(0)
	return buf, size


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Package game for publishing')
	parser.add_argument('target', choices={'lin', 'osx', 'win'})
	parser.add_argument('game_name')
	parser.add_argument('blender_dist')
	parser.add_argument('mainfile')
	args = parser.parse_args()

	if args.target == 'lin':
		fn = package_for_lin
	elif args.target == 'win':
		fn = package_for_win
	elif args.target == 'osx':
		fn = package_for_osx
	fn(args.game_name, args.blender_dist, args.mainfile)
