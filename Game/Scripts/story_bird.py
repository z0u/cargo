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
	if not "Bird" in scene.objectsInactive:
		try:
			bge.logic.LibLoad('//Bird_loader.blend', 'Scene', load_actions=True)
		except ValueError as e:
			print('Warning: could not load bird:', e)

	return bxt.types.add_and_mutate_object(scene, "Bird", "Bird")

class Bird(Chapter, bxt.types.BX_GameObject, bge.types.BL_ArmatureObject):
	def __init__(self, old_owner):
		Chapter.__init__(self, old_owner)
		# if at bottle...
		if True:
			bxt.types.WeakEvent("StartLoading", self).send()
			self.pick_up_shell()
			self.create_bottle_state_graph()

	def create_bottle_state_graph(self):
		def steal_shell():
			inventory.Shells().discard("Shell")
			bxt.types.Event('ShellChanged', 'new').send()

		s = self.rootState.createTransition("Init")
		s.addAction(ActSuspendInput())
		s.addAction(ActSetCamera('B_BirdIntroCam'))
		s.addAction(ActSetFocalPoint('Bi_FootHook.L'))

		s = s.createTransition()
		s.addCondition(CondWait(0.5))
		s.addWeakEvent("FinishLoading", self)
		s.addAction(ActAction("B_BirdCloseCamAction", 1, 96, 0,
			ob="B_BirdIntroCam"))

		s = s.createTransition()
		s.addCondition(CondWait(2.5))
		s.addAction(ActSetFocalPoint('Bi_Face'))
		s.addAction(ActRemoveFocalPoint('Bi_FootHook.L'))
		s.addEvent("ShowDialogue", "Ooh, look at this lovely red thing!")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", ("It's so shiny. It will really brighten up my nest!",
				("Excuse me...", "Oi, that's my \[shell]!")))

		s = s.createTransition()
		s.addCondition(CondWait(1))
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addAction(ActSetCamera('B_DoorCamera'))
		s.addAction(ActRemoveCamera('B_BirdIntroCam'))

		s = s.createTransition()
		s.addCondition(CondWait(1))
		s.addEvent("ShowDialogue", "Eh? You say it's yours?")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "Couldn't be; it was just lying here! Finders keepers, I always say.")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "Tell you what, I'll make you a deal.")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", ("If you can bring me 3 other shiny red things, I'll give this one to you.",
				("That's not fair!", "I need it to do my job!")))

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "Now now, you can't just go taking things from other people.")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "If you want this \[shell], bring 3 red things to my nest at the top of the tree.")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addEvent("ShowDialogue", "Toodles!")

		s = s.createTransition()
		s.addCondition(CondEvent("DialogueDismissed"))
		s.addAction(ActGeneric(steal_shell))

		#
		# Return to game. Note that this actually destroys the bird.
		#
		s = s.createTransition("Return to game")
		s.addAction(ActResumeInput())
		s.addAction(ActRemoveCamera('B_BirdIntroCam'))
		s.addAction(ActRemoveCamera('B_DoorCamera'))
		s.addAction(ActRemoveFocalPoint('Bi_Face'))
		s.addAction(ActRemoveFocalPoint('Bi_FootHook.L'))
		s.addAction(ActDestroy())

	def pick_up(self, ob, left=True):
		attach_point = self.children["Bi_FootHook.L"]

		referential = ob
		for child in ob.children:
			if child.name.startswith("GraspHook"):
				referential = child
				break

		# Similar to Snail._stow_shell
		bxt.bmath.set_rel_orn(ob, attach_point, referential)
		bxt.bmath.set_rel_pos(ob, attach_point, referential)
		ob.setParent(attach_point)

	def pick_up_shell(self):
		try:
			shell = self.scene.objects["Shell"]
		except KeyError:
			shell = shells.factory("Shell")
		shell.localScale = (0.75, 0.75, 0.75)
		self.pick_up(shell)
		try:
			shell.on_grasped()
		except AttributeError as e:
			print("Warning:", e)
