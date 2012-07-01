#
# Copyright 2009-2010 Alex Fraser <alex@phatcore.com>
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

import bxt

from . import camera
from . import director
from . import lodtree
from . import menu
from . import ui
from . import impulse

# Create singletons. Order should not be important.
camera.AutoCamera()
camera.MainGoalManager()
director.Director()
lodtree.LODManager()
menu.SessionManager()
ui.HUDState()

# Some basic configuration
bxt.sound.set_volume("Mush_Spore", 0.15)
bxt.sound.set_volume("FlowerPowSound", 0.2)
bxt.sound.set_volume("Wheel", 0.5)
bxt.sound.set_volume("Shell", 8.0)
bxt.sound.set_volume("BottleCap", 1.0)
