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

	def __init__(self, old_owner):
		bat.story.Chapter.__init__(self, old_owner)
		# if at bottle...
		if True:
			bat.event.WeakEvent("StartLoading", self).send()
			self.pick_up_shell()
			self.create_bottle_state_graph()

	def create_bottle_state_graph(self):
		def steal_shell():
			Scripts.inventory.Shells().discard("Shell")
			bat.event.Event('ShellChanged', 'new').send()

		s = self.rootState.create_successor("Init")
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
		s.add_action(bat.story.ActAction('Bi_Discuss', 1, 6, Bird.L_ANIM,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=2.0))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		sKnock.add_condition(bat.story.CondActionGE(Bird.L_ANIM, 5, tap=True)) # One less than max for tolerance
		s.add_event("ShowDialogue", "Tell you what, I'll make you a deal.")
		s.add_action(bat.story.ActAction('Bi_Discuss', 6, 17, Bird.L_ANIM))
		s.add_action(bat.story.ActAction('Bi_Discuss_Idle', 100, 149, Bird.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=5.0))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		sKnock.add_condition(bat.story.CondActionGE(Bird.L_ANIM, 17, tap=True))
		s.add_event("ShowDialogue", ("If you can bring me 3 other shiny red things, I'll give this one to you.",
				("That's not fair!", "I need it to do my job!")))
		s.add_action(bat.story.ActAction('Bi_Discuss', 17, 36, Bird.L_ANIM))
		s.add_action(bat.story.ActAction('Bi_Discuss_Idle', 1, 49, Bird.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=5.0))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "Now now, you can't just go taking things from other people.")
		s.add_action(bat.story.ActSound('//Sound/cc-by/BirdStatement1.ogg'))
		s.add_action(bat.story.ActAction('Bi_Discuss', 36, 47, Bird.L_ANIM))
		s.add_action(bat.story.ActAction('Bi_Discuss_Idle', 200, 249, Bird.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=5.0))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(Scripts.story.ActSetCamera('BirdCamera_BottleToNest'))

		s = s.create_successor()
		s.add_action(Scripts.story.ActSetCamera('BirdCamera_BottleToNest_zoom'))
		s.add_action(Scripts.story.ActSetFocalPoint('Nest'))
		s.add_action(Scripts.story.ActShowMarker('Nest'))
		s.add_event("ShowDialogue", "If you want this \[shell], bring 3 red things to my nest at the top of the tree.")
		s.add_action(bat.story.ActSound('//Sound/cc-by/BirdMutter.ogg'))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(Scripts.story.ActRemoveFocalPoint('Nest'))
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
		s.add_action(Scripts.story.ActRemoveFocalPoint('Nest'))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(bat.story.ActGeneric(steal_shell))
		s.add_action(bat.story.ActStoreSet('/game/level/birdTookShell', True))
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
