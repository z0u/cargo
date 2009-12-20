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

import Mathutils
import Utilities
from Story import *

def CreateWorm(c):
	if not Utilities.allSensorsPositive(c):
		return
	
	def SleepSnail(c, animate):
		snail = c.sensors['sNearSnail'].hitObject['Actor']
		snail.enterShell(animate)
	
	def WakeSnail(c, animate):
		snail = c.sensors['sNearSnail'].hitObject['Actor']
		snail.exitShell(animate)
	
	def SprayDirt(c, number, maxSpeed):
		act = c.actuators['aParticleEmitter']
		emitterBase = act.owner.parent
		
		angle = 0.0
		ANGLE_INCREMENT = 80.0
		
		for _ in xrange(number):
			elr = Mathutils.Euler(0.0, 0.0, angle)
			angle = angle + ANGLE_INCREMENT
			oMat = elr.toMatrix()
			oMat.transpose()
			emitterBase.worldOrientation = oMat
			act.linearVelocity = (0.0, 0.0, maxSpeed * Utilities.Random.next())
			act.instantAddObject()
	
	def CleanUp(c):
		worm = c.owner['Actor']
		worm.Destroy()
	
	worm = Character(c.owner)
	
	step = worm.NewStep()
	step.AddAction(ActGenericContext(SleepSnail, False))
	
	step = worm.NewStep()
	step.AddCondition(CondSensor('sSnailAsleep'))
	step.AddAction(ActSetCamera('WormCamera_Enter'))
	step.AddAction(ActSuspendInput())
	step.AddAction(ActShowDialogue("Press Return to start."))
	
	#
	# Peer out of ground
	#
	step = worm.NewStep()
	step.AddCondition(CondSensor('sReturn'))
	step.AddAction(ActHideDialogue())
	step.AddAction(ActGeneric(UI.HUD.HideLoadingScreen))
	step.AddAction(ActGenericContext(SprayDirt, 10, 15.0))
	step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 1.0, 75.0))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 75.0))
	step.AddAction(ActShowDialogue("Cargo?"))
	
	#
	# Get out of the ground
	#
	step = worm.NewStep()
	step.AddCondition(CondSensor('sReturn'))
	step.AddAction(ActHideDialogue())
	step.AddAction(ActRemoveCamera('WormCamera_Enter'))
	step.AddAction(ActSetCamera('WormCamera_Converse'))
	step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 75.0, 180.0))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 115))
	step.AddAction(ActGenericContext(SprayDirt, 3, 10.0))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 147))
	step.AddAction(ActGenericContext(SprayDirt, 5, 10.0))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 153))
	step.AddAction(ActGenericContext(SprayDirt, 5, 10.0))
	
	#
	# Knock on shell
	#
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 180.0))
	step.AddAction(ActSetCamera('WormCamera_Knock', instantCut = True))
	step.AddAction(ActShowDialogue("Wake up, Cargo!"))
	step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 181.0, 197.0, True))
	
	step = worm.NewStep()
	step.AddCondition(CondSensor('sReturn'))
	step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 181.0, 220.0))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 200.0))
	step.AddAction(ActRemoveCamera('WormCamera_Knock'))

	#
	# Wake / chastise
	#	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 205.0))
	step.AddAction(ActGenericContext(WakeSnail, True))
	step.AddAction(ActHideDialogue())
	
	step = worm.NewStep()
	step.AddCondition(CondSensor('sSnailAwake'))
	step.AddAction(ActShowDialogue("Sleeping in, eh? Don't worry, I won't tell anyone."))
	
	step = worm.NewStep()
	step.AddCondition(CondSensor('sReturn'))
	step.AddAction(ActShowDialogue("I have something for you!"))
	
	#
	# Dig up letter
	#
	step = worm.NewStep()
	step.AddCondition(CondSensor('sReturn'))
	step.AddAction(ActHideDialogue())
	step.AddAction(ActActuate('aParticleEmitMove'))
	step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 220.0, 280.0))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 235))
	step.AddAction(ActGenericContext(SprayDirt, 3, 10.0))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 241))
	step.AddAction(ActGenericContext(SprayDirt, 3, 7.0))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 249))
	step.AddAction(ActGenericContext(SprayDirt, 3, 7.0))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 257))
	step.AddAction(ActGenericContext(SprayDirt, 3, 7.0))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 265))
	step.AddAction(ActGenericContext(SprayDirt, 3, 7.0))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 275.0))
	step.AddAction(ActSetCamera('WormCamera_Envelope', instantCut = True))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 280.0))
	step.AddAction(ActShowDialogue("Ta-da! Please deliver this letter for me."))
	
	#
	# Give letter
	#
	step = worm.NewStep()
	step.AddCondition(CondSensor('sReturn'))
	step.AddAction(ActHideDialogue())
	step.AddAction(ActRemoveCamera('WormCamera_Envelope'))
	step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 290.0, 330.0))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 315.0))
	step.AddAction(ActActuate('aHideLetter'))
	step.AddAction(ActShowDialogue("Is that OK?"))
	
	#
	# Point to lighthouse
	#
	step = worm.NewStep()
	step.AddCondition(CondSensor('sReturn'))
	step.AddAction(ActShowDialogue("Great! Please take it to the lighthouse keeper."))
	step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 330.0, 395.0))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 360.0))
	step.AddAction(ActSetCamera('WormCamera_Lighthouse', fac = 0.01))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 395.0))
	step.AddCondition(CondSensor('sReturn'))
	step.AddAction(ActRemoveCamera('WormCamera_Lighthouse'))
	step.AddAction(ActShowDialogue("See you later!"))
	step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 395.0, 420.0))
	
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 420.0))
	step.AddCondition(CondSensor('sReturn'))
	step.AddAction(ActHideDialogue())
	step.AddAction(ActActionPair('aArmature', 'aMesh', 'BurstOut', 420.0, 540.0))
	
	#
	# Return to game
	#
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 460.0))
	step.AddAction(ActActuate('aFadeSods'))
	step.AddAction(ActResumeInput())
	step.AddAction(ActRemoveCamera('WormCamera_Converse'))
	
	#
	# Clean up. At this point, the worm is completely hidden and the sods have faded.
	#
	step = worm.NewStep()
	step.AddCondition(CondPropertyGE('ActionFrame', 540.0))
	step.AddAction(ActGenericContext(CleanUp))

