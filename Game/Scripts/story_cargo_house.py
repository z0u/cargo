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

import bge

import bat.bats
import bat.event
import bat.sound
import bat.bmath
import bat.store
import bat.story

import Scripts.story

class CargoHouse(bat.bats.BX_GameObject, bge.types.KX_GameObject):
	_prefix = 'CH_'

	def __init__(self, old_owner):
		pass

	@bat.bats.expose
	@bat.utils.controller_cls
	def touched(self, c):
		s = c.sensors['Near']
		if s.hitObject is not None:
			bat.store.put('/game/level/spawnPoint', 'SpawnCargoHouse')
			# Create the worm *before* starting the music, because the worm may
			# want to override the tune.
			self.init_worm()
			bat.sound.Jukebox().play_files(self, 1, '//Sound/Music/House.ogg', volume=0.7)
		else:
			bat.sound.Jukebox().stop(self)

	def init_worm(self):
		if not bat.store.get('/game/level/wormMissionStarted', False):
			worm = factory(self.scene)
			bat.bmath.copy_transform(self.scene.objects['WormSpawn'], worm)

def factory(sce):
	if not "Worm" in sce.objectsInactive:
		try:
			bge.logic.LibLoad('//Worm_loader.blend', 'Scene', load_actions=True)
		except ValueError as e:
			print('Warning: could not load worm:', e)

	return bat.bats.add_and_mutate_object(sce, "Worm", "Worm")

class Worm(bat.story.Chapter, bge.types.BL_ArmatureObject):
	L_IDLE = 0
	L_ANIM = 1

	def __init__(self, old_owner):
		bat.story.Chapter.__init__(self, old_owner)
		bat.event.WeakEvent('StartLoading', self).send()
		self.create_state_graph()
		bat.sound.Jukebox().play_files(self, 2, '//Sound/Music/Worm1.ogg',
				volume=0.7)

	def create_state_graph(self):
		def letter_auto(c):
			sce = bge.logic.getCurrentScene()
			ob = sce.objects['Worm_Letter']
			hook = c.owner.childrenRecursive['CargoHoldAuto']
			ob.setParent(hook)
			bat.bmath.copy_transform(hook, ob)
		def letter_manual(c):
			sce = bge.logic.getCurrentScene()
			ob = sce.objects['Worm_Letter']
			hook = c.owner.childrenRecursive['CargoHoldManual']
			ob.setParent(hook)
			bat.bmath.copy_transform(hook, ob)
		def letter_hide(c):
			sce = bge.logic.getCurrentScene()
			ob = sce.objects['Worm_Letter']
			ob.visible = False

		def spray_dirt(c, number, maxSpeed):
			o = c.sensors['sParticleHook'].owner
			o['nParticles'] = o['nParticles'] + number
			o['maxSpeed'] = maxSpeed

		s = self.rootState.createTransition("Init")
		s.addAction(Scripts.story.ActSuspendInput())

		s = s.createTransition("Init")
		s.addCondition(bat.story.CondWait(1))
		s.addEvent("ForceEnterShell", False)
		s.addAction(Scripts.story.ActSetCamera('WormCamera_Enter'))
		s.addAction(Scripts.story.ActSetFocalPoint('CargoHoldAuto'))
		s.addAction(bat.story.ActAction('ParticleEmitMove', 1, 1, Worm.L_ANIM, "ParticleEmitterLoc"))
		s.addAction(bat.story.ActGenericContext(letter_manual))

		#
		# Peer out of ground
		#
		s = s.createTransition("Begin")
		s.addCondition(bat.story.CondEvent('ShellEntered', self))
		s.addEvent('AnchorShell', 'CH_ShellAnchor')
		s.addWeakEvent("FinishLoading", self)
		s.addAction(bat.story.ActGenericContext(spray_dirt, 10, 15.0))
		s.addAction(bat.story.ActAction('BurstOut', 1, 75, Worm.L_ANIM))
		s.addAction(bat.story.ActAction('BurstOut_S', 1, 75, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition("Greet")
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 74.0))
		s.addEvent("ShowDialogue", "Cargo?")

		#
		# Get out of the ground
		#
		s = s.createTransition("Get out of the ground")
		s.addCondition(bat.story.CondEvent('DialogueDismissed', self))
		s.addAction(Scripts.story.ActRemoveCamera('WormCamera_Enter'))
		s.addAction(Scripts.story.ActSetCamera('WormCamera_Converse'))
		s.addAction(bat.story.ActAction('BurstOut', 75, 186, Worm.L_ANIM))
		s.addAction(bat.story.ActAction('BurstOut_S', 75, 186, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition()
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 115.0))
		s.addAction(bat.story.ActGenericContext(spray_dirt, 3, 10.0))

		s = s.createTransition()
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 147.0))
		s.addAction(bat.story.ActGenericContext(spray_dirt, 5, 10.0))

		s = s.createTransition()
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 153.0))
		s.addAction(bat.story.ActGenericContext(spray_dirt, 5, 10.0))

		#
		# Knock on shell
		#
		s = s.createTransition("Knock on shell")
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 185.0))
		s.addAction(Scripts.story.ActSetCamera('WormCamera_Knock'))
		s.addEvent("ShowDialogue", "Wake up, Cargo!")
		s.addAction(bat.story.ActAction('BurstOut', 187, 200, Worm.L_ANIM,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))
		s.addAction(bat.story.ActAction('BurstOut_S', 187, 200, Worm.L_ANIM, 'WormBody'))

		sKnock = s.createSubStep("Knock sound")
		sKnock.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 189, tap=True))
		sKnock.addAction(bat.story.ActSound('//Sound/Knock.ogg', vol=0.6, pitchmin=0.8,
				pitchmax= 1.1))

		s = s.createTransition()
		s.addCondition(bat.story.CondEvent('DialogueDismissed', self))
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 199))
		s.addAction(bat.story.ActAction('BurstOut', 200, 220, Worm.L_ANIM))
		s.addAction(bat.story.ActAction('BurstOut_S', 200, 220, Worm.L_ANIM, 'WormBody'))
		s.addAction(bat.story.ActSound('//Sound/Knock.ogg', vol=0.6, pitchmin=0.8,
				pitchmax= 1.1))

		s = s.createTransition()
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 200.0))
		s.addAction(Scripts.story.ActRemoveCamera('WormCamera_Knock'))

		#
		# Wake / chastise
		#	
		s = s.createTransition("Wake")
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 205.0))
		s.addEvent("ForceExitShell", True)

		s = s.createTransition("Chastise")
		s.addCondition(bat.story.CondEvent('ShellExited', self))
		s.addEvent("ShowDialogue", "Sleeping in, eh? Don't worry, I won't tell anyone.")

		s = s.createTransition()
		s.addCondition(bat.story.CondEvent('DialogueDismissed', self))
		s.addEvent("ShowDialogue", "I have something for you!")

		#
		# Dig up letter
		#
		s = s.createTransition("Dig up letter")
		s.addCondition(bat.story.CondEvent('DialogueDismissed', self))
		s.addAction(bat.story.ActAction('ParticleEmitMove', 2, 2, Worm.L_ANIM, "ParticleEmitterLoc"))
		s.addAction(bat.story.ActAction('BurstOut', 220, 280, Worm.L_ANIM))
		s.addAction(bat.story.ActAction('BurstOut_S', 220, 280, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition()
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 235))
		s.addAction(bat.story.ActGenericContext(spray_dirt, 3, 10.0))

		s = s.createTransition()
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 241))
		s.addAction(bat.story.ActGenericContext(spray_dirt, 3, 7.0))

		s = s.createTransition()
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 249))
		s.addAction(bat.story.ActGenericContext(spray_dirt, 3, 7.0))

		s = s.createTransition()
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 257))
		s.addAction(bat.story.ActGenericContext(spray_dirt, 3, 7.0))

		s = s.createTransition()
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 265))
		s.addAction(bat.story.ActGenericContext(spray_dirt, 3, 7.0))
		s.addAction(bat.story.ActGenericContext(letter_auto))

		s = s.createTransition()
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 275))
		s.addAction(Scripts.story.ActSetCamera('WormCamera_Envelope'))

		s = s.createTransition()
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 279))
		s.addEvent("ShowDialogue",
				("Ta-da! Please deliver this express \[envelope] for me.",
						("Of course!", "I'm too sleepy...")))

		#
		# FORK - conversation splits.
		#
		syes = s.createTransition("Yes")
		# Use 'not equal' here, because it's safer than using two equals (in
		# case the dialogue returns a value other than 1 or 0).
		syes.addCondition(bat.story.CondEventNe("DialogueDismissed", 1, self))
		syes.addEvent("ShowDialogue", "Great!")

		sno = s.createTransition("No")
		sno.addCondition(bat.story.CondEventEq("DialogueDismissed", 1, self))
		sno.addEvent("ShowDialogue", "Oh, come on! It's your job, after all.")
		# Lots of text, so wait for a second.
		sno = sno.createTransition()
		sno.addCondition(bat.story.CondWait(1))

		#
		# Give letter - conversation merges.
		#
		s = bat.story.State("Give letter")
		syes.addTransition(s)
		sno.addTransition(s)
		s.addAction(Scripts.story.ActRemoveCamera('WormCamera_Envelope'))
		s.addAction(bat.story.ActAction('BurstOut', 290, 330, Worm.L_ANIM))
		s.addAction(bat.story.ActAction('BurstOut_S', 290, 330, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition()
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 308))
		s.addAction(bat.story.ActGenericContext(letter_manual))

		s = s.createTransition()
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 315))
		s.addAction(bat.story.ActGenericContext(letter_hide))

		#
		# Point to lighthouse
		#
		s = s.createTransition("Point to lighthouse")
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 330))
		s.addEvent("ShowDialogue", "Please take it to the lighthouse keeper as soon as possible. I have paid for express mail!")
		s.addAction(bat.story.ActAction('BurstOut', 360, 395, Worm.L_ANIM))
		s.addAction(bat.story.ActAction('BurstOut_S', 360, 395, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition()
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 360))
		s.addAction(Scripts.story.ActSetCamera('WormCamera_Lighthouse'))
		s.addAction(Scripts.story.ActSetFocalPoint('Torch'))
		s.addAction(Scripts.story.ActShowMarker('Torch'))

		s = s.createTransition()
		s.addAction(Scripts.story.ActSetCamera('WormCamera_Lighthouse_zoom'))

		s = s.createTransition()
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 394))
		s.addCondition(bat.story.CondEvent("DialogueDismissed", self))
		s.addAction(Scripts.story.ActRemoveCamera('WormCamera_Lighthouse_zoom'))
		s.addAction(Scripts.story.ActRemoveCamera('WormCamera_Lighthouse'))
		s.addAction(Scripts.story.ActRemoveFocalPoint('Torch'))
		s.addAction(Scripts.story.ActShowMarker(None))
		s.addEvent("ShowDialogue", "See you later!")
		s.addAction(bat.story.ActAction('BurstOut', 395, 420, Worm.L_ANIM))
		s.addAction(bat.story.ActAction('BurstOut_S', 395, 420, Worm.L_ANIM, 'WormBody'))

		s = s.createTransition()
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 420))
		s.addCondition(bat.story.CondEvent("DialogueDismissed", self))
		s.addAction(bat.story.ActAction('BurstOut', 420, 540, Worm.L_ANIM))
		s.addAction(bat.story.ActAction('BurstOut_S', 420, 540, Worm.L_ANIM, 'WormBody'))
		s.addAction(bat.story.ActMusicStop())

		#
		# Return to game
		#
		s = s.createTransition("Return to game")
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 460))
		s.addAction(bat.story.ActAction('SodFade', 120, 200, 0, 'Sods'))
		s.addAction(Scripts.story.ActResumeInput())
		s.addAction(Scripts.story.ActRemoveCamera('WormCamera_Lighthouse_zoom'))
		s.addAction(Scripts.story.ActRemoveCamera('WormCamera_Converse'))
		s.addAction(Scripts.story.ActRemoveFocalPoint('CargoHoldAuto'))
		s.addAction(bat.story.ActStoreSet('/game/level/wormMissionStarted', True))

		#
		# Clean up. At this point, the worm is completely hidden and the sods have faded.
		#
		s = s.createTransition("Clean up")
		s.addCondition(bat.story.CondActionGE(Worm.L_ANIM, 540))
		s.addAction(bat.story.ActDestroy())

	def isInsideWorld(self):
		return True
