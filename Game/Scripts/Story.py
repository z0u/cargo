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

class StoryError(Exception):
	pass

#
# Step progression conditions. These determine whether a step may execute.
#
class CondSensor:
	def __init__(self, name):
		self.Name = name
	
	def Evaluate(self, c):
		s = c.sensors[self.Name]
		return s.positive and s.triggered

class CondPropertyGE:
	def __init__(self, name, value):
		self.Name = name
		self.Value = value
	
	def Evaluate(self, c):
		return c.owner[self.Name] >= self.Value

#
# Actions. These belong to and are executed by steps.
#
class ActSuspendInput:
	def Execute(self, c):
		bxt.utils.EventBus().notify(bxt.utils.Event('SuspendPlay'))

class ActResumeInput:
	def Execute(self, c):
		bxt.utils.EventBus().notify(bxt.utils.Event('ResumePlay'))

class ActActuate:
	def __init__(self, actuatorName):
		self.ActuatorName = actuatorName
	
	def Execute(self, c):
		c.activate(c.actuators[self.ActuatorName])

class ActActionPair:
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
		self.Message = message
	
	def Execute(self, c):
		evt = bxt.utils.Event('ShowDialogue', self.Message)
		bxt.utils.EventBus().notify(evt)

class ActHideDialogue:
	def Execute(self, c):
		evt = bxt.utils.Event('ShowDialogue', None)
		bxt.utils.EventBus().notify(evt)

class ActShowMessage:
	def __init__(self, message):
		self.Message = message
	
	def Execute(self, c):
		evt = bxt.utils.Event('ShowMessage', self.Message)
		bxt.utils.EventBus().notify(evt)

class ActSetCamera:
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
	def __init__(self, f, *closure):
		self.Function = f
		self.Closure = closure
	
	def Execute(self, c):
		try:
			self.Function(*self.Closure)
		except Exception as e:
			raise StoryError("Error executing " + str(self.Function), e)

class ActGenericContext(ActGeneric):
	def Execute(self, c):
		try:
			self.Function(c, *self.Closure)
		except Exception as e:
			raise StoryError("Error executing " + str(self.Function), e)

class ActEvent:
	def __init__(self, event):
		self.event = event

	def Execute(self, c):
		bxt.utils.EventBus().notify(self.event)

class ActDebug:
	def __init__(self, message):
		self.Message = message
	
	def Execute(self, c):
		print(self.Message)

#
# Steps. These are executed by Characters when their conditions are met and they
# are at the front of the queue.
#
class Step:
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

class Character(bxt.types.BX_GameObject, bge.types.KX_GameObject):
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

	@bxt.types.expose_fun
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
