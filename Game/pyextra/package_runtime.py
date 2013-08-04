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
# Zip and tar file manipulation
# Copyright 2013 Alex Fraser
#

'''
Creates an executable game by combining a Blender file with the blenderplayer.
Asset files can be included. The blenderplayer is sourced from a Blender release
archive.
'''

import argparse
import fnmatch
import io
import os
import re
import struct
import tarfile
import zipfile


class GameMeta:
	def __init__(self, game_name, mainfile, assets):
		self.name = game_name
		self.mainfile = mainfile
		self.assets = assets
		self.suffix = None

	@property
	def archive_root(self):
		if self.suffix is None:
			return self.name
		else:
			return '{0}-{1}'.format(self.name, self.suffix)

	@property
	def runtime_root(self):
		return '{}/{}'.format(self.archive_root, os.path.dirname(self.mainfile))


def package_for_osx(game_meta, exclude, blend_dist):
	# Work directly with zip file contents to avoid changing OSX file metadata.

	PLAYER_PATTERN = re.compile('^Blender/blenderplayer.app(.*)$')
	ROOT_PATTERN = re.compile('^Blender(/[^/]*)$')

	target_path = game_meta.archive_root + '-osx.zip'
	with zipfile.ZipFile(blend_dist, 'r') as blender, \
			zipfile.ZipFile(target_path, 'w') as game:

		# First, copy over blenderplayer contents, but rename to game name
		for zi in blender.infolist():
			original_filename = zi.filename
			if original_filename == 'Blender/copyright.txt':
				zi.filename = '{0}/Blender-copyright.txt'.format(game_meta.runtime_root)
			elif PLAYER_PATTERN.match(original_filename) is not None:
				match = PLAYER_PATTERN.match(original_filename)
				zi.filename = '{0}/{1}.app{2}'.format(game_meta.runtime_root, game_meta.name, match.group(1))
			elif ROOT_PATTERN.match(original_filename) is not None:
				match = ROOT_PATTERN.match(original_filename)
				zi.filename = '{0}{1}'.format(game_meta.runtime_root, match.group(1))
			else:
				# Don't copy main blender app directory.
				continue

			print(zi.filename)
			data = blender.read(original_filename)
			game.writestr(zi, data)

		# No need to patch the player on OSX - just copy the data in as a
		# resource.
		arcname = '{0}/{1}.app/Contents/Resources/game.blend'.format(game_meta.runtime_root, game_meta.name)
		print(arcname)
		game.write(game_meta.mainfile, arcname=arcname)

		# Now copy other resources.
		for dirpath, _, filenames in os.walk(game_meta.assets):
			if exclude(os.path.basename(dirpath)):
				continue
			path = dirpath
			arcname = '{}/{}'.format(game_meta.archive_root, dirpath)
			print(arcname)
			game.write(path, arcname=arcname)
			for f in filenames:
				if exclude(f):
					continue
				path = os.path.join(dirpath, f)
				arcname = '{}/{}'.format(game_meta.archive_root, path)
				print(arcname)
				game.write(path, arcname=arcname)

	print('Game packaged as %s' % target_path)


def package_for_win(game_meta, exclude, blend_dist):
	# Work directly with the zip file, because we can.
	pass


def package_for_lin(game_meta, exclude, blend_dist):
	# Copy from tar to zip.

	PATTERN = re.compile('^[^/]+(.*)$')
	EXCLUDE_PATTERNS = re.compile('^/blender$|^/blender-softwaregl$|^/blender-thumbnailer.py$|'
		'^/icons|'
		'^/[0-9].[0-9][0-9]/scripts/(?!modules)')

	def get_target_path(src_path):
		match = PATTERN.match(src_path)
		if match is None:
			return None
		sub_path = match.group(1)
		if EXCLUDE_PATTERNS.match(sub_path) is not None:
			path = None
		elif sub_path == '/blenderplayer':
			path = '{0}/{1}'.format(game_meta.runtime_root, game_meta.name)
		elif sub_path == '/copyright.txt':
			path = '{0}/Blender-copyright.txt'.format(game_meta.runtime_root)
		else:
			path = '{0}{1}'.format(game_meta.runtime_root, sub_path)
		return sub_path, path

	target_path = game_meta.archive_root + '-linux.tar.bz2'
	with tarfile.open(blend_dist, 'r') as blender, \
			tarfile.open(target_path, 'w:bz2') as game:

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
					with open(game_meta.mainfile, 'rb') as mf:
						buf, ti.size = concat_game(buf, mf)
					print('new size', ti.size)
	
				ti.name = name
				print(ti.name)
				game.addfile(ti, fileobj=buf)

		# Now copy other resources.
		for dirpath, _, filenames in os.walk(game_meta.assets):
			if exclude(os.path.basename(dirpath)):
				continue
			path = dirpath
			arcname = '{}/{}'.format(game_meta.archive_root, dirpath)
			print(arcname)
			game.add(path, arcname=arcname, recursive=False)
			for f in filenames:
				if exclude(f):
					continue
				path = os.path.join(dirpath, f)
				arcname = '{}/{}'.format(game_meta.archive_root, path)
				print(arcname)
				game.add(path, arcname=arcname, recursive=False)
	print('Game packaged as %s' % target_path)


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


class ExGlobber:
	'''Filter used to include or exclude files.'''
	def __init__(self):
		self.patterns = []

	@staticmethod
	def from_file(file_name):
		globber = ExGlobber()
		with open(args.exclude) as f:
			for line in f:
				if line.startswith('#'):
					continue
				if line.endswith('\n'):
					line = line[:-1]
				globber.add(line)
		return globber

	def add(self, pattern):
		regex = fnmatch.translate(pattern)
		self.patterns.append(re.compile(regex))

	def __call__(self, filename):
		'''Returns False iff the file should be included.'''
		for p in self.patterns:
			if p.match(filename) is not None:
				return True
		return False


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Package game for publishing')
	parser.add_argument('target', choices={'lin', 'osx', 'win'},
		help="Package for Windows (win), Mac (osx) or GNU/Linux (lin)")
	parser.add_argument('mainfile',
		help="The file to embed in the executable (startup .blend file). This will also be used to name the package.")
	parser.add_argument('assets',
		help="The directory to package.")
	parser.add_argument('blender_dist',
		help="The location of the Blender distributable archive.")
	parser.add_argument('-v', '--version', dest='version',
		help="Optional release version string.")
	parser.add_argument('-x', '--exclude', dest='exclude',
		help="File that contains exclusion rules as file glob strings (e.g. "
			"*.blend1), one per line. Any asset files that match will be "
			"excluded from the package.")
	args = parser.parse_args()

	name = os.path.basename(args.mainfile)
	if not name.endswith('.blend'):
		raise ValueError('mainfile must be a .blend file')
	name = name[:-6]
	game_meta = GameMeta(name, args.mainfile, args.assets)
	if 'version' in args:
		game_meta.suffix = args.version

	if 'exclude' not in args:
		globber = ExGlobber()
	else:
		globber = ExGlobber.from_file(args.exclude)

	if args.target == 'lin':
		fn = package_for_lin
	elif args.target == 'win':
		fn = package_for_win
	elif args.target == 'osx':
		fn = package_for_osx
	fn(game_meta, globber, args.blender_dist)
