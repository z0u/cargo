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
from . import Utilities

current = 0
def getSessionId():
    '''Get the ID of the current session.'''
    return current

def setSessionId(id):
    '''Set the ID of the current session.'''
    global current
    current = id

def resolve(path):
    return str(path).replace('/game', '/savedGames/' + str(getSessionId()), 1)

def get(path, defaultValue = None):
    '''
    Get a value from persistent storage. By convention, there are three well-
    known base paths:
     - /opt: Global options.
     - /savedGames/N: Data specific to saved game 'N'.
     - /game: Data specific to the current game, as determined by getSessionId.
              E.g. if the current session is game 0, /game == /savedGames/0.
    These conventions will not change, so you can use them in scripts or bind
    them to Blender objects.
    
    Parameters:
    defaultValue: The value to return if 'path' can't be found. Remember that
        None, zero, empty strings and empty lists all evaluate as False. Most
        other things evaluate as True.
    '''
    
    p = resolve(path)
    try:
        return bge.logic.globalDict[p]
    except KeyError:
        set(path, defaultValue)
        return defaultValue

dirty = False
def set(path, value):
    '''Set a value in persistent storage. The data will be saved to file the
    next time save() is called.'''
    global dirty
    
    p = resolve(path)
    if (not p in bge.logic.globalDict) or (not bge.logic.globalDict[p] == value):
        bge.logic.globalDict[p] = value
        dirty = True

def _save():
    global dirty
    
    bge.logic.saveGlobalDict()
    dirty = False

def _load():
    global dirty
    
    bge.logic.loadGlobalDict()
    dirty = False

# Load once on initialisation.
_load()

def save(c):
    '''Save the data to a file. This should be called periodically.'''
    if not Utilities.allSensorsPositive(c):
        return
    
    if dirty:
        _save()
