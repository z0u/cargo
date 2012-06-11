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

import bxt

from . import shells
from . import inventory
from .story import *

def factory():
	scene = bge.logic.getCurrentScene()
	if not "Ant" in scene.objectsInactive:
		try:
			bge.logic.LibLoad('//Ant_loader.blend', 'Scene', load_actions=True)
		except ValueError as e:
			print('Warning: could not load ant:', e)

	return bxt.types.add_and_mutate_object(scene, "Ant", "Ant")

class Honeypot(bxt.types.BX_GameObject, bge.types.KX_GameObject):

	_prefix = "HP_"

	def __init__(self, old_owner):
		Chapter.__init__(self, old_owner)
		#bxt.types.WeakEvent("StartLoading", self).send()
		ant1 = factory()
		bxt.bmath.copy_transform(self.children["Ant1SpawnPoint"], ant1)
		ant1.setParent(self)

	@bxt.types.expose
	@bxt.utils.controller_cls
	def approach(self, c):
		if c.sensors[0].positive:
			bxt.types.Event("ApproachAnts").send()

class Ant(Chapter, bxt.types.BX_GameObject, bge.types.BL_ArmatureObject):
	L_IDLE = 0
	L_ANIM = 1

	def __init__(self, old_owner):
		Chapter.__init__(self, old_owner)
		self.create_state_graph()
		self.pick = self.childrenRecursive['Ant_Pick']

	def create_state_graph(self):
		s = self.rootState.createTransition("Init")
		s.addAction(ActConstraintSet("Hand.L", "Copy Transforms", 1.0))
		s.addAction(ActAction('Ant_Digging1', 1, 38, Ant.L_ANIM,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))
		sKnock = s.createSubStep("Knock sound")
		sKnock.addCondition(CondActionGE(Ant.L_ANIM, 34.5, tap=True))
		sKnock.addAction(ActSound('//Sound/Knock.ogg', vol=1.0, pitchmin=0.7,
				pitchmax=0.76, emitter=self, maxdist=75.0))

		s = s.createTransition("Talk")
		s.addCondition(CondEvent("ApproachAnts"))
		s.addAction(ActSuspendInput())
		s.addWeakEvent("StartLoading", self)

		# Start conversation

		s = s.createTransition()
		s.addCondition(CondWait(1))
		s.addWeakEvent("FinishLoading", self)
		s.addAction(ActSetFocalPoint('Ant'))
		s.addAction(ActSetCamera('AntCloseCam'))
		s.addEvent("TeleportSnail", "HP_SnailTalkPos")
		# Reset camera pos
		s.addAction(ActAction('HP_AntConverse_Cam', 1, 1, 0, ob='AntCloseCam'))
		s.addAction(ActAction('HP_AntCrackCam', 1, 1, 0, ob='AntCrackCam'))
		# Raises head, takes deep breath
		s.addEvent("ShowDialogue", "Mmmm, smell that?")
		s.addAction(ActAction('HP_AntConverse', 30, 70, Ant.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))
		s.addAction(ActAction('HP_AntConverse', 1, 30, Ant.L_ANIM))
		s.addAction(ActMusicPlay('//Sound/Music/Ants1.ogg'))

		# Gestures fiercely at Cargo

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addAction(ActGeneric(self.drop_pick))
		s.addEvent("ShowDialogue", "Doesn't it smell amazing? So sweet! So sugary!")
		s.addAction(ActAction('HP_AntConverse', 90, 93, Ant.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=5.0))
		s.addAction(ActAction('HP_AntConverse', 70, 90, Ant.L_ANIM, blendin=5.0))
		s.addAction(ActAction('HP_AntConverse_Cam', 70, 90, 0, ob='AntCloseCam'))
		sdrop_pick = s.createSubStep("Adjust influence")
		sdrop_pick.addAction(ActConstraintFade("Hand.L", "Copy Transforms",
				1.0, 0.0, 70.0, 76.0, Ant.L_ANIM))

		# Holds fists tight; then, gestures towards the tree

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addAction(ActActionStop(Ant.L_IDLE))
		s.addAction(ActAction('HP_AntConverse', 95, 140, Ant.L_ANIM, blendin=2.0))
		s.addEvent("ShowDialogue", "I've got to have it! But this wood is just too strong,")
		sswitch_cam = s.createSubStep("Switch camera")
		sswitch_cam.addCondition(CondActionGE(Ant.L_ANIM, 126, tap=True))
		sswitch_cam.addAction(ActSetCamera('AntCrackCam'))
		sswitch_cam.addAction(ActAction('HP_AntCrackCam', 140, 360, 0,
				ob='AntCrackCam'))

		# Sizes up door with hands in front of his eyes

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addCondition(CondActionGE(Ant.L_ANIM, 140))
		s.addEvent("ShowDialogue", "... and this crack is too small, even for me.")
		s.addAction(ActAction('HP_AntConverse', 240, 255, Ant.L_ANIM, blendin=2.0))
		s.addAction(ActRemoveCamera('AntCrackCam'))
		s.addAction(ActSetCamera('AntCrackCamIn'))
		sloop = s.createSubStep("Loop")
		sloop.addCondition(CondActionGE(Ant.L_ANIM, 255, tap=True))
		sloop.addAction(ActAction('HP_AntConverse', 255, 283, Ant.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=2.0))

		# Pauses to consider

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "If only I had something stronger...")
		s.addAction(ActAction('HP_AntConverse', 290, 300, Ant.L_ANIM, blendin=1.0))
		s.addAction(ActRemoveCamera('AntCrackCamIn'))
		s.addAction(ActSetCamera('AntCloseCam'))
		sloop = s.createSubStep("Loop")
		sloop.addCondition(CondActionGE(Ant.L_ANIM, 300, tap=True))
		sloop.addAction(ActAction('HP_AntConverse', 300, 347, Ant.L_IDLE,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP, blendin=2.0))

		# Picks up mattock, and glares at the door

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addAction(ActActionStop(Ant.L_IDLE))
		s.addAction(ActAction('HP_AntConverse', 360, 407, Ant.L_ANIM, blendin=1.0))
		s.addEvent("ShowDialogue", "But I won't give up!")
		sgrab_pickR = s.createSubStep("Grab pick - right hand")
		sgrab_pickR.addCondition(CondActionGE(Ant.L_ANIM, 370.5, tap=True))
		sgrab_pickR.addAction(ActGeneric(self.pick_up))
		sgrab_pickL = s.createSubStep("Grab pick - left hand")
		sgrab_pickL.addAction(ActConstraintFade("Hand.L", "Copy Transforms",
				0.0, 1.0, 401.0, 403.0, Ant.L_ANIM))

		# Play the first bit of the digging animation

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addAction(ActAction('HP_AntConverse', 407, 437, Ant.L_ANIM, blendin=1.0))
		sKnock = s.createSubStep("Knock sound")
		sKnock.addCondition(CondActionGE(Ant.L_ANIM, 433.5, tap=True))
		sKnock.addAction(ActSound('//Sound/Knock.ogg', vol=1.0, pitchmin=0.7,
				pitchmax=0.76, emitter=self, maxdist=75.0))

		#
		# Loop back to start.
		#
		s = s.createTransition("Reset")
		s.addCondition(CondActionGE(Ant.L_ANIM, 437))
		s.addAction(ActResumeInput())
		s.addAction(ActRemoveCamera('AntCloseCam'))
		s.addAction(ActRemoveCamera('AntCrackCam'))
		s.addAction(ActRemoveCamera('AntCrackCamIn'))
		s.addAction(ActRemoveCamera('AntMidCam'))
		s.addAction(ActRemoveFocalPoint('Ant'))
		s.addAction(ActMusicStop())
		s.addAction(ActActionStop(Ant.L_IDLE))
		s.addTransition(self.rootState)

	def pick_up(self):
		''';)'''
		bxt.bmath.copy_transform(self.children['Ant_RH_Hook'], self.pick)
		self.pick.setParent(self.children['Ant_RH_Hook'])

	def drop_pick(self):
		'''Release the pick, and leave it stuck where it is.'''
		self.pick.removeParent()

	def get_focal_points(self):
		return [self.children['Ant_Face'], self]

def oversee(c):
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
	ant = bxt.types.mutate(ant)
	ant.playAction('AntActionTEST', 1, 120, 0)
