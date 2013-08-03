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
import logging

import bat.bats
import bat.event
import bat.bmath
import bat.story

import Scripts.story
import Scripts.shells
import Scripts.inventory

def factory():
	scene = bge.logic.getCurrentScene()
	if not "Bird" in scene.objectsInactive:
		try:
			bge.logic.LibLoad('//Bird_loader.blend', 'Scene', load_actions=True)
		except ValueError as e:
			print('Warning: could not load bird:', e)

	return bat.bats.add_and_mutate_object(scene, "Bird", "Bird")

class Bird(bat.story.Chapter, bat.bats.BX_GameObject, bge.types.BL_ArmatureObject):
	L_IDLE = 0
	L_ANIM = 1

	log = logging.getLogger(__name__ + '.Bird')

	def __init__(self, old_owner):
		bat.story.Chapter.__init__(self, old_owner)
		bat.event.EventBus().add_listener(self)

	def on_event(self, evt):
		if evt.message == 'ShellDropped':
			self.shoot_shell(evt.body)

	def create_bottle_state_graph(self):
		bat.event.WeakEvent("StartLoading", self).send()
		self.pick_up_shell()

		def steal_shell():
			Scripts.inventory.Shells().discard("Shell")
			bat.event.Event('ShellChanged', 'new').send()

		s = self.rootState.create_successor("Init bottle")
		s.add_action(Scripts.story.ActSuspendInput())
		s.add_action(Scripts.story.ActSetCamera('B_BirdIntroCam'))
		s.add_action(Scripts.story.ActSetFocalPoint('Bi_FootHook.L'))
		s.add_action(bat.story.ActAction('Bi_Excited', 1, 25, Bird.L_ANIM,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))
		s.add_action(bat.story.ActMusicPlay(
				'//Sound/Music/06-TheBird_loop.ogg',
				introfile='//Sound/Music/06-TheBird_intro.ogg',
				fade_in_rate=1))
		s.add_action(bat.story.ActAction("B_BirdCloseCamAction", 1, 1, 0,
			ob="B_BirdIntroCam"))

		s = s.create_successor()
		s.add_condition(bat.story.CondNextFrame())
		s.add_condition(bat.story.CondWait(0.5))
		s.add_event("FinishLoading", self)
		s.add_action(bat.story.ActAction("B_BirdCloseCamAction", 1, 96, 0,
			ob="B_BirdIntroCam"))

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(2.5))
		s.add_action(Scripts.story.ActSetFocalPoint('Bi_Face'))
		s.add_action(Scripts.story.ActRemoveFocalPoint('Bi_FootHook.L'))
		s.add_event("ShowDialogue", "Ooh, look at this lovely red thing!")
		s.add_action(bat.story.ActSound('//Sound/cc-by/BirdSquarkLarge.ogg'))

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(1))
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(Scripts.story.ActSetCamera('B_DoorCamera'))
		s.add_action(Scripts.story.ActRemoveCamera('B_BirdIntroCam'))
		s.add_action(bat.story.ActAction('Bi_SmashShell', 1, 12, Bird.L_ANIM,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=2.0))

		sKnock = s.create_sub_step("Knock sound")
		sKnock.add_condition(bat.story.CondActionGE(Bird.L_ANIM, 10.5, tap=True))
		sKnock.add_action(bat.story.ActSound('//Sound/Knock.ogg', vol=0.6, pitchmin=0.7,
				pitchmax=0.76))

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(2))
		s.add_sub_step(sKnock)
		s.add_event("ShowDialogue", ("It's so shiny. It will really brighten up my nest!",
				("Excuse me...", "Oi, that's my \[shell]!")))
		s.add_action(bat.story.ActSound('//Sound/cc-by/BirdTweet1.ogg'))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(bat.story.ActAction('Bi_LookCargo', 1, 20, Bird.L_ANIM, blendin=2.0))

		sKnock = s.create_sub_step("Knock sound")
		sKnock.add_condition(bat.story.CondActionGE(Bird.L_ANIM, 9.5, tap=True))
		sKnock.add_action(bat.story.ActSound('//Sound/Knock.ogg', vol=0.2, pitchmin=0.7,
				pitchmax=0.74))

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(1))
		s.add_sub_step(sKnock)
		s.add_event("ShowDialogue", "Eh? You say it's yours?")
		s.add_action(bat.story.ActSound('//Sound/cc-by/BirdQuestion1.ogg'))
		s.add_action(Scripts.story.ActSetCamera('B_BirdConverseCam'))
		s.add_action(bat.story.ActAction('Bi_Discuss_Idle', 1, 49, Bird.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=5.0))

		s = s.create_successor()
		sKnock.add_condition(bat.story.CondActionGE(Bird.L_ANIM, 20, tap=True))
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "Couldn't be; it was just lying here! Finders keepers, I always say.")
		s.add_action(bat.story.ActAction('Bi_Discuss', 1, 10, Bird.L_ANIM,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=2.0))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		sKnock.add_condition(bat.story.CondActionGE(Bird.L_ANIM, 9, tap=True)) # One less than max for tolerance
		s.add_event("ShowDialogue", "Tell you what, I'll make you a deal.")
		s.add_action(bat.story.ActAction('Bi_Discuss', 10, 21, Bird.L_ANIM))
		s.add_action(bat.story.ActAction('Bi_Discuss_Idle', 100, 149, Bird.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=5.0))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		sKnock.add_condition(bat.story.CondActionGE(Bird.L_ANIM, 21, tap=True))
		s.add_event("ShowDialogue", ("If you can bring me 3 other shiny red things, I'll give this one to you.",
				("That's not fair!", "I need it to do my job!")))
		s.add_action(bat.story.ActAction('Bi_Discuss', 21, 40, Bird.L_ANIM))
		s.add_action(bat.story.ActAction('Bi_Discuss_Idle', 1, 49, Bird.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=5.0))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "Now now, you can't just go taking things from other people.")
		s.add_action(bat.story.ActSound('//Sound/cc-by/BirdStatement1.ogg'))
		s.add_action(bat.story.ActAction('Bi_Discuss', 40, 51, Bird.L_ANIM))
		s.add_action(bat.story.ActAction('Bi_Discuss_Idle', 200, 249, Bird.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=5.0))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(Scripts.story.ActSetCamera('BirdCamera_BottleToNest'))

		s = s.create_successor()
		s.add_action(Scripts.story.ActSetCamera('BirdCamera_BottleToNest_zoom'))
		s.add_action(Scripts.story.ActSetFocalPoint('B_Nest'))
		s.add_action(Scripts.story.ActShowMarker('B_Nest'))
		s.add_event("ShowDialogue", "If you want this \[shell], bring 3 red things to my nest at the top of the tree.")
		s.add_action(bat.story.ActSound('//Sound/cc-by/BirdMutter.ogg'))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(Scripts.story.ActRemoveFocalPoint('B_Nest'))
		s.add_action(Scripts.story.ActShowMarker(None))
		s.add_action(Scripts.story.ActRemoveCamera('B_BirdConverseCam'))
		s.add_action(Scripts.story.ActRemoveCamera('BirdCamera_BottleToNest_zoom'))
		s.add_action(Scripts.story.ActRemoveCamera('BirdCamera_BottleToNest'))

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(1))
		s.add_event("ShowDialogue", "Toodles!")
		s.add_action(bat.story.ActAction('Bi_FlyAway', 1, 35, Bird.L_ANIM, blendin=5.0))
		s.add_action(bat.story.ActSound('//Sound/cc-by/BirdTweet2.ogg'))
		s.add_action(Scripts.story.ActRemoveFocalPoint('Bi_Face'))
		s.add_action(Scripts.story.ActRemoveFocalPoint('Bi_FootHook.L'))
		s.add_action(Scripts.story.ActRemoveFocalPoint('B_Nest'))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(bat.story.ActGeneric(steal_shell))
		s.add_action(bat.story.ActStoreSet('/game/level/birdTookShell', True))
		s.add_action(bat.story.ActStoreSet('/game/storySummary', 'birdTookShell'))
		s.add_action(bat.story.ActStoreSet('/game/canDropShell', True))

		#
		# Return to game. Note that this actually destroys the bird.
		#
		s = s.create_successor("Return to game")
		s.add_action(Scripts.story.ActResumeInput())
		s.add_action(Scripts.story.ActRemoveCamera('B_BirdIntroCam'))
		s.add_action(Scripts.story.ActRemoveCamera('B_BirdConverseCam'))
		s.add_action(Scripts.story.ActRemoveCamera('B_DoorCamera'))
		s.add_action(Scripts.story.ActRemoveCamera('BirdCamera_BottleToNest_zoom'))
		s.add_action(Scripts.story.ActRemoveCamera('BirdCamera_BottleToNest'))
		s.add_action(bat.story.ActDestroy())

	def create_nest_state_graph(self):
		s = (self.rootState.create_successor('Init nest')
			# Need to set Tree as parent so that animations play in the right
			# coordinate system. All other objects (nest, etc) are already
			# parented.
			(bat.story.ActParentSet('T_Tree'))
			(bat.story.ActAction('B_Nest', 1, 1, ob='B_Nest'))
			(bat.story.ActAction('B_Egg', 1, 1, ob='B_Egg'))
			(bat.story.ActAction("B_TorchButton", 1, 1, ob="B_TorchButton"))
			(bat.story.ActAction("B_Nest_Shell", 1, 1, ob="B_Nest_Shell"))
			(bat.story.ActAction('B_Final', 1, 1))
			(bat.story.ActAction("B_nest_cam", 1, 1, ob="B_nest_cam"))
			(bat.story.ActCopyTransform('B_NestSpawn'))
			(Scripts.story.ActSleepParticles(start=True, scale=2, target_descendant='Bi_Head'))
		)

		s = (s.create_successor()
			(bat.story.CondEvent('ApproachBird', self))
			("StartLoading", self)
			(Scripts.story.ActSuspendInput())
		)

		s = (s.create_successor()
			(bat.story.CondEvent("LoadingScreenShown", self))
			(Scripts.story.ActSetCamera('B_nest_cam'))
			(Scripts.story.ActSetFocalPoint('Bi_Face'))
			(bat.story.ActMusicPlay(
				'//Sound/Music/06-TheBird_loop.ogg',
				introfile='//Sound/Music/06-TheBird_intro.ogg',
				fade_in_rate=1))
			("TeleportSnail", "B_nest_snail_talk_pos")
			("ForceEquipShell", "Thimble")
		)

		# Cache shell materials to prevent frame dropping
		def matshell_spawn(name):
			shell = Scripts.shells.factory(name)
			anchor = self.scene.objects['B_matspawn']
			bat.bmath.copy_transform(anchor, shell)
			shell.setParent(self)
			self.shell = shell
		def destroy_matshell():
			self.shell.endObject()
		s = (s.create_successor()
			(bat.story.ActGeneric(matshell_spawn, 'BottleCap'))
		)
		s = (s.create_successor()
			(bat.story.CondNextFrame()) # Ensure redraw
			(bat.story.ActGeneric(destroy_matshell))
		)
		s = (s.create_successor()
			(bat.story.ActGeneric(matshell_spawn, 'Nut'))
		)
		s = (s.create_successor()
			(bat.story.CondNextFrame()) # Ensure redraw
			(bat.story.ActGeneric(destroy_matshell))
		)
		s = (s.create_successor()
			(bat.story.ActGeneric(matshell_spawn, 'Wheel'))
		)
		s = (s.create_successor()
			(bat.story.CondNextFrame()) # Ensure redraw
			(bat.story.ActGeneric(destroy_matshell))
		)
		s = (s.create_successor()
			(bat.story.ActGeneric(matshell_spawn, 'Thimble'))
		)
		s = (s.create_successor()
			(bat.story.CondNextFrame()) # Ensure redraw
			(bat.story.ActGeneric(destroy_matshell))
		)

		s = sready = (s.create_successor()
			(bat.story.CondNextFrame()) # Ensure redraw
			(bat.story.CondWait(0.5))
			("FinishLoading", self)
		)

		snd_alarm1 = bat.story.ActSound('//Sound/cc-by/BirdAlarm1.ogg', pitchmin=0.9, pitchmax=1.1)
		snd_alarm2 = bat.story.ActSound('//Sound/cc-by/BirdAlarm2.ogg', pitchmin=0.9, pitchmax=1.1)
		snd_squark_small = bat.story.ActSound('//Sound/cc-by/BirdSquarkSmall.ogg', pitchmin=0.9, pitchmax=1.1)
		snd_squark_large = bat.story.ActSound('//Sound/cc-by/BirdSquarkLarge.ogg', pitchmin=0.9, pitchmax=1.1)
		snd_question = bat.story.ActSound('//Sound/cc-by/BirdQuestion1.ogg', pitchmin=0.9, pitchmax=1.1)
		snd_statement = bat.story.ActSound('//Sound/cc-by/BirdStatement.ogg', pitchmin=0.9, pitchmax=1.1)
		snd_mutter = bat.story.ActSound('//Sound/cc-by/BirdMutter.ogg', pitchmin=0.9, pitchmax=1.1)
		snd_tweet1 = bat.story.ActSound('//Sound/cc-by/BirdTweet1.ogg', pitchmin=0.9, pitchmax=1.1)
		snd_tweet2 = bat.story.ActSound('//Sound/cc-by/BirdTweet2.ogg', pitchmin=0.9, pitchmax=1.1)

		s = (s.create_successor()
			(bat.story.CondWait(3))
			(bat.story.ActAction("B_Final", 1, 60))
			(Scripts.story.ActSleepParticles(start=False, target_descendant='Bi_Head'))
			(bat.story.State()
				(bat.story.CondActionGE(0, 14, tap=True))
				(snd_squark_small)
			)
		)

		s = (s.create_successor()
			(bat.story.CondActionGE(0, 45))
			("ShowDialogue", "Hi there, little snail! It's nice of you to come "
				"to visit.")
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", "Hey! That's a nice shiny red thing you have "
				"there.")
			(bat.story.ActAction("B_Final", 65, 100))
			(bat.story.State()
				(bat.story.CondActionGE(0, 69, tap=True))
				(snd_question)
			)
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", "Are you here to talk business?")
			(bat.story.ActAction("B_Final", 105, 130))
			(bat.story.State()
				(bat.story.CondActionGE(0, 111, tap=True))
				(snd_alarm2)
			)
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", "I haven't forgotten our deal: if you give me "
				"three shiny red things, I'll give you this one in return.")
			(bat.story.ActAction("B_Final", 150, 180))
			(bat.story.State()
				(bat.story.CondActionGE(0, 157, tap=True))
				(snd_alarm1)
			)
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", ("So, will you give me that \[thimble]?",
				("Actually I think I'll keep it.", "I guess so.")))
			(bat.story.ActAction("B_Final", 190, 225))
			(bat.story.State()
				(bat.story.CondActionGE(0, 198, tap=True))
				(snd_tweet2)
			)
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ForceDropShell", True)
			(bat.story.ActAction("B_Final", 230, 275))
			(bat.story.ActAction("B_nest_cam", 230, 275, ob="B_nest_cam"))
			(bat.story.State()
				(bat.story.CondActionGE(0, 235, tap=True))
				(snd_squark_large)
			)
		)

		s = (s.create_successor()
			(bat.story.CondEvent("ShellDropped", self))
			("ForceEquipShell", "Wheel")
		)

		s = (s.create_successor()
			(bat.story.CondActionGE(0, 275))
			("ShowDialogue", ("Thanks! And, ooh, what a lovely \[wheel]!",
				("Here you go.", "Let's get this over with.")))
			(bat.story.ActAction("B_Final", 290, 310))
			(bat.story.State()
				(bat.story.CondActionGE(0, 290, tap=True))
				(snd_tweet2)
			)
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ForceDropShell", True)
		)

		s = (s.create_successor()
			(bat.story.CondEvent("ShellDropped", self))
			("ForceEquipShell", "BottleCap")
		)

		s = (s.create_successor()
			(bat.story.CondWait(0.5))
			("ShowDialogue", ("And a \[bottlecap]! That's for me too, right?",
				("Of course.", "Sure, why not :(")))
			(bat.story.ActAction("B_Final", 320, 340))
			(bat.story.State()
				(bat.story.CondActionGE(0, 324, tap=True))
				(snd_tweet1)
			)
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ForceDropShell", True)
		)

		s = (s.create_successor()
			(bat.story.CondEvent("ShellDropped", self))
			("ForceEquipShell", "Nut")
		)

		s = (s.create_successor()
			(bat.story.CondWait(0.5))
			("ShowDialogue", "Hooray! What an excellent collection.")
			(bat.story.ActAction("B_Final", 360, 450))
			(bat.story.ActAction("B_Nest", 360, 450, ob="B_Nest"))
			(bat.story.ActAction("B_Nest_Shell", 360, 450, ob="B_Nest_Shell"))
			(bat.story.ActAction("B_Egg", 360, 450, ob="B_Egg"))
			(bat.story.ActAction("B_TorchButton", 360, 450, ob="B_TorchButton"))
			(bat.story.ActAction("B_nest_cam", 360, 470, ob="B_nest_cam")) # note different end time
			(bat.story.State()
				(bat.story.CondActionGE(0, 386, tap=True))
				(snd_tweet1)
			)
			(bat.story.State()
				(bat.story.CondActionGE(0, 401, tap=True))
				(snd_tweet1)
			)
			(bat.story.State()
				(bat.story.CondActionGE(0, 416, tap=True))
				(snd_tweet2)
			)
		)
		# TEST
		#s.add_predecessor(sready)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", "But you know what would make it even better? "
				"That \[nut]! I know it wasn't part of the deal...")
			(bat.story.ActAction("B_Final", 460, 550))
			(bat.story.State()
				(bat.story.CondActionGE(0, 472, tap=True))
				(snd_mutter)
			)
			(bat.story.State()
				(bat.story.CondActionGE(0, 500, tap=True))
				(snd_alarm2)
			)
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", ("... but now that I have seen it, I know I can't "
				"part with the \[shell] for anything less.",
				("Whatever!", "Take it; it's slowing me down.")))
			(bat.story.ActAction("B_Final", 560, 600))
			(bat.story.State()
				(bat.story.CondActionGE(0, 567, tap=True))
				(snd_tweet1)
			)
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ForceDropShell", True)
		)

		s = (s.create_successor()
			(bat.story.CondEvent("ShellDropped", self))
		)

		s = (s.create_successor()
# 			(bat.story.CondWait(0.5))
			(bat.story.ActAction("B_Final", 680, 735))
			(bat.story.ActAction("B_Nest", 680, 735, ob="B_Nest"))
			(bat.story.ActAction("B_Nest_Shell", 680, 735, ob="B_Nest_Shell"))
			(bat.story.ActAction("B_Egg", 680, 735, ob="B_Egg"))
			(bat.story.ActAction("B_TorchButton", 680, 735, ob="B_TorchButton"))
			(bat.story.State()
				(bat.story.CondActionGE(0, 703, tap=True))
				("ShowDialogue", "Whoa, whoa! It's too heavy. Look out!")
				(snd_squark_large)
			)
		)
		s = (s.create_successor()
				(bat.story.CondActionGE(0, 734.5))
			(bat.story.ActAction("B_Final", 735, 771,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))
			(bat.story.ActAction("B_Nest", 735, 771, ob="B_Nest",
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))
			(bat.story.ActAction("B_Nest_Shell", 735, 771, ob="B_Nest_Shell",
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))
			(bat.story.ActAction("B_Egg", 735, 771, ob="B_Egg",
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))
			(bat.story.ActAction("B_TorchButton", 735, 771, ob="B_TorchButton",
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))
# 			(bat.story.State()
# 				(bat.story.CondActionGE(0, 744, tap=True))
# 				(snd_squark_small)
# 			)
# 			(bat.story.State()
# 				(bat.story.CondActionGE(0, 762, tap=True))
# 				(snd_squark_small)
# 			)
		)

		# Nest falls down.
		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			(Scripts.story.ActSetCamera('B_nest_fall_cam'))
			(Scripts.story.ActRemoveCamera('B_nest_cam'))
			(bat.story.ActAction("B_Final", 850, 980))
			(bat.story.ActAction("B_Nest", 850, 980, ob="B_Nest"))
			(bat.story.ActAction("B_Nest_Shell", 850, 980, ob="B_Nest_Shell"))
			(bat.story.ActAction("B_Egg", 850, 980, ob="B_Egg"))
			(bat.story.ActAction("B_TorchButton", 850, 980, ob="B_TorchButton"))
			# Destroy the funnel; things are *supposed* to fall out of the nest
			# now.
			(bat.story.ActDestroy(ob="B_Nest_funnel"))
			(bat.story.ActMusicStop())
		)

		# Nest has fallen; initialise next shot
		s = (s.create_successor()
			(bat.story.CondActionGE(0, 900, ob="B_Nest"))
			("StartLoading", self)
			(bat.story.State() # sub-step
				(bat.story.CondActionGE(0, 910, ob="B_Nest", tap=True))
				(bat.story.ActCopyTransform('B_shell_spawn_1', ob='BottleCap'))
				(bat.story.ActCopyTransform('B_shell_spawn_2', ob='Nut'))
				(bat.story.ActCopyTransform('B_shell_spawn_3', ob='Wheel'))
				(bat.story.ActCopyTransform('B_shell_spawn_4', ob='Thimble'))
			)
		)

		s = (s.create_successor()
			(bat.story.CondEvent("LoadingScreenShown", self))
			(bat.story.ActCopyTransform('B_shell_spawn_1', ob='BottleCap'))
			(bat.story.ActCopyTransform('B_shell_spawn_2', ob='Nut'))
			(bat.story.ActCopyTransform('B_shell_spawn_3', ob='Wheel'))
			(bat.story.ActCopyTransform('B_shell_spawn_4', ob='Thimble'))
		)

		# For testing - can jump here by pressing a button.
		self.super_state = bat.story.State('Super')
		sjump = (self.super_state.create_successor()
			(bat.story.CondEvent("TESTNestBottom", self))
			("StartLoading", self)
			(Scripts.story.ActSetFocalPoint('Bi_Face'))
			(Scripts.story.ActSuspendInput())
		)
		sjump.add_successor(s)

		s = (s.create_successor()
			(bat.story.CondNextFrame())
			(bat.story.CondWait(0.5))
			("FinishLoading", self)
			(bat.story.ActAction("B_Nest", 1000, 1000, ob="B_Nest"))
			(bat.story.ActAction("B_Egg", 1000, 1000, ob="B_Egg"))
			(bat.story.ActAction("B_TorchButton", 1000, 1000, ob="B_TorchButton"))
			(bat.story.ActAction("B_Final", 1000, 1000))
			(bat.story.ActAction("B_base_cam_above", 1000, 1150, ob="B_base_cam_above"))
			(bat.story.ActDestroy(ob="B_Nest_Shell"))
			(bat.story.ActCopyTransform('B_TreeBaseSpawn'))
			(Scripts.story.ActSetCamera('B_base_cam_above'))
			(Scripts.story.ActRemoveCamera('B_nest_fall_cam'))
			("TeleportSnail", "B_ground_snail_talk_pos")
			('SpawnShell', 'Shell')
		)

		s = (s.create_successor()
			(bat.story.CondActionGE(0, 1140, ob="B_base_cam_above"))
			(Scripts.story.ActSetCamera('B_base_cam'))
			(Scripts.story.ActRemoveCamera('B_base_cam_above'))
			(bat.story.ActAction("B_base_cam", 1100, 1300, ob="B_base_cam"))
		)

		# Cut to being at base of tree with contents of nest scattered around.
		s = (s.create_successor()
			(bat.story.CondWait(1))
			("ShowDialogue", "Oh my beautiful egg! What luck that it is not broken.")
			(bat.story.ActAction("B_Final", 1005, 1040))
		)
		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", ("You know, I think I may have been a little greedy.",
				("Well, maybe a little.", "You were so greedy!")))
			(bat.story.ActAction("B_Final", 1050, 1090))
		)

		# Bird is told that it was greedy, so it gives back the loot.
		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", "Oh you're right! I was greedy, and a fool.")
			(bat.story.ActAction("B_Final", 1100, 1150))
		)
		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", "Please, take back the things you brought me.")
			(bat.story.ActAction("B_Final", 1200, 1280))
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			(Scripts.story.ActSetCamera('B_base_cam_above'))
			(bat.story.ActAction("B_Final", 1300, 1360))
		)

		s = (s.create_successor()
			(bat.story.CondWait(1))
			("ForceEquipShell", "BottleCap")
		)
		s = (s.create_successor()
			(bat.story.CondWait(1))
			("ForceEquipShell", "Nut")
		)
		s = (s.create_successor()
			(bat.story.CondWait(1))
			("ForceEquipShell", "Wheel")
		)
		s = (s.create_successor()
			(bat.story.CondWait(1))
			("ForceEquipShell", "Thimble")
		)

		s = (s.create_successor()
			(bat.story.CondWait(0.5))
			(Scripts.story.ActSetCamera('B_base_cam2'))
			(Scripts.story.ActRemoveCamera('B_base_cam'))
			(Scripts.story.ActRemoveCamera('B_base_cam_above'))
			("ShowDialogue", "You can even take my shell. I can't bear to look "
				"at it! Besides, my nest was becoming a bit cluttered.")
			(bat.story.ActAction("B_Final", 1400, 1450))
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			# Don't equip shell - let the player pick it up.
# 			("ForceEquipShell", "Shell")
		)

		s = (s.create_successor()
			(bat.story.CondWait(0.5))
			("ShowDialogue", "Ah, I feel better already!")
			(bat.story.ActAction("B_Final", 1500, 1570))
		)

		s = (s.create_successor("Return to game")
			(bat.story.CondActionGE(0, 1570))
			(bat.story.CondEvent("DialogueDismissed", self))
			(Scripts.story.ActResumeInput())
			(Scripts.story.ActRemoveCamera('B_base_cam'))
			(Scripts.story.ActRemoveCamera('B_base_cam2'))
			(Scripts.story.ActRemoveCamera('B_base_cam_above'))
			(Scripts.story.ActRemoveCamera('B_nest_cam'))
			(Scripts.story.ActRemoveCamera('B_nest_fall_cam'))
			(Scripts.story.ActRemoveFocalPoint('Bi_Face'))
			(bat.story.ActMusicStop())
		)

	def pick_up(self, ob, left=True):
		attach_point = self.children["Bi_FootHook.L"]

		referential = ob
		for child in ob.children:
			if child.name.startswith("GraspHook"):
				referential = child
				break

		# Similar to Snail._stow_shell
		bat.bmath.set_rel_orn(ob, attach_point, referential)
		bat.bmath.set_rel_pos(ob, attach_point, referential)
		ob.setParent(attach_point)

	def pick_up_shell(self):
		try:
			shell = self.scene.objects["Shell"]
		except KeyError:
			shell = Scripts.shells.factory("Shell")
		shell.localScale = (0.75, 0.75, 0.75)
		self.pick_up(shell)
		try:
			shell.on_grasped()
		except AttributeError as e:
			print("Warning:", e)

	def shoot_shell(self, shell):
		if shell is None:
			Bird.log.warn('Could not shoot shell: does not exist!')
		Bird.log.info("Shooting shell %s", shell)
		shooter = self.scene.objects['B_shell_launcher']
		vec = shooter.getAxisVect(bat.bmath.ZAXIS)
		bat.bmath.copy_transform(shooter, shell)
		shell.worldLinearVelocity = vec * 32.0

def spawn_nest(c):
	required_shells = set()
	required_shells.update(Scripts.inventory.Shells().get_all_shells())
	required_shells.discard('Shell')
	if not required_shells.issubset(Scripts.inventory.Shells().get_shells()):
		# Player still needs to collect more shells.
		return
	bird = factory()
	bird.create_nest_state_graph()
	bat.bmath.copy_transform(c.owner, bird)
