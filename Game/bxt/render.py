#
# Copyright 2009-2011 Alex Fraser <alex@phatcore.com>
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

from bge import render
import mathutils

RED   = mathutils.Vector([1.0, 0.0, 0.0, 1.0])
GREEN = mathutils.Vector([0.0, 1.0, 0.0, 1.0])
BLUE  = mathutils.Vector([0.0, 0.0, 1.0, 1.0])
YELLOW = RED + GREEN
YELLOW.w = 1.0
ORANGE = RED + (GREEN * 0.5)
ORANGE.w = 1.0
CYAN  = GREEN + BLUE
CYAN.w = 1.0
MAGENTA = RED + BLUE
MAGENTA.w = 1.0
WHITE = mathutils.Vector([1.0, 1.0, 1.0, 1.0])
BLACK = mathutils.Vector([0.0, 0.0, 0.0, 1.0])

_NAMED_COLOURS = {
	'red'   : '#ff0000',
	'green' : '#00ff00',
	'blue'  : '#0000ff',
	'black' : '#000000',
	'white' : '#ffffff',
	'darkred'   : '#331111',
	'darkgreen' : '#113311',
	'darkblue' : '#080833',
	
	'cargo' : '#36365a',
}

def draw_polyline(points, colour, cyclic=False):
	'''Like bge.render.drawLine, but operates on any number of points.'''

	for (a, b) in zip(points, points[1:]):
		render.drawLine(a, b, colour[0:3])
	if cyclic and len(points) > 2:
		render.drawLine(points[0], points[-1], colour[0:3])

def parse_colour(colstr):
	'''Parse a colour from a hexadecimal number; either "#rrggbb" or
	"#rrggbbaa". If no alpha is specified, a value of 1.0 will be used.

	Returns:
	A 4D vector compatible with object colour.
	'''

	if colstr[0] != '#':
		colstr = _NAMED_COLOURS[colstr]

	if colstr[0] != '#':
		raise ValueError('Hex colours need to start with a #')
	colstr = colstr[1:]
	if len(colstr) != 6 and len(colstr) != 8:
		raise ValueError('Hex colours need to be 6 or 8 characters long.')

	colour = BLACK.copy()

	components = [(x + y) for x,y in zip(colstr[0::2], colstr[1::2])]
	colour.x = int(components[0], 16)
	colour.y = int(components[1], 16)
	colour.z = int(components[2], 16)
	if len(components) == 4:
		colour.w = int(components[3], 16)
	else:
		colour.w = 255.0

	colour /= 255.0
	return colour
