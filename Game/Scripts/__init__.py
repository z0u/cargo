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

import bat.impulse
import bat.sound

import Scripts.camera
import Scripts.director
import Scripts.lodtree
import Scripts.menu
import Scripts.ui

bat.sound.use_linear_clamped_falloff(dist_min=5, dist_max=50)

# Create singletons. Order should not be important.
Scripts.camera.AutoCamera()
Scripts.director.Director()
Scripts.lodtree.LODManager()
Scripts.menu.SessionManager()
Scripts.ui.HUDState()

def configure_controls():
	'''Bind keys and buttons to the interfaces.'''

	[
		{
			"name": "Movement",
			"type": "DPad2D",
			"sensors": [
				{
					"name": "up",
					"char": "u",
					"bindings": [
						{
							"cls": "KeyboardSensor",
							"options": ['uparrowkey']
						},
						{
							"cls": "KeyboardSensor",
							"options": ['wkey']
						},
						{
							"cls": "JoystickDpadSensor",
							"options": [0, 1]
						},
						]
				}
				]
		}
	]

	ip = bat.impulse.Input()
	ip.clear_buttons()
	bat.impulse.mouse_sensitivity = 15

	# Acquire movement from a 2D directional pad.
	ip.add_controller(bat.impulse.DPad2D("Movement", 'u', 'd', 'l', 'r'))
	ip.add_controller(bat.impulse.DPad2D("CameraMovement", '^', '_', '<', '>'))
	# The switch command can be "next" or "previous"; use a 1D pad to filter
	# out multiple conflicting button presses.
	ip.add_controller(bat.impulse.DPad1D("Switch", 'n', 'p'))
	ip.add_controller(bat.impulse.Button("1", '1'))
	ip.add_controller(bat.impulse.Button("2", '2'))
	ip.add_controller(bat.impulse.Button("CameraReset", 'c'))
	ip.add_controller(bat.impulse.Button("2", '2'))
	ip.add_controller(bat.impulse.Button("Start", 's'))
	# Cheats!
	ip.add_sequence("udlr12", bat.event.Event("GiveAllShells"))
	ip.add_sequence("udlr21", bat.event.Event("LoseCurrentShell"))
	ip.add_sequence("uuddllrr", bat.event.Event("GiveFullHealth"))
	ip.add_sequence("udud22", bat.event.Event("TeleportCheat"))

	ip.bind('Movement/up', 'keyboard', 'uparrowkey')
	ip.bind('Movement/up', 'keyboard', 'wkey')
	ip.bind('Movement/up', 'joydpad', 0, 1)
	ip.bind('Movement/right', 'keyboard', 'rightarrowkey')
	ip.bind('Movement/right', 'keyboard', 'dkey')
	ip.bind('Movement/right', 'joydpad', 0, 2)
	ip.bind('Movement/down', 'keyboard', 'downarrowkey')
	ip.bind('Movement/down', 'keyboard', 'skey')
	ip.bind('Movement/down', 'joydpad', 0, 4)
	ip.bind('Movement/left', 'keyboard', 'leftarrowkey')
	ip.bind('Movement/left', 'keyboard', 'akey')
	ip.bind('Movement/left', 'joydpad', 0, 8)
	ip.bind('Movement/xaxis', 'joystick', 0)
	ip.bind('Movement/yaxis', 'joystick', 1)

	ip.bind('CameraMovement/up', 'keyboard', 'ikey')
	ip.bind('CameraMovement/right', 'keyboard', 'rightarrowkey')
	ip.bind('CameraMovement/down', 'keyboard', 'downarrowkey')
	ip.bind('CameraMovement/left', 'keyboard', 'leftarrowkey')
	ip.bind('CameraMovement/xaxis', 'joystick', 2)
	ip.bind('CameraMovement/xaxis', 'mouselook', 0)
	ip.bind('CameraMovement/yaxis', 'joystick', 3)
	ip.bind('CameraMovement/yaxis', 'mouselook', 1)

	ip.bind('Switch/next', 'keyboard', 'ekey')
	ip.bind('Switch/next', 'joybutton', 5)
	ip.bind('Switch/next', 'mousebutton', 'wheeldownmouse')
	ip.bind('Switch/prev', 'keyboard', 'qkey')
	ip.bind('Switch/prev', 'joybutton', 4)
	ip.bind('Switch/prev', 'mousebutton', 'wheelupmouse')

	ip.bind('1', 'keyboard', 'spacekey')
	ip.bind('1', 'keyboard', 'enterkey')
	ip.bind('1', 'joybutton', 2)
	ip.bind('1', 'mousebutton', 'leftmouse')

	ip.bind('2', 'keyboard', 'xkey')
	ip.bind('2', 'joybutton', 1)
	ip.bind('2', 'mousebutton', 'rightmouse')

	ip.bind('CameraReset', 'keyboard', 'ckey')
	ip.bind('CameraReset', 'joybutton', 0)
	ip.bind('CameraReset', 'mousebutton', 'middlemouse')

	ip.bind('Start', 'keyboard', 'esckey')
	ip.bind('Start', 'joybutton', 9)


configure_controls()
