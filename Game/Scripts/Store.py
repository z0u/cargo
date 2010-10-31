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

class Path:
    '''A helper class for '''
    def __init__(self, path):
        self.path = str(path)
    
    def __add__(self, subPath):
        return Path(self.path + '/' + str(subPath))
    
    def __str__(self):
        return self.path
    
    def __repr__(self):
        return 'Path(%s)' % self.path

P_SAVES = Path('sg')

'''Global options, e.g. options/musicVolume'''
P_OPTS = Path('options')

def getGameP(id):
    return P_SAVES + id

current = 0
def getCurrentP():
    '''Get the base path of the current saved game.'''
    return getGameP(current)

def setCurrent(id):
    global current
    current = id

def get(path, defaultValue = None):
    '''
    Get a value from persistent storage.
    
    Parameters:
    defaultValue: The value to return if 'path' can't be found. Remember that
        None, zero, empty strings and empty lists all evaluate as False. Most
        other things evaluate as True.
    '''
    
    try:
        return bge.logic.globalDict[str(path)]
    except KeyError:
        bge.logic.globalDict[str(path)] = defaultValue
        return defaultValue

dirty = False
def set(path, value):
    '''Set a value in persistent storage. The data will be saved to file the
    next time save() is called.'''
    global dirty
    
    if not bge.logic.globalDict[str(path)] == value:
        bge.logic.globalDict[str(path)] = value
        dirty = True

def _save():
    global dirty
    
    bge.logic.saveGlobalDict()
    print('saved')
    dirty = False

def _load():
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
