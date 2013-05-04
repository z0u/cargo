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

import bge

import bat.sound

import Scripts.camera
import Scripts.director
import Scripts.lodtree
import Scripts.menu
import Scripts.ui
import Scripts.input

bat.sound.use_linear_clamped_falloff(dist_min=5, dist_max=50)

# Create singletons. Order should not be important.
Scripts.camera.AutoCamera()
Scripts.director.Director()
Scripts.lodtree.LODManager()
Scripts.menu.SessionManager()
Scripts.ui.HUDState()

Scripts.input.create_controls()
Scripts.input.apply_bindings()
