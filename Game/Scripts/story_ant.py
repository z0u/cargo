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

import logging

import bge

import bat.bats
import bat.bmath

import bat.story
import Scripts.story

log = logging.getLogger(__name__)

def prepare():
	scene = bge.logic.getCurrentScene()
	if not "Ant" in scene.objectsInactive:
		try:
			bge.logic.LibLoad('//Ant_loader.blend', 'Scene', load_actions=True)
		except ValueError:
			log.warn('could not load ant', exc_info=1)

def factory():
	scene = bge.logic.getCurrentScene()
	if not "Ant" in scene.objectsInactive:
		try:
			bge.logic.LibLoad('//Ant_loader.blend', 'Scene', load_actions=True)
		except ValueError:
			log.error('could not load ant', exc_info=1)

	return bat.bats.add_and_mutate_object(scene, "Ant", "Ant")

class Honeypot(bat.bats.BX_GameObject, bge.types.KX_GameObject):

	def __init__(self, old_owner):
		#bat.event.WeakEvent("StartLoading", self).send()
		ant1 = factory()
		bat.bmath.copy_transform(self.children["Ant1SpawnPoint"], ant1)
		ant1.setParent(self)

class Ant(bat.story.Chapter, bat.bats.BX_GameObject, bge.types.BL_ArmatureObject):
	L_IDLE = 0
	L_ANIM = 1

	def __init__(self, old_owner):
		bat.story.Chapter.__init__(self, old_owner)
		self.music1_action = bat.story.ActMusicPlay(
				'//Sound/Music/08-TheAnt_loop.ogg',
				introfile='//Sound/Music/08-TheAnt_intro.ogg', volume=0.7,
				fade_in_rate=1, name='ant_music')
		self.music2_action = bat.story.ActMusicPlay(
				'//Sound/Music/10-TheAntReturns_loop.ogg',
				introfile='//Sound/Music/10-TheAntReturns_intro.ogg', volume=0.7,
				fade_in_rate=1, name='ant_music')
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
		return [self.children['Ant_Face'], self.children['Ant_Centre']]

	#########################
	# Outdoors
	#########################

	def create_outdoors_state_graph(self):
		s = self.rootState.create_successor("Init")
		s.add_action(bat.story.ActConstraintSet("Hand.L", "Copy Transforms", 1.0))
		s.add_action(bat.story.ActAction('Ant_Digging1', 1, 42, Ant.L_ANIM,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))
		sKnock = s.create_sub_step("Knock sound")
		sKnock.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 34.5, tap=True))
		sKnock.add_action(self.knock_sound_action)

		senter_start, _ = self.create_enter_states()
		senter_start.add_predecessor(s)

		sconv_start, sconv_end = self.create_conversation()
		sconv_start.add_predecessor(s)

		# Create a super state to catch when the player leaves. Can't have one
		# for canceling dialogue, because that would catch any dialogue
		# elsewhere in the level.
		self.super_state = bat.story.State('Super')
		s_leave = self.super_state.create_successor('Leave')
		s_leave.add_condition(bat.story.CondEvent('LeaveAnt', self))
		s_leave.add_action(bat.story.ActMusicStop(name='ant_music'))

		#
		# Loop back to start.
		#
		s = bat.story.State("Reset")
		s.add_predecessor(sconv_end)
		s.add_predecessor(s_leave)
		s.add_action(Scripts.story.ActResumeInput())
		s.add_action(Scripts.story.ActRemoveCamera('AntCloseCam'))
		s.add_action(Scripts.story.ActRemoveCamera('AntCrackCam'))
		s.add_action(Scripts.story.ActRemoveCamera('AntCrackCamIn'))
		s.add_action(Scripts.story.ActRemoveCamera('AntMidCam'))
		s.add_action(Scripts.story.ActRemoveFocalPoint('Ant'))
		s.add_action(bat.story.ActActionStop(Ant.L_IDLE))
		s.add_successor(self.rootState)

	def create_conversation(self):
		'''
		State graph that plays when Cargo approaches the ant at the tree door.
		'''
		s = sconv_start = bat.story.State("Talk")
		s.add_condition(Scripts.story.CondNotInShell())
		s.add_condition(bat.story.CondEvent("ApproachAnt", self))
		s.add_action(Scripts.story.ActSuspendInput())
		s.add_event("StartLoading", self)
		s.add_action(self.music1_action)

		# Catch-many state for when the user cancels a dialogue. Should only be
		# allowed if the conversation has been played once already.
		scancel = bat.story.State("Cancel")
		scancel.add_condition(bat.story.CondEvent('DialogueCancelled', self))
		scancel.add_condition(bat.story.CondStore('/game/level/antConversation1', True, default=False))

		# Start conversation

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(1))
		s.add_event("FinishLoading", self)
		s.add_action(Scripts.story.ActSetFocalPoint('Ant'))
		s.add_action(Scripts.story.ActSetCamera('AntCloseCam'))
		s.add_event("TeleportSnail", "HP_SnailTalkPos")
		# Reset camera pos
		s.add_action(bat.story.ActAction('HP_AntConverse_Cam', 1, 1, 0, ob='AntCloseCam'))
		s.add_action(bat.story.ActAction('HP_AntCrackCam', 1, 1, 0, ob='AntCrackCam'))
		sKnock = s.create_sub_step("Knock sound")
		sKnock.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 34.5, tap=True))
		sKnock.add_action(self.knock_sound_action)



		# Raises head, takes deep breath
		s = s.create_successor()
		s.add_condition(bat.story.CondWait(2))
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 38))
		s.add_action(bat.story.ActAction('HP_AntConverse', 30, 70, Ant.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))
		s.add_action(bat.story.ActAction('HP_AntConverse', 1, 30, Ant.L_ANIM))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 20))
		s.add_event("ShowDialogue", "Mmmm, smell that?")
		s.add_action(bat.story.ActSound('//Sound/ant.question.ogg'))

		# Gestures fiercely at Cargo

		scancel.add_predecessor(s)
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(bat.story.ActGeneric(self.drop_pick))
		s.add_event("ShowDialogue", "Doesn't it smell amazing? So sweet! So sugary!")
		s.add_action(bat.story.ActSound('//Sound/ant.outrage.ogg'))
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
		s.add_action(bat.story.ActSound('//Sound/ant.mutter3.ogg'))
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
		s.add_action(bat.story.ActSound('//Sound/ant.mutter2.ogg'))
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
		s.add_action(bat.story.ActSound('//Sound/ant.mutter1.ogg'))
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
		s.add_action(bat.story.ActSound('//Sound/ant.surprise.ogg'))
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
		s.add_action(bat.story.ActActionStop(Ant.L_IDLE))
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

		s = sconv_end = s.create_successor()
		s.add_predecessor(scancel)

		return sconv_start, sconv_end

	def create_enter_states(self):
		'''State graph that plays when the tree door is broken.'''
		s = senter_start = bat.story.State("Enter start")
		s.add_condition(bat.story.CondEvent("treeDoorBroken", self))
		s.add_action(Scripts.story.ActSetCamera('AntMidCam'))
		s.add_action(Scripts.story.ActSetFocalPoint('Ant'))
		s.add_action(Scripts.story.ActSuspendInput())
		# No intro here - straight into main part of the song!
		s.add_action(self.music1_action)
		s.add_action(bat.story.ActAction('HP_AntEnter', 1, 40,
				Ant.L_ANIM, blendin=1.0))
		s.add_action(bat.story.ActDestroy(target_descendant='Ant_Pick'))
		sdrop_pick = s.create_sub_step("Adjust influence")
		sdrop_pick.add_action(bat.story.ActConstraintFade("Hand.L",
				"Copy Transforms", 1.0, 0.0, 1.0, 4.0, Ant.L_ANIM))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 25))
		s.add_action(Scripts.story.ActSetCamera('AntVictoryCam'))
		s.add_event("ShowDialogue", "Amazing! You've done it!")
		s.add_action(bat.story.ActSound('//Sound/ant.outrage.ogg'))
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
		s.add_action(bat.story.ActSound('//Sound/ant.mutter1.ogg'))
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
		s.add_action(bat.story.ActSound('//Sound/ant.gratitude.ogg'))
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

		s = senter_end = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 230))
		s.add_action(Scripts.story.ActRemoveCamera('AntSniffCam'))
		s.add_action(Scripts.story.ActRemoveCamera('AntVictoryCam'))
		s.add_action(Scripts.story.ActRemoveCamera('AntMidCam'))
		s.add_action(Scripts.story.ActResumeInput())
		s.add_action(bat.story.ActDestroy(ob='Honeypot'))
		s.add_action(bat.story.ActDestroy())

		return senter_start, senter_end

	#########################
	# Dungeon
	#########################

	def create_dungeon_state_graph(self):
		s = self.rootState.create_successor("Init")
		# Hide ant first thing
		s.add_action(bat.story.ActAttrSet('visible', False, target_descendant="Ant_Body"))
		s.add_action(bat.story.ActAttrSet('visible', False, target_descendant="Ant_Pick"))
		# Pick was left outside.
		s.add_action(bat.story.ActConstraintSet("Hand.L", "Copy Transforms", 0))
		s.add_action(bat.story.ActAction('Ant_Idle', 1, 80, Ant.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))

		srescue_start, srescue_end = self.create_rescue_states()
		srescue_start.add_predecessor(s)

		sstranded_start, sstranded_end = self.create_stranded_states()
		sstranded_start.add_predecessor(s)

		sgrab_start, sgrab_end = self.create_grab_states()
		sgrab_start.add_predecessor(s)

		# Create a super state to catch when the player leaves. Can't have one
		# for canceling dialogue, because that would catch any dialogue
		# elsewhere in the level.
		self.super_state = bat.story.State('Super')
		s_leave = self.super_state.create_successor('Leave')
		s_leave.add_condition(bat.story.CondEvent('LeaveAnt', self))
		s_leave.add_action(bat.story.ActMusicStop(name='ant_music'))

		#
		# Loop back to start.
		#
		s = self.s_reset = bat.story.State("Reset")
		s.add_predecessor(s_leave)
		s.add_predecessor(sgrab_end)
		s.add_predecessor(srescue_end)
		s.add_predecessor(sstranded_end)
		s.add_action(Scripts.story.ActResumeInput())
		s.add_action(Scripts.story.ActRemoveCamera('WindowCam'))
		s.add_action(Scripts.story.ActRemoveCamera('AntGrabCam'))
		s.add_action(Scripts.story.ActRemoveFocalPoint('Ant'))
		s.add_action(bat.story.ActActionStop(Ant.L_IDLE))
		s.add_successor(self.rootState)

	def create_grab_states(self):
		#
		# Non-interactive cut-scene: the camera dollys through a window to show
		# the machine room. A bucket rises from the lower level. It is grabbed
		# by the Ant, who pulls it away from the rubber band it is attached to.
		# The force knocks the ant off the ledge and out of view.
		#
		s = s_start = bat.story.State("Grab")
		s.add_condition(bat.story.CondStore('/game/level/AntStranded', False, False))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("ApproachWindow", self))
		s.add_action(Scripts.story.ActSuspendInput())
#		s.add_action(self.music1_action)
		s.add_action(bat.story.ActAddObject('Thimble_ant'))
		s.add_event('ParkBuckets')

		s_fra = 855
		e_fra = 1020

		s = s.create_successor()
		s.add_action(Scripts.story.ActSetCamera('WindowCam'))
		s.add_action(Scripts.story.ActSetFocalPoint('Ant'))
		s.add_action(bat.story.ActAttrSet('visible', True, target_descendant="Ant_Body"))
		s.add_action(bat.story.ActAction('Ant_GetThimble', s_fra, e_fra, Ant.L_ANIM))
		s.add_action(bat.story.ActAction('WindowCam', s_fra, e_fra, ob='WindowCam'))
		s.add_action(bat.story.ActAction('AntGrabCam', s_fra, e_fra, ob='AntGrabCam'))
		s.add_action(bat.story.ActAction('RubberBandPluck', s_fra, e_fra, ob='RubberBand_upper'))
		s.add_action(bat.story.ActAction('Thimble_ant_grab', s_fra, e_fra, ob='Thimble_ant'))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 935))
		s.add_action(Scripts.story.ActSetCamera('AntGrabCam'))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 977))
		s.add_action(self.step_sound_action)

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 986))
		s.add_action(bat.story.ActSound('//Sound/cc-by/RubberBandTwang.ogg'))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 1020))

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(1))
		s.add_action(bat.story.ActDestroy(ob='Thimble_ant'))
		s.add_action(Scripts.story.ActRemoveCamera('WindowCam'))
		s.add_action(Scripts.story.ActRemoveCamera('WindowCam.001'))
		s.add_action(Scripts.story.ActRemoveCamera('AntGrabCam'))
		s.add_action(Scripts.story.ActRemoveFocalPoint('Ant'))

		# Start the buckets again, and set saved game state. When story state
		# loops, create_stranded_states will be executed instead.
		s = s_end = s.create_successor()
		s.add_event('StartBuckets')
		s.add_action(bat.story.ActStoreSet('/game/level/AntStranded', True))
		s.add_action(bat.story.ActStoreSet('/game/storySummary', 'AntStranded'))

		return s_start, s_end

	def create_stranded_states(self):
		s = s_start = bat.story.State("Stranded")
		s.add_condition(bat.story.CondStore('/game/level/AntStranded', True, False))

		s = s.create_successor('Strand ant')
		s.add_action(bat.story.ActAttrSet('visible', True, target_descendant="Ant_Body"))
		s.add_action(bat.story.ActAction('Ant_Stranded', 1, 1, Ant.L_ANIM))
		s.add_event('SpawnShell', 'Thimble')

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("ApproachAnt", self))
		s.add_action(Scripts.story.ActSuspendInput())
		s.add_event("StartLoading", self)
		s.add_action(bat.story.ActAction('AntStrandedCamLS_FrontAction', 1, 1, ob='AntStrandedCamLS_Front'))
		# Music stops when Cargo moves away; see event handler for 'LeaveAnt'.
		s.add_action(self.music2_action)

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(1))
		s.add_action(Scripts.story.ActSetFocalPoint('Ant'))
		s.add_event("TeleportSnail", "AntStranded_SnailTalkPos")
		s.add_action(Scripts.story.ActSetCamera('AntStrandedCamLS_Front'))
		s.add_event("FinishLoading", self)

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(1))
		s.add_event("ShowDialogue", "Cargo! Am I glad to see you!")
		s.add_action(bat.story.ActAction('Ant_Stranded', 1, 22, Ant.L_ANIM))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "This is a bit embarrassing, but I fell down, and now I'm stuck.")
		s.add_action(bat.story.ActAction('Ant_Stranded', 30, 70, Ant.L_ANIM))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "I was obsessed with the honey. I couldn't stop eating it.")
		s.add_action(bat.story.ActAction('Ant_Stranded', 90, 120, Ant.L_ANIM))
		s.add_action(bat.story.ActAction('AntStrandedCamLS_FrontAction', 90, 140, ob='AntStrandedCamLS_Front'))
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 103, tap=True))
		sub.add_action(self.step_sound_action)

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(bat.story.ActAction('Ant_Stranded', 150, 180, Ant.L_ANIM))
		s.add_event("ShowDialogue", "Then I thought, I should take some home to my family, you know?")

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(Scripts.story.ActSetFocalPoint('Thimble'))
		s.add_event("ShowDialogue", "I took this thimble to use as a bucket...")
		s.add_action(bat.story.ActAction('Ant_Stranded', 200, 225, Ant.L_ANIM))
		s.add_action(Scripts.story.ActSetCamera('AntStrandedCamLS_FrontZoom'))
		s.add_action(bat.story.ActAction('AntStrandedCamLS_FrontAction', 200, 250, ob='AntStrandedCamLS_Front'))
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 207, tap=True))
		sub.add_action(self.step_sound_action)
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 212, tap=True))
		sub.add_action(self.step_sound_action)
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 219, tap=True))
		sub.add_action(self.step_sound_action)
	
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(Scripts.story.ActSetCamera('AntStrandedCamLS'))
		s.add_event("ShowDialogue", "... I feel like such a fool.")
	
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(Scripts.story.ActRemoveFocalPoint('Thimble'))
		s.add_event("ShowDialogue", "I can't walk through the honey: it's too sticky.")
		s.add_action(bat.story.ActAction('AntStrandedCamLS_FrontAction', 90, 90, ob='AntStrandedCamLS_FrontZoom'))
	
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(Scripts.story.ActRemoveCamera('AntStrandedCamLS'))
		s.add_event("ShowDialogue", "But I bet you could do it. Please, help me out!")
		s.add_action(bat.story.ActAction('Ant_Stranded', 260, 300, Ant.L_ANIM))
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 283, tap=True))
		sub.add_action(self.step_sound_action)
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 292, tap=True))
		sub.add_action(self.step_sound_action)
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 298, tap=True))
		sub.add_action(self.step_sound_action)

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(Scripts.story.ActRemoveCamera('AntStrandedCamLS_FrontZoom'))
		s.add_action(Scripts.story.ActRemoveCamera('AntStrandedCamLS_Front'))
		s.add_action(Scripts.story.ActRemoveCamera('AntStrandedCamLS'))
		s.add_action(Scripts.story.ActRemoveFocalPoint('Thimble'))
		s.add_action(Scripts.story.ActRemoveFocalPoint('Ant'))
		s.add_action(Scripts.story.ActResumeInput())

		# Player is free to move around now. If they go outside of the sensor,
		# the global state will notice and reset.

		s = s.create_successor("BeingRescued")
		s.add_condition(bat.story.CondEventEq("ShellFound", "Thimble", self))

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(0.5))
		s.add_action(Scripts.story.ActSuspendInput())
		s.add_event("ShowDialogue", "You got the Thimble! It's impervious to sharp objects.")

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(Scripts.story.ActSetCamera('AntStrandedCamLS_Front'))
		s.add_action(Scripts.story.ActSetFocalPoint('Ant'))
		s.add_event("ShowDialogue", "Hey, nice work! I'll jump on. Thanks a million!")
		s.add_action(bat.story.ActAction('Ant_Stranded', 320, 340, Ant.L_ANIM))
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 325, tap=True))
		sub.add_action(self.step_sound_action)
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 329, tap=True))
		sub.add_action(self.step_sound_action)
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 333, tap=True))
		sub.add_action(self.step_sound_action)

		# No animation here; just show the loading screen and teleport ant on to
		# thimble.
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("StartLoading", self)

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(1))
		s.add_action(bat.story.ActAction('Ant_SitOnThimble', 1, 1, Ant.L_ANIM))
		s.add_action(bat.story.ActCopyTransform("Thimble"))
		s.add_action(bat.story.ActParentSet("Thimble"))
		s.add_action(Scripts.story.ActRemoveFocalPoint('Ant'))

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(0))
		s.add_event("FinishLoading", self)
		s.add_action(bat.story.ActStoreSet('/game/storySummary', 'gotThimble'))
		s.add_action(Scripts.story.ActRemoveCamera('AntStrandedCamLS_Front'))
		s.add_action(Scripts.story.ActResumeInput())

		# Player is free to move around now. Here, we override the super state
		# transition which watches for the LeaveAnt event.

		s = s.create_successor('Carried ant over honey')
		s.add_condition(bat.story.CondEvent('ReachShore', self))
		s.add_action(Scripts.story.ActSuspendInput())
		s.add_event("StartLoading", self)

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(1))
		s.add_action(bat.story.ActAction('AntStrandedCam_RescueTopAction', 1, 150, ob='AntStrandedCam_RescueTop'))
		s.add_action(Scripts.story.ActSetCamera('AntStrandedCam_RescueTop'))
		s.add_action(Scripts.story.ActSetFocalPoint('Ant'))
		s.add_action(bat.story.ActParentRemove())

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(0))
		s.add_action(bat.story.ActCopyTransform("AntSpawnPoint"))
		s.add_event("TeleportSnail", "AntStranded_SnailTalkPos_rescue")
		s.add_action(bat.story.ActAction('Ant_Rescued', 1, 1, Ant.L_ANIM))

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(0))
		s.add_event("FinishLoading", self)

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(1))
		s.add_action(bat.story.ActAction('Ant_Rescued', 1, 53, Ant.L_ANIM))
		s.add_event("ShowDialogue", "All right - we made it!")

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event('ParkBuckets')
		s.add_action(Scripts.story.ActSetCamera('AntStrandedCam_RescueFront'))
		s.add_action(bat.story.ActAction('Ant_Rescued', 78, 151, Ant.L_ANIM))
		s.add_event("ShowDialogue", "I bet that was the strangest delivery you ever made, eh? He-he.")

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 150))
		s.add_action(bat.story.ActAction('Ant_Rescued', 175, 285, Ant.L_ANIM))
		s.add_event("ShowDialogue", "You know, with that thimble you should be able to sneak past the bees if you want to.")

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 285))
		s.add_action(bat.story.ActAction('Ant_Rescued', 313, 373, Ant.L_ANIM))
		s.add_event("ShowDialogue", "There must be another entrance to the hive further up the tree.")

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 370))
		s.add_action(bat.story.ActAction('Ant_Rescued', 398, 555, Ant.L_ANIM))
		s.add_event("ShowDialogue", "Well, I'm going to head outside. I'm looking forward to some fresh air after being stranded!")

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 540))
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(bat.story.ActAction('Ant_Rescued', 593, 660, Ant.L_ANIM))
		s.add_action(bat.story.ActStoreSet('/game/level/AntRescued', True))
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 605, tap=True))
		sub.add_action(self.step_sound_action)
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 607, tap=True))
		sub.add_action(self.step_sound_action)
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 611, tap=True))
		sub.add_action(self.step_sound_action)
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 615, tap=True))
		sub.add_action(self.step_sound_action)
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 618, tap=True))
		sub.add_action(self.step_sound_action)
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 621, tap=True))
		sub.add_action(self.step_sound_action)
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 623, tap=True))
		sub.add_action(self.step_sound_action)
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 626, tap=True))
		sub.add_action(self.step_sound_action)
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 103, tap=True))
		sub.add_action(self.step_sound_action)
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 630, tap=True))
		sub.add_action(self.step_sound_action)
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 632, tap=True))
		sub.add_action(self.step_sound_action)
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 636, tap=True))
		sub.add_action(self.step_sound_action)

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Ant.L_ANIM, 660))
		s.add_event('StartBuckets')
		s.add_action(Scripts.story.ActRemoveCamera('AntStrandedCam_RescueFront'))
		s.add_action(Scripts.story.ActRemoveCamera('AntStrandedCam_RescueTop'))
		s.add_action(Scripts.story.ActRemoveFocalPoint('Ant'))
		s.add_action(Scripts.story.ActResumeInput())
		s.add_action(bat.story.ActDestroy())

		s_end = s

		return s_start, s_end

	def create_rescue_states(self):
		# Just destroy the ant: already rescued!
		s = s_start = bat.story.State("Rescued")
		s.add_condition(bat.story.CondStore('/game/level/AntRescued', True, False))
		s.add_action(bat.story.ActDestroy())

		s = s_end = s.create_successor()

		return s_start, s_end


def oversee(c):
	if bat.store.get('/game/level/treeDoorBroken', False):
		# Ant has already entered tree.
		c.owner.endObject()
		return

	sce = bge.logic.getCurrentScene()
	if c.sensors['Once'].positive:
		log.info("Loading ant")
		prepare()

	if c.sensors['Near'].positive:
		if "Honeypot" not in sce.objects:
			log.info("Creating honeypot")
			sce.addObject("Honeypot", c.owner)
	else:
		if "Honeypot" in sce.objects:
			log.info("Destroying honeypot")
			sce.objects["Honeypot"].endObject()

def test_anim():
	sce = bge.logic.getCurrentScene()
	ant = sce.objects['Ant']
	ant = bat.bats.mutate(ant)
	ant.playAction('AntActionTEST', 1, 120, 0)
