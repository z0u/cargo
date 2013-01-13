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
import bat.bmath
import bat.utils

import bat.story
import Scripts.story

def factory():
	scene = bge.logic.getCurrentScene()
	if not "Ant" in scene.objectsInactive:
		try:
			bge.logic.LibLoad('//Ant_loader.blend', 'Scene', load_actions=True)
		except ValueError as e:
			print('Warning: could not load ant:', e)

	return bat.bats.add_and_mutate_object(scene, "Ant", "Ant")

class Honeypot(bat.bats.BX_GameObject, bge.types.KX_GameObject):

	_prefix = "HP_"

	def __init__(self, old_owner):
		#bat.event.WeakEvent("StartLoading", self).send()
		ant1 = factory()
		bat.bmath.copy_transform(self.children["Ant1SpawnPoint"], ant1)
		ant1.setParent(self)

	@bat.bats.expose
	@bat.utils.controller_cls
	def approach(self, c):
		if c.sensors[0].positive:
			player = c.sensors[0].hitObject
			if not player.is_in_shell:
				bat.event.Event("ApproachAnts").send()

class Ant(bat.story.Chapter, bat.bats.BX_GameObject, bge.types.BL_ArmatureObject):
	L_IDLE = 0
	L_ANIM = 1

	def __init__(self, old_owner):
		bat.story.Chapter.__init__(self, old_owner)
		self.music1_action = bat.story.ActMusicPlay(
				'//Sound/Music/08-TheAnt_loop.ogg',
				introfile='//Sound/Music/08-TheAnt_intro.ogg', volume=0.7,
				fade_in_rate=1)
		self.knock_sound_action = bat.story.ActSound('//Sound/Knock.ogg',
				vol=0.5, pitchmin=0.7, pitchmax=0.76, emitter=self,
				maxdist=60.0)
		self.step_sound_action = bat.story.ActSound('//Sound/AntStep1.ogg',
				'//Sound/AntStep2.ogg')
		self.pick = self.childrenRecursive['Ant_Pick']

		if 'Level_Dungeon' in self.scene.objects:
			self.create_dungeon_state_graph()
		else:
			self.create_outdoors_state_graph()

	def pick_up(self):
		''';)'''
		bat.bmath.copy_transform(self.children['Ant_RH_Hook'], self.pick)
		self.pick.setParent(self.children['Ant_RH_Hook'])

	def drop_pick(self):
		'''Release the pick, and leave it stuck where it is.'''
		self.pick.removeParent()

	def get_focal_points(self):
		return [self.children['Ant_Face'], self]

	#########################
	# Outdoors
	#########################

	def create_outdoors_state_graph(self):
		s = self.rootState.create_successor("Init")
		s.add_action(bat.story.ActConstraintSet("Hand.L", "Copy Transforms", 1.0))
		s.add_action(bat.story.ActAction('Ant_Digging1', 1, 38, Ant.L_ANIM,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))
		sKnock = s.create_sub_step("Knock sound")
		sKnock.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 34.5, tap=True))
		sKnock.add_action(self.knock_sound_action)

		sconv_start, sconv_end = self.create_conversation()
		sconv_start.add_predecessor(s)

		senter_start, _ = self.create_enter_states()
		senter_start.add_predecessor(s)

		#
		# Loop back to start.
		#
		s = bat.story.State("Reset")
		s.add_predecessor(sconv_end)
		s.add_action(Scripts.story.ActResumeInput())
		s.add_action(Scripts.story.ActRemoveCamera('AntCloseCam'))
		s.add_action(Scripts.story.ActRemoveCamera('AntCrackCam'))
		s.add_action(Scripts.story.ActRemoveCamera('AntCrackCamIn'))
		s.add_action(Scripts.story.ActRemoveCamera('AntMidCam'))
		s.add_action(Scripts.story.ActRemoveFocalPoint('Ant'))
		s.add_action(bat.story.ActMusicStop())
		s.add_action(bat.story.ActActionStop(Ant.L_IDLE))
		s.add_successor(self.rootState)

	def create_conversation(self):
		'''
		State graph that plays when Cargo approaches the ant at the tree door.
		'''
		sconv_start = bat.story.State("Talk")
		sconv_start.add_condition(bat.story.CondEvent("ApproachAnts", self))
		sconv_start.add_action(Scripts.story.ActSuspendInput())
		sconv_start.add_event("StartLoading", self)

		# Catch-many state for when the user cancels a dialogue. Should only be
		# allowed if the conversation has been played once already.
		scancel = bat.story.State("Cancel")
		scancel.add_condition(bat.story.CondEvent('DialogueCancelled', self))
		scancel.add_condition(bat.story.CondStore('/game/level/antConversation1', True, default=False))

		# Start conversation

		s = sconv_start.create_successor()
		s.add_condition(bat.story.CondWait(1))
		s.add_event("FinishLoading", self)
		s.add_action(Scripts.story.ActSetFocalPoint('Ant'))
		s.add_action(Scripts.story.ActSetCamera('AntCloseCam'))
		s.add_event("TeleportSnail", "HP_SnailTalkPos")
		# Reset camera pos
		s.add_action(bat.story.ActAction('HP_AntConverse_Cam', 1, 1, 0, ob='AntCloseCam'))
		s.add_action(bat.story.ActAction('HP_AntCrackCam', 1, 1, 0, ob='AntCrackCam'))
		# Raises head, takes deep breath
		s.add_event("ShowDialogue", "Mmmm, smell that?")
		s.add_action(bat.story.ActAction('HP_AntConverse', 30, 70, Ant.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))
		s.add_action(bat.story.ActAction('HP_AntConverse', 1, 30, Ant.L_ANIM))
		s.add_action(self.music1_action)

		# Gestures fiercely at Cargo

		scancel.add_predecessor(s)
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(bat.story.ActGeneric(self.drop_pick))
		s.add_event("ShowDialogue", "Doesn't it smell amazing? So sweet! So sugary!")
		s.add_action(bat.story.ActAction('HP_AntConverse', 90, 93, Ant.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=5.0))
		s.add_action(bat.story.ActAction('HP_AntConverse', 70, 90, Ant.L_ANIM, blendin=5.0))
		s.add_action(bat.story.ActAction('HP_AntConverse_Cam', 70, 90, 0, ob='AntCloseCam'))
		sdrop_pick = s.create_sub_step("Adjust influence")
		sdrop_pick.add_action(bat.story.ActConstraintFade("Hand.L", "Copy Transforms",
				1.0, 0.0, 70.0, 76.0, Ant.L_ANIM))
		# Step sounds
		sstep = s.create_sub_step()
		sstep.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 76, tap=True))
		sstep.add_action(self.step_sound_action)
		sstep = s.create_sub_step()
		sstep.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 82, tap=True))
		sstep.add_action(self.step_sound_action)

		# Holds fists tight; then, gestures towards the tree

		scancel.add_predecessor(s)
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(bat.story.ActActionStop(Ant.L_IDLE))
		s.add_action(bat.story.ActAction('HP_AntConverse', 95, 160, Ant.L_ANIM, blendin=2.0))
		s.add_event("ShowDialogue", "I've got to have it! But this wood is just too strong,")
		sswitch_cam = s.create_sub_step("Switch camera")
		sswitch_cam.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 126, tap=True))
		sswitch_cam.add_action(Scripts.story.ActSetCamera('AntCrackCam'))
		sswitch_cam.add_action(bat.story.ActAction('HP_AntCrackCam', 140, 360, 0,
				ob='AntCrackCam'))
		sloop = s.create_sub_step("Loop")
		sloop.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 160, tap=True))
		sloop.add_action(bat.story.ActAction('HP_AntConverse', 160, 230, Ant.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=2.0))

		# Sizes up door with hands in front of his eyes

		scancel.add_predecessor(s)
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 140))
		s.add_event("ShowDialogue", "... and this crack is too small, even for me.")
		s.add_action(bat.story.ActAction('HP_AntConverse', 240, 255, Ant.L_ANIM, blendin=2.0))
		s.add_action(Scripts.story.ActRemoveCamera('AntCrackCam'))
		s.add_action(Scripts.story.ActSetCamera('AntCrackCamIn'))
		sloop = s.create_sub_step("Loop")
		sloop.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 255, tap=True))
		sloop.add_action(bat.story.ActAction('HP_AntConverse', 255, 283, Ant.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=2.0))
		# Step sounds
		sstep = s.create_sub_step()
		sstep.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 245, tap=True))
		sstep.add_action(self.step_sound_action)
		sstep = s.create_sub_step()
		sstep.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 248, tap=True))
		sstep.add_action(self.step_sound_action)
		sstep = s.create_sub_step()
		sstep.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 267, tap=True))
		sstep.add_action(self.step_sound_action)
		sstep = s.create_sub_step()
		sstep.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 272, tap=True))
		sstep.add_action(self.step_sound_action)

		# Pauses to consider

		scancel.add_predecessor(s)
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "If only I had something stronger...")
		s.add_action(bat.story.ActAction('HP_AntConverse', 290, 300, Ant.L_ANIM, blendin=1.0))
		s.add_action(Scripts.story.ActRemoveCamera('AntCrackCamIn'))
		s.add_action(Scripts.story.ActSetCamera('AntCloseCam'))
		sloop = s.create_sub_step("Loop")
		sloop.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 300, tap=True))
		sloop.add_action(bat.story.ActAction('HP_AntConverse', 300, 347, Ant.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=2.0))

		# Picks up mattock, and glares at the door

		scancel.add_predecessor(s)
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 300))
		s.add_action(bat.story.ActActionStop(Ant.L_IDLE))
		s.add_action(bat.story.ActAction('HP_AntConverse', 360, 407, Ant.L_ANIM, blendin=1.0))
		s.add_event("ShowDialogue", "But I won't give up!")
		sgrab_pickR = s.create_sub_step("Grab pick - right hand")
		sgrab_pickR.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 370.5, tap=True))
		sgrab_pickR.add_action(bat.story.ActGeneric(self.pick_up))
		sgrab_pickL = s.create_sub_step("Grab pick - left hand")
		sgrab_pickL.add_action(bat.story.ActConstraintFade("Hand.L", "Copy Transforms",
				0.0, 1.0, 401.0, 403.0, Ant.L_ANIM))
		sloop = s.create_sub_step("Loop")
		sloop.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 407, tap=True))
		sloop.add_action(bat.story.ActAction('HP_AntConverse', 407, 440, Ant.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=2.0))
		# Step sounds
		sstep = s.create_sub_step()
		sstep.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 367, tap=True))
		sstep.add_action(self.step_sound_action)
		sstep = s.create_sub_step()
		sstep.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 373, tap=True))
		sstep.add_action(self.step_sound_action)
		sstep = s.create_sub_step()
		sstep.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 392, tap=True))
		sstep.add_action(self.step_sound_action)

		# Play the first bit of the digging animation

		scancel.add_predecessor(s)
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 407))
		s.add_action(bat.story.ActAction('HP_AntConverse', 440, 470, Ant.L_ANIM, blendin=1.0))
		s.add_action(bat.story.ActConstraintSet("Hand.L", "Copy Transforms", 1.0))
		sKnock = s.create_sub_step("Knock sound")
		sKnock.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 466.5, tap=True))
		sKnock.add_action(self.knock_sound_action)
		# Step sounds
		sstep = s.create_sub_step()
		sstep.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 443, tap=True))
		sstep.add_action(self.step_sound_action)
		sstep = s.create_sub_step()
		sstep.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 446, tap=True))
		sstep.add_action(self.step_sound_action)

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 470))
		s.add_action(bat.story.ActStoreSet('/game/level/antConversation1', True))

		sconv_end = bat.story.State()
		sconv_end.add_predecessor(s)
		sconv_end.add_predecessor(scancel)

		return sconv_start, sconv_end

	def create_enter_states(self):
		'''State graph that plays when the tree door is broken.'''
		senter_start = bat.story.State("Enter start")
		senter_start.add_condition(bat.story.CondEvent("treeDoorBroken", self))
		senter_start.add_action(Scripts.story.ActSetCamera('AntMidCam'))
		senter_start.add_action(Scripts.story.ActSetFocalPoint('Ant'))
		senter_start.add_action(Scripts.story.ActSuspendInput())
		# No intro here - straight into main part of the song!
		senter_start.add_action(bat.story.ActMusicPlay('//Sound/Music/10-TheAntReturns_loop.ogg', volume=0.7))
		senter_start.add_action(bat.story.ActAction('HP_AntEnter', 1, 40,
				Ant.L_ANIM, blendin=1.0))
		senter_start.add_action(bat.story.ActDestroy(target_descendant='Ant_Pick'))
		sdrop_pick = senter_start.create_sub_step("Adjust influence")
		sdrop_pick.add_action(bat.story.ActConstraintFade("Hand.L",
				"Copy Transforms", 1.0, 0.0, 1.0, 4.0, Ant.L_ANIM))

		s = senter_start.create_successor()
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 25))
		s.add_action(Scripts.story.ActSetCamera('AntVictoryCam'))
		s.add_event("ShowDialogue", "Amazing! You've done it!")
		s.add_event("TeleportSnail", "HP_SnailTalkPos")
		sbreathe = s.create_sub_step()
		sbreathe.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 40, tap=True))
		sbreathe.add_action(bat.story.ActAction('HP_AntEnter', 40, 80, Ant.L_ANIM,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 40))
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(Scripts.story.ActSetCamera('AntSniffCam'))
		s.add_event("ShowDialogue", "And look, it's just as I suspected - sugary syrup!")
		s.add_action(bat.story.ActAction('HP_AntEnter', 80, 100, Ant.L_ANIM,
				blendin=3.0))
		ssniff = s.create_sub_step("Sniff")
		ssniff.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 100, tap=True))
		ssniff.add_action(bat.story.ActAction('HP_AntEnter', 100, 132, Ant.L_ANIM,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 100))
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "Let's find the source. Last one up the tree is a rotten egg!")
		s.add_action(bat.story.ActAction('HP_AntEnter', 132, 153, Ant.L_ANIM,
				blendin=3.0))
		slook = s.create_sub_step("look")
		slook.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 153, tap=True))
		slook.add_action(bat.story.ActAction('HP_AntEnter', 153, 188, Ant.L_ANIM,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(bat.story.ActAction('HP_AntEnter', 188, 230, Ant.L_ANIM,
				blendin=3.0))

		senter_end = s.create_successor()
		senter_end.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 230))
		senter_end.add_action(Scripts.story.ActRemoveCamera('AntSniffCam'))
		senter_end.add_action(Scripts.story.ActRemoveCamera('AntVictoryCam'))
		senter_end.add_action(Scripts.story.ActRemoveCamera('AntMidCam'))
		senter_end.add_action(Scripts.story.ActResumeInput())
		senter_end.add_action(bat.story.ActDestroy(ob='Honeypot'))
		senter_end.add_action(bat.story.ActDestroy())

		return senter_start, senter_end

	#########################
	# Dungeon
	#########################

	def create_dungeon_state_graph(self):
		s = self.rootState.create_successor("Init")
		# Hide ant first thing
		s.add_action(bat.story.ActAttrSet('visible', False, target_descendant="Ant_Body"))
		s.add_action(bat.story.ActAttrSet('visible', False, target_descendant="Ant_Pick"))

		sgrab_start, sgrab_end = self.create_grab_states()
		sgrab_start.add_predecessor(s)

		srescue_start, srescue_end = self.create_rescue_states()
		srescue_start.add_predecessor(s)

		#
		# Loop back to start.
		#
		s = bat.story.State("Reset")
		s.add_predecessor(sgrab_end)
		s.add_predecessor(srescue_end)
		s.add_action(Scripts.story.ActResumeInput())
		s.add_action(Scripts.story.ActRemoveCamera('WindowCam'))
		s.add_action(Scripts.story.ActRemoveCamera('AntGrabCam'))
		s.add_action(Scripts.story.ActRemoveFocalPoint('Ant'))
		s.add_action(bat.story.ActMusicStop())
		s.add_action(bat.story.ActActionStop(Ant.L_IDLE))
		s.add_successor(self.rootState)

	def create_grab_states(self):
		s = s_start = bat.story.State("Grab")
		s.add_condition(bat.story.CondEvent("ApproachWindow", self))
		s.add_condition(bat.story.CondStore('/game/level/AntGrabbed', False, False))
		s.add_action(Scripts.story.ActSuspendInput())
#		s.add_action(self.music1_action)
		s.add_action(bat.story.ActAddObject('Thimble_ant'))
		s.add_event('ParkBuckets')

		s = s.create_successor()
		s.add_action(Scripts.story.ActSetCamera('WindowCam'))
		s.add_action(Scripts.story.ActSetFocalPoint('Ant'))
		s.add_action(bat.story.ActAttrSet('visible', True, target_descendant="Ant_Body"))
		s.add_action(bat.story.ActAction('Ant_GetThimble', 880, 1020, Ant.L_ANIM))
		s.add_action(bat.story.ActAction('AntGrabCam', 880, 1020, ob='AntGrabCam'))
		s.add_action(bat.story.ActAction('RubberBandPluck', 880, 1020, ob='RubberBand_upper'))
		s.add_action(bat.story.ActAction('Thimble_ant_grab', 880, 1020, ob='Thimble_ant'))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 935))
		s.add_action(Scripts.story.ActSetCamera('AntGrabCam'))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 986))
		s.add_action(bat.story.ActSound('//Sound/cc-by/RubberBandTwang.ogg'))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 1020))

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(1))
		s.add_action(bat.story.ActDestroy(ob='Thimble_ant'))
		s.add_action(Scripts.story.ActRemoveCamera('WindowCam'))
		s.add_action(Scripts.story.ActRemoveCamera('AntGrabCam'))
		s.add_action(Scripts.story.ActRemoveFocalPoint('Ant'))

		s = s.create_successor()
		s.add_event('StartBuckets')

		s_end = s.create_successor()

		return s_start, s_end

	def create_rescue_states(self):
		s = s_start = bat.story.State("Rescue")
		s.add_condition(bat.story.CondStore('/game/level/AntGrabbed', True, False))
		s.add_action(bat.story.ActAttrSet('visible', True, target_descendant="Ant_Body"))

		s_end = s.create_successor()

		return s_start, s_end

	def create_post_rescue_states(self):
		s = s_start = bat.story.State("Finished")
		s.add_condition(bat.story.CondStore('/game/level/AntRescued', True, False))
		s.add_action(bat.story.ActDestroy())

		s_end = s.create_successor()

		return s_start, s_end

def oversee(c):
	if bat.store.get('/game/level/treeDoorBroken', False):
		# Ant has already entered tree.
		c.owner.endObject()
		return

	sce = bge.logic.getCurrentScene()
	if c.sensors[0].positive:
		if "Honeypot" not in sce.objects:
			print("Creating honeypot")
			sce.addObject("Honeypot", c.owner)
	else:
		if "Honeypot" in sce.objects:
			print("Destroying honeypot")
			sce.objects["Honeypot"].endObject()

def test_anim():
	sce = bge.logic.getCurrentScene()
	ant = sce.objects['Ant']
	ant = bat.bats.mutate(ant)
	ant.playAction('AntActionTEST', 1, 120, 0)
