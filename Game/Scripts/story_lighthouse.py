
import bge

import bxt
from . import director
from .story import *

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
		sce = self.scene
		if "LighthouseKeeper" in sce.objects:
			print("Warning: tried to create LighthouseKeeperSet twice.")
			return

		obTemplate = sce.objectsInactive["LighthouseKeeperSet"]
		spawnPoint = sce.objects["LighthouseKeeperSpawn"]
		ob = sce.addObject(obTemplate, spawnPoint)
		bxt.bmath.copy_transform(spawnPoint, ob)
		bxt.types.Event("ShowLoadingScreen", (False, None)).send()

	def kill_keeper(self):
		try:
			ob = self.scene.objects["LighthouseKeeperSet"]
			ob.endObject()
		except KeyError:
			print("Warning: could not delete LighthouseKeeperSet")

	def arrive(self):
		print("Arriving at lighthouse.")
		self.inLocality = True
		cbEvent = bxt.types.Event("EnterLighthouse")
		bxt.types.Event("ShowLoadingScreen", (True, cbEvent)).send()

	def leave(self):
		# Remove the keeper to prevent its armature from chewing up resources.
		print("Leaving lighthouse.")
		self.kill_keeper()
		self.inLocality = False

	@bxt.types.expose
	@bxt.utils.controller_cls
	def touched(self, c):
		if self.inLocality:
			# Check whether the snail is leaving.
			sNear = c.sensors["Near"]
			if not director.Director().mainCharacter in sNear.hitObjectList:
				self.leave()
		else:
			# Check whether the snail is entering.
			sCollision = c.sensors[0]
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
		s.addCondition(CondSensor('Near'))
		s.addAction(ActSuspendInput())
		s.addWeakEvent("StartLoading", self)
		s.addAction(ActSetCamera('LK_Cam_Long'))
		s.addAction(ActSetFocalPoint('LighthouseKeeper'))

		s = s.createTransition()
		s.addCondition(CondWait(1))
		s.addWeakEvent("FinishLoading", self)

		s = s.createTransition("Close-up")
		s.addCondition(CondWait(2))
		s.addAction(ActRemoveCamera('LK_Cam_Long'))
		s.addAction(ActSetCamera('LK_Cam_CU_LK'))

		sfirstmeeting = s.createTransition()
		sfirstmeeting.addCondition(CondStoreNe('/game/level/lkMissionStarted', True, False))
		sfirstmeeting.addEvent("ShowDialogue", ("Oh, hello Cargo! What's up?",
				("\[envelope]!", "Just saying \"hi\".")))

		sdeliver1 = sfirstmeeting.createTransition("delivery1")
		sdeliver1.addCondition(CondEventNe("DialogueDismissed", 1))
		sdeliver1 = self.sg_accept_delivery([sdeliver1])

		ssecondmeeting = s.createTransition()
		ssecondmeeting.addCondition(CondStoreEq('/game/level/lkMissionStarted', True, False))
		ssecondmeeting.addEvent("ShowDialogue", ("Hi again! What's up?",
				("What am I to do again?", "Just saying \"hi\".")))

		sdeliver2 = ssecondmeeting.createTransition("delivery2")
		sdeliver2.addCondition(CondEventNe("DialogueDismissed", 1))

		sdeliver_merged = self.sg_give_mission([sdeliver1, sdeliver2])

		snothing = State("nothing")
		sfirstmeeting.addTransition(snothing)
		ssecondmeeting.addTransition(snothing)
		snothing.addCondition(CondEventEq("DialogueDismissed", 1))
		snothing.addEvent("ShowDialogue", "OK - hi! But I'm kind of busy. Let's talk later.")
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
		s.addAction(ActRemoveFocalPoint('LighthouseKeeper'))

		#
		# Loop back to start when snail moves away.
		#
		s = s.createTransition("Reset")
		s.addCondition(CondSensorNot('Near'))
		s.addTransition(self.rootState)

	def sg_accept_delivery(self, preceding_states):
		s = State("delivery")
		for ps in preceding_states:
			ps.addTransition(s)
		s.addEvent("ShowDialogue", "Ah, a \[envelope] for me? Thanks.")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "I'm glad you're here, actually - I need "\
				"you to deliver something for me, too!")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "I'm all out of sauce, you see. I'm "\
				"parched! But work is busy, so I can't get to the sauce bar.")

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
