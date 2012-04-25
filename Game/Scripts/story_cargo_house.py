#
# Copyright 2009-2012 Alex Fraser <alex@phatcore.com>
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

import bxt

import bge

from . import store
from .story import *

class CargoHouse(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	_prefix = 'CH_'

	def __init__(self, old_owner):
		self.load_npcs()
		self.init_worm()

	@bxt.types.expose
	@bxt.utils.controller_cls
	def touched(self, c):
		s = c.sensors['Near']
		if s.hitObject is not None:
			store.set('/game/spawnPoint', 'SpawnCargoHouse')

	def load_npcs(self):
		try:
			bge.logic.LibLoad('//OutdoorsNPCLoader.blend', 'Scene',
					load_actions=True)
		except ValueError:
			print('Warning: could not load characters.')

	def init_worm(self):
		sce = bge.logic.getCurrentScene()
		if not store.get('/game/level/wormMissionStarted', False):
			sce.addObject("G_Worm", "WormSpawn")
			bxt.bmath.copy_transform(sce.objects['WormSpawn'], sce.objects['Worm'])

class Worm(Chapter, bge.types.BL_ArmatureObject):
	L_IDLE = 0
	L_ANIM = 1

	def __init__(self, old_owner):
		Chapter.__init__(self, old_owner)
		bxt.types.WeakEvent('StartLoading', self).send()
		self.create_state_graph()

	def create_state_graph(self):
		def letter_auto(c):
			sce = bge.logic.getCurrentScene()
			ob = sce.objects['Worm_Letter']
			hook = c.owner.childrenRecursive['CargoHoldAuto']
			ob.setParent(hook)
			bxt.bmath.copy_transform(hook, ob)
		def letter_manual(c):
			sce = bge.logic.getCurrentScene()
			ob = sce.objects['Worm_Letter']
			hook = c.owner.childrenRecursive['CargoHoldManual']
			ob.setParent(hook)
			bxt.bmath.copy_transform(hook, ob)
		def letter_hide(c):
			sce = bge.logic.getCurrentScene()
			ob = sce.objects['Worm_Letter']
			ob.visible = False

		def spray_dirt(c, number, maxSpeed):
			o = c.sensors['sParticleHook'].owner
			o['nParticles'] = o['nParticles'] + number
			o['maxSpeed'] = maxSpeed

		s = self.rootState.createTransition("Init")
		s.addAction(ActSuspendInput())

		s = s.createTransition("Init")
		s.addCondition(CondWait(1))
		s.addEvent("ForceEnterShell", False)
		s.addAction(ActSetCamera('WormCamera_Enter'))
		s.addAction(ActSetFocalPoint('CargoHoldAuto'))
		s.addEvent("ShowDialogue", "Press Return to start.")
		s.addAction(ActAction('ParticleEmitMove', 1, 1, Worm.L_ANIM, "ParticleEmitterLoc"))
		s.addAction(ActGenericContext(letter_manual))

		#
		# Peer out of ground
		#
		s = s.createTransition("Begin")
		s.addCondition(CondEvent('DialogueDismissed'))
		s.addWeakEvent("FinishLoading", self)
		s.addAction(ActGenericContext(spray_dirt, 10, 15.0))
		s.addAction(ActAction('BurstOut', 1, 75, Worm.L_ANIM))
		s.addAction(ActAction('BurstOut_S', 1, 75, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition("Greet")
		s.addCondition(CondActionGE(Worm.L_ANIM, 74.0))
		s.addEvent("ShowDialogue", "Cargo?")

		#
		# Get out of the ground
		#
		s = s.createTransition("Get out of the ground")
		s.addCondition(CondEvent('DialogueDismissed'))
		s.addAction(ActRemoveCamera('WormCamera_Enter'))
		s.addAction(ActSetCamera('WormCamera_Converse'))
		s.addAction(ActAction('BurstOut', 75, 186, Worm.L_ANIM))
		s.addAction(ActAction('BurstOut_S', 75, 186, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 115.0))
		s.addAction(ActGenericContext(spray_dirt, 3, 10.0))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 147.0))
		s.addAction(ActGenericContext(spray_dirt, 5, 10.0))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 153.0))
		s.addAction(ActGenericContext(spray_dirt, 5, 10.0))

		#
		# Knock on shell
		#
		s = s.createTransition("Knock on shell")
		s.addCondition(CondActionGE(Worm.L_ANIM, 185.0))
		s.addAction(ActSetCamera('WormCamera_Knock'))
		s.addEvent("ShowDialogue", "Wake up, Cargo!")
		s.addAction(ActAction('BurstOut', 185, 198, Worm.L_ANIM,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))
		s.addAction(ActAction('BurstOut_S', 185, 198, Worm.L_ANIM, 'WormBody'))

		sKnock = s.createSubStep("Knock sound")
		sKnock.addCondition(CondActionGE(Worm.L_ANIM, 187, tap=True))
		sKnock.addAction(ActSound('//Sound/Knock.ogg', vol=0.6, pitchmin=0.8,
				pitchmax= 1.1))

		s = s.createTransition()
		s.addCondition(CondEvent('DialogueDismissed'))
		s.addAction(ActAction('BurstOut', 185, 220, Worm.L_ANIM))
		s.addAction(ActAction('BurstOut_S', 185, 220, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 200.0))
		s.addAction(ActRemoveCamera('WormCamera_Knock'))

		#
		# Wake / chastise
		#	
		s = s.createTransition("Wake")
		s.addCondition(CondActionGE(Worm.L_ANIM, 205.0))
		s.addEvent("ForceExitShell", True)

		s = s.createTransition("Chastise")
		s.addCondition(CondEvent('ShellExited'))
		s.addEvent("ShowDialogue", "Sleeping in, eh? Don't worry, I won't tell anyone.")

		s = s.createTransition()
		s.addCondition(CondEvent('DialogueDismissed'))
		s.addEvent("ShowDialogue", "I have something for you!")

		#
		# Dig up letter
		#
		s = s.createTransition("Dig up letter")
		s.addCondition(CondEvent('DialogueDismissed'))
		s.addAction(ActAction('ParticleEmitMove', 2, 2, Worm.L_ANIM, "ParticleEmitterLoc"))
		s.addAction(ActAction('BurstOut', 220, 280, Worm.L_ANIM))
		s.addAction(ActAction('BurstOut_S', 220, 280, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 235))
		s.addAction(ActGenericContext(spray_dirt, 3, 10.0))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 241))
		s.addAction(ActGenericContext(spray_dirt, 3, 7.0))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 249))
		s.addAction(ActGenericContext(spray_dirt, 3, 7.0))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 257))
		s.addAction(ActGenericContext(spray_dirt, 3, 7.0))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 265))
		s.addAction(ActGenericContext(spray_dirt, 3, 7.0))
		s.addAction(ActGenericContext(letter_auto))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 275))
		s.addAction(ActSetCamera('WormCamera_Envelope'))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 279))
		s.addEvent("ShowDialogue",
				("Ta-da! Please deliver this \[envelope] for me.",
						("Of course!", "I'm too sleepy...")))

		#
		# FORK - conversation splits.
		#
		syes = s.createTransition("Yes")
		# Use 'not equal' here, because it's safer than using two equals (in
		# case the dialogue returns a value other than 1 or 0).
		syes.addCondition(CondEventNe("DialogueDismissed", 1))
		syes.addEvent("ShowDialogue", "Great!")

		sno = s.createTransition("No")
		sno.addCondition(CondEventEq("DialogueDismissed", 1))
		sno.addEvent("ShowDialogue", "Oh, come on! It's your job, after all.")
		# Lots of text, so wait for a second.
		sno = sno.createTransition()
		sno.addCondition(CondWait(1))

		#
		# Give letter - conversation merges.
		#
		s = State("Give letter")
		syes.addTransition(s)
		sno.addTransition(s)
		s.addAction(ActRemoveCamera('WormCamera_Envelope'))
		s.addAction(ActAction('BurstOut', 290, 330, Worm.L_ANIM))
		s.addAction(ActAction('BurstOut_S', 290, 330, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 308))
		s.addAction(ActGenericContext(letter_manual))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 315))
		s.addAction(ActGenericContext(letter_hide))

		#
		# Point to lighthouse
		#
		s = s.createTransition("Point to lighthouse")
		s.addEvent("ShowDialogue", "Please take it to the lighthouse keeper.")
		s.addAction(ActAction('BurstOut', 330, 395, Worm.L_ANIM))
		s.addAction(ActAction('BurstOut_S', 330, 395, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 360))
		s.addAction(ActSetCamera('WormCamera_Lighthouse'))
		s.addAction(ActSetFocalPoint('Torch'))
		s.addAction(ActShowMarker('Torch'))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 394))
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addAction(ActRemoveCamera('WormCamera_Lighthouse'))
		s.addAction(ActRemoveFocalPoint('Torch'))
		s.addAction(ActShowMarker(None))
		s.addEvent("ShowDialogue", "See you later!")
		s.addAction(ActAction('BurstOut', 395, 420, Worm.L_ANIM))
		s.addAction(ActAction('BurstOut_S', 395, 420, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition()
		s.addCondition(CondActionGE(Worm.L_ANIM, 420))
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addAction(ActAction('BurstOut', 420, 540, Worm.L_ANIM))
		s.addAction(ActAction('BurstOut_S', 420, 540, Worm.L_ANIM, 'WormBody'))

		#
		# Return to game
		#
		s = s.createTransition("Return to game")
		s.addCondition(CondActionGE(Worm.L_ANIM, 460))
		s.addAction(ActAction('SodFade', 120, 200, 0, 'Sods'))
		s.addAction(ActResumeInput())
		s.addAction(ActRemoveCamera('WormCamera_Converse'))
		s.addAction(ActRemoveFocalPoint('CargoHoldAuto'))
		s.addAction(ActStoreSet('/game/level/wormMissionStarted', True))

		#
		# Clean up. At this point, the worm is completely hidden and the sods have faded.
		#
		s = s.createTransition("Clean up")
		s.addCondition(CondActionGE(Worm.L_ANIM, 540))
		s.addAction(ActDestroy())

	def isInsideWorld(self):
		return True

@bxt.utils.controller
def worm_knock_sound(c):
	frame = c.owner['ActionFrame']
	if (frame > 187 and frame < 189) or (frame > 200 and frame < 201):
		bxt.sound.play_with_random_pitch(c)
