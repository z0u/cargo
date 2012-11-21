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

		bat.bats.add_and_mutate_object(self.scene, "FlyingCutscene", self)


class Spider(bat.story.Chapter, bat.bats.BX_GameObject, bge.types.BL_ArmatureObject):
	L_IDLE = 0
	L_ANIM = 1

	def __init__(self, old_owner):
		bat.story.Chapter.__init__(self, old_owner)
		self.create_state_graph()
		self.playAction('Spider_conv', 1, 1)

	def create_state_graph(self):
		s = self.rootState.create_successor("Init")
		s.add_condition(bat.story.CondEvent("ApproachWeb", self))
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
		s.add_action(bat.story.ActAction('Spider_conv', 1, 80, Spider.L_ANIM))
		scancel.add_predecessor(s)

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_action(Scripts.story.ActRemoveCamera("SpiderCam_CU"))
		s.add_action(Scripts.story.ActSetCamera("SpiderCam_Side"))
		s.add_event("ShowDialogue", "Ah, where are my manners? Welcome, my dear! Forgive me; I don't get many visitors.")
		scancel.add_predecessor(s)

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "It's strange, don't you think? Who could resist the beauty of Spider Isle?")

		scancel.add_predecessor(s)
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "Ah, I see you're admiring my collection. Isn't it marvellous?")
		scancel.add_predecessor(s)

		# START SPLIT 1
		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", ("I bet you've never seen the like on Tree Island.",
			("What about the Lighthouse?", "The Sauce Bar, madam!")))
		scancel.add_predecessor(s)

		storch = s.create_successor("torch")
		storch.add_condition(bat.story.CondEventEq("DialogueDismissed", 0, self))
		storch.add_event("ShowDialogue", "... Yes. The torch is quite a piece.")
		scancel.add_predecessor(s)

		sbar = s.create_successor("bar")
		sbar.add_condition(bat.story.CondEventEq("DialogueDismissed", 1, self))
		sbar.add_event("ShowDialogue", "Oh ho, but it is full of slugs!\n...Mind you, they do serve a smashing gravy.")
		scancel.add_predecessor(s)

		s = bat.story.State()
		storch.add_successor(s)
		sbar.add_successor(s)
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "I suppose you may find the occasional trinket there...")
		scancel.add_predecessor(s)
		# END SPLIT 1

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
		s.add_event("ShowDialogue", "But the unique bay of Spider Isle gathers a volume of treasure that other islands simply cannot compete with.")
		scancel.add_predecessor(s)
		s.add_action(bat.story.ActStoreSet('/game/level/spiderWelcome1', True))

		s = s.create_successor()
		s.add_condition(bat.story.CondEvent("DialogueDismissed", self))

		sconv_end = bat.story.State()
		sconv_end.add_predecessor(s)
		sconv_end.add_predecessor(scancel)

		s = sconv_end.create_successor("Clean up")
		s.add_action(Scripts.story.ActResumeInput())
		s.add_action(Scripts.story.ActRemoveFocalPoint('Spider'))
		s.add_action(Scripts.story.ActRemoveCamera("SpiderCam_Side"))
		s.add_action(Scripts.story.ActRemoveCamera("SpiderCam_CU"))
		s.add_action(Scripts.story.ActRemoveCamera("SpiderCam"))

		s = s.create_successor("Reset")
		s.add_condition(bat.story.CondEvent("LeaveWeb", self))
		s.add_successor(self.rootState)

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
