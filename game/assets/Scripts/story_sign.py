#
# Copyright 2013 Alex Fraser <alex@phatcore.com>
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
import bat.utils
import bat.bmath
import bat.story

import Scripts.story

class Sign(bat.story.Chapter, bge.types.KX_GameObject):

    _prefix = ''

    S_INIT = 1
    S_IDLE = 2
    S_ACTIVE = 3

    def __init__(self, old_owner):
        bat.story.Chapter.__init__(self, old_owner)
        self.engaged = False
        self.create_state_graph()

    @bat.bats.expose
    @bat.utils.controller_cls
    def approach(self, c):
        s = c.sensors[0]
        if not s.positive:
            print("negative")
            self.engaged = False
            return
        player = s.hitObject
        relpos = bat.bmath.to_local(c.owner, player.worldPosition)
        if relpos.y > 0:
            print("not in front", relpos)
            self.engaged = False
            return
        player_y_axis = player.getAxisVect((0, 1, 0))
        own_y_axis = c.owner.getAxisVect((0, 1, 0))
        if player_y_axis.dot(own_y_axis) < 0:
            print("not facing", player_y_axis, own_y_axis, player_y_axis.dot(own_y_axis))
            self.engaged = False
            return

        print("engaged")
        self.engaged = True
        self.add_state(Sign.S_ACTIVE)

    def create_state_graph(self):
        s = self.rootState.create_successor("Init")

        s = s.create_successor("Engage!")
        s.add_condition(bat.story.CondAttrEq('engaged', True))

        s_start, s_end = self.create_sign_conversation()
        s.add_successor(s_start)

        s = s.create_successor("Reset")
        s.add_predecessor(s_end)
        s.add_condition(bat.story.CondAttrEq('engaged', False))
        s.add_successor(self.rootState)
        # Go back to idle state.
        s.add_action(bat.story.ActStateChange('REM', Sign.S_ACTIVE))


class SignMainCargoHouse(Sign):
    def create_sign_conversation(self):
        s = s_start = bat.story.State()
        s.add_event("ShowDialogue", "Cargo's House")

        s = s.create_successor()
        s.add_condition(bat.story.CondEvent("DialogueDismissed", self))

        s_end = s.create_successor()
        return s_start, s_end


class SignMainCargoNotes(Sign):
    def create_sign_conversation(self):
        s = s_start = bat.story.State()
        s.add_event("ShowDialogue", "Cargo's notes!")

        s = s.create_successor()
        s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
        s.add_event("ShowDialogue", "1/5: Use the mouse or second joystick to look around.")

        s = s.create_successor()
        s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
        s.add_event("ShowDialogue", "2/5: Press the camera button \[btnCameraReset] to reset the camera.")

        s = s.create_successor()
        s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
        s.add_event("ShowDialogue", "3/5: Press button 1 \[btn1] to go into your shell and roll around.")

        s = s.create_successor()
        s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
        s.add_event("ShowDialogue", "4/5: Don't touch the salt.")

        s = s.create_successor()
        s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
        s.add_event("ShowDialogue", "5/5: Eat clovers if you get sick, or have a bath at home.")

        s = s.create_successor()
        s.add_condition(bat.story.CondEvent("DialogueDismissed", self))

        s_end = s.create_successor()
        return s_start, s_end


class SignMainLighthouse(Sign):
    def create_sign_conversation(self):
        s = s_start = bat.story.State()
        s.add_event("ShowDialogue", "Welcome to the Lighthouse!")

        s = s.create_successor()
        s.add_condition(bat.story.CondEvent("DialogueDismissed", self))

        s_end = s.create_successor()
        return s_start, s_end


class SignMainSpider(Sign):
    def create_sign_conversation(self):
        s = s_start = bat.story.State()
        s.add_event("ShowDialogue", "Slugs and snails beware! The island you see before you is Spider Isle.")
        s.add_action(Scripts.story.ActSetFocalPoint("LaunchRamp"))
        s.add_action(Scripts.story.ActSetCamera('Sign_MainSpider_Cam1'))

        s = s.create_successor()
        s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
        s.add_event("ShowDialogue", "Apart from the spider, the island is covered with salt. And it is surrounded by poisonous muck!")

        s = s.create_successor()
        s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
        s.add_event("ShowDialogue", "For safe passage, approach the island from the beach to your right. You do have a boat, don't you?")
        s.add_action(Scripts.story.ActSetFocalPoint("Beach"))
        s.add_action(Scripts.story.ActSetCamera('Sign_MainSpider_Cam2'))

        s = s.create_successor()
        s.add_condition(bat.story.CondEvent("DialogueDismissed", self))
        s.add_action(Scripts.story.ActRemoveFocalPoint("LaunchRamp"))
        s.add_action(Scripts.story.ActRemoveFocalPoint("Beach"))
        s.add_action(Scripts.story.ActRemoveCamera('Sign_MainSpider_Cam1'))
        s.add_action(Scripts.story.ActRemoveCamera('Sign_MainSpider_Cam2'))

        s_end = s.create_successor()
        return s_start, s_end
