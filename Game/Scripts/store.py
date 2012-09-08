#
# Copyright 2010 Alex Fraser <alex@phatcore.com>
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

import bxt.utils

DEBUG = False

__dirty = False

def get_session_id():
	'''Get the ID of the current session.'''
	try:
		return bge.logic.globalDict['/_sessionId']
	except KeyError:
		return 0

def set_session_id(identifier):
	'''Set the ID of the current session.'''
	global __dirty
	bge.logic.globalDict['/_sessionId'] = identifier
	__dirty = True

def resolve(path, session=None, level=None):
	if session is None:
		session = str(get_session_id())
	rp = str(path).replace('/game/', '/savedGames/%s/' % str(session), 1)
	if '/level/' in rp:
		if level is None:
			level = get('/game/levelFile', session=session)
		rp = str(rp).replace('/level/', '/_levels/%s/' % str(level), 1)
	return rp

def get(path, defaultValue=None, session=None, level=None):
	'''
	Get a value from persistent storage. By convention, there are three well-
	known base paths:
	 - /opt/: Global options.
	 - /_savedGames/N/: Data specific to saved game 'N'.
	 - /game/: Data specific to the current game, as determined by get_session_id.
			  E.g. if the current session is game 0, /game/ == /_savedGames/0/.
			  NOTE: The path must start with '/game/', not '/game'.
	 - /level/: Data specific to the current level in the current game.
	 		  E.g. /game/level/ == /_savedGames/0/_levels/Dungeon.blend/
	These conventions will not change, so you can use them in scripts or bind
	them to Blender objects.

	Parameters:
	defaultValue: The value to return if 'path' can't be found. Remember that
		None, zero, empty strings and empty lists all evaluate as False. Most
		other things evaluate as True.
	'''

	p = resolve(path, session=session, level=level)
	try:
		if DEBUG:
			print("store.get(%s) ->" % p, bge.logic.globalDict[p])
		return bge.logic.globalDict[p]
	except KeyError:
		if DEBUG:
			print("store.get(%s) ->" % p, defaultValue)
		put(p, defaultValue)
		return defaultValue

def put(path, value, session=None, level=None):
	'''Set a value in persistent storage. The data will be saved to file the
	next time save() is called.'''
	p = resolve(path, session=session, level=level)
	global __dirty
	if DEBUG:
		print("store.put(%s) <-" % p, value)
	bge.logic.globalDict[p] = value
	__dirty = True

def unset(path, session=None, level=None):
	'''Delete a value from persistent storage.'''
	global __dirty

	p = resolve(path, session=session, level=level)
	if p in bge.logic.globalDict:
		if DEBUG:
			print("store.unset(%s)" % p)
		del(bge.logic.globalDict[p])
		__dirty = True

def search(path='/', session=None, level=None):
	'''Returns a copy of the store keys for iteration.'''
	p = resolve(path, session=session, level=level)
	keys = []
	for k in bge.logic.globalDict.keys():
		if k.startswith(p):
			keys.append(k)
	return keys

def _save():
	global __dirty

	bge.logic.saveGlobalDict()
	__dirty = False

def _load():
	global __dirty

	bge.logic.loadGlobalDict()
	__dirty = False

# Load once on initialisation.
_load()

@bxt.utils.all_sensors_positive
def save():
	'''Save the data to a file. This should be called periodically - it will
	only actually write the file if the settings have changed.'''
	if __dirty:
		_save()
		print('Game saved.')
