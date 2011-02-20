#
# Copyright 2009-2010 Alex Fraser <alex@phatcore.com>
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

import mathutils
from bge import logic
from bge import render
import bxt

DEBUG = False

###################
# Sensor management
###################

@bxt.utils.singleton()
class SceneManager:
	
	def __init__(self):
		self.Observers = set()
		self.NewScene = True
	
	def OnNewScene(self):
		logic.setGravity([0.0, 0.0, -75.0])
		self.NewScene = False
	
	def Subscribe(self, observer):
		'''Subscribe to the set of listeners. It is OK to call this function
		twice for the same observer.'''
		if self.NewScene:
			self.OnNewScene()
		self.Observers.add(observer)
	
	def Unsubscribe(self, observer):
		self.Observers.remove(observer)
	
	def EndScene(self):
		'''Notifies observers that they should release all game objects.
		Observers should unsubscribe themselves if they are no longer interested
		in the scene.'''
		observers = self.Observers.copy()
		for o in observers:
			o.OnSceneEnd()
		self.NewScene = True

@bxt.utils.all_sensors_positive
@bxt.utils.controller
def EndScene(c):
	'''Releases all object references (e.g. Actors). Then, all actuators are
	activated. Call this from a Python controller attached to a switch scene
	actuator instead of using an AND controller.'''
	
	SceneManager().EndScene()
	for act in c.actuators:
		c.activate(act)

class SemanticException(Exception):
	pass

def parseChildren(self, o):
	for child in o.children:
		if 'Type' in child:
			if (not self.parseChild(child, child['Type'])):
				print("Warning: child %s of %s has unexpected type (%s)" % (
					child.name,
					o.name,
					child['Type']))
