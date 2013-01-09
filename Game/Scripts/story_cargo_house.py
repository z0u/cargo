#
# Copyright 2009-2012 Alex Fraser <alex@phatcore.com>
# Copyright 2012, Ben Sturmfels <ben@sturm.com.au>
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
			bat.sound.Jukebox().play_files(self, 1, '//Sound/Music/03-TheHouse.ogg', volume=0.7, loop=False)
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

		s = self.rootState.create_successor("Init")
		s.add_action(Scripts.story.ActSuspendInput())

		s = s.create_successor("Init")
		s.add_condition(bat.story.CondWait(1))
		s.add_event("ForceEnterShell", False)
		s.add_action(Scripts.story.ActSetCamera('WormCamera_Enter'))
		s.add_action(Scripts.story.ActSetFocalPoint('CargoHoldAuto'))
		s.add_action(bat.story.ActAction('ParticleEmitMove', 1, 1, Worm.L_ANIM, "ParticleEmitterLoc"))
		s.add_action(bat.story.ActGenericContext(letter_manual))

		#
		# Peer out of ground
		#
		s = s.create_successor("Begin")
		s.add_condition(bat.story.CondEvent('ShellEntered', self))
		s.add_event('AnchorShell', 'CH_ShellAnchor')
		s.add_event("FinishLoading", self)
		s.add_action(bat.story.ActGenericContext(spray_dirt, 10, 15.0))
		s.add_action(bat.story.ActAction('BurstOut', 1, 75, Worm.L_ANIM))
		s.add_action(bat.story.ActAction('BurstOut_S', 1, 75, Worm.L_ANIM, 'WormBody'))

		s = s.create_successor("Greet")
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 74.0))
		s.add_event("ShowDialogue", "Cargo?")
		s.add_action(bat.story.ActSound('//Sound/WormQuestion1.ogg'))

		#
		# Get out of the ground
		#
		s = s.create_successor("Get out of the ground")
		s.add_condition(bat.story.CondEvent('DialogueDismissed', self))
		s.add_action(Scripts.story.ActRemoveCamera('WormCamera_Enter'))
		s.add_action(Scripts.story.ActSetCamera('WormCamera_Converse'))
		s.add_action(bat.story.ActAction('BurstOut', 75, 186, Worm.L_ANIM))
		s.add_action(bat.story.ActAction('BurstOut_S', 75, 186, Worm.L_ANIM, 'WormBody'))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 115.0))
		s.add_action(bat.story.ActGenericContext(spray_dirt, 3, 10.0))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 147.0))
		s.add_action(bat.story.ActGenericContext(spray_dirt, 5, 10.0))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 153.0))
		s.add_action(bat.story.ActGenericContext(spray_dirt, 5, 10.0))

		#
		# Knock on shell
		#
		s = s.create_successor("Knock on shell")
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 185.0))
		s.add_action(Scripts.story.ActSetCamera('WormCamera_Knock'))
		s.add_event("ShowDialogue", "Wake up, Cargo!")
		s.add_action(bat.story.ActAction('BurstOut', 187, 200, Worm.L_ANIM,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))
		s.add_action(bat.story.ActAction('BurstOut_S', 187, 200, Worm.L_ANIM, 'WormBody'))

		sKnock = s.create_sub_step("Knock sound")
		sKnock.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 189, tap=True))
		sKnock.add_action(bat.story.ActSound('//Sound/Knock.ogg', vol=0.6, pitchmin=0.8,
				pitchmax= 1.1))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent('DialogueDismissed', self))
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 199))
		s.add_action(bat.story.ActAction('BurstOut', 200, 220, Worm.L_ANIM))
		s.add_action(bat.story.ActAction('BurstOut_S', 200, 220, Worm.L_ANIM, 'WormBody'))
		s.add_action(bat.story.ActSound('//Sound/Knock.ogg', vol=0.6, pitchmin=0.8,
				pitchmax= 1.1))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 200.0))
		s.add_action(Scripts.story.ActRemoveCamera('WormCamera_Knock'))

		#
		# Wake / chastise
		#
		s = s.create_successor("Wake")
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 205.0))
		s.add_event("ForceExitShell", True)

		s = s.create_successor("Chastise")
		s.add_condition(bat.story.CondEvent('ShellExited', self))
		s.add_event("ShowDialogue", "Sleeping in, eh? Don't worry, I won't tell anyone.")
		s.add_action(bat.story.ActSound('//Sound/WormQuestion2.ogg'))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent('DialogueDismissed', self))
		s.add_event("ShowDialogue", "I have something for you!")

		#
		# Dig up letter
		#
		s = s.create_successor("Dig up letter")
		s.add_condition(bat.story.CondEvent('DialogueDismissed', self))
		s.add_action(bat.story.ActAction('ParticleEmitMove', 2, 2, Worm.L_ANIM, "ParticleEmitterLoc"))
		s.add_action(bat.story.ActAction('BurstOut', 220, 280, Worm.L_ANIM))
		s.add_action(bat.story.ActAction('BurstOut_S', 220, 280, Worm.L_ANIM, 'WormBody'))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 235))
		s.add_action(bat.story.ActGenericContext(spray_dirt, 3, 10.0))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 241))
		s.add_action(bat.story.ActGenericContext(spray_dirt, 3, 7.0))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 249))
		s.add_action(bat.story.ActGenericContext(spray_dirt, 3, 7.0))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 257))
		s.add_action(bat.story.ActGenericContext(spray_dirt, 3, 7.0))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 265))
		s.add_action(bat.story.ActGenericContext(spray_dirt, 3, 7.0))
		s.add_action(bat.story.ActGenericContext(letter_auto))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 275))
		s.add_action(Scripts.story.ActSetCamera('WormCamera_Envelope'))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 279))
		s.add_event("ShowDialogue",
				("Ta-da! Please deliver this express \[envelope] for me.",
						("Of course!", "I'm too sleepy...")))
		s.add_action(bat.story.ActSound('//Sound/WormTaDa.ogg'))

		#
		# FORK - conversation splits.
		#
		syes = s.create_successor("Yes")
		# Use 'not equal' here, because it's safer than using two equals (in
		# case the dialogue returns a value other than 1 or 0).
		syes.add_condition(bat.story.CondEventNe("DialogueDismissed", 1, self))
		syes.add_event("ShowDialogue", "Great!")
		syes.add_action(bat.story.ActSound('//Sound/WormPleased.ogg'))

		sno = s.create_successor("No")
		sno.add_condition(bat.story.CondEventEq("DialogueDismissed", 1, self))
		sno.add_event("ShowDialogue", "Oh, come on! It's your job, after all.")
		sno.add_action(bat.story.ActSound('//Sound/WormFrown.ogg'))
		# Lots of text, so wait for a second.
		sno = sno.create_successor()
		sno.add_condition(bat.story.CondWait(1))

		#
		# Give letter - conversation merges.
		#
		s = bat.story.State("Give letter")
		syes.add_successor(s)
		sno.add_successor(s)
		s.add_action(Scripts.story.ActRemoveCamera('WormCamera_Envelope'))
		s.add_action(bat.story.ActAction('BurstOut', 290, 330, Worm.L_ANIM))
		s.add_action(bat.story.ActAction('BurstOut_S', 290, 330, Worm.L_ANIM, 'WormBody'))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 308))
		s.add_action(bat.story.ActGenericContext(letter_manual))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 315))
		s.add_action(bat.story.ActGenericContext(letter_hide))

		#
		# Point to lighthouse
		#
		s = s.create_successor("Point to lighthouse")
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 330))
		s.add_event("ShowDialogue", "Please take it to the lighthouse keeper as soon as possible. I have paid for express mail!")
		s.add_action(bat.story.ActAction('BurstOut', 360, 395, Worm.L_ANIM))
		s.add_action(bat.story.ActAction('BurstOut_S', 360, 395, Worm.L_ANIM, 'WormBody'))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 360))
		s.add_action(Scripts.story.ActSetCamera('WormCamera_Lighthouse'))
		s.add_action(Scripts.story.ActSetFocalPoint('Torch'))
		s.add_action(Scripts.story.ActShowMarker('Torch'))

		s = s.create_successor()
		s.add_action(Scripts.story.ActSetCamera('WormCamera_Lighthouse_zoom'))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 394))
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(Scripts.story.ActRemoveCamera('WormCamera_Lighthouse_zoom'))
		s.add_action(Scripts.story.ActRemoveCamera('WormCamera_Lighthouse'))
		s.add_action(Scripts.story.ActRemoveFocalPoint('Torch'))
		s.add_action(Scripts.story.ActShowMarker(None))

		s = s.create_successor()
		s.add_event("ShowDialogue", "The lighthouse is marked in red on your map.")
		s.add_action(bat.story.ActStoreSet('/game/level/mapGoal', 'Torch'))
		s.add_event("MapGoalChanged")

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "See you later!")
		s.add_action(bat.story.ActSound('//Sound/WormBye.ogg'))
		s.add_action(bat.story.ActAction('BurstOut', 395, 420, Worm.L_ANIM))
		s.add_action(bat.story.ActAction('BurstOut_S', 395, 420, Worm.L_ANIM, 'WormBody'))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 420))
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(bat.story.ActAction('BurstOut', 420, 540, Worm.L_ANIM))
		s.add_action(bat.story.ActAction('BurstOut_S', 420, 540, Worm.L_ANIM, 'WormBody'))
		s.add_action(bat.story.ActMusicStop())

		#
		# Return to game
		#
		s = s.create_successor("Return to game")
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 460))
		s.add_action(bat.story.ActAction('SodFade', 120, 200, 0, 'Sods'))
		s.add_action(Scripts.story.ActResumeInput())
		s.add_action(Scripts.story.ActRemoveCamera('WormCamera_Lighthouse_zoom'))
		s.add_action(Scripts.story.ActRemoveCamera('WormCamera_Converse'))
		s.add_action(Scripts.story.ActRemoveFocalPoint('CargoHoldAuto'))
		s.add_action(bat.story.ActStoreSet('/game/level/wormMissionStarted', True))

		#
		# Clean up. At this point, the worm is completely hidden and the sods have faded.
		#
		s = s.create_successor("Clean up")
		s.add_condition(bat.story.CondActionGE(Worm.L_ANIM, 540))
		s.add_action(bat.story.ActDestroy())

	def isInsideWorld(self):
		return True
