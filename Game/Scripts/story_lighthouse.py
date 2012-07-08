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

import bxt
from . import director
from .story import *

def factory(sce):
	if not "Firefly" in sce.objectsInactive:
		try:
			bge.logic.LibLoad('//Firefly_loader.blend', 'Scene', load_actions=True)
		except ValueError as e:
			print('Warning: could not load firefly:', e)

	return bxt.types.add_and_mutate_object(sce, "Firefly", "Firefly")

class Lighthouse(bxt.types.BX_GameObject, bge.types.KX_GameObject):
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
		bxt.types.EventBus().add_listener(self)
		self.inLocality = False

	def on_event(self, event):
		if event.message == "EnterLighthouse":
			self.spawn_keeper()

	def spawn_keeper(self):
		# Need to use self.scene here because we might be called from another
		# scene (due to the event bus).
		lk = factory(self.scene)
		spawnPoint = self.scene.objects["LK_FireflySpawn"]
		bxt.bmath.copy_transform(spawnPoint, lk)
		bxt.types.Event("TeleportSnail", "LK_SnailTalkPos").send()

	def kill_keeper(self):
		try:
			ob = self.scene.objects["Firefly"]
			ob.endObject()
		except KeyError:
			print("Warning: could not delete Firefly")

	def arrive(self):
		self.inLocality = True
		cbEvent = bxt.types.Event("EnterLighthouse")
		bxt.types.Event("ShowLoadingScreen", (True, cbEvent)).send()
		store.put('/game/level/spawnPoint', 'SpawnTorch')

	def leave(self):
		# Remove the keeper to prevent its armature from chewing up resources.
		self.kill_keeper()
		self.inLocality = False

	@bxt.types.expose
	@bxt.utils.controller_cls
	def touched(self, c):
		if self.inLocality:
			# Check whether the snail is leaving.
			sNear = c.sensors['Near']
			if not director.Director().mainCharacter in sNear.hitObjectList:
				self.leave()
		else:
			# Check whether the snail is entering.
			sCollision = c.sensors['Collision']
			if director.Director().mainCharacter in sCollision.hitObjectList:
				self.arrive()

class LighthouseKeeper(Chapter, bge.types.BL_ArmatureObject):
	L_IDLE = 0
	L_ANIM = 1

	def __init__(self, old_owner):
		Chapter.__init__(self, old_owner)
		#bxt.types.WeakEvent('StartLoading', self).send()
		self.create_state_graph()

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
		s.addAction(ActSuspendInput())
		s.addWeakEvent("StartLoading", self)

		s = s.createTransition()
		s.addCondition(CondWait(1))
		s.addWeakEvent("FinishLoading", self)
		s.addAction(ActSetCamera('LK_Cam_Long'))
		s.addAction(ActSetFocalPoint('FF_Face'))
		# Teleport here in addition to when the lighthouse keeper is first
		# spawned, since this may be the second time the snail is approaching.
		s.addEvent("TeleportSnail", "LK_SnailTalkPos")
		s.addAction(ActAction('LK_Converse', 1, 60, LighthouseKeeper.L_ANIM))

		s = s.createTransition("Close-up")
		s.addCondition(CondActionGE(LighthouseKeeper.L_ANIM, 40))
		s.addAction(ActSetCamera('LK_Cam_CU_LK'))
		s.addAction(ActRemoveCamera('LK_Cam_Long'))

		sfirstmeeting = s.createTransition()
		sfirstmeeting.addCondition(CNot(CondStore('/game/level/lkMissionStarted', True, False)))
		sfirstmeeting.addEvent("ShowDialogue", ("Cargo! What's up?",
				("\[envelope]!", "Just saying \"hi\".")))

		sdeliver1 = sfirstmeeting.createTransition("delivery1")
		sdeliver1.addCondition(CondEventNe("DialogueDismissed", 1))
		sdeliver1 = self.sg_accept_delivery([sdeliver1])

		ssecondmeeting = s.createTransition()
		ssecondmeeting.addCondition(CondStore('/game/level/lkMissionStarted', True, False))
		ssecondmeeting.addEvent("ShowDialogue", ("Hi again! What's up?",
				("What am I to do again?", "Just saying \"hi\".")))

		sdeliver2 = ssecondmeeting.createTransition("delivery2")
		sdeliver2.addCondition(CondEventNe("DialogueDismissed", 1))

		sdeliver_merged = self.sg_give_mission([sdeliver1, sdeliver2])

		snothing = State("nothing")
		sfirstmeeting.addTransition(snothing)
		ssecondmeeting.addTransition(snothing)
		snothing.addCondition(CondEventEq("DialogueDismissed", 1))
		snothing.addEvent("ShowDialogue", "OK - hi! But it's hard work operating the lighthouse without a button! Let's talk later.")
		# Intermediate step, then jump to end
		snothing = snothing.createTransition()
		snothing.addCondition(CondEvent("DialogueDismissed"))

		#
		# Return to game
		#
		s = State("Return to game")
		sdeliver_merged.addTransition(s)
		snothing.addTransition(s)
		s.addAction(ActResumeInput())
		s.addAction(ActRemoveCamera('LK_Cam_Long'))
		s.addAction(ActRemoveCamera('LK_Cam_CU_LK'))
		s.addAction(ActRemoveCamera('LK_Cam_CU_Cargo'))
		s.addAction(ActRemoveFocalPoint('FF_Face'))

		#
		# Loop back to start when snail moves away.
		#
		s = s.createTransition()
		s.addCondition(CondSensorNot('Near'))

		s = s.createTransition("Reset")
		s.addCondition(CondSensor('Near'))
		s.addTransition(self.rootState)

	def sg_accept_delivery(self, preceding_states):
		s = State("delivery")
		for ps in preceding_states:
			ps.addTransition(s)
		s.addEvent("ShowDialogue", "Ah, a \[envelope] for me? Thanks.")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))

		s = s.createTransition()
		s.addCondition(CondWait(1))
		s.addEvent("ShowDialogue", "Oh no! It's a quote for a new button, and it's too expensive.")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "Blast! I can't believe someone stole it in the first place.")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))

		s = s.createTransition()
		s.addCondition(CondWait(1))
		s.addEvent("ShowDialogue", "Phew, this is thirsty work.")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "Can you deliver something for me too?")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "I'm all out of sauce, you see. I'm "\
				"parched! But I'm stuck here, so I can't get to the sauce bar.")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))

		return s

	def sg_give_mission(self, preceding_states):
		s = State("split")
		for ps in preceding_states:
			ps.addTransition(s)
		s.addEvent("ShowDialogue", ("Please go to the bar and order me some "\
				"black bean sauce.", ("Gross!", "No problem.")))
		s.addAction(ActSetCamera('LK_Cam_SauceBar'))
		s.addAction(ActSetFocalPoint('B_SauceBarSign'))
		s.addAction(ActShowMarker('B_SauceBarSign'))

		sno = s.createTransition("no")
		sno.addCondition(CondEventNe("DialogueDismissed", 1))
		sno.addEvent("ShowDialogue", "Hey, no one asked you to drink it! Off you go.")
		sno.addAction(ActRemoveCamera('LK_Cam_SauceBar'))
		sno.addAction(ActRemoveFocalPoint('B_SauceBarSign'))
		sno.addAction(ActShowMarker(None))

		syes = s.createTransition("yes")
		syes.addCondition(CondEventEq("DialogueDismissed", 1))
		syes.addEvent("ShowDialogue", "Thanks!")
		syes.addAction(ActRemoveCamera('LK_Cam_SauceBar'))
		syes.addAction(ActRemoveFocalPoint('B_SauceBarSign'))
		syes.addAction(ActShowMarker(None))

		s = State("merge")
		syes.addTransition(s)
		sno.addTransition(s)
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addAction(ActStoreSet('/game/level/lkMissionStarted', True))

		return s
