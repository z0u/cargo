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
import bat.bmath
import bat.utils
import bat.sound
import bat.story

import Scripts.director
import Scripts.story
import logging

def factory(sce):
	if not "Firefly" in sce.objectsInactive:
		try:
			bge.logic.LibLoad('//Firefly_loader.blend', 'Scene', load_actions=True)
		except ValueError as e:
			print('Warning: could not load firefly:', e)

	return bat.bats.add_and_mutate_object(sce, "Firefly", "Firefly")

class Lighthouse(bat.bats.BX_GameObject, bge.types.KX_GameObject):
	'''Watches for Cargo's approach of the lighthouse, and creates the
	lighthouse keeper in response.'''
	_prefix = 'LH_'

	# Note that this is a little convoluted:
	#  1. Cargo touches a sensor, causing the loading screen to be shown.
	#  2. When the loading screen has been fully displayed, it sends an event
	#     (specified in 1.)
	#  3. When the event is received here, the lighthouse keeper is spawned.
	#  4. Then, the loading screen is hidden again.
	# This is because spawning the lighthouse keeper results in a small delay.
	# Showing the loading screen also allows us to reposition the snail for the
	# conversation.

	def __init__(self, old_owner):
		bat.event.EventBus().add_listener(self)
		self.inLocality = False

	def on_event(self, event):
		if event.message == "EnterLighthouse":
			self.spawn_keeper()

	def spawn_keeper(self):
		# Need to use self.scene here because we might be called from another
		# scene (due to the event bus).
		lk = factory(self.scene)
		spawnPoint = self.scene.objects["LK_FireflySpawn"]
		bat.bmath.copy_transform(spawnPoint, lk)
		bat.event.Event("TeleportSnail", "LK_SnailTalkPos").send()

	def kill_keeper(self):
		try:
			ob = self.scene.objects["Firefly"]
			ob.endObject()
		except KeyError:
			print("Warning: could not delete Firefly")

	def arrive(self):
		self.inLocality = True
		cbEvent = bat.event.Event("EnterLighthouse")
		bat.event.Event("ShowLoadingScreen", (True, cbEvent)).send()
		bat.store.put('/game/level/spawnPoint', 'SpawnTorch')

	def leave(self):
		# Remove the keeper to prevent its armature from chewing up resources.
		self.kill_keeper()
		self.inLocality = False

	@bat.bats.expose
	@bat.utils.controller_cls
	def touched(self, c):
		sNear = c.sensors['Near']
		sCollision = c.sensors['Collision']

		# Music is controlled by near sensor only.
		if sNear.triggered:
			if sNear.positive:
				bat.sound.Jukebox().play_files(self, 1,
						'//Sound/Music/Idea-Random_loop.ogg',
						introfile='//Sound/Music/Idea-Random_intro.ogg')
			else:
				bat.sound.Jukebox().stop(self)

		# Firefly lifecycle is controller by near and touch sensor. This object
		# maintains a state (inLocality) to prevent the firefly from being
		# spawned again when leaving the top of the lighthouse.
		if self.inLocality:
			# Check whether the snail is leaving.
			if not Scripts.director.Director().mainCharacter in sNear.hitObjectList:
				self.leave()
		else:
			# Check whether the snail is entering.
			if Scripts.director.Director().mainCharacter in sCollision.hitObjectList:
				self.arrive()

class LighthouseKeeper(bat.story.Chapter, bge.types.BL_ArmatureObject):
	L_IDLE = 0
	L_ANIM = 1

	log = logging.getLogger(__name__ + '.LighthouseKeeper')

	def __init__(self, old_owner):
		LighthouseKeeper.log.info("Creating new LighthouseKeeper")
		bat.story.Chapter.__init__(self, old_owner)
		#bat.event.WeakEvent('StartLoading', self).send()
		self.create_state_graph()
		self.playAction('LK_Breathing', 1, 36, LighthouseKeeper.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=4.0)

	def create_state_graph(self):
		'''
		Create the state machine that drives interaction with the lighthouse
		keeper.
		@see ../../doc/story_states/LighthouseKeeper.dia
		'''
		#
		# Set scene with a long shot camera.
		#
		s = self.rootState.create_successor("Init")
		s.add_action(Scripts.story.ActSuspendInput())
		s.add_event("StartLoading", self)

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(1))
		s.add_event("FinishLoading", self)
		s.add_action(Scripts.story.ActSetCamera('LK_Cam_Long'))
		s.add_action(Scripts.story.ActSetFocalPoint('FF_Face'))
		# Teleport here in addition to when the lighthouse keeper is first
		# spawned, since this may be the second time the snail is approaching.
		s.add_event("TeleportSnail", "LK_SnailTalkPos")
		s.add_action(bat.story.ActAction('LK_Greet', 1, 80, LighthouseKeeper.L_ANIM))

		s = s.create_successor("Close-up")
		s.add_condition(bat.story.CondActionGE(LighthouseKeeper.L_ANIM, 32))
		s.add_action(Scripts.story.ActSetCamera('LK_Cam_CU_LK'))
		s.add_action(Scripts.story.ActRemoveCamera('LK_Cam_Long'))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(LighthouseKeeper.L_ANIM, 70))

		sfirstmeeting = s.create_successor()
		sfirstmeeting.add_condition(bat.story.CNot(bat.story.CondStore(
				'/game/level/lkMissionStarted', True, False)))
		sfirstmeeting.add_event("ShowDialogue", ("Cargo! What's up?",
				("\[envelope]!", "Just saying \"hi\".")))

		sdliver1_start, sdeliver1_end = self.sg_accept_delivery()
		sdliver1_start.add_predecessor(sfirstmeeting)
		sdliver1_start.add_condition(bat.story.CondEventNe("DialogueDismissed", 1, self))

		ssecondmeeting = s.create_successor()
		ssecondmeeting.add_condition(bat.story.CondStore(
				'/game/level/lkMissionStarted', True, False))
		ssecondmeeting.add_event("ShowDialogue", ("Hi again! What's up?",
				("What am I to do again?", "Just saying \"hi\".")))

		sdeliver2 = ssecondmeeting.create_successor("delivery2")
		sdeliver2.add_condition(bat.story.CondEventNe("DialogueDismissed", 1, self))

		smission_start, smission_end = self.sg_give_mission()
		smission_start.add_predecessor(sdeliver1_end)
		smission_start.add_predecessor(sdeliver2)

		snothing = bat.story.State("nothing")
		snothing.add_predecessor(sfirstmeeting)
		snothing.add_predecessor(ssecondmeeting)
		snothing.add_condition(bat.story.CondEventEq("DialogueDismissed", 1, self))
		snothing.add_event("ShowDialogue", "OK - hi! But it's hard work operating the lighthouse without a button! Let's talk later.")
		snothing.add_action(bat.story.ActAction('LK_Goodbye', 1, 80, LighthouseKeeper.L_ANIM))
		# Intermediate step, then jump to end
		snothing = snothing.create_successor()
		snothing.add_condition(bat.story.CondActionGE(LighthouseKeeper.L_ANIM, 80))
		snothing.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		snothing.add_action(bat.story.ActAction('LK_Goodbye', 80, 90, LighthouseKeeper.L_ANIM))

		snothing = snothing.create_successor()
		snothing.add_condition(bat.story.CondActionGE(LighthouseKeeper.L_ANIM, 90))

		#
		# Return to game
		#
		s = bat.story.State("Return to game")
		s.add_predecessor(smission_end)
		s.add_predecessor(snothing)
		s.add_action(Scripts.story.ActResumeInput())
		s.add_action(Scripts.story.ActRemoveCamera('LK_Cam_Long'))
		s.add_action(Scripts.story.ActRemoveCamera('LK_Cam_CU_LK'))
		s.add_action(Scripts.story.ActRemoveFocalPoint('FF_Face'))

		#
		# Play idle animation
		#
		s = s.create_successor()
		s.add_action(bat.story.ActAction('LK_WorkingHard', 1, 36, LighthouseKeeper.L_ANIM,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=4.0))

		#
		# Loop back to start when snail moves away.
		#
		s = s.create_successor()
		s.add_condition(bat.story.CondSensorNot('Near'))

		s = s.create_successor("Reset")
		s.add_condition(bat.story.CondSensor('Near'))
		s.add_successor(self.rootState)

	def sg_accept_delivery(self):
		sdeliver_start = bat.story.State("delivery")
		sdeliver_start.add_event("ShowDialogue", "Ah, a \[envelope] for me? Thanks.")

		s = sdeliver_start.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(1))
		s.add_event("ShowDialogue", "Oh no! It's a quote for a new button, and it's too expensive.")

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "Blast! I can't believe someone stole it in the first place.")

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(1))
		s.add_event("ShowDialogue", "Phew, this is thirsty work.")

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "Can you deliver something for me too?")

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "I'm all out of sauce, you see. I'm "\
				"parched! But I'm stuck here, so I can't get to the sauce bar.")

		sdeliver_end = s.create_successor()
		sdeliver_end.add_condition(bat.story.CondEvent("DialogueDismissed", self))

		return sdeliver_start, sdeliver_end

	def sg_give_mission(self):
		smission_start = bat.story.State("split")
		smission_start.add_action(Scripts.story.ActSetCamera('LK_Cam_SauceBar'))
		smission_start.add_action(Scripts.story.ActSetFocalPoint('B_SauceBarSign'))
		smission_start.add_action(Scripts.story.ActShowMarker('B_SauceBarSign'))

		s = smission_start.create_successor()
		s.add_event("ShowDialogue", ("Please go to the bar and order me some "\
				"black bean sauce.", ("Gross!", "No problem.")))
		s.add_action(Scripts.story.ActSetCamera('LK_Cam_SauceBar_zoom'))

		sno = s.create_successor("no")
		sno.add_condition(bat.story.CondEventNe("DialogueDismissed", 1, self))
		sno.add_event("ShowDialogue", "Hey, no one asked you to drink it! Off you go.")
		sno.add_action(Scripts.story.ActRemoveCamera('LK_Cam_SauceBar_zoom'))
		sno.add_action(Scripts.story.ActRemoveCamera('LK_Cam_SauceBar'))
		sno.add_action(Scripts.story.ActRemoveFocalPoint('B_SauceBarSign'))
		sno.add_action(Scripts.story.ActShowMarker(None))

		syes = s.create_successor("yes")
		syes.add_condition(bat.story.CondEventEq("DialogueDismissed", 1, self))
		syes.add_event("ShowDialogue", "Thanks!")
		syes.add_action(Scripts.story.ActRemoveCamera('LK_Cam_SauceBar_zoom'))
		syes.add_action(Scripts.story.ActRemoveCamera('LK_Cam_SauceBar'))
		syes.add_action(Scripts.story.ActRemoveFocalPoint('B_SauceBarSign'))
		syes.add_action(Scripts.story.ActShowMarker(None))

		smission_end = bat.story.State("merge")
		smission_end.add_predecessor(syes)
		smission_end.add_predecessor(sno)
		smission_end.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		smission_end.add_action(bat.story.ActStoreSet('/game/level/lkMissionStarted', True))

		return smission_start, smission_end
