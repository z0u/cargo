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
import bat.story

import Scripts.story
import Scripts.shells

def factory(sce):
	if not "Spider" in sce.objectsInactive:
		try:
			bge.logic.LibLoad('//Spider_loader.blend', 'Scene', load_actions=True)
		except ValueError as e:
			print('Warning: could not load spider:', e)

	return bat.bats.add_and_mutate_object(sce, "Spider", "Spider")

class SpiderIsle(bat.bats.BX_GameObject, bge.types.KX_GameObject):

	_prefix = "SI_"

	def __init__(self, old_owner):
		self.catapult_primed = False
		bat.event.EventBus().add_listener(self)

	def on_event(self, evt):
		if evt.message == 'ShellDropped':
			self.play_flying_cutscene(evt.body)

	@bat.bats.expose
	@bat.utils.controller_cls
	def approach_centre(self, c):
		if c.sensors[0].positive:
			if 'Spider' in self.scene.objects:
				return
			spider = factory(self.scene)
			spawn_point = self.scene.objects['Spider_SpawnPoint']
			bat.bmath.copy_transform(spawn_point, spider)
		else:
			if 'Spider' not in self.scene.objects:
				return
			spider = self.scene.objects['Spider']
			spider.endObject()

	@bat.bats.expose
	@bat.utils.controller_cls
	def approach_web(self, c):
		for s in c.sensors:
			if not s.positive:
				continue
			player = s.hitObject
			if not player.is_in_shell:
				bat.event.Event('ApproachWeb').send()
			return
		# else
		bat.event.Event('LeaveWeb').send()

	@bat.bats.expose
	@bat.utils.controller_cls
	def catapult_end_touched(self, c):
		self.catapult_primed = c.sensors[0].positive
		if self.catapult_primed:
			print("side cam")
			bat.event.Event("AddCameraGoal", "FC_SideCamera_Preview").send()
		else:
			bat.event.Event("RemoveCameraGoal", "FC_SideCamera_Preview").send()

	def play_flying_cutscene(self, shell):
		if not self.catapult_primed:
			return
		if shell is None or shell.name != "Nut":
			return

		snail = Scripts.director.Director().mainCharacter
		snail_up = snail.getAxisVect(bat.bmath.ZAXIS)
		if snail_up.dot(bat.bmath.ZAXIS) < 0.0:
			# Snail is upside down, therefore on wrong side of catapult
			return

		spawn_point = self.scene.objects["FC_SpawnPoint"]
		bat.bats.add_and_mutate_object(self.scene, "FlyingCutscene", spawn_point)


class Spider(bat.story.Chapter, bat.bats.BX_GameObject, bge.types.BL_ArmatureObject):
	L_ANIM = 0
	L_IDLE = 1

	def __init__(self, old_owner):
		bat.story.Chapter.__init__(self, old_owner)
		self.anim_welcome = bat.story.AnimBuilder('Spider_conv', layer=Spider.L_ANIM)
		self.anim_nice = bat.story.AnimBuilder('Spider_conv_nice', layer=Spider.L_ANIM)
		self.anim_rude = bat.story.AnimBuilder('Spider_conv_rude', layer=Spider.L_ANIM)
		self.anim_get = bat.story.AnimBuilder('Spider_conv_get', layer=Spider.L_ANIM)
		self.create_state_graph()

	def create_state_graph(self):
		sinit = self.rootState.create_successor("Init")
		self.anim_welcome.play(sinit, 1, 1)
		sinit.add_action(bat.story.ActAction('Spider_idle', 1, 60, Spider.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))

		# This graph plays the first time you meet the spider.
		swelcome_start, swelcome_end = self.create_welcome_graph()
		swelcome_start.add_predecessor(sinit)

		# This one plays when you pick up the wheel.
		sget_start, sget_end = self.create_wheel_get_graph()
		sget_start.add_predecessor(sinit)

		# This one plays if you approach the spider again after getting the
		# wheel.
		safter_start, safter_end = self.create_after_wheel_graph()
		safter_start.add_predecessor(sinit)

		sinit.add_predecessor(swelcome_end)
		sinit.add_predecessor(sget_end)
		sinit.add_predecessor(safter_end)

	def create_welcome_graph(self):
		sstart = bat.story.State("Welcome")
		sstart.add_condition(bat.story.CNot(Scripts.story.CondHasShell("Wheel")))
		sstart.add_condition(bat.story.CondEvent("ApproachWeb", self))

		s = sstart.create_successor()
		s.add_action(Scripts.story.ActSuspendInput())
		s.add_action(Scripts.story.ActSetFocalPoint('Spider'))
		s.add_action(Scripts.story.ActSetCamera("SpiderCam"))

		# Catch-many state for when the user cancels a dialogue. Should only be
		# allowed if the conversation has been played once already.
		scancel = bat.story.State("Cancel")
		scancel.add_condition(bat.story.CondEvent('DialogueCancelled', self))
		scancel.add_condition(bat.story.CondStore('/game/level/spiderWelcome1', True, default=False))

		s = s.create_successor()
		s.add_action(Scripts.story.ActSetCamera("SpiderCam_CU"))
		s.add_event("ShowDialogue", "Who goes there?")
		self.anim_welcome.play(s, 1, 20)
		scancel.add_predecessor(s)

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "Ah, where are my manners? Welcome, my dear! Forgive me; I don't get many visitors.")
		self.anim_welcome.play(s, 30, 45)
		scancel.add_predecessor(s)
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Spider.L_ANIM, 36, tap=True))
		sub.add_action(Scripts.story.ActRemoveCamera("SpiderCam_CU"))
		sub.add_action(Scripts.story.ActSetCamera("SpiderCam_Side"))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(Scripts.story.ActRemoveCamera("SpiderCam_CU"))
		s.add_action(Scripts.story.ActSetCamera("SpiderCam_Side"))
		s.add_event("ShowDialogue", "It's strange, don't you think? Who could resist the beauty of Spider Isle?")
		self.anim_welcome.play(s, 50, 60)
		scancel.add_predecessor(s)

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "I just love the salt forest. And you won't believe this...")
		self.anim_welcome.play(s, 70, 120)
		scancel.add_predecessor(s)

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "... Treasure simply washes up on the shore! Ha ha!")
		self.anim_welcome.play(s, 130, 150)
		scancel.add_predecessor(s)

		# START SPLIT 1
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", ("This is my latest find. Isn't it marvelous?",
			("Can I have it?", "Hey, my \[shell] was taken, so...")))
		self.anim_welcome.play(s, 160, 170)
		s.add_successor(scancel)
		sub = s.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Spider.L_ANIM, 163, tap=True))
		sub.add_action(Scripts.story.ActSetCamera("SpiderCam_Wheel"))

		sask = s.create_successor("bar")
		sask.add_condition(bat.story.CondActionGE(Spider.L_ANIM, 170))
		sask.add_condition(bat.story.CondEventEq("DialogueDismissed", 0, self))
		sask.add_event("ShowDialogue", "Oh ho, you must be joking!")
		self.anim_rude.play(sask, 1, 30)
		sask.add_action(Scripts.story.ActRemoveCamera("SpiderCam_Wheel"))
		sask.add_successor(scancel)

		ssob = s.create_successor("sobstory")
		ssob.add_condition(bat.story.CondActionGE(Spider.L_ANIM, 170))
		ssob.add_condition(bat.story.CondEventEq("DialogueDismissed", 1, self))
		ssob.add_event("ShowDialogue", "Oh, what a nuisance. He is indeed a pesky bird.")
		self.anim_nice.play(ssob, 1, 30)
		ssob.add_action(Scripts.story.ActRemoveCamera("SpiderCam_Wheel"))
		ssob.add_successor(scancel)

		# END SPLIT 1; START SPLIT 2
		s = bat.story.State()
		ssob.add_successor(s)
		sask.add_successor(s)
		s.add_condition(bat.story.CondActionGE(Spider.L_ANIM, 30))
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", ("But no, I can't just give it to you. It is too precious.",
			("I'll be your best friend.", "You're not even using it!")))
		self.anim_welcome.play(s, 180, 200, blendin=10)
		s.add_successor(scancel)

		splead = s.create_successor("plead")
		splead.add_condition(bat.story.CondActionGE(Spider.L_ANIM, 200))
		splead.add_condition(bat.story.CondEventEq("DialogueDismissed", 0, self))
		splead.add_event("ShowDialogue", "Oh! Well then... let's play a game.")
		self.anim_nice.play(splead, 40, 100)
		splead.add_successor(scancel)

		splead = splead.create_successor()
		splead.add_condition(bat.story.CondActionGE(Spider.L_ANIM, 100))
		splead.add_condition(bat.story.CondEvent("DialogueDismissed", self))

		sdemand = s.create_successor("demand")
		sdemand.add_condition(bat.story.CondActionGE(Spider.L_ANIM, 200))
		sdemand.add_condition(bat.story.CondEventEq("DialogueDismissed", 1, self))
		sdemand.add_event("ShowDialogue", "What a rude snail you are! You shall not have it.")
		self.anim_rude.play(sdemand, 40, 100)
		sdemand.add_successor(scancel)
		sub = sdemand.create_sub_step()
		sub.add_condition(bat.story.CondActionGE(Spider.L_ANIM, 74, tap=True))
		sub.add_action(Scripts.story.ActSetCamera("SpiderCam_ECU"))

		sdemand = sdemand.create_successor()
		sdemand.add_condition(bat.story.CondActionGE(Spider.L_ANIM, 80))
		sdemand.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		sdemand.add_event("ShowDialogue", "But allow me to taunt you. Hehehe...")
		self.anim_rude.play(sdemand, 110, 150)
		sdemand.add_action(Scripts.story.ActRemoveCamera("SpiderCam_ECU"))
		sdemand.add_successor(scancel)

		sdemand = sdemand.create_successor()
		sdemand.add_condition(bat.story.CondActionGE(Spider.L_ANIM, 150))
		sdemand.add_condition(bat.story.CondEvent("DialogueDismissed", self))

		s = bat.story.State()
		splead.add_successor(s)
		sdemand.add_successor(s)
		s.add_event("ShowDialogue", "If you can touch the wheel \[wheel], you can keep it.")
		self.anim_welcome.play(s, 210, 280, blendin=7)
		s.add_action(Scripts.story.ActSetFocalPoint("Wheel_Icon"))
		s.add_action(bat.story.ActAttrSet("visible", True, ob="Wheel_Icon"))
		s.add_action(bat.story.ActAction("Wheel_IconAction", 210, 280, ob="Wheel_Icon"))
		s.add_successor(scancel)
		# END SPLIT 2

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Spider.L_ANIM, 260))
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "But we both know it's going to be tricky!")
		self.anim_welcome.play(s, 290, 330)
		s.add_action(bat.story.ActAttrSet("visible", False, ob="Wheel_Icon"))
		s.add_action(Scripts.story.ActRemoveFocalPoint('Wheel_Icon'))
		scancel.add_predecessor(s)

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(bat.story.ActStoreSet('/game/level/spiderWelcome1', True))

		sconv_end = bat.story.State()
		sconv_end.add_predecessor(s)
		sconv_end.add_predecessor(scancel)

		s = sconv_end.create_successor("Clean up")
		s.add_action(Scripts.story.ActResumeInput())
		s.add_action(Scripts.story.ActRemoveFocalPoint('Spider'))
		s.add_action(Scripts.story.ActRemoveFocalPoint('Wheel_Icon'))
		s.add_action(Scripts.story.ActRemoveCamera("SpiderCam_Side"))
		s.add_action(Scripts.story.ActRemoveCamera("SpiderCam_Wheel"))
		s.add_action(Scripts.story.ActRemoveCamera("SpiderCam_CU"))
		s.add_action(Scripts.story.ActRemoveCamera("SpiderCam_ECU"))
		s.add_action(Scripts.story.ActRemoveCamera("SpiderCam"))

		send = s.create_successor("end")
		send.add_condition(bat.story.CondEvent("LeaveWeb", self))

		return sstart, send

	def create_wheel_get_graph(self):
		sstart = bat.story.State("Get")
		sstart.add_condition(bat.story.CondEventEq("ShellFound", "Wheel", self))

		s = sstart.create_successor()
		s.add_event("ShowDialogue", "You got the Wheel! It's strong and fast.")

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(Scripts.story.ActSuspendInput())
		s.add_action(Scripts.story.ActSetFocalPoint('Spider'))
		s.add_action(Scripts.story.ActSetCamera("SpiderCam_Side"))

		s = s.create_successor()
		s.add_event("ShowDialogue", "Good gracious!")
		self.anim_get.play(s, 1, 45)

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Spider.L_ANIM, 45))
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "... I must admit, I'm impressed. I didn't expect you to be able to reach it.")
		self.anim_get.play(s, 50, 80)

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Spider.L_ANIM, 75))
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "But I am a lady of my word. Keep it. May it serve you well.")
		self.anim_get.play(s, 90, 130)

		s = s.create_successor()
		s.add_condition(bat.story.CondActionGE(Spider.L_ANIM, 130))
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))

		s = s.create_successor("Clean up")
		s.add_action(Scripts.story.ActResumeInput())
		s.add_action(Scripts.story.ActRemoveFocalPoint('Spider'))
		s.add_action(Scripts.story.ActRemoveCamera("SpiderCam_Side"))

		send = s.create_successor("end")

		return sstart, send

	def create_after_wheel_graph(self):
		sstart = bat.story.State("Get")
		sstart.add_condition(Scripts.story.CondHasShell("Wheel"))
		sstart.add_condition(bat.story.CondEvent("ApproachWeb", self))

		s = sstart.create_successor()
		s.add_action(Scripts.story.ActSuspendInput())
		s.add_action(Scripts.story.ActSetFocalPoint('Spider'))
		s.add_action(Scripts.story.ActSetCamera("SpiderCam_Side"))

		s = s.create_successor()
		s.add_event("ShowDialogue", "How is the new shell? It looks like fun.")

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))

		s = s.create_successor("Clean up")
		s.add_action(Scripts.story.ActResumeInput())
		s.add_action(Scripts.story.ActRemoveFocalPoint('Spider'))
		s.add_action(Scripts.story.ActRemoveCamera("SpiderCam_Side"))

		send = s.create_successor("end")

		return sstart, send

	def get_focal_points(self):
		return [self.children['Spider_Face'], self]


class FlyingCutscene(bat.story.Chapter, bat.bats.BX_GameObject, bge.types.KX_GameObject):

	def __init__(self, old_owner):
		bat.story.Chapter.__init__(self, old_owner)
		self.create_state_graph()

	def create_state_graph(self):
		# This state is executed as a sub-step of other states. That is, it
		# runs every frame while those states are active to make sure the snail
		# trapped.
		snail_holder = bat.story.State("Snail hold")
		snail_holder.add_action(bat.story.ActGeneric(self.hold_snail))

		# Far shot.
		s = self.rootState.create_successor("Init")
		s.add_action(Scripts.story.ActSetCamera("FC_SideCamera"))
		s.add_action(Scripts.story.ActSuspendInput())

		# Close-up
		s = s.create_successor("Transition")
		s.add_condition(bat.story.CondWait(0.5))
		s.add_action(Scripts.story.ActSetCamera("FC_Camera"))
		s.add_action(Scripts.story.ActSetFocalPoint("FC_SnailFlyFocus"))
		s.add_sub_step(snail_holder)

		# Flying through the air. This is a separate state with a CondWait
		# condition to ensure that the GLSL materials have all been compiled
		# before starting the animation.
		s = s.create_successor("Warp speed")
		s.add_condition(bat.story.CondWait(0.01))
		s.add_action(bat.story.ActAction("FC_AirstreamAction", 1, 51, 0, ob="FC_Airstream"))
		s.add_action(bat.story.ActAction("FC_CameraAction", 1, 51, 0, ob="FC_Camera"))
		s.add_action(bat.story.ActAction("FC_SnailFlyAction", 1, 100, 0, ob="FC_SnailFly"))
		s.add_sub_step(snail_holder)

		# Shoot the snail through the web. Note that the snail_holder sub-state
		# is no longer used.
		s = s.create_successor("Pick up wheel")
		s.add_condition(bat.story.CondActionGE(0, 49, ob="FC_Airstream"))
		s.add_action(Scripts.story.ActRemoveCamera("FC_Camera"))
		s.add_action(Scripts.story.ActRemoveFocalPoint("FC_SnailFlyFocus"))
		s.add_action(bat.story.ActGeneric(self.shoot_snail))

		s = s.create_successor("Clean up")
		s.add_condition(bat.story.CondWait(1))
		s.add_action(Scripts.story.ActRemoveCamera("FC_SideCamera"))
		s.add_action(Scripts.story.ActResumeInput())
		s.add_action(bat.story.ActDestroy())

	def hold_snail(self):
		snail = Scripts.director.Director().mainCharacter
		anchor = self.scene.objects['FC_SnailShoot']
		bat.bmath.copy_transform(anchor, snail)
		snail.localLinearVelocity = bat.bmath.MINVECTOR

	def shoot_snail(self):
		snail = Scripts.director.Director().mainCharacter
		anchor = self.scene.objects['FC_SnailShoot']
		bat.bmath.copy_transform(anchor, snail)
		snail.localLinearVelocity = bat.bmath.YAXIS * 75.0
