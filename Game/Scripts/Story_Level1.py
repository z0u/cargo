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

import mathutils
from . import Utilities
from . import Sound
from .Story import *

class Worm(Character):
	def __init__(self, owner):
		Character.__init__(self, owner)
		UI.HUD.ShowLoadingScreen(self)

	def CreateSteps(self):
		#
		# Local utility functions
		#
		def SleepSnail(c, animate):
			snail = c.sensors['sNearSnail'].hitObject['Actor']
			snail.enterShell(animate)
		
		def WakeSnail(c, animate):
			snail = c.sensors['sNearSnail'].hitObject['Actor']
			snail.exitShell(animate)
		
		def SprayDirt(c, number, maxSpeed):
			o = c.sensors['sParticleHook'].owner
			o['nParticles'] = o['nParticles'] + number
			o['maxSpeed'] = maxSpeed
			
		def CleanUp(c):
			worm = c.owner['Actor']
			worm.Destroy()

		step = self.NewStep()
		step.AddAction(ActGenericContext(SleepSnail, False))
		step.AddAction(ActSuspendInput())
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sSnailAsleep'))
		step.AddAction(ActSetCamera('WormCamera_Enter'))
		step.AddAction(ActShowDialogue("Press Return to start."))
		
		#
		# Peer out of ground
		#
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActHideDialogue())
		step.AddAction(ActGeneric(UI.HUD.HideLoadingScreen, self))
		step.AddAction(ActGenericContext(SprayDirt, 10, 15.0))
		step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 1.0, 75.0))
		
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 75.0))
		step.AddAction(ActShowDialogue("Cargo?"))
		
		#
		# Get out of the ground
		#
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActHideDialogue())
		step.AddAction(ActRemoveCamera('WormCamera_Enter'))
		step.AddAction(ActSetCamera('WormCamera_Converse'))
		step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 75.0, 186.0))
		
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 115))
		step.AddAction(ActGenericContext(SprayDirt, 3, 10.0))
		
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 147))
		step.AddAction(ActGenericContext(SprayDirt, 5, 10.0))
		
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 153))
		step.AddAction(ActGenericContext(SprayDirt, 5, 10.0))
		
		#
		# Knock on shell
		#
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 185.0))
		step.AddAction(ActSetCamera('WormCamera_Knock', instantCut = True))
		step.AddAction(ActShowDialogue("Wake up, Cargo!"))
		step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 185.0, 198.0, True))
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 185.0, 220.0))
		
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 200.0))
		step.AddAction(ActRemoveCamera('WormCamera_Knock'))
	
		#
		# Wake / chastise
		#	
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 205.0))
		step.AddAction(ActGenericContext(WakeSnail, True))
		step.AddAction(ActHideDialogue())
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sSnailAwake'))
		step.AddAction(ActShowDialogue("Sleeping in, eh? Don't worry, I won't tell anyone."))
		
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActShowDialogue("I have something for you!"))
		
		#
		# Dig up letter
		#
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActHideDialogue())
		step.AddAction(ActActuate('aParticleEmitMove'))
		step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 220.0, 280.0))
		
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 235))
		step.AddAction(ActGenericContext(SprayDirt, 3, 10.0))
		
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 241))
		step.AddAction(ActGenericContext(SprayDirt, 3, 7.0))
		
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 249))
		step.AddAction(ActGenericContext(SprayDirt, 3, 7.0))
		
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 257))
		step.AddAction(ActGenericContext(SprayDirt, 3, 7.0))
		
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 265))
		step.AddAction(ActGenericContext(SprayDirt, 3, 7.0))
		
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 275.0))
		step.AddAction(ActSetCamera('WormCamera_Envelope', instantCut = True))
		
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 280.0))
		step.AddAction(ActShowDialogue("Ta-da! Please deliver this letter for me."))
		
		#
		# Give letter
		#
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActHideDialogue())
		step.AddAction(ActRemoveCamera('WormCamera_Envelope'))
		step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 290.0, 330.0))
		
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 315.0))
		step.AddAction(ActActuate('aHideLetter'))
		step.AddAction(ActShowDialogue("Is that OK?"))
		
		#
		# Point to lighthouse
		#
		step = self.NewStep()
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActShowDialogue("Great! Please take it to the lighthouse keeper."))
		step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 330.0, 395.0))
		
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 360.0))
		step.AddAction(ActSetCamera('WormCamera_Lighthouse', fac = 0.01))
		
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 395.0))
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActRemoveCamera('WormCamera_Lighthouse'))
		step.AddAction(ActShowDialogue("See you later!"))
		step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 395.0, 420.0))
		
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 420.0))
		step.AddCondition(CondSensor('sReturn'))
		step.AddAction(ActHideDialogue())
		step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 420.0, 540.0))
		
		#
		# Return to game
		#
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 460.0))
		step.AddAction(ActActuate('aFadeSods'))
		step.AddAction(ActResumeInput())
		step.AddAction(ActRemoveCamera('WormCamera_Converse'))
		
		#
		# Clean up. At this point, the worm is completely hidden and the sods have faded.
		#
		step = self.NewStep()
		step.AddCondition(CondPropertyGE('ActionFrame', 540.0))
		step.AddAction(ActGenericContext(CleanUp))
	
	def isInsideWorld(self):
		return True
		
def CreateWorm(c):
	if not Utilities.allSensorsPositive(c):
		return
	Worm(c.owner)

def wormKnockSound(c):
	frame = c.owner['ActionFrame']
	if (frame > 187 and frame < 189) or (frame > 200 and frame < 201):
		Sound.PlayWithRandomPitch(c)
