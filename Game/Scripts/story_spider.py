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

import bxt.types
import bxt.utils
import bxt.bmath

from Scripts.story import *

def factory(sce):
	if not "Spider" in sce.objectsInactive:
		try:
			bge.logic.LibLoad('//Spider_loader.blend', 'Scene', load_actions=True)
		except ValueError as e:
			print('Warning: could not load spider:', e)

	return bxt.types.add_and_mutate_object(sce, "Spider", "Spider")

class SpiderIsle(bxt.types.BX_GameObject, bge.types.KX_GameObject):

	_prefix = "SI_"

	def __init__(self, old_owner):
		self.catapult_primed = False
		bxt.types.EventBus().add_listener(self)

	def on_event(self, evt):
		if evt.message == 'ShellDropped':
			self.play_flying_cutscene(evt.body)

	@bxt.types.expose
	@bxt.utils.controller_cls
	def approach_centre(self, c):
		if c.sensors[0].positive:
			if 'Spider' in self.scene.objects:
				return
			spider = factory(self.scene)
			spawn_point = self.scene.objects['Spider_SpawnPoint']
			bxt.bmath.copy_transform(spawn_point, spider)
		else:
			if 'Spider' not in self.scene.objects:
				return
			spider = self.scene.objects['Spider']
			spider.endObject()

	@bxt.types.expose
	@bxt.utils.controller_cls
	def approach_web(self, c):
		if c.sensors[0].positive:
			bxt.types.Event('ApproachWeb').send()
		else:
			bxt.types.Event('LeaveWeb').send()

	@bxt.types.expose
	@bxt.utils.controller_cls
	def catapult_end_touched(self, c):
		self.catapult_primed = c.sensors[0].positive

	def play_flying_cutscene(self, shell):
		if not self.catapult_primed:
			return
		if shell is None or shell.name != "Nut":
			return

		snail = Scripts.director.Director().mainCharacter
		snail_up = snail.getAxisVect(bxt.bmath.ZAXIS)
		if snail_up.dot(bxt.bmath.ZAXIS) < 0.0:
			# Snail is upside down, therefore on wrong side of catapult
			return

		bxt.types.add_and_mutate_object(self.scene, "FlyingCutscene", self)


class Spider(Chapter, bxt.types.BX_GameObject, bge.types.BL_ArmatureObject):
	L_IDLE = 0
	L_ANIM = 1

	def __init__(self, old_owner):
		Chapter.__init__(self, old_owner)
		self.create_state_graph()
		self.playAction('Spider_conv', 1, 1)

	def create_state_graph(self):
		s = self.rootState.createTransition("Init")
		s.addCondition(CondEvent("ApproachWeb"))
		s.addAction(ActSuspendInput())
		s.addAction(ActSetFocalPoint('Spider'))
		s.addAction(ActSetCamera("SpiderCam"))

		s = s.createTransition()
		s.addAction(ActSetCamera("SpiderCam_CU"))
		s.addEvent("ShowDialogue", "Who goes there?")
		s.addAction(ActAction('Spider_conv', 1, 80, Spider.L_ANIM))

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addAction(ActRemoveCamera("SpiderCam_CU"))
		s.addAction(ActSetCamera("SpiderCam_Side"))
		s.addEvent("ShowDialogue", "Ah, where are my manners? Welcome, my dear! Forgive me; I don't get many visitors.")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "It's strange, don't you think? Who could resist the beauty of Spider Isle?")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "Ah, I see you're admiring my collection. Isn't it marvellous?")

		# START SPLIT 1
		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", ("I bet you've never seen the like on Tree Island.",
			("What about the Lighthouse?", "The Sauce Bar, madam!")))

		storch = s.createTransition("torch")
		storch.addCondition(CondEventEq("DialogueDismissed", 0))
		storch.addEvent("ShowDialogue", "... Yes. The torch is quite a piece.")

		sbar = s.createTransition("bar")
		sbar.addCondition(CondEventEq("DialogueDismissed", 1))
		sbar.addEvent("ShowDialogue", "Oh ho, but it is full of slugs!\n...Mind you, they do serve a smashing gravy.")

		s = State()
		storch.addTransition(s)
		sbar.addTransition(s)
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "I suppose you may find the occasional trinket there...")
		# END SPLIT 1

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "But the unique bay of Spider Isle gathers a volume of treasure that other islands simply cannot compete with.")

		s = s.createTransition("Clean up")
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addAction(ActResumeInput())
		s.addAction(ActRemoveFocalPoint('Spider'))
		s.addAction(ActRemoveCamera("SpiderCam_Side"))
		s.addAction(ActRemoveCamera("SpiderCam_CU"))
		s.addAction(ActRemoveCamera("SpiderCam"))

		s = s.createTransition("Reset")
		s.addCondition(CondEvent("LeaveWeb"))
		s.addTransition(self.rootState)

	def get_focal_points(self):
		return [self.children['Spider_Face'], self]


class FlyingCutscene(Chapter, bxt.types.BX_GameObject, bge.types.KX_GameObject):

	def __init__(self, old_owner):
		Chapter.__init__(self, old_owner)
		self.create_state_graph()

	def create_state_graph(self):
		# This state is executed as a sub-step of other states. That is, it
		# runs every frame while those states are active to make sure the snail
		# trapped.
		snail_holder = State("Snail hold")
		snail_holder.addAction(ActGeneric(self.hold_snail))

		# Far shot.
		s = self.rootState.createTransition("Init")
		s.addAction(ActSetCamera("FC_SideCamera"))
		s.addAction(ActSuspendInput())

		# Close-up
		s = s.createTransition("Transition")
		s.addCondition(CondWait(0.5))
		s.addAction(ActSetCamera("FC_Camera"))
		s.addAction(ActSetFocalPoint("FC_SnailFlyFocus"))
		s.addSubStep(snail_holder)

		# Flying through the air. This is a separate state with a CondWait
		# condition to ensure that the GLSL materials have all been compiled
		# before starting the animation.
		s = s.createTransition("Warp speed")
		s.addCondition(CondWait(0.01))
		s.addAction(ActAction("FC_AirstreamAction", 1, 51, 0, ob="FC_Airstream"))
		s.addAction(ActAction("FC_CameraAction", 1, 51, 0, ob="FC_Camera"))
		s.addAction(ActAction("FC_SnailFlyAction", 1, 100, 0, ob="FC_SnailFly"))
		s.addSubStep(snail_holder)

		# Shoot the snail through the web. Note that the snail_holder sub-state
		# is no longer used.
		s = s.createTransition("Pick up wheel")
		s.addCondition(CondActionGE(0, 49, ob="FC_Airstream"))
		s.addAction(ActRemoveCamera("FC_Camera"))
		s.addAction(ActGeneric(self.shoot_snail))

		s = s.createTransition("Clean up")
		s.addCondition(CondWait(1))
		s.addAction(ActRemoveCamera("FC_SideCamera"))
		s.addAction(ActResumeInput())
		s.addAction(ActDestroy())

	def hold_snail(self):
		snail = Scripts.director.Director().mainCharacter
		anchor = self.children['FC_SnailShoot']
		bxt.bmath.copy_transform(anchor, snail)
		snail.localLinearVelocity = bxt.bmath.MINVECTOR

	def shoot_snail(self):
		snail = Scripts.director.Director().mainCharacter
		anchor = self.children['FC_SnailShoot']
		bxt.bmath.copy_transform(anchor, snail)
		snail.localLinearVelocity = bxt.bmath.YAXIS * 75.0
