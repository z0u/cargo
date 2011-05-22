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

from bge import logic
import bxt

__dirty = False

def getSessionId():
	'''Get the ID of the current session.'''
	try:
		return logic.globalDict['/_sessionId']
	except KeyError:
		return 0

def setSessionId(id):
	'''Set the ID of the current session.'''
	global __dirty
	logic.globalDict['/_sessionId'] = id
	__dirty = True

def resolve(path):
	rp = str(path).replace('/game/', '/savedGames/%s/' % str(getSessionId()), 1)
	if '/level/' in rp:
		level = get('/game/levelFile')
		rp = str(rp).replace('/level/', '/_levels/%s/' % level, 1)
	return rp

def get(path, defaultValue = None):
	'''
	Get a value from persistent storage. By convention, there are three well-
	known base paths:
	 - /opt/: Global options.
	 - /_savedGames/N/: Data specific to saved game 'N'.
	 - /game/: Data specific to the current game, as determined by getSessionId.
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

	p = resolve(path)
	try:
		print('get', p, logic.globalDict[p])
		return logic.globalDict[p]
	except KeyError:
		set(path, defaultValue)
		return defaultValue

def set(path, value):
	'''Set a value in persistent storage. The data will be saved to file the
	next time save() is called.'''
	global __dirty

	p = resolve(path)
	print('set', p, value)
	if (not p in logic.globalDict) or (not logic.globalDict[p] == value):
		logic.globalDict[p] = value
		__dirty = True

def unset(path):
	'''Delete a value from persistent storage.'''
	global __dirty

	p = resolve(path)
	print('unset', p)
	if p in logic.globalDict:
		del(logic.globalDict[p])
		__dirty = True

def list(path='/'):
	'''Returns a copy of the store keys for iteration.'''
	p = resolve(path)
	keys = []
	for k in logic.globalDict.keys():
		if k.startswith(p):
			keys.append(k)
	return keys

def _save():
	global __dirty

	logic.saveGlobalDict()
	__dirty = False

def _load():
	global __dirty

	logic.loadGlobalDict()
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
