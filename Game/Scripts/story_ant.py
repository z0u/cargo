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
		#bxt.types.WeakEvent("StartLoading", self).send()
		self.create_state_graph()

	def create_state_graph(self):
		s = self.rootState.createTransition("Init")
		s.addAction(ActAction('Ant_Digging1', 1, 42, Ant.L_ANIM,
				play_mode=bge.logic.KX_ACTION_MODE_LOOP))

		sKnock = s.createSubStep("Knock sound")
		sKnock.addCondition(CondActionGE(Ant.L_ANIM, 14.5, tap=True))
		sKnock.addAction(ActSound('//Sound/Knock.ogg', vol=0.6, pitchmin=0.7,
				pitchmax=0.76, emitter=self, maxdist=50.0))

		s = s.createTransition("Talk")
		s.addCondition(CondEvent("ApproachAnts"))
		s.addAction(ActSuspendInput())
		s.addWeakEvent("StartLoading", self)

		s = s.createTransition()
		s.addCondition(CondWait(1))
		s.addWeakEvent("FinishLoading", self)
		s.addAction(ActSetCamera('AntMidCam'))
		s.addAction(ActSetFocalPoint("Ant"))
		s.addEvent("TeleportSnail", "HP_SnailTalkPos")

		s.addEvent("ShowDialogue", "Ho there, Cargo!")
		s.addAction(ActAction('Ant_Digging1', 1, 1, Ant.L_ANIM)) # stop

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))

		#
		# Loop back to start.
		#
		s = s.createTransition("Reset")
		s.addAction(ActResumeInput())
		s.addAction(ActRemoveCamera('AntMidCam'))
		s.addAction(ActRemoveFocalPoint("Ant"))
		s.addTransition(self.rootState)

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
