#
# Copyright 2009 Alex Fraser <alex@phatcore.com>
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

import Actor
import UI
import GameLogic
import Camera
import Utilities

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
		Actor.Director.SuspendUserInput()

class ActResumeInput:
	def Execute(self, c):
		Actor.Director.ResumeUserInput()

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
		self.Start = start
		self.End = end
		self.Loop = loop
		
	def Execute(self, c):
		aArm = c.actuators[self.aArmName]
		aMesh = c.actuators[self.aMeshName]
		aArm.action = self.ActionPrefix
		aMesh.action = self.ActionPrefix + '_S'
		
		aArm.frameStart = aMesh.frameStart = self.Start
		aArm.frameEnd = aMesh.frameEnd = self.End
		aArm.frame = aMesh.frame = self.Start
		
		if self.Loop:
			aArm.mode = aMesh.mode = GameLogic.KX_ACTIONACT_LOOPEND
		else:
			aArm.mode = aMesh.mode = GameLogic.KX_ACTIONACT_PLAY
		
		c.activate(aArm)
		c.activate(aMesh)

class ActShowDialogue:
	def __init__(self, message):
		self.Message = message
	
	def Execute(self, c):
		UI.HUD.ShowDialogue(self.Message)

class ActHideDialogue:
	def Execute(self, c):
		UI.HUD.HideDialogue()

class ActSetCamera:
	def __init__(self, camName, fac = None, instantCut = False):
		self.CamName = camName
		self.InstantCut = instantCut
		self.Fac = fac
	
	def Execute(self, c):
		try:
			cam = GameLogic.getCurrentScene().objects['OB' + self.CamName]
		except KeyError:
			print ("Warning: couldn't find camera %s. Not adding." %
				self.CamName)
			return
		Camera.AutoCamera.AddGoal(cam, True, self.Fac, self.InstantCut)

class ActRemoveCamera:
	def __init__(self, camName):
		self.CamName = camName
	
	def Execute(self, c):
		try:
			cam = GameLogic.getCurrentScene().objects['OB' + self.CamName]
		except KeyError:
			print ("Warning: couldn't find camera %s. Not removing." %
				self.CamName)
			return
		Camera.AutoCamera.RemoveGoal(cam)

class ActGeneric:
	def __init__(self, f, *closure):
		self.Function = f
		self.Closure = closure
	
	def Execute(self, c):
		try:
			self.Function(*self.Closure)
		except Exception, e:
			raise StoryError("Error executing " + str(self.Function), e)

class ActGenericContext(ActGeneric):
	def Execute(self, c):
		try:
			self.Function(c, *self.Closure)
		except Exception, e:
			raise StoryError("Error executing " + str(self.Function), e)

class ActDebug:
	def __init__(self, message):
		self.Message = message
	
	def Execute(self, c):
		print self.Message

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
				act.Execute(c)
			except Exception, e:
				print "Warning: Action %s failed." % act
				print e

class Character(Actor.Actor):

	def __init__(self, owner):
		Actor.Actor.__init__(self, owner)
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
			step.Execute(controller)
			self.NextStep = self.NextStep + 1
	
	def CreateSteps(self):
		pass

def Progress(c):
	character = c.owner['Actor']
	character.Progress(c)

