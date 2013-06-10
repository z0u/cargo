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
		s = (self.rootState.create_successor("Init nest")
			(bat.story.CondEvent('ApproachBird', self))
			(Scripts.story.ActSuspendInput())
			(Scripts.story.ActSetCamera('B_BirdIntroCam'))
			(Scripts.story.ActSetFocalPoint('Bi_FootHook.L'))
			(bat.story.ActMusicPlay(
				'//Sound/Music/06-TheBird_loop.ogg',
				introfile='//Sound/Music/06-TheBird_intro.ogg',
				fade_in_rate=1))
		)

		s = (s.create_successor()
			(bat.story.CondWait(0.5))
			("FinishLoading", self)
			(bat.story.ActAction("B_BirdCloseCamAction", 1, 96, 0, ob="B_BirdIntroCam"))
		)

		s = (s.create_successor()
			(bat.story.CondWait(0.5))
			("ShowDialogue", "Hi there, little snail! It's nice of you to come "
				"to visit.")
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", "Hey! That's a nice shiny red thing you have "
				"there. Are you here to talk business?")
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", "I haven't forgotten our deal: if you give me "
				"three shiny red things, I'll give you this one in return.")
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", ("So, will you give me that \[thimble]?",
				("Actually I think I'll keep it.", "I guess so.")))
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", ("Thanks! And, ooh, what a lovely \[wheel]!",
				("Here you go.", "Let's get this over with.")))
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", ("And a \[bottlecap]! That's for me too, right?",
				("Of course.", "Sure, why not :(")))
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", "Wonderful! What an excellent collection.")
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", "But you know what would make it even better? "
				"That \[nut]! I know it wasn't part of the deal...")
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", ("... but now that I have seen it, I know I can't "
				"part with the \[shell] for anything less.",
				("Whatever!", "Take it; it's slowing me down.")))
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", "Whoa, whoa! It's too heavy. Look out!")
		)

		# Nest falls down.

		# Cut to being at base of tree with contents of nest scattered around.
		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", "Oh my beautiful egg! What luck that it is not broken.")
		)
		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", "Hmm...")
		)
		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", ("You know, it strikes me that I may have been a "
				"little greedy.",
				("Well, maybe a little.", "You were so greedy!")))
		)

		# Bird is told that it was greedy, so it gives back the loot.
		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", "Oh you're right! I was greedy, and a fool.")
		)
		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ShowDialogue", "Please, take back the things you brought me.")
		)

		s = s.create_successor()(bat.story.CondEvent("DialogueDismissed", self))

		s = (s.create_successor()
			(bat.story.CondWait(1))
			("ForceEquipShell", "Thimble")
		)
		s = (s.create_successor()
			(bat.story.CondWait(1))
			("ForceEquipShell", "Wheel")
		)
		s = (s.create_successor()
			(bat.story.CondWait(1))
			("ForceEquipShell", "BottleCap")
		)

		s = (s.create_successor()
			(bat.story.CondWait(0.5))
			("ShowDialogue", "You can even take my shell. I can't bear to look "
				"at it! Besides, my nest was becoming a bit cluttered.")
		)

		s = (s.create_successor()
			(bat.story.CondEvent("DialogueDismissed", self))
			("ForceEquipShell", "Shell")
		)

		s = (s.create_successor()
			(bat.story.CondWait(0.5))
			("ShowDialogue", "Ah, I feel better already!")
		)

		s = (s.create_successor("Return to game")
			(Scripts.story.ActResumeInput())
			(Scripts.story.ActRemoveCamera('B_BirdIntroCam'))
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

def spawn_nest(c):
	required_shells = set()
	required_shells.update(Scripts.inventory.Shells().get_all_shells())
	if not required_shells.issubset(Scripts.inventory.Shells().get_shells()):
		# Player still needs to collect more shells.
		return
	bird = factory()
	bird.create_nest_state_graph()
	bat.bmath.copy_transform(c.owner, bird)
