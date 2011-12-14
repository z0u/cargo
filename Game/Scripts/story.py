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
import mathutils

import bxt

from . import ui
from . import camera
from . import director
from . import store

GRAVITY = 75.0

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
class BaseAct:
	def execute(self, c):
		pass

	def __str__(self):
		return self.__class__.__name__

class ActSuspendInput(BaseAct):
	'''Prevent the player from moving around.'''
	def execute(self, c):
		bxt.types.EventBus().notify(bxt.types.Event('SuspendPlay'))

class ActResumeInput(BaseAct):
	'''Let the player move around.'''
	def execute(self, c):
		bxt.types.EventBus().notify(bxt.types.Event('ResumePlay'))

class ActActuate(BaseAct):
	'''Activate an actuator.'''
	def __init__(self, actuatorName):
		self.ActuatorName = actuatorName

	def execute(self, c):
		c.activate(c.actuators[self.ActuatorName])

	def __str__(self):
		return "ActActuate: %s" % self.ActuatorName

class ActActionPair(BaseAct):
	'''Play an armature action and an IPO at the same time.'''
	def __init__(self, aArmName, aMeshName, actionPrefix, start, end, loop = False):
		self.aArmName = aArmName
		self.aMeshName = aMeshName
		self.ActionPrefix = actionPrefix
		self.start = start
		self.End = end
		self.Loop = loop

	def execute(self, c):
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

	def __str__(self):
		return "ActActionPair: %s, %d -> %d" % (self.ActionPrefix, self.start,
				self.End)

class ActShowDialogue(BaseAct):
	def __init__(self, message):
		self.message = message

	def execute(self, c):
		evt = bxt.types.Event('ShowDialogue', self.message)
		bxt.types.EventBus().notify(evt)

	def __str__(self):
		return 'ActShowDialogue: "%s"' % self.message

class ActHideDialogue(BaseAct):
	def execute(self, c):
		evt = bxt.types.Event('ShowDialogue', None)
		bxt.types.EventBus().notify(evt)

class ActShowMessage(BaseAct):
	def __init__(self, message):
		self.message = message

	def execute(self, c):
		evt = bxt.types.Event('ShowMessage', self.message)
		bxt.types.EventBus().notify(evt)

	def __str__(self):
		return 'ActShowMessage: "%s"' % self.message

class ActSetCamera(BaseAct):
	'''Switch to a named camera.'''
	def __init__(self, camName):
		self.CamName = camName

	def execute(self, c):
		try:
			cam = bge.logic.getCurrentScene().objects[self.CamName]
		except KeyError:
			print(("Warning: couldn't find camera %s. Not adding." %
				self.CamName))
			return
		camera.AutoCamera().add_goal(cam)

	def __str__(self):
		return "ActSetCamera: %s" % self.CamName

class ActRemoveCamera(BaseAct):
	def __init__(self, camName):
		self.CamName = camName

	def execute(self, c):
		try:
			cam = bge.logic.getCurrentScene().objects[self.CamName]
		except KeyError:
			print(("Warning: couldn't find camera %s. Not removing." %
				self.CamName))
			return
		camera.AutoCamera().remove_goal(cam)

	def __str__(self):
		return "ActRemoveCamera: %s" % self.CamName

class ActGeneric(BaseAct):
	'''Run any function.'''
	def __init__(self, f, *args):
		self.Function = f
		self.args = args

	def execute(self, c):
		try:
			self.Function(*self.args)
		except Exception as e:
			raise StoryError("Error executing " + str(self.Function), e)

	def __str__(self):
		return "ActGeneric: %s" % self.Function

class ActGenericContext(ActGeneric):
	'''Run any function, passing in the current controller as the first
	argument.'''
	def execute(self, c):
		try:
			self.Function(c, *self.args)
		except Exception as e:
			raise StoryError("Error executing " + str(self.Function), e)

class ActEvent(BaseAct):
	'''Fire an event.'''
	def __init__(self, event):
		self.event = event

	def execute(self, c):
		bxt.types.EventBus().notify(self.event)

	def __str__(self):
		return "ActEvent: %s" % self.event.message

class ActDebug(BaseAct):
	'''Print a debugging message to the console.'''
	def __init__(self, message):
		self.message = message

	def execute(self, c):
		print(self.message)

#
# Steps. These are executed by Characters when their conditions are met and they
# are at the front of the queue.
#
class Step:
	'''A collection of Conditions and Actions. This should be placed in a queue
	(see Character.NewStep()). When this step is at the front of the queue, its
	actions will be executed when all conditions are true.'''

	def __init__(self, name=""):
		self.name = name
		self.Conditions = []
		self.Actions = []

	def AddAction(self, action):
		self.Actions.append(action)

	def AddEvent(self, message, body):
		evt = bxt.types.Event(message, body)
		self.Actions.append(ActEvent(evt))

	def AddWeakEvent(self, message, body):
		evt = bxt.types.WeakEvent(message, body)
		self.Actions.append(ActEvent(evt))

	def AddCondition(self, cond):
		self.Conditions.append(cond)

	def CanExecute(self, c):
		for condition in self.Conditions:
			if not condition.Evaluate(c):
				return False
		return True

	def execute(self, c):
		if self.name != "":
			print("== Step {} ==".format(self.name))
		else:
			print("== Step ==")
		for act in self.Actions:
			try:
				print(act)
				act.execute(c)
			except Exception as e:
				print("Warning: Action %s failed." % act)
				print("\t%s" % e)

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

	def NewStep(self, name=""):
		step = Step(name)
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
		if step.CanExecute(controller):
			step.execute(controller)
			self.NextStep = self.NextStep + 1

	def CreateSteps(self):
		pass

class Level(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	'''Embodies a level. By default, this just sets some common settings when
	initialised. This should not be included in cut scenes etc; just in scenes
	where the player can move around.'''

	def __init__(self, old_owner):
		# Adjust gravity to be appropriate for the size of the scene..
		g = mathutils.Vector((0.0, 0.0, 0 - GRAVITY))
		bge.logic.setGravity(g)
		evt = bxt.types.Event('GravityChanged', g)
		bxt.types.EventBus().notify(evt)

		evt = bxt.types.Event('GameModeChanged', 'Playing')
		bxt.types.EventBus().notify(evt)

class GameLevel(Level):
	'''A level that is part of the main game. Handles things such as spawn
	points and level transitions. Test scenes may use these too, but it is not
	required.'''

	def __init__(self, old_owner):
		Level.__init__(self, old_owner)

		scene = bge.logic.getCurrentScene()
		spawnPointName = store.get('/game/spawnPoint',
				self['defaultSpawnPoint'])
		spawnPoint = None
		try:
			spawnPoint = scene.objects[spawnPointName]
		except KeyError:
			print("Error: spawn point %s not found." % spawnPointName)
			spawnPoint = scene.objects[self['defaultSpawnPoint']]
		print("Spawning snail at %s" % spawnPoint.name)
		bxt.types.add_and_mutate_object(scene, 'Snail', spawnPoint)

		bxt.types.EventBus().add_listener(self)

		evt = bxt.types.WeakEvent('Spawned', spawnPoint)
		bxt.types.EventBus().notify(evt)

	def on_event(self, event):
		if event.message == "LoadLevel":
			bge.logic.startGame(event.body)

def load_level(caller, level, spawnPoint):
	print('Loading next level: %s, %s' % (level, spawnPoint))
	store.set('/game/levelFile', level)
	store.set('/game/spawnPoint', spawnPoint)
	store.save()

	evt = bxt.types.WeakEvent('StartLoading', caller)
	bxt.types.EventBus().notify(evt)

	evt = bxt.types.Event('LoadLevel', level)
	bxt.types.EventBus().notify(evt, 2)

def activate_portal(c):
	'''Loads the next level, based on the properties of the owner.

	Properties:
		level: The name of the .blend file to load.
		spawnPoint: The name of the spawn point that the player should start at.
	'''
	if director.Director().mainCharacter in c.sensors[0].hitObjectList:
		portal = c.owner
		load_level(portal, portal['level'], portal['spawnPoint'])
