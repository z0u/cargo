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
		s = self.rootState.createTransition("Init")
		s.addAction(Scripts.story.ActSuspendInput())
		s.addWeakEvent("StartLoading", self)

		s = s.createTransition()
		s.addCondition(bat.story.CondWait(1))
		s.addWeakEvent("FinishLoading", self)
		s.addAction(Scripts.story.ActSetCamera('LK_Cam_Long'))
		s.addAction(Scripts.story.ActSetFocalPoint('FF_Face'))
		# Teleport here in addition to when the lighthouse keeper is first
		# spawned, since this may be the second time the snail is approaching.
		s.addEvent("TeleportSnail", "LK_SnailTalkPos")
		s.addAction(bat.story.ActAction('LK_Greet', 1, 80, LighthouseKeeper.L_ANIM))

		s = s.createTransition("Close-up")
		s.addCondition(bat.story.CondActionGE(LighthouseKeeper.L_ANIM, 32))
		s.addAction(Scripts.story.ActSetCamera('LK_Cam_CU_LK'))
		s.addAction(Scripts.story.ActRemoveCamera('LK_Cam_Long'))

		s = s.createTransition()
		s.addCondition(bat.story.CondActionGE(LighthouseKeeper.L_ANIM, 70))

		sfirstmeeting = s.createTransition()
		sfirstmeeting.addCondition(bat.story.CNot(bat.story.CondStore(
				'/game/level/lkMissionStarted', True, False)))
		sfirstmeeting.addEvent("ShowDialogue", ("Cargo! What's up?",
				("\[envelope]!", "Just saying \"hi\".")))

		sdeliver1 = sfirstmeeting.createTransition("delivery1")
		sdeliver1.addCondition(bat.story.CondEventNe("DialogueDismissed", 1, self))
		sdeliver1 = self.sg_accept_delivery([sdeliver1])

		ssecondmeeting = s.createTransition()
		ssecondmeeting.addCondition(bat.story.CondStore(
				'/game/level/lkMissionStarted', True, False))
		ssecondmeeting.addEvent("ShowDialogue", ("Hi again! What's up?",
				("What am I to do again?", "Just saying \"hi\".")))

		sdeliver2 = ssecondmeeting.createTransition("delivery2")
		sdeliver2.addCondition(bat.story.CondEventNe("DialogueDismissed", 1, self))

		sdeliver_merged = self.sg_give_mission([sdeliver1, sdeliver2])

		snothing = bat.story.State("nothing")
		sfirstmeeting.addTransition(snothing)
		ssecondmeeting.addTransition(snothing)
		snothing.addCondition(bat.story.CondEventEq("DialogueDismissed", 1, self))
		snothing.addEvent("ShowDialogue", "OK - hi! But it's hard work operating the lighthouse without a button! Let's talk later.")
		snothing.addAction(bat.story.ActAction('LK_Goodbye', 1, 80, LighthouseKeeper.L_ANIM))
		# Intermediate step, then jump to end
		snothing = snothing.createTransition()
		snothing.addCondition(bat.story.CondActionGE(LighthouseKeeper.L_ANIM, 80))
		snothing.addCondition(bat.story.CondEvent("DialogueDismissed", self))
		snothing.addAction(bat.story.ActAction('LK_Goodbye', 80, 90, LighthouseKeeper.L_ANIM))

		snothing = snothing.createTransition()
		snothing.addCondition(bat.story.CondActionGE(LighthouseKeeper.L_ANIM, 90))

		#
		# Return to game
		#
		s = bat.story.State("Return to game")
		sdeliver_merged.addTransition(s)
		snothing.addTransition(s)
		s.addAction(Scripts.story.ActResumeInput())
		s.addAction(Scripts.story.ActRemoveCamera('LK_Cam_Long'))
		s.addAction(Scripts.story.ActRemoveCamera('LK_Cam_CU_LK'))
		s.addAction(Scripts.story.ActRemoveFocalPoint('FF_Face'))

		#
		# Play idle animation
		#
		s = s.createTransition()
		s.addAction(bat.story.ActAction('LK_WorkingHard', 1, 36, LighthouseKeeper.L_ANIM,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=4.0))

		#
		# Loop back to start when snail moves away.
		#
		s = s.createTransition()
		s.addCondition(bat.story.CondSensorNot('Near'))

		s = s.createTransition("Reset")
		s.addCondition(bat.story.CondSensor('Near'))
		s.addTransition(self.rootState)

	def sg_accept_delivery(self, preceding_states):
		s = bat.story.State("delivery")
		for ps in preceding_states:
			ps.addTransition(s)
		s.addEvent("ShowDialogue", "Ah, a \[envelope] for me? Thanks.")

		s = s.createTransition()
		s.addCondition(bat.story.CondEvent("DialogueDismissed", self))

		s = s.createTransition()
		s.addCondition(bat.story.CondWait(1))
		s.addEvent("ShowDialogue", "Oh no! It's a quote for a new button, and it's too expensive.")

		s = s.createTransition()
		s.addCondition(bat.story.CondEvent("DialogueDismissed", self))
		s.addEvent("ShowDialogue", "Blast! I can't believe someone stole it in the first place.")

		s = s.createTransition()
		s.addCondition(bat.story.CondEvent("DialogueDismissed", self))

		s = s.createTransition()
		s.addCondition(bat.story.CondWait(1))
		s.addEvent("ShowDialogue", "Phew, this is thirsty work.")

		s = s.createTransition()
		s.addCondition(bat.story.CondEvent("DialogueDismissed", self))
		s.addEvent("ShowDialogue", "Can you deliver something for me too?")

		s = s.createTransition()
		s.addCondition(bat.story.CondEvent("DialogueDismissed", self))
		s.addEvent("ShowDialogue", "I'm all out of sauce, you see. I'm "\
				"parched! But I'm stuck here, so I can't get to the sauce bar.")

		s = s.createTransition()
		s.addCondition(bat.story.CondEvent("DialogueDismissed", self))

		return s

	def sg_give_mission(self, preceding_states):
		s = bat.story.State("split")
		for ps in preceding_states:
			ps.addTransition(s)

		s.addAction(Scripts.story.ActSetCamera('LK_Cam_SauceBar'))
		s.addAction(Scripts.story.ActSetFocalPoint('B_SauceBarSign'))
		s.addAction(Scripts.story.ActShowMarker('B_SauceBarSign'))

		s = s.createTransition()
		s.addEvent("ShowDialogue", ("Please go to the bar and order me some "\
				"black bean sauce.", ("Gross!", "No problem.")))
		s.addAction(Scripts.story.ActSetCamera('LK_Cam_SauceBar_zoom'))

		sno = s.createTransition("no")
		sno.addCondition(bat.story.CondEventNe("DialogueDismissed", 1, self))
		sno.addEvent("ShowDialogue", "Hey, no one asked you to drink it! Off you go.")
		sno.addAction(Scripts.story.ActRemoveCamera('LK_Cam_SauceBar_zoom'))
		sno.addAction(Scripts.story.ActRemoveCamera('LK_Cam_SauceBar'))
		sno.addAction(Scripts.story.ActRemoveFocalPoint('B_SauceBarSign'))
		sno.addAction(Scripts.story.ActShowMarker(None))

		syes = s.createTransition("yes")
		syes.addCondition(bat.story.CondEventEq("DialogueDismissed", 1, self))
		syes.addEvent("ShowDialogue", "Thanks!")
		syes.addAction(Scripts.story.ActRemoveCamera('LK_Cam_SauceBar_zoom'))
		syes.addAction(Scripts.story.ActRemoveCamera('LK_Cam_SauceBar'))
		syes.addAction(Scripts.story.ActRemoveFocalPoint('B_SauceBarSign'))
		syes.addAction(Scripts.story.ActShowMarker(None))

		s = bat.story.State("merge")
		syes.addTransition(s)
		sno.addTransition(s)
		s.addCondition(bat.story.CondEvent("DialogueDismissed", self))
		s.addAction(bat.story.ActStoreSet('/game/level/lkMissionStarted', True))

		return s
