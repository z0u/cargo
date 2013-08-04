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


class Error(Exception):
	pass

class TranslationError(Error):
	def __init__(self, message):
		self.message = message
	def __str__(self):
		return repr(self.message)


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


class OsxMapper:

	PLAYER_PATTERN = re.compile('^Blender/blenderplayer.app(.*)$')
	ROOT_PATTERN = re.compile('^Blender(/[^/]*)$')

	def __init__(self, game_meta):
		self.game_meta = game_meta
		self.executable = None

	def apply(self, name):
		original_filename = name
		if original_filename == 'Blender/copyright.txt':
			name = '{0}/Blender-copyright.txt'.format(self.game_meta.runtime_root)
		elif OsxMapper.PLAYER_PATTERN.search(original_filename) is not None:
			match = OsxMapper.PLAYER_PATTERN.search(original_filename)
			if match.group(1) == '/Contents/MacOS/blenderplayer':
				name = '{0}/{1}.app/Contents/MacOS/{1}'.format(self.game_meta.runtime_root, self.game_meta.name)
				self.executable = '{0}/{1}.app'.format(self.game_meta.runtime_root, self.game_meta.name)
			else:
				name = '{0}/{1}.app{2}'.format(self.game_meta.runtime_root, self.game_meta.name, match.group(1))
		elif OsxMapper.ROOT_PATTERN.search(original_filename) is not None:
			match = OsxMapper.ROOT_PATTERN.search(original_filename)
			name = '{0}{1}'.format(self.game_meta.runtime_root, match.group(1))
		else:
			# Don't copy main blender app directory.
			name = None
		return name

	def patch(self, name, data):
		return data


class WinMapper:

	PATTERN = re.compile('^[^/]+(.*)$')
	EXCLUDE_PATTERNS = re.compile('^/blender\\.exe|^/BlendThumb.*\\.dll$|'
		'^/[0-9]\\.[0-9][0-9]/scripts/(?!modules)')

	def __init__(self, game_meta):
		self.game_meta = game_meta
		self.executable = None

	def apply(self, name):
		match = WinMapper.PATTERN.match(name)
		if match is None:
			return None
		sub_path = match.group(1)
		if WinMapper.EXCLUDE_PATTERNS.search(sub_path) is not None:
			name = None
		elif sub_path == '/blenderplayer.exe':
			name = '{0}/{1}.exe'.format(game_meta.runtime_root, game_meta.name)
			self.executable = name
		elif sub_path == '/copyright.txt':
			name = '{0}/Blender-copyright.txt'.format(game_meta.runtime_root)
		else:
			name = '{0}{1}'.format(game_meta.runtime_root, sub_path)
		return name

	def patch(self, name, data):
		if name == self.executable:
			print('\tPatching...')
			with open(game_meta.mainfile, 'rb') as mf:
				data = concat_game(data, mf.read())
		return data


class LinMapper:

	PATTERN = re.compile('^[^/]+(.*)$')
	EXCLUDE_PATTERNS = re.compile('^/blender$|^/blender-softwaregl$|^/blender-thumbnailer.py$|'
		'^/icons|'
		'^/[0-9]\\.[0-9][0-9]/scripts/(?!modules)')

	def __init__(self, game_meta):
		self.game_meta = game_meta
		self.executable = None

	def apply(self, name):
		match = LinMapper.PATTERN.match(name)
		if match is None:
			return None
		sub_path = match.group(1)
		if LinMapper.EXCLUDE_PATTERNS.search(sub_path) is not None:
			name = None
		elif sub_path == '/blenderplayer':
			name = '{0}/{1}'.format(game_meta.runtime_root, game_meta.name)
			self.executable = name
		elif sub_path == '/copyright.txt':
			name = '{0}/Blender-copyright.txt'.format(game_meta.runtime_root)
		else:
			name = '{0}{1}'.format(game_meta.runtime_root, sub_path)
		return name

	def patch(self, name, data):
		if name == self.executable:
			print('\tPatching...')
			with open(game_meta.mainfile, 'rb') as mf:
				data = concat_game(data, mf.read())
		return data


def package_for_osx(game_meta, exclude, blend_dist):
	# Work directly with zip file contents to avoid changing OSX file metadata.

	mapper = OsxMapper(game_meta)

	target_path = game_meta.archive_root + '.zip'
	with zipfile.ZipFile(blend_dist, 'r') as blender, \
			zipfile.ZipFile(target_path, 'w') as game:

		# First, copy over blenderplayer contents, but rename to game name
		for zi in blender.infolist():
			name = mapper.apply(zi.filename)
			if name is None:
				continue
			data = mapper.patch(zi.filename, blender.read(zi.filename))
			zi.filename = name
			print(zi.filename)
			game.writestr(zi, data)

		if mapper.executable is None:
			raise TranslationError('blenderplayer not present in archive')

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

	return target_path, mapper.executable


def package_for_win(game_meta, exclude, blend_dist):
	# Work directly with the zip file, because we can.

	mapper = WinMapper(game_meta)

	target_path = game_meta.archive_root + '.zip'
	with zipfile.ZipFile(blend_dist, 'r') as blender, \
			zipfile.ZipFile(target_path, 'w') as game:

		# First, copy over blenderplayer contents, but rename to game name.
		for zi in blender.infolist():
			name = mapper.apply(zi.filename)
			if name is None:
				continue
			data = mapper.patch(name, blender.read(zi.filename))
			zi.filename = name
			print(zi.filename)
			game.writestr(zi, data)

		if mapper.executable is None:
			raise TranslationError('blenderplayer not present in archive')

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

	return target_path, mapper.executable


def package_for_lin(game_meta, exclude, blend_dist):
	# Copy from tar to zip.

	mapper = LinMapper(game_meta)

	target_path = game_meta.archive_root + '.tar.bz2'
	with tarfile.open(blend_dist, 'r') as blender, \
			tarfile.open(target_path, 'w:bz2') as game:

		# First, copy over blenderplayer contents, but rename to game name.
		for ti in blender:
			name = mapper.apply(ti.name)
			if name is None:
				continue

			print(name)
			# Special handling for links
			if ti.type in {tarfile.LNKTYPE, tarfile.SYMTYPE}:
				ti.name = name
				game.addfile(ti)
			elif ti.type in {tarfile.DIRTYPE}:
				ti.name = name
				game.addfile(ti)
			else:
				data = blender.extractfile(ti).read()
				data = mapper.patch(name, data)
				ti.name = name
				ti.size = len(data)
				game.addfile(ti, fileobj=io.BytesIO(data))

		if mapper.executable is None:
			raise TranslationError('blenderplayer not present in archive')

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

	return target_path, mapper.executable


def concat_game(playerfile, mainfile):
	'''
	Concatenate the primary game data file onto the blenderplayer executable.
	'''
	buf = io.BytesIO()
	offset = buf.write(playerfile)
	buf.write(mainfile)

	# Store the offset (an int is 4 bytes, so we split it up into 4 bytes and save it)
	buf.write(struct.pack('B', (offset>>24)&0xFF))
	buf.write(struct.pack('B', (offset>>16)&0xFF))
	buf.write(struct.pack('B', (offset>>8)&0xFF))
	buf.write(struct.pack('B', (offset>>0)&0xFF))
	buf.write(b'BRUNTIME')
	buf.seek(0)
	return buf.read()


class ExGlobber:
	'''Filter used to exclude files.'''
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
		'''Exclude files matching this pattern.'''
		regex = fnmatch.translate(pattern)
		self.patterns.append(re.compile(regex))

	def __call__(self, filename):
		'''Returns False iff the file should be included.'''
		for p in self.patterns:
			if p.match(filename) is not None:
				return True
		return False


PACKAGERS = {
	('gnu+linux', '64'): package_for_lin,
	('gnu+linux', '32'): package_for_lin,
	('osx', '64'): package_for_osx,
	('osx', '32'): package_for_osx,
	('win', '64'): package_for_win,
	('win', '32'): package_for_win,
	}


def guess_platform(blender_dist):
	# If need be, this could peek inside the files to be sure. But for now, just
	# check file name.
	if re.search('64\\.tar(.bz2|.gz)$', blender_dist) is not None:
		return 'gnu+linux', '64'
	elif re.search('\\.tar(.bz2|.gz)$', blender_dist) is not None:
		return 'gnu+linux', '32'
	elif re.search('OSX.*64\\.zip$', blender_dist) is not None:
		return 'osx', '64'
	elif re.search('OSX.*\\.zip$', blender_dist) is not None:
		return 'osx', '32'
	elif re.search('windows64\\.zip$', blender_dist) is not None:
		return 'win', '64'
	elif re.search('windows32\\.zip$', blender_dist) is not None:
		return 'win', '32'
	else:
		raise ValueError("Can't determine target platform from archive name.")


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Package game for publishing')
	parser.add_argument('mainfile',
		help="The file to embed in the executable (startup .blend file). This will also be used to name the package.")
	parser.add_argument('asset_dir',
		help="The directory to package. The main file can be in this directory, or not.")
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
	game_meta = GameMeta(name, args.mainfile, args.asset_dir)
	if 'version' in args:
		game_meta.suffix = args.version

	if 'exclude' not in args:
		globber = ExGlobber()
	else:
		globber = ExGlobber.from_file(args.exclude)

	platform = guess_platform(args.blender_dist)
	game_meta.suffix += '-{}-{}'.format(*platform)
	packager = PACKAGERS[platform]
	archive, executable = packager(game_meta, globber, args.blender_dist)

	print('Game packaged as {}'.format(archive))
	print('To play the game, extract the archive and run `{}`'.format(executable))
