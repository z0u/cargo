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
		bat.store.put('/game/level/spawnPoint', 'SpawnBottle')
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

	S_INIT = 1
	S_DROPPED = 2

	_prefix = 'DZ_'

	def __init__(self, old_owner):
		bat.event.EventBus().add_listener(self)
		# Only handle overridden input events (see impulse.Handler).
		self.default_handler_response = False
		self.shell_drop_initiated_at_door = False
		self.dropped_shell = None

	def on_event(self, evt):
		if evt.message == 'ShellDropped':
			if self.shell_drop_initiated_at_door:
				cbEvent = bat.event.Event("EnterBottle")
				bat.event.Event("ShowLoadingScreen", (True, cbEvent)).send()
				self.shell_drop_initiated_at_door = False
				self.dropped_shell = evt.body
				self.add_state(BottleDropZone.S_DROPPED)

	@bat.bats.expose
	@bat.utils.controller_cls
	def touched(self, c):
		'''Register self as an input handler to allow snail to drop shell.'''
		s = c.sensors[0]
		mainChar = Scripts.director.Director().mainCharacter
		if mainChar in s.hitObjectList:
			bat.impulse.Input().add_handler(self, 'STORY')
		else:
			self.shell_drop_initiated_at_door = False
			bat.impulse.Input().remove_handler(self)

	@bat.bats.expose
	def park_shell(self):
		if self.dropped_shell is None or self.dropped_shell.invalid:
			return
		park = self.children['B_ShellPark']
		self.dropped_shell.worldPosition = park.worldPosition
		self.dropped_shell.worldLinearVelocity = (0, 0, 0.0001)
		self.dropped_shell = None
		self.rem_state(BottleDropZone.S_DROPPED)

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

	serve_action = bat.story.ActAction('Slug_Serve', 1, 140,
				targetDescendant='SlugArm_Min', blendin=3)
	serve_action_glass = bat.story.ActAction('B_ServingGlass_Serve', 1, 140,
				ob='B_ServingGlass', blendin=3)
	serve_glass_reset = bat.story.ActAction('B_ServingGlass_Serve', 1, 1,
				ob='B_ServingGlass')

	def __init__(self, old_owner):
		bat.story.Chapter.__init__(self, old_owner)
		self.arm = bat.bats.add_and_mutate_object(self.scene, "SlugArm_Min",
				self.children["SlugSpawnPos"])
		self.arm.setParent(self)
		self.arm.localScale = (0.75, 0.75, 0.75)
		slug_body = self.arm.children['SlugBody_Min']
		slug_body.color = bat.render.parse_colour('#FFCC5C')

		# This is modified using ActAttrSet
		self.bird_arrived = False
		self.first = True

		# Half-baked animations ;)
		self.anim_idle = bat.story.AnimBuilder('Slug_AtBar',
				target_descendant='SlugArm_Min', blendin=15)
		self.anim_idle.store('loop', 1, 119, loop=True)

		self.anim_greet = bat.story.AnimBuilder('Slug_Greet',
				target_descendant='SlugArm_Min', blendin=3)
		self.anim_greet.store('greet', 1, 40)

		self.anim_delivery = bat.story.AnimBuilder('Slug_AcceptDelivery',
				target_descendant='SlugArm_Min', blendin=3)
		self.anim_after_bird = bat.story.AnimBuilder('Slug_AfterBird',
				target_descendant='SlugArm_Min', blendin=3)
		self.anim_bottle_cap = bat.story.AnimBuilder('Slug_AfterBottleCap',
				target_descendant='SlugArm_Min', blendin=3)

		self.create_state_graph()

	def create_state_graph(self):
		#
		# Set scene with a long shot camera.
		#
		s = self.rootState.create_successor("Init")
		s.add_action(BarKeeper.serve_glass_reset)
		s.add_action(bat.story.ActAction('B_EnvelopeDeliver', 1, 1,
				 ob='B_Envelope'))
		s.add_action(bat.story.ActGeneric(self.arm.look_at, 'Snail'))
		s.add_action(bat.story.ActAction('Slug_AtBar', 1, 1,
				targetDescendant='SlugArm_Min'))

		sfirsttimeonly = s.create_sub_step()
		sfirsttimeonly.add_condition(bat.story.CondAttrEq('first', True))
		# No need to stop the music, because this object is destroyed when
		# leaving the area.
		sfirsttimeonly.add_action(bat.story.ActMusicPlay(
				'//Sound/Music/04-TheBar_loop.ogg',
				introfile='//Sound/Music/04-TheBar_intro.ogg',
				fade_in_rate=1))
		sfirsttimeonly.add_action(bat.story.ActAttrSet('first', False))

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(0))
		self.anim_idle.recall(s, 'loop')

		s = s.create_successor()
		s.add_condition(bat.story.CondSensor('Near'))
		s.add_action(Scripts.story.ActSuspendInput())
		#s.add_event("StartLoading", self)

		s = s.create_successor()
		#s.add_condition(bat.story.CondWait(1))
		#s.add_event("FinishLoading", self)
		s.add_action(Scripts.story.ActSetCamera('BottleCamera_Close'))
		s.add_action(Scripts.story.ActSetFocalPoint("SlugArm_Min"))
		s.add_action(bat.story.ActGeneric(self.arm.look_at, None))
		s.add_event("TeleportSnail", "BK_SnailTalkPos")

		# Split story.
		# Note that these are added IN ORDER: if the first one fails, it will
		# fall through to the second, and so on. Therefore, the ones that come
		# later in the story are listed first.
		sstart, safterbottlecap = self.sg_afterbottlecap()
		sstart.add_predecessor(s)
		sstart, safterbird = self.sg_afterbird()
		sstart.add_predecessor(s)
		sstart, sbeforebird = self.sg_beforebird()
		sstart.add_predecessor(s)
		sstart, sbeforelighthouse = self.sg_beforelighthouse()
		sstart.add_predecessor(s)

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
		s.add_action(Scripts.story.ActRemoveFocalPoint("SlugArm_Min"))

		#
		# Loop back to start when snail moves away. Unless the bird has arrived,
		# in which case the slug should remain cowering behind the bar, with the
		# music stopped.
		#
		s = s.create_successor("Reset")
		s.add_condition(bat.story.CondSensorNot('Near'))
		s.add_condition(bat.story.CondAttrEq('bird_arrived', False))
		s.add_successor(self.rootState)

	def sg_beforelighthouse(self):
		sstart = bat.story.State("beforelighthouse")

		s = sstart.create_successor()
		s.add_condition(bat.story.CondActionGE(0, 15, targetDescendant='SlugArm_Min'))
		s.add_event("ShowDialogue", "Hi Cargo. What will it be, the usual?")
		self.anim_idle.recall(s, 'loop')

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(BarKeeper.serve_action)
		s.add_action(BarKeeper.serve_action_glass)

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(0, 40, targetDescendant='SlugArm_Min'))
		s.add_event("ShowDialogue", "There you go - one tomato sauce. Enjoy!")
		self.anim_idle.recall(s, 'loop', after=115)

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))

		return sstart, s

	def sg_beforebird(self):
		sstart = bat.story.State("beforebird")
		sstart.add_condition(bat.story.CondStore('/game/level/lkMissionStarted', True, False))

		s = sstart.create_successor()
		s.add_event("ShowDialogue", ("Hi there, Mr Postman. What can I do for you?",
				("\[envelope].", "1 tomato sauce, please.")))
		self.anim_greet.recall(s, 'greet')
		self.anim_idle.recall(s, 'loop', after=15)

		sauce = s.create_successor("sauce please")
		sauce.add_condition(bat.story.CondEventEq("DialogueDismissed", 1, self))
		sauce.add_action(BarKeeper.serve_action)
		sauce.add_action(BarKeeper.serve_action_glass)

		sauce = sauce.create_successor()
		sauce.add_condition(bat.story.CondActionGE(0, 40, targetDescendant='SlugArm_Min'))
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
		sdeliver.add_action(bat.story.ActAction('B_EnvelopeDeliver', 1, 70, ob='B_Envelope'))
		self.anim_delivery.play(sdeliver, 1, 70)

		sdeliver = sdeliver.create_successor()
		sdeliver.add_condition(bat.story.CondActionGE(0, 70, targetDescendant='SlugArm_Min'))
		sdeliver.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		sdeliver.add_event("ShowDialogue", "She must be busy to not come here to get it herself.")
		self.anim_delivery.play(sdeliver, 80, 132)
		self.anim_delivery.loop(sdeliver, 150, 190, after=132, blendin=10)

		sdeliver = sdeliver.create_successor()
		sdeliver.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		sdeliver.add_event("ShowDialogue", "Oh, the lighthouse is broken?")
		self.anim_delivery.play(sdeliver, 230, 240)
		self.anim_idle.recall(sdeliver, 'loop', after=240)

		sdeliver = sdeliver.create_successor()
		sdeliver.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		sdeliver.add_event("ShowDialogue", "There has been a thief here too. You must have noticed the missing lights on your way in?")
		self.anim_delivery.play(sdeliver, 260, 280)
		self.anim_delivery.loop(sdeliver, 298, 338, after=280, blendin=10)

		sdeliver = sdeliver.create_successor()
		sdeliver.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		sdeliver.add_event("ShowDialogue", "They disappeared just last night.")

		sdeliver = sdeliver.create_successor()
		sdeliver.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		sdeliver.add_event("ShowDialogue", "What is the island coming to? I can imagine this happening on Spider Isle, but not here.")
		self.anim_delivery.play(sdeliver, 380, 400)
		self.anim_idle.recall(sdeliver, 'loop', after=400)

		sdeliver = sdeliver.create_successor()
		sdeliver.add_condition(bat.story.CondEvent("DialogueDismissed", self))

		# Bird arrives! Shake the camera about.
		sdeliver = sdeliver.create_successor()
		sdeliver.add_condition(bat.story.CondWait(2))
		sdeliver.add_action(bat.story.ActAction("BottleCamera_CloseAction",
				1, 75, 0, ob="BottleCamera_Close"))
		sdeliver.add_event('BirdArrived')
		self.anim_delivery.play(sdeliver, 440, 450)
		sdeliver.add_action(bat.story.ActMusicStop(fade_rate=0.1))
		sdeliver.add_action(bat.story.ActSound('//Sound/cc-by/NeedleOff.ogg'))
		sdeliver.add_action(bat.story.ActSound('//Sound/cc-by/CrashBoom1.ogg', vol=0.6))

		stweet1 = sdeliver.create_sub_step("Bird Sound 1")
		stweet1.add_condition(bat.story.CondActionGE(0, 20, ob="BottleCamera_Close", tap=True))
		stweet1.add_action(bat.story.ActSound('//Sound/cc-by/BirdTweet1.ogg'))
		self.anim_delivery.play(stweet1, 450, 500)

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
		self.anim_delivery.loop(sdeliver, 543, 583, after=500, blendin=10)

		sdeliver = sdeliver.create_successor()
		sdeliver.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		sdeliver.add_action(bat.story.ActAttrSet('bird_arrived', True))

		s = bat.story.State("merge")
		sauce.add_successor(s)
		sdeliver.add_successor(s)

		return sstart, s

	def sg_afterbird(self):
		sstart = bat.story.State("afterbird")
		sstart.add_condition(bat.story.CondStore('/game/level/birdTookShell', True, False))

		scancel = bat.story.State("Cancel")
		scancel.add_condition(bat.story.CondEvent('DialogueCancelled', self))
		scancel.add_condition(bat.story.CondStore('/game/level/slugBottleCapConv1', True, default=False))

		s = sstart.create_successor()
		s.add_event("ShowDialogue", "Hi again, Cargo. Terribly sorry to hear about your shell!")
		self.anim_greet.recall(s, 'greet')
		self.anim_idle.recall(s, 'loop', after=15)

		scancel.add_predecessor(s)
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "That pesky bird needs to be taught a lesson!")
		self.anim_after_bird.play(s, 1, 25, 65)

		scancel.add_predecessor(s)
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "It's no good charging up the tree: the bees won't allow it. They're very protective of their honey.")
		self.anim_after_bird.play(s, 80, 115, 155)

		scancel.add_predecessor(s)
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "But, first things first, eh? You need to get your shell back.")
		self.anim_after_bird.play(s, 160, 180, 220)

		scancel.add_predecessor(s)
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "I don't know how you'll get to the nest, but, hmm... shiny red things...")
		self.anim_after_bird.play(s, 220, 264)
		self.anim_after_bird.loop(s, 294, 334, after=264)

		scancel.add_predecessor(s)
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))

		s = s.create_successor()
		s.add_condition(bat.story.CondWait(2))
		s.add_event("ShowDialogue", "Ah, that's right! This bottle used to have a bright red lid \[bottlecap]!")
		self.anim_after_bird.play(s, 370, 385, 420)

		scancel.add_predecessor(s)
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "I used to use it as a door, but it washed away one day in heavy rain.")
		self.anim_after_bird.play(s, 430, 468)
		self.anim_after_bird.loop(s, 470, 505, after=468)

		scancel.add_predecessor(s)
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "I think I saw the \[bottlecap] on that little island near your house.")
		# This map goal is un-set by Scripts.story.GameLevel when the next shell is collected.
		s.add_action(bat.story.ActStoreSet('/game/level/mapGoal', 'BottleCapSpawn'))
		s.add_event("MapGoalChanged")

		scancel.add_predecessor(s)
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "The water is deep, though, so you'll have to figure out how to get there dry.")

		scancel.add_predecessor(s)
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "Quick, go and get it!")
		self.anim_after_bird.play(s, 520, 530, 586)

		scancel.add_predecessor(s)
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		self.anim_after_bird.play(s, 595, 610)

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(0, 605, targetDescendant='SlugArm_Min'))
		s.add_action(bat.story.ActStoreSet('/game/level/slugBottleCapConv1', True))
		s.add_action(bat.story.ActStoreSet('/game/storySummary', 'slugBottleCapConv1'))

		sconv_end = bat.story.State()
		sconv_end.add_predecessor(s)
		sconv_end.add_predecessor(scancel)

		return sstart, sconv_end

	def sg_afterbottlecap(self):
		sstart = bat.story.State("afterbottlecap")
		sstart.add_condition(bat.story.CondStore('/game/level/birdTookShell', True, False))
		sstart.add_condition(Scripts.story.CondHasShell('BottleCap'))

		scancel = bat.story.State("Cancel")
		scancel.add_condition(bat.story.CondEvent('DialogueCancelled', self))
		scancel.add_condition(bat.story.CondStore('/game/level/slugBottleCapConv2', True, default=False))

		s = sstart.create_successor()
		s.add_event("ShowDialogue", ("Hi Cargo, what's happening?",
				("\[bottlecap]!", "I'm thirsty.")))

		## Second option.
		scancel.add_predecessor(s)
		sauce = s.create_successor("sauce please")
		sauce.add_condition(bat.story.CondEventEq("DialogueDismissed", 1, self))
		sauce.add_event("ShowDialogue", "More tomato sauce?")
		sauce.add_action(BarKeeper.serve_action)
		sauce.add_action(BarKeeper.serve_action_glass)

		sauce = sauce.create_successor()
		sauce.add_condition(bat.story.CondActionGE(0, 40,
				targetDescendant='SlugArm_Min'))
		sauce.add_event("ShowDialogue", "There you go.")

		sauce = sauce.create_successor()
		sauce.add_condition(bat.story.CondEvent("DialogueDismissed", self))

		## First option.
		scancel.add_predecessor(s)
		scap = s.create_successor("cap")
		scap.add_condition(bat.story.CondEventNe("DialogueDismissed", 1, self))
		scap.add_event("ShowDialogue", "You found my bottle cap! That's great news.")

		scancel.add_predecessor(scap)
		scap = scap.create_successor()
		scap.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		scap.add_event("ShowDialogue", "It's OK, you can keep it. I like not having a door: I get more customers this way.")
		self.anim_bottle_cap.play(scap, 1, 45, 70)

		scancel.add_predecessor(scap)
		scap = scap.create_successor()
		scap.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		scap.add_event("ShowDialogue", "Only two more shiny red things to go, eh? Sadly I haven't seen anything else that is shiny and red.")
		self.anim_bottle_cap.play(scap, 80, 96)
		self.anim_idle.recall(scap, 'loop', after=96)

		scancel.add_predecessor(scap)
		scap = scap.create_successor()
		scap.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		scap.add_event("ShowDialogue", "You'll just have to keep looking.")

		scancel.add_predecessor(scap)
		scap = scap.create_successor()
		scap.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		scap.add_action(bat.story.ActStoreSet('/game/level/slugBottleCapConv2', True))

		s = bat.story.State("merge")
		sauce.add_successor(s)
		scap.add_successor(s)

		sconv_end = bat.story.State()
		sconv_end.add_predecessor(s)
		sconv_end.add_predecessor(scancel)

		return sstart, sconv_end


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
