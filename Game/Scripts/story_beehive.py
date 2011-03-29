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

from . import director
from . import ui
from . import camera
from .story import *

class Intro(Character):
	def __init__(self, old_owner):
		Character.__init__(self, old_owner)
		evt = bxt.types.WeakEvent('StartLoading', self)
		bxt.types.EventBus().notify(evt)
	
	def CreateSteps(self):
		step = self.NewStep()
		step.AddAction(ActSuspendInput())
		step.AddAction(ActShowDialogue("Press Return to start."))
		step.AddAction(ActSetCamera('IntroCam'))
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActEvent(bxt.types.WeakEvent('FinishLoading', self)))
		step.AddAction(ActActuate('aStartDungeonMusic'))
		step.AddAction(ActShowDialogue("Welcome to the Cargo demo! This level is a short version of the main dungeon."))
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActShowDialogue("Use the arrow keys to control the snail. You can crawl up walls, and even on the ceiling!"))
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActShowDialogue("Press space to go inside the shell."))
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActShowDialogue("Press Escape at any time to quit."))
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActRemoveCamera('IntroCam'))
		step.AddAction(ActResumeInput())
		step.AddAction(ActHideDialogue())
		step.AddAction(ActGeneric(bge.types.KX_GameObject.endObject, self))

class Extro(Character):
	S_MUSIC = 3
	
	def __init__(self, old_owner):
		Character.__init__(self, old_owner)
	
	def CreateSteps(self):
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sTouch'))
		step.AddAction(ActSuspendInput())
		step.AddAction(ActSetCamera('EndGameCamera'))
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sStoryTimer'))
		step.AddAction(ActShowDialogue("To be continued..."))
		step.AddAction(ActActuate('aStopDungeonMusic'))
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActEvent(bxt.types.WeakEvent('StartLoading', self)))
		step.AddAction(ActHideDialogue())
		step.AddAction(ActActuate('aStartEndingMusic'))
		
		# Empty step to re-sync with timer.
		step = self.NewStep()
		step.AddCondition(CondSensor('sStoryTimer'))
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sStoryTimer'))
		step.AddAction(ActShowMessage("Credits"))
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sStoryTimer'))
		step.AddAction(ActShowDialogue("Story: Alex Fraser, Lara Mikocki"))
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActShowDialogue("Design, modelling, rigging, animation: Alex Fraser"))
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActShowDialogue("Music: Robert Leigh"))
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActShowDialogue("Programming: Alex Fraser, Mark Triggs"))
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActShowDialogue("Sound effects: Alex Fraser, freesound.org users: anamorphosis, tigersound, HerbertBoland"))
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActShowDialogue("Sound effects (cont.): freesound.org users: MeltyMcFace, kijjaz, arnaud, FreqMan"))
	
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActShowDialogue("Testing: Jodie Fraser, Lachlan Kanaley, Damien Elmes, Mark Triggs"))
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActShowDialogue("Made with: Blender, Bullet, The GIMP and Inkscape"))
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActShowDialogue("Thanks for playing! You can follow development at phatcore.com/alex?cat=8"))
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActShowDialogue("Press ESC to exit."))

class Bucket(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	DIR_UP = 1
	DIR_DOWN = 2
	
	LOC_TOP = 1
	LOC_BOTTOM = 2
	
	PROJECTION = [0.0, 0.0, 20.0]

	camTop = bxt.types.weakprop('camTop')
	camBottom = bxt.types.weakprop('camBottom')
	
	def __init__(self, old_owner):
		scene = bge.logic.getCurrentScene()
		self.water = self.find_descendant([('Type', 'BucketWater')])
		self.camTop = scene.objects['BucketTopCam']
		self.camBottom = scene.objects['BucketBottomCam']
		self.currentCamera = None
		
		self.dir = Bucket.DIR_UP
		self.loc = Bucket.LOC_BOTTOM
		self.isTouchingPlayer = False

	@bxt.types.expose
	@bxt.utils.controller_cls
	def update(self, c):
		sCollision = c.sensors['sPlayer']
		self.frameChanged()

		if director.Director().mainCharacter in sCollision.hitObjectList:
			self.setTouchingPlayer(True)
		else:
			self.setTouchingPlayer(False)
	
	def spawnWaterBall(self):
		scene = bge.logic.getCurrentScene()
		waterBall = scene.addObject(self['WaterBallTemplate'], self.water)
		waterBall.setLinearVelocity(self.water.getAxisVect(Bucket.PROJECTION))
	
	def setDirection(self, dir):
		if dir == self.dir:
			return
		
		if dir == Bucket.DIR_UP:
			self.water.setVisible(True, False)
		else:
			self.water.setVisible(False, False)
			self.spawnWaterBall()
		self.dir = dir
	
	def setLocation(self, loc):
		if loc == self.loc:
			return
		
		if loc == Bucket.LOC_TOP:
			self.water.setVisible(True, False)
		else:
			self.water.setVisible(False, False)
		self.loc = loc
		self.updateCamera()
	
	def frameChanged(self):
		frame = self['Frame']
		if frame < 170:
			self.setDirection(Bucket.DIR_UP)
		else:
			self.setDirection(Bucket.DIR_DOWN)
		
		if frame > 100 and frame < 260:
			self.setLocation(Bucket.LOC_TOP)
		else:
			self.setLocation(Bucket.LOC_BOTTOM)
	
	def updateCamera(self):
		cam = None
		if self.isTouchingPlayer:
			if self.loc == Bucket.LOC_BOTTOM:
				cam = self.camBottom
			else:
				cam = self.camTop
		
		if cam == self.currentCamera:
			return
		
		if self.currentCamera != None:
			camera.AutoCamera().remove_goal(self.currentCamera)
		if cam != None:
			camera.AutoCamera().add_goal(cam)
		
		self.currentCamera = cam
	
	def setTouchingPlayer(self, isTouchingPlayer):
		if isTouchingPlayer == self.isTouchingPlayer:
			return
		
		self.isTouchingPlayer = isTouchingPlayer
		if isTouchingPlayer:
			bxt.types.EventBus().notify(bxt.types.Event('SuspendInput', True))
		else:
			bxt.types.EventBus().notify(bxt.types.Event('SuspendInput', False))
		self.updateCamera()
