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

import bge

import bxt

from . import ui
from . import camera
from . import director
from . import store

class StoryError(Exception):
	pass

#
# Step progression conditions. These determine whether a step may execute.
#
class CondSensor:
	'''Allow the story to progress when a particular sensor is true.'''
	def __init__(self, name):
		self.Name = name

	def Evaluate(self, c):
		s = c.sensors[self.Name]
		return s.positive and s.triggered

class CondPropertyGE:
	'''Allow the story to progress when a property matches an inequality. In
	this case, when the property is greater than or equal to the given value.'''
	def __init__(self, name, value):
		self.Name = name
		self.Value = value

	def Evaluate(self, c):
		return c.owner[self.Name] >= self.Value

#
# Actions. These belong to and are executed by steps.
#
class ActSuspendInput:
	'''Prevent the player from moving around.'''
	def Execute(self, c):
		bxt.types.EventBus().notify(bxt.types.Event('SuspendPlay'))

class ActResumeInput:
	'''Let the player move around.'''
	def Execute(self, c):
		bxt.types.EventBus().notify(bxt.types.Event('ResumePlay'))

class ActActuate:
	'''Activate an actuator.'''
	def __init__(self, actuatorName):
		self.ActuatorName = actuatorName

	def Execute(self, c):
		c.activate(c.actuators[self.ActuatorName])

class ActActionPair:
	'''Play an armature action and an IPO at the same time.'''
	def __init__(self, aArmName, aMeshName, actionPrefix, start, end, loop = False):
		self.aArmName = aArmName
		self.aMeshName = aMeshName
		self.ActionPrefix = actionPrefix
		self.start = start
		self.End = end
		self.Loop = loop

	def Execute(self, c):
		aArm = c.actuators[self.aArmName]
		aMesh = c.actuators[self.aMeshName]
		aArm.action = self.ActionPrefix
		aMesh.action = self.ActionPrefix + '_S'

		aArm.frameStart = aMesh.frameStart = self.start
		aArm.frameEnd = aMesh.frameEnd = self.End
		aArm.frame = aMesh.frame = self.start

		if self.Loop:
			aArm.mode = aMesh.mode = bge.logic.KX_ACTIONACT_LOOPEND
		else:
			aArm.mode = aMesh.mode = bge.logic.KX_ACTIONACT_PLAY

		c.activate(aArm)
		c.activate(aMesh)

class ActShowDialogue:
	def __init__(self, message):
		self.message = message

	def Execute(self, c):
		evt = bxt.types.Event('ShowDialogue', self.message)
		bxt.types.EventBus().notify(evt)

class ActHideDialogue:
	def Execute(self, c):
		evt = bxt.types.Event('ShowDialogue', None)
		bxt.types.EventBus().notify(evt)

class ActShowMessage:
	def __init__(self, message):
		self.message = message

	def Execute(self, c):
		evt = bxt.types.Event('ShowMessage', self.message)
		bxt.types.EventBus().notify(evt)

class ActSetCamera:
	'''Switch to a named camera.'''
	def __init__(self, camName):
		self.CamName = camName

	def Execute(self, c):
		try:
			cam = bge.logic.getCurrentScene().objects[self.CamName]
		except KeyError:
			print(("Warning: couldn't find camera %s. Not adding." %
				self.CamName))
			return
		camera.AutoCamera().add_goal(cam)

class ActRemoveCamera:
	def __init__(self, camName):
		self.CamName = camName

	def Execute(self, c):
		try:
			cam = bge.logic.getCurrentScene().objects[self.CamName]
		except KeyError:
			print(("Warning: couldn't find camera %s. Not removing." %
				self.CamName))
			return
		camera.AutoCamera().remove_goal(cam)

class ActGeneric:
	'''Run any function.'''
	def __init__(self, f, *args):
		self.Function = f
		self.args = args

	def Execute(self, c):
		try:
			self.Function(*self.args)
		except Exception as e:
			raise StoryError("Error executing " + str(self.Function), e)

class ActGenericContext(ActGeneric):
	'''Run any function, passing in the current controller as the first
	argument.'''
	def Execute(self, c):
		try:
			self.Function(c, *self.args)
		except Exception as e:
			raise StoryError("Error executing " + str(self.Function), e)

class ActEvent:
	'''Fire an event.'''
	def __init__(self, event):
		self.event = event

	def Execute(self, c):
		bxt.types.EventBus().notify(self.event)

class ActDebug:
	'''Print a debugging message to the console.'''
	def __init__(self, message):
		self.message = message

	def Execute(self, c):
		print(self.message)

#
# Steps. These are executed by Characters when their conditions are met and they
# are at the front of the queue.
#
class Step:
	'''A collection of Conditions and Actions. This should be placed in a queue
	(see Character.NewStep()). When this step is at the front of the queue, its
	actions will be executed when all conditions are true.'''

	def __init__(self):
		self.Conditions = []
		self.Actions = []

	def AddAction(self, action):
		self.Actions.append(action)

	def AddCondition(self, cond):
		self.Conditions.append(cond)

	def CanExecute(self, c):
		for condition in self.Conditions:
			if not condition.Evaluate(c):
				return False
		return True

	def Execute(self, c):
		for act in self.Actions:
			try:
				print(act)
				act.Execute(c)
			except Exception as e:
				print("Warning: Action %s failed." % act)
				print(e)

class Character(bxt.types.BX_GameObject):
	'''Embodies a story in the scene. Subclass this to define the story
	(override CreateSteps). Then call Progress on each frame to allow the steps
	to be executed.'''

	_prefix = ''

	def __init__(self, old_owner):
		self.NextStep = 0
		self.Steps = []
		self.CreateSteps()
		self.setCyclic(False)

	def setCyclic(self, value):
		self.Cyclic = value

	def NewStep(self):
		step = Step()
		self.Steps.append(step)
		return step

	@bxt.types.expose
	@bxt.utils.controller_cls
	def Progress(self, controller):
		if self.NextStep >= len(self.Steps):
			if self.Cyclic:
				# Loop.
				self.NextStep = 0
			else:
				# Finished.
				return

		step = self.Steps[self.NextStep]
		print(step)
		if step.CanExecute(controller):
			step.Execute(controller)
			self.NextStep = self.NextStep + 1

	def CreateSteps(self):
		pass

def activate_portal(c):
	'''Loads the next level, based on the properties of the owner.

	Properties:
		level: The name of the .blend file to load.
		spawnPoint: The name of the spawn point that the player should start at.
	'''
	if director.Director().mainCharacter in c.sensors[0].hitObjectList:
		portal = c.owner
		print('Loading next level: %s, %s' % (portal['level'], portal['spawnPoint']))
		store.set('/game/levelFile', portal['level'])
		store.set('/game/level/spawnPoint', portal['spawnPoint'])
		store.save()
		bge.logic.startGame(portal['level'])
