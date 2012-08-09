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
import time

import bge
import mathutils
import aud

import bxt

from . import ui
from . import camera
from . import director
from . import store
from . import impulse
from . import inventory
from . import jukebox

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

	def evaluate(self):
		raise NotImplementedError()

	def get_short_name(self):
		raise NotImplementedError()

	def find_source(self, c, ob_or_name, descendant_name=None):
		ob = ob_or_name
		if ob is None:
			ob = c.owner
		elif isinstance(ob, str):
			ob = bge.logic.getCurrentScene().objects[ob]

		if descendant_name is not None:
			ob = ob.childrenRecursive[descendant_name]

		return ob

class CNot(Condition):
	'''Inverts a condition.'''
	def __init__(self, wrapped):
		self.wrapped = wrapped

	def evaluate(self, c):
		return not self.wrapped.evaluate(c)

	def get_short_name(self):
		return self.wrapped.get_short_name()

class CondSensor(Condition):
	'''Allow the story to progress when a particular sensor is true.'''
	def __init__(self, name):
		self.Name = name

	def evaluate(self, c):
		s = c.sensors[self.Name]
		return s.positive

	def get_short_name(self):
		return " SE"

class CondSensorNot(Condition):
	'''Allow the story to progress when a particular sensor is false.'''
	def __init__(self, name):
		self.Name = name

	def evaluate(self, c):
		s = c.sensors[self.Name]
		return not s.positive

	def get_short_name(self):
		return " SN"

class CondPropertyGE(Condition):
	'''Allow the story to progress when a property matches an inequality. In
	this case, when the property is greater than or equal to the given value.'''
	def __init__(self, name, value):
		self.Name = name
		self.Value = value

	def evaluate(self, c):
		return c.owner[self.Name] >= self.Value

	def get_short_name(self):
		return "PGE"

class CondActionGE(Condition):
	def __init__(self, layer, frame, tap=False, ob=None, targetDescendant=None):
		'''
		@param layer: The animation layer to watch.
		@param frame: The frame to trigger from.
		@param tap: If True, the condition will only evaluate True once while
			the current frame is increasing. If the current frame decreases (as
			it may when an animation is looping) the condition will be reset,
			and may trigger again. This is often required for sub-steps;
			otherwise, the actions will trigger every frame until the parent
			progresses to the next state. This is especially true for starting
			animations and sounds.
		@param ob: The object whose action should be tested. If None, the object
			that evaluates this condition is used.
		'''
		self.layer = layer
		self.frame = frame
		self.ob = ob
		self.descendant_name = targetDescendant

		self.tap = tap
		self.triggered = False
		self.lastFrame = frame - 1

	def evaluate(self, c):
		ob = self.find_source(c, self.ob, self.descendant_name)

		cfra = ob.getActionFrame(self.layer)
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

	def get_short_name(self):
		return "AGE"

class CondEvent(Condition):
	'''
	Continue if an event is received.
	'''
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

	def get_short_name(self):
		return " EV"

class CondEventEq(Condition):
	'''
	Continue if an event is received, and its body is equal to the specified
	value.
	'''
	def __init__(self, message, body):
		self.message = message
		self.body = body
		self.triggered = False

	def enable(self, enabled):
		if enabled:
			bxt.types.EventBus().add_listener(self)
		else:
			bxt.types.EventBus().remove_listener(self)
			self.triggered = False

	def on_event(self, evt):
		if evt.message == self.message and evt.body == self.body:
			self.triggered = True

	def evaluate(self, c):
		return self.triggered

	def get_short_name(self):
		return " EE"

# This cannot be replaced by CNot(CondEventEq)
class CondEventNe(Condition):
	'''
	Continue if an event is received, and its body is NOT equal to the specified
	value. Note that this will not be True until the event is received;
	therefore, this is NOT equivalent to CNot(CondEventEq).
	'''
	def __init__(self, message, body):
		self.message = message
		self.body = body
		self.triggered = False

	def enable(self, enabled):
		if enabled:
			bxt.types.EventBus().add_listener(self)
		else:
			bxt.types.EventBus().remove_listener(self)
			self.triggered = False

	def on_event(self, evt):
		if evt.message == self.message and evt.body != self.body:
			self.triggered = True

	def evaluate(self, c):
		return self.triggered

	def get_short_name(self):
		return "ENE"

class CondStore(Condition):
	def __init__(self, path, value, default=None):
		self.path = path
		self.value = value
		self.default = default

	def evaluate(self, c):
		return self.value == store.get(self.path, self.default)

	def get_short_name(self):
		return "StE"

class CondHasShell(Condition):
	def __init__(self, name):
		self.name = name

	def evaluate(self, c):
		return self.name in inventory.Shells().get_shells()

	def get_short_name(self):
		return " HS"

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

	def get_short_name(self):
		return "  W"

#
# Actions. These belong to and are executed by steps.
#
class BaseAct:
	def execute(self, c):
		pass

	def __str__(self):
		return self.__class__.__name__

	def find_target(self, c, ob_or_name, descendant_name=None):
		ob = ob_or_name
		if ob is None:
			ob = c.owner
		elif isinstance(ob, str):
			ob = bge.logic.getCurrentScene().objects[ob]

		if descendant_name is not None:
			ob = ob.childrenRecursive[descendant_name]

		return ob

class ActStoreSet(BaseAct):
	'''Write to the save game file.'''
	def __init__(self, path, value):
		self.path = path
		self.value = value

	def execute(self, c):
		store.put(self.path, self.value)

class ActSuspendInput(BaseAct):
	'''Prevent the player from moving around.'''
	def execute(self, c):
		bxt.types.Event('GameModeChanged', 'Cutscene').send()

class ActResumeInput(BaseAct):
	'''Let the player move around.'''
	def execute(self, c):
		bxt.types.Event('GameModeChanged', 'Playing').send()

class ActActuate(BaseAct):
	'''Activate an actuator.'''
	def __init__(self, actuatorName):
		self.ActuatorName = actuatorName

	def execute(self, c):
		c.activate(c.actuators[self.ActuatorName])

	def __str__(self):
		return "ActActuate: %s" % self.ActuatorName

class ActAction(BaseAct):
	'''Plays an animation.'''
	def __init__(self, action, start, end, layer, targetDescendant=None,
			play_mode=bge.logic.KX_ACTION_MODE_PLAY, ob=None, blendin=0.0):
		self.action = action
		self.start = start
		self.end = end
		self.layer = layer
		self.targetDescendant = targetDescendant
		self.playMode = play_mode
		self.ob = ob
		self.blendin = blendin

	def execute(self, c):
		ob = self.find_target(c, self.ob, self.targetDescendant)
		ob.playAction(self.action, self.start, self.end, self.layer,
			blendin=self.blendin, play_mode=self.playMode)

	def __str__(self):
		return "ActAction: %s, %d -> %d" % (self.action, self.start, self.end)

class ActActionStop(BaseAct):
	'''Stops an animation.'''
	def __init__(self, layer, targetDescendant=None, ob=None):
		self.layer = layer
		self.targetDescendant = targetDescendant
		self.ob = ob

	def execute(self, c):
		ob = self.find_target(c, self.ob, self.targetDescendant)
		ob.stopAction(self.layer)

	def __str__(self):
		return "ActActionStop: %d" % self.layer

class ActConstraintSet(BaseAct):
	'''
	Adjusts the strength of a constraint on an armature over a range of frames
	of an animation. It is recommended that this be used in a sub-step with no
	condition.
	'''
	def __init__(self, bone_name, constraint_name, fac, ob=None,
			target_descendant=None):
		self.name = "{}:{}".format(bone_name, constraint_name)
		self.fac = fac
		self.target_descendant = target_descendant
		self.ob = ob

	def execute(self, c):
		ob = self.find_target(c, self.ob, self.target_descendant)
		con = ob.constraints[self.name]
		con.enforce = self.fac

	def __str__(self):
		return "ActConstraintSet: %s" % (self.name)

class ActConstraintFade(BaseAct):
	'''
	Adjusts the strength of a constraint on an armature over a range of frames
	of an animation. It is recommended that this be used in a sub-step with no
	condition.
	'''
	def __init__(self, bone_name, constraint_name, fac1, fac2, frame1, frame2,
			layer, ob=None, target_descendant=None):
		self.name = "{}:{}".format(bone_name, constraint_name)
		self.fac1 = fac1
		self.fac2 = fac2
		self.frame1 = frame1
		self.frame2 = frame2
		self.layer = layer
		self.target_descendant = target_descendant
		self.ob = ob

	def execute(self, c):
		ob = self.find_target(c, self.ob, self.target_descendant)
		con = ob.constraints[self.name]
		cfra = ob.getActionFrame(self.layer)
		k = bxt.bmath.unlerp(self.frame1, self.frame2, cfra)
		power = bxt.bmath.clamp(0.0, 1.0,
				bxt.bmath.lerp(self.fac1, self.fac2, k))
		con.enforce = power

	def __str__(self):
		return "ActConstraintFade: %s" % (self.name)

class ActSound(BaseAct):
	'''Plays a short sound.'''

	emitter = bxt.types.weakprop("emitter")

	def __init__(self, filename, vol=1, pitchmin=1, pitchmax=1, delay=0,
			emitter=None, maxdist=50.0):
		self.filename = bge.logic.expandPath(filename)
		self.volume = vol
		self.pitchmin = pitchmin
		self.pitchmax = pitchmax
		self.delay = delay
		self.emitter = emitter
		self.maxdist = maxdist
		self.mindist = maxdist / 5.0 # Just a guess, can change this if needed
		self._factory = None

	def execute(self, c):
		bxt.sound.play_sample(self.filename, self.volume, self.pitchmin, self.pitchmax, self.emitter, self.mindist, self.maxdist)

	def __str__(self):
		return "ActSound: %s" % self.filename

class ActMusicPlay(BaseAct):
	'''
	Plays a music track. The previous track will be stopped, but will remain
	queued in the jukebox.

	Music is associated with a real object (the 'target'). If the object dies,
	the music will stop. To stop music manually, use ActMusicStop with the same
	object. To use the current object as the target, set ob=None and
	target_descendant=None.
	'''
	def __init__(self, *filepaths, volume=1.0, loop=True, ob=None,
			target_descendant=None, priority=2):

		self.filepaths = filepaths
		self.volume = volume
		self.loop = loop
		self.target_descendant = target_descendant
		self.ob = ob
		self.priority = priority

	def execute(self, c):
		# Play the track. Use priority 1 for this kind of music, because it's
		# important for the story.
		ob = self.find_target(c, self.ob, self.target_descendant)
		jukebox.Jukebox().play(ob, self.priority, *self.filepaths,
				volume=self.volume)

	def __str__(self):
		return "ActMusicPlay: %s" % str(self.filepaths)

class ActMusicStop(BaseAct):
	'''
	Stops a music track. The previous track on the jukebox stack will then play
	again.

	Music is associated with a real object. See ActMusicPlay for details.
	'''
	def __init__(self, ob=None, target_descendant=None):
		self.target_descendant = target_descendant
		self.ob = ob

	def execute(self, c):
		ob = self.find_target(c, self.ob, self.target_descendant)
		jukebox.Jukebox().stop(ob)

	def __str__(self):
		return "ActMusicStop"

class ActShowMarker(BaseAct):
	'''Show a marker on the screen that points to an object.'''

	target = bxt.types.weakprop("target")

	def __init__(self, target):
		'''
		@para target: The object to highlight. If None, the highlight will be
				hidden.
		'''
		if isinstance(target, str):
			try:
				self.target = bge.logic.getCurrentScene().objects[target]
			except KeyError:
				self.target = None
		else:
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

	def addEvent(self, message, body=None):
		'''Convenience method to add an ActEvent action.'''
		evt = bxt.types.Event(message, body)
		self.actions.append(ActEvent(evt))

	def addWeakEvent(self, message, body):
		'''Convenience method to add an ActEvent action.'''
		evt = bxt.types.WeakEvent(message, body)
		self.actions.append(ActEvent(evt))

	def addTransition(self, state):
		'''
		Transitions are links to other states. During evaluation, the state will
		progress from this state to one of its transitions when all conditions
		of that transition are satisfied.

		Transitions are evaluated *in order*, i.e. if two transitions both have
		their conditions met, the one that was added first is progressed to
		next.
		'''
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
				print("Warning: Action %s failed." % act)
				print("\t%s" % e)

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
				log.write("%s:x " % condition.get_short_name())
				return False
			else:
				log.write("%s:o " % condition.get_short_name())
		return True

	def __str__(self):
		return "== State {} ==".format(self.name)

class Chapter(bxt.types.BX_GameObject):
	'''Embodies a story in the scene. Subclass this to define the story
	(add transitions to self.rootState). Then call 'progress' on each frame to
	allow the steps to be executed.'''

	_prefix = ''

	def __init__(self, old_owner):
		# Need one dummy transition before root state to ensure the children of
		# the root get activated.
		self.zeroState = State(name="Zero")
		self.rootState = self.zeroState.createTransition("Root")
		self.currentState = self.zeroState

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

		self.spawn()
		self.set_map()

		bxt.types.EventBus().add_listener(self)

	def spawn(self):
		scene = bge.logic.getCurrentScene()
		spawn_point = store.get('/game/level/spawnPoint',
				self['defaultSpawnPoint'])
		if not spawn_point in scene.objects:
			print("Error: spawn point %s not found." % spawn_point)
			spawn_point = self['defaultSpawnPoint']

		bxt.types.add_and_mutate_object(scene, 'Snail', self)
		bxt.types.Event('TeleportSnail', spawn_point).send()

	def set_map(self):
		if 'Map' not in self:
			return

		map_file = self['Map']

		if 'MapScaleX' in self:
			scale_x = self['MapScaleX']
		else:
			scale_x = 1.0
		if 'MapScaleY' in self:
			scale_y = self['MapScaleY']
		else:
			scale_y = 1.0

		if 'MapOffsetX' in self:
			off_x = self['MapOffsetX']
		else:
			off_x = 0.0
		if 'MapOffsetY' in self:
			off_y = self['MapOffsetY']
		else:
			off_y = 0.0

		if 'MapZoom' in self:
			zoom = self['MapZoom']
		else:
			zoom = 1.0

		scale = mathutils.Vector((scale_x, scale_y))
		offset = mathutils.Vector((off_x, off_y))
		bxt.types.Event('SetMap', (map_file, scale, offset, zoom)).send()

	def on_event(self, event):
		if event.message == "LoadLevel":
			# Listen for load events from portals.
			level = store.get('/game/levelFile')
			bge.logic.startGame(level)

def load_level(caller, level, spawnPoint):
	print('Loading next level: %s, %s' % (level, spawnPoint))

	store.put('/game/levelFile', level)
	store.put('/game/level/spawnPoint', spawnPoint, level=level)
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
