#
# Copyright 2012, Alex Fraser <alex@phatcore.com>
# Copyright 2012, Ben Sturmfels <ben@sturm.com.au>
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

#
# This file contains code to play miscellaneous sounds that don't deserve their
# own module.
#

import bge

import bat.sound
import bat.bats
import bat.bmath

def dry_leaf_touched(c):
    sample = bat.sound.Sample(
            '//Sound/cc-by/Crunch1.ogg',
            '//Sound/cc-by/Crunch2.ogg',
            '//Sound/cc-by/Crunch3.ogg')
    sample.add_effect(bat.sound.Localise(c.owner))
    sample.play()

def dandelion_touched(c):
    sample = bat.sound.Sample(
            '//Sound/cc-by/Swosh1.ogg',
            '//Sound/cc-by/Swosh2.ogg')
    sample.volume = 0.5
    sample.add_effect(bat.sound.Localise(c.owner))
    sample.play()

def ripple(c):
    sample = bat.sound.Sample(
            '//Sound/Puddle1.ogg',
            '//Sound/Puddle2.ogg',
            '//Sound/Puddle3.ogg',
            '//Sound/Puddle4.ogg')
    sample.volume = 0.5
    sample.add_effect(bat.sound.Localise(c.owner))
    sample.play()


class SleepEmitter(bat.bats.BX_GameObject, bge.types.KX_GameObject):
    _prefix = 'S_'

    DELAY = 60
    LIFETIME = 240

    def __init__(self, old_owner):
        self.countdown = 0

    @bat.bats.expose
    def pulse(self):
        self.countdown -= 1
        if self.countdown <= 0:
            self.countdown = SleepEmitter.DELAY
            instance = self.scene.addObject('SleepCharBase', 'SleepCharBase', SleepEmitter.LIFETIME)
            bat.bmath.copy_transform(self, instance)
            instance.localScale = self.worldScale
