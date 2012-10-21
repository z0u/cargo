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
import bat.utils
import bat.bmath
import bat.sound
import bat.render
import bat.story
import bat.impulse
import bat.store

import Scripts.director
import Scripts.story_bird

import Scripts.story

class Bottle(bat.impulse.Handler, bat.bats.BX_GameObject, bge.types.KX_GameObject):
	'''The Sauce Bar'''

	_prefix = 'B_'

	def __init__(self, oldOwner):
		self.snailInside = False
		self.transition_delay = 0
		self.open_window(False)
		bat.event.EventBus().add_listener(self)
		# Only handle overridden input events (see impulse.Handler).
		self.default_handler_response = False
		self.bird_arrived = False

	def on_event(self, evt):
		if evt.message == 'EnterBottle':
			self.enter_bottle()
		elif evt.message == 'ExitBottle':
			self.exit_bottle()
		elif evt.message == 'BirdArrived':
			self.bird_arrived = True

	@bat.bats.expose
	@bat.utils.controller_cls
	def door_touched(self, c):
		'''Control access to the Sauce Bar. If the snail is carrying a shell,
		the door should be shut; otherwise, the SauceBar level should be loaded.
		'''

		door = c.sensors['sDoor']
		safety = c.sensors['sSafetyZone']

		mainChar = Scripts.director.Director().mainCharacter

		# Eject all objects other than the snail.
		for ob in door.hitObjectList:
			if ob.parent is not None:
				continue
			if not ob == mainChar:
				# Only a snail can enter
				self.eject(ob)

		# If the bottle mode indicates that the snail is inside, double-check
		# that that's still the case.
		if self.snailInside and not mainChar in safety.hitObjectList:
			print("Exiting because snail not in safety.")
			self.exit_bottle()
			return

		if self.transition_delay > 0:
			self.transition_delay -= 1
			return
		elif self.transition_delay < 0:
			return

		if not mainChar in door.hitObjectList:
			return

		if not 'HasShell' in mainChar:
			# Touched by an occupied shell.
			self.eject(mainChar)
		elif not self.snailInside and mainChar['HasShell']:
			# Touched by a snail who is wearing a shell.
			bat.event.Event('ShowDialogue',
					"You can't fit! Press X to drop your shell.").send()
			self.eject(mainChar)
		elif self.snailInside:
			#print("Exiting because snail touched door.")
			cbEvent = bat.event.Event("ExitBottle")
			bat.event.Event("ShowLoadingScreen", (True, cbEvent)).send()
			self.transition_delay = -1
		else:
			#print("Entering because snail touched door.")
			cbEvent = bat.event.Event("EnterBottle")
			bat.event.Event("ShowLoadingScreen", (True, cbEvent)).send()
			self.transition_delay = -1

	def enter_bottle(self):
		bat.store.put('/game/spawnPoint', 'SpawnBottle')
		self.open_window(True)
		bat.event.Event('TeleportSnail', 'SpawnBottleInner').send()
		bat.event.Event("AddCameraGoal", 'BottleCamera').send()
		bat.impulse.Input().add_handler(self, 'STORY')

		self.snailInside = True
		self.transition_delay = 1
		bat.event.Event("ShowLoadingScreen", (False, None)).send()

	def exit_bottle(self):
		# Transitioning to outside; move camera to sensible location.
		self.open_window(False)
		bat.event.Event('TeleportSnail', 'SpawnBottle').send()
		bat.event.Event("RemoveCameraGoal", 'BottleCamera').send()

		if self.bird_arrived:
			# The bird has interrupted the story (triggered by conversation with
			# barkeeper).
			# First, really make sure the snail hasn't got a shell. Just in
			# case!
			bat.event.Event('ForceDropShell', False).send()
			# Then spawn the bird.
			spawn_point = self.scene.objects["Bird_SauceBar_Spawn"]
			bird = Scripts.story_bird.factory()
			bat.bmath.copy_transform(spawn_point, bird)
			self.bird_arrived = False

		elif not bat.store.get("/game/canDropShell", False):
			# Don't let a snail wander around with no shell until after the bird
			# has taken one.
			bat.event.Event('ForceReclaimShell').send()
		bat.impulse.Input().remove_handler(self)

		self.snailInside = False
		self.transition_delay = 1
		bat.event.Event("ShowLoadingScreen", (False, None)).send()

	def eject(self, ob):
		direction = self.children['B_Door'].getAxisVect(bat.bmath.ZAXIS)
		ob.worldPosition += direction

	def open_window(self, isOpening):
		sce = bge.logic.getCurrentScene()
		if isOpening:
			# Create bar interior; destroy exterior (so it doesn't get in the
			# way when crawling).
			if not 'B_Inner' in sce.objects:
				sce.addObject('B_Inner', self)
			if 'B_Outer' in sce.objects:
				sce.objects['B_Outer'].endObject()
		else:
			# Create bar exterior; destroy interior.
			if 'B_Inner' in sce.objects:
				sce.objects['B_Inner'].endObject()
			if not 'B_Outer' in sce.objects:
				sce.addObject('B_Outer', self)

	def can_handle_input(self, state):
		'''Don't allow snail to reclaim shell when inside.'''
		return state.name in ('1', '2', 'Switch')

class BottleRock(bat.bats.BX_GameObject, bge.types.KX_GameObject):
	'''A rock that hides itself when the snail enters the bar.'''
	def __init__(self, old_owner):
		bat.event.EventBus().add_listener(self)

	def on_event(self, evt):
		if evt.message == 'EnterBottle':
			self.visible = False
			self.children['B_SoilCrossSection'].visible = True
		elif evt.message == 'ExitBottle':
			self.visible = True
			self.children['B_SoilCrossSection'].visible = False


class BottleDropZone(bat.impulse.Handler, bat.bats.BX_GameObject, bge.types.KX_GameObject):
	'''
	Allows snail to drop shell, but only when standing at the door of the
	bottle.
	'''

	_prefix = 'DZ_'

	def __init__(self, old_owner):
		bat.event.EventBus().add_listener(self)
		# Only handle overridden input events (see impulse.Handler).
		self.default_handler_response = False
		self.shell_drop_initiated_at_door = False

	def on_event(self, evt):
		if evt.message == 'ShellDropped':
			if self.shell_drop_initiated_at_door:
				cbEvent = bat.event.Event("EnterBottle")
				bat.event.Event("ShowLoadingScreen", (True, cbEvent)).send()
				self.shell_drop_initiated_at_door = False

	@bat.bats.expose
	@bat.utils.controller_cls
	def touched(self, c):
		'''Register self as an input handler to allow snail to drop shell.'''
		s = c.sensors[0]
		mainChar = Scripts.director.Director().mainCharacter
		if mainChar in s.hitObjectList:
			bat.impulse.Input().add_handler(self, 'STORY')
		else:
			bat.impulse.Input().remove_handler(self)

	def can_handle_input(self, state):
		'''Allow snail to drop shell.'''
		return state.name == '2'

	def handle_input(self, state):
		if state.name == '2':
			self.handle_bt_2(state)

	def handle_bt_2(self, state):
		'''
		Handle a drop-shell request when the snail is nearby. This is required
		because the shell cannot be dropped at will until later in the game.
		'''
		if state.activated:
			bat.event.Event('ForceDropShell', True).send()
			self.shell_drop_initiated_at_door = True


class BarKeeper(bat.story.Chapter, bge.types.KX_GameObject):

	_prefix = 'BK_'

	L_IDLE = 0
	L_ANIM = 1

	idle_action = bat.story.ActAction('Slug_AtBar', 1, 119, L_ANIM,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP,
				targetDescendant='SlugArm_Min', blendin=15)
	serve_action = bat.story.ActAction('Slug_Serve', 1, 140, L_ANIM,
				targetDescendant='SlugArm_Min', blendin=3)
	serve_action_glass = bat.story.ActAction('B_ServingGlass_Serve', 1, 140,
				L_ANIM, ob='B_ServingGlass', blendin=3)
	serve_glass_reset = bat.story.ActAction('B_ServingGlass_Serve', 1, 1,
				L_ANIM, ob='B_ServingGlass')

	def __init__(self, old_owner):
		bat.story.Chapter.__init__(self, old_owner)
		self.arm = bat.bats.add_and_mutate_object(self.scene, "SlugArm_Min",
				self.children["SlugSpawnPos"])
		self.arm.setParent(self)
		self.arm.localScale = (0.75, 0.75, 0.75)
		self.create_state_graph()
		# This is modified using ActAttrSet
		self.bird_arrived = False
		self.first = True

	def create_state_graph(self):
		#
		# Set scene with a long shot camera.
		#
		s = self.rootState.create_successor("Init")
#		s.add_action(BarKeeper.idle_action)
		s.add_action(BarKeeper.serve_glass_reset)
		s.add_action(bat.story.ActAction('B_EnvelopeDeliver', 1, 1,
				 ob='B_Envelope'))
		s.add_action(bat.story.ActGeneric(self.arm.look_at, 'Snail'))
		s.add_action(bat.story.ActAction('Slug_AtBar', 1, 1, BarKeeper.L_ANIM,
				targetDescendant='SlugArm_Min'))

		sfirsttimeonly = s.create_sub_step()
		sfirsttimeonly.add_condition(bat.story.CondAttrEq('first', True))
		sfirsttimeonly.add_action(bat.story.ActMusicPlay('//Sound/Music/Idea-Random2.ogg'))
		sfirsttimeonly.add_action(bat.story.ActAttrSet('first', False))

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(0))
		s.add_action(BarKeeper.idle_action)

		s = s.create_successor()
		s.add_condition(bat.story.CondSensor('Near'))
		s.add_action(Scripts.story.ActSuspendInput())
		#s.add_event("StartLoading", self)

		s = s.create_successor()
		#s.add_condition(bat.story.CondWait(1))
		#s.add_event("FinishLoading", self)
		s.add_action(Scripts.story.ActSetCamera('BottleCamera_Close'))
		s.add_action(Scripts.story.ActSetFocalPoint("SlugLookTarget"))
		s.add_action(bat.story.ActGeneric(self.arm.look_at, None))
		s.add_event("TeleportSnail", "BK_SnailTalkPos")

		# Split story.
		# Note that these are added IN ORDER: if the first one fails, it will
		# fall through to the second, and so on. Therefore, the ones that come
		# later in the story are listed first.
		safterbottlecap = self.sg_afterbottlecap([s])
		safterbird = self.sg_afterbird([s])
		sbeforebird = self.sg_beforebird([s])
		sbeforelighthouse = self.sg_beforelighthouse([s])

		#
		# Merge, and return to game
		#
		s = bat.story.State("Return to game")
		safterbottlecap.add_successor(s)
		safterbird.add_successor(s)
		sbeforebird.add_successor(s)
		sbeforelighthouse.add_successor(s)
		s.add_action(Scripts.story.ActResumeInput())
		s.add_action(Scripts.story.ActRemoveCamera('BottleCamera_Close'))
		s.add_action(Scripts.story.ActRemoveFocalPoint("SlugLookTarget"))

		#
		# Loop back to start when snail moves away. Unless the bird has arrived,
		# in which case the slug should remain cowering behind the bar, with the
		# music stopped.
		#
		s = s.create_successor("Reset")
		s.add_condition(bat.story.CondSensorNot('Near'))
		s.add_condition(bat.story.CondAttrEq('bird_arrived', False))
		s.add_successor(self.rootState)

	def sg_beforelighthouse(self, preceding_states):
		s = bat.story.State("beforelighthouse")
		for ps in preceding_states:
			ps.add_successor(s)

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 15,
				targetDescendant='SlugArm_Min'))
		s.add_event("ShowDialogue", "Hi Cargo. What will it be, the usual?")
		s.add_action(BarKeeper.idle_action)

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(BarKeeper.serve_action)
		s.add_action(BarKeeper.serve_action_glass)

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 40,
				targetDescendant='SlugArm_Min'))
		s.add_event("ShowDialogue", "There you go - one tomato sauce. Enjoy!")

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		return s

	def sg_beforebird(self, preceding_states):
		s = bat.story.State("beforebird")
		for ps in preceding_states:
			ps.add_successor(s)
		s.add_condition(bat.story.CondStore('/game/level/lkMissionStarted', True, False))
		s.add_event("ShowDialogue", ("Hi there, Mr Postman. What can I do for you?",
				("\[envelope].", "1 tomato sauce, please.")))
		s.add_action(bat.story.ActAction('Slug_Greet', 1, 40, BarKeeper.L_ANIM,
				targetDescendant='SlugArm_Min', blendin=3))

		sauce = s.create_successor("sauce please")
		sauce.add_condition(bat.story.CondEventEq("DialogueDismissed", 1, self))
		sauce.add_action(BarKeeper.serve_action)
		sauce.add_action(BarKeeper.serve_action_glass)

		sauce = sauce.create_successor()
		sauce.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 40,
				targetDescendant='SlugArm_Min'))
		sauce.add_event("ShowDialogue", "There you go.")

		sauce = sauce.create_successor()
		sauce.add_condition(bat.story.CondEvent("DialogueDismissed", self))

		sauce = sauce.create_successor()
		sauce.add_condition(bat.story.CondWait(2))
		sauce.add_event("ShowDialogue", "Be careful, Cargo. It's a strange day.")

		sauce = sauce.create_successor()
		sauce.add_condition(bat.story.CondEvent("DialogueDismissed", self))

		sdeliver = s.create_successor("deliver")
		sdeliver.add_condition(bat.story.CondEventNe("DialogueDismissed", 1, self))
		sdeliver.add_event("ShowDialogue", "Ah, cheers for the letter. So, the "
				"lighthouse keeper wants some more black bean sauce, eh?")
		sdeliver.add_action(bat.story.ActAction('B_EnvelopeDeliver', 1, 70,
				BarKeeper.L_ANIM, ob='B_Envelope'))
		sdeliver.add_action(bat.story.ActAction('Slug_AcceptDelivery', 1, 70,
				BarKeeper.L_ANIM, targetDescendant='SlugArm_Min', blendin=3))

		sdeliver = sdeliver.create_successor()
		sdeliver.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 70,
				targetDescendant='SlugArm_Min'))
		sdeliver.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		sdeliver.add_event("ShowDialogue", "She must be busy to not come here to get it herself.")
		sdeliver.add_action(bat.story.ActAction('Slug_AcceptDelivery', 80, 132,
				BarKeeper.L_ANIM, targetDescendant='SlugArm_Min', blendin=3))
		sloop = sdeliver.create_sub_step()
		sloop.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 132,
				targetDescendant='SlugArm_Min', tap=True))
		sloop.add_action(bat.story.ActAction('Slug_AcceptDelivery', 150, 190,
					BarKeeper.L_ANIM, play_mode=bge.logic.KX_ACTION_MODE_LOOP,
					targetDescendant='SlugArm_Min', blendin=10))

		sdeliver = sdeliver.create_successor()
		sdeliver.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		sdeliver.add_event("ShowDialogue", "Oh, the lighthouse is broken?")
		sdeliver.add_action(bat.story.ActAction('Slug_AcceptDelivery', 230, 240,
				BarKeeper.L_ANIM, targetDescendant='SlugArm_Min', blendin=3))
		sloop = sdeliver.create_sub_step()
		sloop.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 240,
				targetDescendant='SlugArm_Min', tap=True))
		sloop.add_action(BarKeeper.idle_action)

		sdeliver = sdeliver.create_successor()
		sdeliver.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		sdeliver.add_event("ShowDialogue", "There has been a thief here too. You must have noticed the missing lights on your way in?")
		sdeliver.add_action(bat.story.ActAction('Slug_AcceptDelivery', 260, 280,
				BarKeeper.L_ANIM, targetDescendant='SlugArm_Min', blendin=3))
		sloop = sdeliver.create_sub_step()
		sloop.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 280,
				targetDescendant='SlugArm_Min', tap=True))
		sloop.add_action(bat.story.ActAction('Slug_AcceptDelivery', 298, 338,
					BarKeeper.L_ANIM, play_mode=bge.logic.KX_ACTION_MODE_LOOP,
					targetDescendant='SlugArm_Min', blendin=10))

		sdeliver = sdeliver.create_successor()
		sdeliver.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		sdeliver.add_event("ShowDialogue", "They disappeared just last night.")

		sdeliver = sdeliver.create_successor()
		sdeliver.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		sdeliver.add_event("ShowDialogue", "What is the island coming to? I can imagine this happening on Spider Isle, but not here.")
		sdeliver.add_action(bat.story.ActAction('Slug_AcceptDelivery', 380, 400,
				BarKeeper.L_ANIM, targetDescendant='SlugArm_Min', blendin=3))
		sloop = sdeliver.create_sub_step()
		sloop.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 400,
				targetDescendant='SlugArm_Min', tap=True))
		sloop.add_action(BarKeeper.idle_action)

		sdeliver = sdeliver.create_successor()
		sdeliver.add_condition(bat.story.CondEvent("DialogueDismissed", self))

		# Bird arrives! Shake the camera about.
		sdeliver = sdeliver.create_successor()
		sdeliver.add_condition(bat.story.CondWait(2))
		sdeliver.add_action(bat.story.ActAction("BottleCamera_CloseAction",
				1, 75, 0, ob="BottleCamera_Close"))
		sdeliver.add_event('BirdArrived')
		sdeliver.add_action(bat.story.ActAction('Slug_AcceptDelivery', 440, 450,
				BarKeeper.L_ANIM, targetDescendant='SlugArm_Min', blendin=3))
		sdeliver.add_action(bat.story.ActMusicStop(fade_rate=0.1))
		sdeliver.add_action(bat.story.ActSound('//Sound/cc-by/NeedleOff.ogg'))
		sdeliver.add_action(bat.story.ActSound('//Sound/cc-by/CrashBoom1.ogg', vol=0.6))

		stweet1 = sdeliver.create_sub_step("Bird Sound 1")
		stweet1.add_condition(bat.story.CondActionGE(0, 20, ob="BottleCamera_Close", tap=True))
		stweet1.add_action(bat.story.ActSound('//Sound/cc-by/BirdTweet1.ogg'))
		stweet1.add_action(bat.story.ActAction('Slug_AcceptDelivery', 450, 500,
				BarKeeper.L_ANIM, targetDescendant='SlugArm_Min', blendin=3))

		sboom1 = sdeliver.create_sub_step()
		sboom1.add_condition(bat.story.CondActionGE(0, 30, ob="BottleCamera_Close", tap=True))
		sboom1.add_action(bat.story.ActSound('//Sound/cc-by/CrashBoom2.ogg', vol=0.6))

		stweet2 = sdeliver.create_sub_step("Bird Sound 2")
		stweet2.add_condition(bat.story.CondActionGE(0, 50, ob="BottleCamera_Close", tap=True))
		stweet2.add_action(bat.story.ActSound('//Sound/cc-by/BirdTweet2.ogg'))

		sboom2 = sdeliver.create_sub_step()
		sboom2.add_condition(bat.story.CondActionGE(0, 60, ob="BottleCamera_Close", tap=True))
		sboom2.add_action(bat.story.ActSound('//Sound/cc-by/CrashBoom3.ogg', vol=0.6))

		sdeliver = sdeliver.create_successor()
		sdeliver.add_condition(bat.story.CondWait(1))
		sdeliver.add_sub_step(stweet1)
		sdeliver.add_sub_step(stweet2)
		sdeliver.add_sub_step(sboom1)
		sdeliver.add_sub_step(sboom2)
		sdeliver.add_event("ShowDialogue", "Look out! It's that cursed thing again. It must be back for the rest of the lights.")

		sloop = sdeliver.create_sub_step()
		sloop.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 500,
				targetDescendant='SlugArm_Min', tap=True))
		sloop.add_action(bat.story.ActAction('Slug_AcceptDelivery', 543, 583,
					BarKeeper.L_ANIM, play_mode=bge.logic.KX_ACTION_MODE_LOOP,
					targetDescendant='SlugArm_Min', blendin=10))

		sdeliver = sdeliver.create_successor()
		sdeliver.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		sdeliver.add_action(bat.story.ActAttrSet('bird_arrived', True))

		s = bat.story.State("merge")
		sauce.add_successor(s)
		sdeliver.add_successor(s)

		return s

	def sg_afterbird(self, preceding_states):
		s = bat.story.State("afterbird")
		for ps in preceding_states:
			ps.add_successor(s)
		s.add_condition(bat.story.CondStore('/game/level/birdTookShell', True, False))
		s.add_event("ShowDialogue", "Hi again, Cargo. Terribly sorry to hear about your shell!")
		s.add_action(BarKeeper.idle_action)
		s.add_action(bat.story.ActAction('Slug_Greet', 1, 40, BarKeeper.L_ANIM,
				targetDescendant='SlugArm_Min', blendin=3))
		sloop = s.create_sub_step()
		sloop.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 15,
				targetDescendant='SlugArm_Min', tap=True))
		sloop.add_action(BarKeeper.idle_action)

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "That pesky bird needs to be taught a lesson!")
		s.add_action(bat.story.ActAction('Slug_AfterBird', 1, 25, BarKeeper.L_ANIM,
				targetDescendant='SlugArm_Min', blendin=3))
		sloop = s.create_sub_step()
		sloop.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 25,
				targetDescendant='SlugArm_Min', tap=True))
		sloop.add_action(bat.story.ActAction('Slug_AfterBird', 25, 65,
					BarKeeper.L_ANIM, play_mode=bge.logic.KX_ACTION_MODE_LOOP,
					targetDescendant='SlugArm_Min'))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "It's no good charging up the tree: the bees won't allow it. They're very protective of their honey.")
		s.add_action(bat.story.ActAction('Slug_AfterBird', 80, 115, BarKeeper.L_ANIM,
				targetDescendant='SlugArm_Min', blendin=3))
		sloop = s.create_sub_step()
		sloop.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 115,
				targetDescendant='SlugArm_Min', tap=True))
		sloop.add_action(bat.story.ActAction('Slug_AfterBird', 115, 155,
					BarKeeper.L_ANIM, play_mode=bge.logic.KX_ACTION_MODE_LOOP,
					targetDescendant='SlugArm_Min'))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "But, first things first, eh? You need to get your shell back.")
		s.add_action(bat.story.ActAction('Slug_AfterBird', 160, 180, BarKeeper.L_ANIM,
				targetDescendant='SlugArm_Min', blendin=3))
		sloop = s.create_sub_step()
		sloop.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 180,
				targetDescendant='SlugArm_Min', tap=True))
		sloop.add_action(bat.story.ActAction('Slug_AfterBird', 180, 220,
					BarKeeper.L_ANIM, play_mode=bge.logic.KX_ACTION_MODE_LOOP,
					targetDescendant='SlugArm_Min'))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "I don't know how you'll get to the nest, but, hmm... shiny red things...")
		s.add_action(bat.story.ActAction('Slug_AfterBird', 220, 264, BarKeeper.L_ANIM,
				targetDescendant='SlugArm_Min', blendin=3))
		sloop = s.create_sub_step()
		sloop.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 264,
				targetDescendant='SlugArm_Min', tap=True))
		sloop.add_action(bat.story.ActAction('Slug_AfterBird', 294, 334,
					BarKeeper.L_ANIM, play_mode=bge.logic.KX_ACTION_MODE_LOOP,
					targetDescendant='SlugArm_Min', blendin=10))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(2))
		s.add_event("ShowDialogue", "Ah, that's right! This bottle used to have a bright red lid \[bottlecap]!")
		s.add_action(bat.story.ActAction('Slug_AfterBird', 370, 385, BarKeeper.L_ANIM,
				targetDescendant='SlugArm_Min', blendin=3))
		sloop = s.create_sub_step()
		sloop.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 385,
				targetDescendant='SlugArm_Min', tap=True))
		sloop.add_action(bat.story.ActAction('Slug_AfterBird', 385, 420,
					BarKeeper.L_ANIM, play_mode=bge.logic.KX_ACTION_MODE_LOOP,
					targetDescendant='SlugArm_Min'))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "I used to use it as a door, but it washed away one day in heavy rain.")
		s.add_action(bat.story.ActAction('Slug_AfterBird', 430, 468, BarKeeper.L_ANIM,
				targetDescendant='SlugArm_Min', blendin=3))
		sloop = s.create_sub_step()
		sloop.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 468,
				targetDescendant='SlugArm_Min', tap=True))
		sloop.add_action(bat.story.ActAction('Slug_AfterBird', 470, 505,
					BarKeeper.L_ANIM, play_mode=bge.logic.KX_ACTION_MODE_LOOP,
					targetDescendant='SlugArm_Min'))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "I think I saw the \[bottlecap] on that little island near your house.")

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "The water is deep, though, so you'll have to figure out how to get there dry.")

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "Quick, go and get it!")
		s.add_action(bat.story.ActAction('Slug_AfterBird', 520, 530, BarKeeper.L_ANIM,
				targetDescendant='SlugArm_Min', blendin=3))
		sloop = s.create_sub_step()
		sloop.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 530,
				targetDescendant='SlugArm_Min', tap=True))
		sloop.add_action(bat.story.ActAction('Slug_AfterBird', 530, 586,
					BarKeeper.L_ANIM, play_mode=bge.logic.KX_ACTION_MODE_LOOP,
					targetDescendant='SlugArm_Min'))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(bat.story.ActAction('Slug_AfterBird', 595, 610, BarKeeper.L_ANIM,
				targetDescendant='SlugArm_Min', blendin=3))

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 605,
				targetDescendant='SlugArm_Min'))
		return s

	def sg_afterbottlecap(self, preceding_states):
		s = bat.story.State("afterbottlecap")
		for ps in preceding_states:
			ps.add_successor(s)
		s.add_condition(bat.story.CondStore('/game/level/birdTookShell', True, False))
		s.add_condition(Scripts.story.CondHasShell('BottleCap'))
		s.add_event("ShowDialogue", ("Hi Cargo, what's happening?",
				("\[bottlecap]!", "I'm thirsty.")))

		## Second option.
		sauce = s.create_successor("sauce please")
		sauce.add_condition(bat.story.CondEventEq("DialogueDismissed", 1, self))
		sauce.add_event("ShowDialogue", "More tomato sauce?")
		sauce.add_action(BarKeeper.serve_action)
		sauce.add_action(BarKeeper.serve_action_glass)

		sauce = sauce.create_successor()
		sauce.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 40,
				targetDescendant='SlugArm_Min'))
		sauce.add_event("ShowDialogue", "There you go.")

		sauce = sauce.create_successor()
		sauce.add_condition(bat.story.CondEvent("DialogueDismissed", self))

		## First option.
		scap = s.create_successor("cap")
		scap.add_condition(bat.story.CondEventNe("DialogueDismissed", 1, self))
		scap.add_event("ShowDialogue", "You found my bottle cap! That's great news.")

		scap = scap.create_successor()
		scap.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		scap.add_event("ShowDialogue", "It's OK, you can keep it. I like not having a door: I get more customers this way.")
		scap.add_action(bat.story.ActAction('Slug_AfterBottleCap', 1, 45,
				BarKeeper.L_ANIM, targetDescendant='SlugArm_Min', blendin=3))
		sloop = scap.create_sub_step()
		sloop.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 45,
				targetDescendant='SlugArm_Min', tap=True))
		sloop.add_action(bat.story.ActAction('Slug_AfterBottleCap', 45, 70,
					BarKeeper.L_ANIM, play_mode=bge.logic.KX_ACTION_MODE_LOOP,
					targetDescendant='SlugArm_Min'))

		scap = scap.create_successor()
		scap.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		scap.add_event("ShowDialogue", "Only two more shiny red things to go, eh? Sadly I haven't seen anything else that is shiny and red.")
		scap.add_action(bat.story.ActAction('Slug_AfterBottleCap', 80, 96,
				BarKeeper.L_ANIM, targetDescendant='SlugArm_Min', blendin=3))
		sloop = scap.create_sub_step()
		sloop.add_condition(bat.story.CondActionGE(BarKeeper.L_ANIM, 96,
				targetDescendant='SlugArm_Min', tap=True))
		sloop.add_action(BarKeeper.idle_action)

		scap = scap.create_successor()
		scap.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		scap.add_event("ShowDialogue", "You'll just have to keep looking.")

		scap = scap.create_successor()
		scap.add_condition(bat.story.CondEvent("DialogueDismissed", self))

		s = bat.story.State("merge")
		sauce.add_successor(s)
		scap.add_successor(s)
		return s


def lighthouse_stub():
	bat.store.put('/game/level/lkMissionStarted', True)

@bat.utils.all_sensors_positive
def test_bird():
	sce = bge.logic.getCurrentScene()
	spawn_point = sce.objects["Bird_SauceBar_Spawn"]
	bird = Scripts.story_bird.factory()
	bat.bmath.copy_transform(spawn_point, bird)


class Blinkenlights(bat.bats.BX_GameObject, bge.types.KX_GameObject):
	'''A series of blinking lights, like you find outside take away joints.'''

	def __init__(self, old_owner):
		'''Create a new Blinkenlights object.

		The owner should be the 'string' holding up the lights. This object
		should have the following children:
			 - One lamp.
			 - Any number of mesh objects. These must have a keyed object
			   colour.
		The mesh children will have their luminance cycled. The lamp will be
		given the colour of the lights that are on.

		Owner properties:
		cycleLen: The number of lights in a pattern. E.g. with a cycle length of
			3, lights will have the pattern [on, off, off, etc.]
		frames: The number of impulses to wait before moving stepping to the
			next state.'''

		self.step = 0

		def isLamp(x): return hasattr(x, 'energy')

		# Sort lights by distance from cord origin.
		self.lights = []
		for ob in self.children:
			self.lights.append(ob)
		self.lights.sort(key=bat.bmath.DistanceKey(self))

		self.cols = list(map(
				lambda x: bat.render.parse_colour(x["colour"]), self.lights))
		self.targetCols = list(self.cols)
		self.targetLampCol = bat.render.BLACK.copy()

		# Hide half of the lights until the end of the game.
		if self['side'] == 'right':
			if not bat.store.get('/game/level/bottleLights', False):
				self.setVisible(False, True)

	@bat.bats.expose
	def blink(self):
		stringLen = self['cycleLen']
		self.step = (self.step + 1) % stringLen
		self.targetLampCol = bat.render.BLACK.copy()
		for i, col in enumerate(self.cols):
			target = None
			if (i % stringLen) == self.step:
				target = col * 2.0
				self.targetLampCol += col
			else:
				target = col * 0.2
				target.w = 1.0
			self.targetCols[i] = target

	@bat.bats.expose
	def update(self):
		for light, targetCol in zip(self.lights, self.targetCols):
			light.color = bat.bmath.lerp(light.color, targetCol, 0.1)
