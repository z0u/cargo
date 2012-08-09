#
# Copyright 2012, Alex Fraser <alex@phatcore.com>
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


import bxt

def dry_leaf(c):
	files = (
		'//Sound/cc-by/Crunch1.ogg',
		'//Sound/cc-by/Crunch2.ogg',
		'//Sound/cc-by/Crunch3.ogg')
	bxt.sound.play_random_sample(files, ob=c.owner)

def dandelion(c):
	files = (
		'//Sound/cc-by/Swosh1.ogg',
		'//Sound/cc-by/Swosh2.ogg')
	bxt.sound.play_random_sample(files, ob=c.owner)

def ripple(c):
	files = (
		'//Sound/Puddle1.ogg',
		'//Sound/Puddle2.ogg',
		'//Sound/Puddle3.ogg',
		'//Sound/Puddle4.ogg')
	bxt.sound.play_random_sample(files, volume=0.5, ob=c.owner)