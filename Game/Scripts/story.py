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

from sys import stdout

import bge
import mathutils
import aud

import bxt

from . import ui
from . import camera
from . import director
from . import store
import time

DEBUG = False
log = bxt.utils.get_logger(DEBUG)

GRAVITY = 75.0

class StoryError(Exception):
	pass

#
# Step progression conditions. These determine whether a step may execute.
#
class Condition:
	def enable(self, enabled):
		pass

class CondSensor(Condition):
	'''Allow the story to progress when a particular sensor is true.'''
	def __init__(self, name):
		self.Name = name

	def evaluate(self, c):
		s = c.sensors[self.Name]
		return s.positive and s.triggered

class CondPropertyGE(Condition):
	'''Allow the story to progress when a property matches an inequality. In
	this case, when the property is greater than or equal to the given value.'''
	def __init__(self, name, value):
		self.Name = name
		self.Value = value

	def evaluate(self, c):
		return c.owner[self.Name] >= self.Value

class CondActionGE(Condition):
	def __init__(self, layer, frame, tap=False):
		'''
		@param layer: The animation layer to watch.
		@param frame: The frame to trigger from.
		@param tap: If True, the condition will only evaluate True once while
			the current frame is increasing. If the current frame decreases (as
			it may when an animation is looping) the condition will be reset,
			and may trigger again.
		'''
		self.layer = layer
		self.frame = frame

		self.tap = tap
		self.triggered = False
		self.lastFrame = frame - 1

	def evaluate(self, c):
		cfra = c.owner.getActionFrame(self.layer)
		if not self.tap:
			# Simple mode
			return cfra >= self.frame
		else:
			# Memory (loop) mode
			if self.lastFrame > cfra:
				self.triggered = False
			if not self.triggered and cfra >= self.frame:
				self.triggered = True
				return True
			self.lastFrame = cfra

class CondEvent(Condition):
	def __init__(self, message):
		self.message = message
		self.triggered = False

	def enable(self, enabled):
		# This should not result in a memory leak, because the EventBus uses a
		# WeakSet to store the listeners. Thus when the object that owns this
		# state machine dies, so will this condition, and it will be removed
		# from the EventBus.
		if enabled:
			bxt.types.EventBus().add_listener(self)
		else:
			bxt.types.EventBus().remove_listener(self)
			self.triggered = False

	def on_event(self, evt):
		if evt.message == self.message:
			self.triggered = True

	def evaluate(self, c):
		return self.triggered

class CondWait(Condition):
	'''A condition that waits for a certain time after being enabled.'''
	def __init__(self, duration):
		self.duration = duration
		self.start = None
		self.triggered = False

	def enable(self, enabled):
		if enabled:
			self.start = time.time()
		else:
			self.start = None

	def evaluate(self, c):
		return time.time() - self.duration > self.start

#
# Actions. These belong to and are executed by steps.
#
class BaseAct:
	def execute(self, c):
		pass

	def __str__(self):
		return self.__class__.__name__

class ActStoreSet(BaseAct):
	'''Write to the save game file.'''
	def __init__(self, path, value):
		self.path = path
		self.value = value

	def execute(self, c):
		store.set(self.path, self.value)

class ActSuspendInput(BaseAct):
	'''Prevent the player from moving around.'''
	def execute(self, c):
		bxt.types.EventBus().notify(bxt.types.Event('SuspendInput', True))

class ActResumeInput(BaseAct):
	'''Let the player move around.'''
	def execute(self, c):
		bxt.types.EventBus().notify(bxt.types.Event('SuspendInput', False))

class ActActuate(BaseAct):
	'''Activate an actuator.'''
	def __init__(self, actuatorName):
		self.ActuatorName = actuatorName

	def execute(self, c):
		c.activate(c.actuators[self.ActuatorName])

	def __str__(self):
		return "ActActuate: %s" % self.ActuatorName

class ActAction(BaseAct):
	def __init__(self, action, start, end, layer, targetDescendant=None,
			play_mode=bge.logic.KX_ACTION_MODE_PLAY):
		self.action = action
		self.start = start
		self.end = end
		self.layer = layer
		self.targetDescendant = targetDescendant
		self.playMode = play_mode

	def execute(self, c):
		ob = c.owner
		if self.targetDescendant != None:
			ob = ob.childrenRecursive[self.targetDescendant]
		ob.playAction(self.action, self.start, self.end, self.layer,
			play_mode=self.playMode)

	def __str__(self):
		return "ActAction: %s, %d -> %d" % (self.action, self.start, self.end)

class ActSound(BaseAct):
	'''Plays a short sound.'''

	def __init__(self, filename, vol=1, pitchmin=1, pitchmax=1, delay=0):
		self.filename = bge.logic.expandPath(filename)
		self.volume = vol
		self.pitchmin = pitchmin
		self.pitchmax = pitchmax
		self.delay = delay
		self._factory = None

	def _get_factory(self):
		if self._factory == None:
			f = aud.Factory.file(self.filename)
			if self.volume != 1:
				f = f.volume(self.volume)
			if self.delay > 0:
				f = f.delay(self.delay)
			self._factory = f
		return self._factory
	factory = property(_get_factory) 

	def execute(self, c):
		f = self.factory
		if self.pitchmax != 1 or self.pitchmin != 1:
			pitch = bxt.bmath.lerp(self.pitchmin, self.pitchmax,
					bge.logic.getRandomFloat())
			f = f.pitch(pitch)

		# Play the sound, and throw away the handle.
		dev = aud.device()
		dev.play(f)

	def __str__(self):
		return "ActSound: %s" % self.filename

class ActShowDialogue(BaseAct):
	def __init__(self, message):
		self.message = message

	def execute(self, c):
		bxt.types.Event('ShowDialogue', self.message).send()

	def __str__(self):
		return 'ActShowDialogue: "%s"' % self.message

class ActHideDialogue(BaseAct):
	def execute(self, c):
		bxt.types.Event('ShowDialogue', None).send()

class ActShowMessage(BaseAct):
	def __init__(self, message):
		self.message = message

	def execute(self, c):
		bxt.types.Event('ShowMessage', self.message).send()

	def __str__(self):
		return 'ActShowMessage: "%s"' % self.message

class ActShowMarker(BaseAct):
	'''Show a marker on the screen that points to an object.'''

	target = bxt.types.weakprop("target")

	def __init__(self, target):
		self.target = target

	def execute(self, c):
		bxt.types.WeakEvent('ShowMarker', self.target).send()

	def __str__(self):
		if self.target is not None:
			name = self.target.name
		else:
			name = "None"
		return 'ActShowMarker: "%s"' % name

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

class ActSetFocalPoint(BaseAct):
	'''Focus on a named object.'''
	def __init__(self, targetName):
		self.targetName = targetName

	def execute(self, c):
		try:
			target = bge.logic.getCurrentScene().objects[self.targetName]
		except KeyError:
			print(("Warning: couldn't find focus point %s. Not adding." %
				self.targetName))
			return
		camera.AutoCamera().add_focus_point(target)

	def __str__(self):
		return "ActSetFocalPoint: %s" % self.targetName

class ActRemoveFocalPoint(BaseAct):
	def __init__(self, targetName):
		self.targetName = targetName

	def execute(self, c):
		try:
			target = bge.logic.getCurrentScene().objects[self.targetName]
		except KeyError:
			print(("Warning: couldn't find focus point %s. Not removing." %
				self.targetName))
			return
		camera.AutoCamera().remove_focus_point(target)

	def __str__(self):
		return "ActRemoveFocalPoint: %s" % self.targetName

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
		return "ActGeneric: %s" % self.Function.__name__

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

class ActDestroy(BaseAct):
	'''Remove the object from the scene.'''
	def execute(self, c):
		c.owner.endObject()

#
# Steps. These are executed by Characters when their conditions are met and they
# are at the front of the queue.
#
class State:
	'''These comprise state machines that may be used to drive a scripted
	sequence, e.g. a dialogue with a non-player character.

	A State may have links to other states; these links are called
	'transitions'. When a State is active, its transitions will be polled
	repeatedly. When a transitions' conditions all test positive, it will be
	made the next active State. At that time, all actions associated with it
	will be executed.

	@see: Chapter'''

	def __init__(self, name=""):
		self.name = name
		self.conditions = []
		self.actions = []
		self.transitions = []
		self.subSteps = []

	def addCondition(self, condition):
		'''Conditions control transition to this state.'''
		self.conditions.append(condition)

	def addAction(self, action):
		'''Actions will run when this state becomes active.'''
		self.actions.append(action)

	def addEvent(self, message, body):
		'''Convenience method to add an ActEvent action.'''
		evt = bxt.types.Event(message, body)
		self.actions.append(ActEvent(evt))

	def addWeakEvent(self, message, body):
		'''Convenience method to add an ActEvent action.'''
		evt = bxt.types.WeakEvent(message, body)
		self.actions.append(ActEvent(evt))

	def addTransition(self, state):
		'''Transitions are other states.'''
		self.transitions.append(state)

	def createTransition(self, stateName=""):
		'''Create a new State and add it as a transition of this one.
		@return: the new state.'''
		s = State(stateName)
		self.addTransition(s)
		return s

	def addSubStep(self, state):
		self.subSteps.append(state)

	def createSubStep(self, stateName=""):
		s = State(stateName)
		self.addSubStep(s)
		return s

	def activate(self, c):
		for state in self.transitions:
			state.parent_activated(True)
		for state in self.subSteps:
			state.parent_activated(True)
		self.execute(c)

	def deactivate(self):
		for state in self.transitions:
			state.parent_activated(False)
		for state in self.subSteps:
			state.parent_activated(False)

	def parent_activated(self, activated):
		for condition in self.conditions:
			condition.enable(activated)

	def execute(self, c):
		'''Run all actions associated with this state.'''
		for act in self.actions:
			try:
				log(act)
				act.execute(c)
			except Exception as e:
				log("Warning: Action %s failed." % act)
				log("\t%s" % e)

	def progress(self, c):
		'''Find the next state that has all conditions met, or None if no such
		state exists.'''
		for state in self.subSteps:
			if state.test(c):
				state.execute(c)

		# Clear line
		log.write("\r")
		log.write("Transition: ")
		target = None
		for state in self.transitions:
			log.write("{}(".format(state.name))
			if state.test(c):
				log.write(") ")
				target = state
				break
			log.write(") ")
		log.flush()
		return target

	def test(self, c):
		'''Check whether this state is ready to be transitioned to.'''
		for condition in self.conditions:
			if not condition.evaluate(c):
				log.write("x")
				return False
			else:
				log.write("o")
		return True

	def __str__(self):
		return "== State {} ==".format(self.name)

class Chapter(bxt.types.BX_GameObject):
	'''Embodies a story in the scene. Subclass this to define the story
	(add transitions to self.rootState). Then call 'progress' on each frame to
	allow the steps to be executed.'''

	_prefix = ''

	def __init__(self, old_owner):
		self.rootState = State(name="Root")
		self.currentState = self.rootState

	@bxt.types.expose
	@bxt.utils.controller_cls
	def progress(self, c):
		if self.currentState != None:
			nextState = self.currentState.progress(c)
			if nextState != None:
				log()
				self.currentState.deactivate()
				self.currentState = nextState
				log(self.currentState)
				self.currentState.activate(c)

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
			# Listen for load events from portals.
			level = store.get('/game/levelFile')
			bge.logic.startGame(level)

def load_level(caller, level, spawnPoint):
	print('Loading next level: %s, %s' % (level, spawnPoint))

	store.set('/game/levelFile', level)
	store.set('/game/spawnPoint', spawnPoint)
	store.save()

	callback = bxt.types.Event('LoadLevel')

	# Start showing the loading screen. When it has finished, the LoadLevel
	# event defined above will be sent, and received by GameLevel.
	bxt.types.Event('ShowLoadingScreen', (True, callback)).send()

def activate_portal(c):
	'''Loads the next level, based on the properties of the owner.

	Properties:
		level: The name of the .blend file to load.
		spawnPoint: The name of the spawn point that the player should start at.
	'''
	if director.Director().mainCharacter in c.sensors[0].hitObjectList:
		portal = c.owner
		load_level(portal, portal['level'], portal['spawnPoint'])
