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

	# Acquire movement from a 2D directional pad.
	movement = bat.impulse.DPad2D("Movement", 'u', 'd', 'l', 'r')
	movement.up.sensors.append(bat.impulse.KeyboardSensor(bge.events.UPARROWKEY))
	movement.up.sensors.append(bat.impulse.KeyboardSensor(bge.events.WKEY))
	movement.up.sensors.append(bat.impulse.JoystickDpadSensor(0, 1))
	movement.right.sensors.append(bat.impulse.KeyboardSensor(bge.events.RIGHTARROWKEY))
	movement.right.sensors.append(bat.impulse.KeyboardSensor(bge.events.DKEY))
	movement.right.sensors.append(bat.impulse.JoystickDpadSensor(0, 2))
	movement.down.sensors.append(bat.impulse.KeyboardSensor(bge.events.DOWNARROWKEY))
	movement.down.sensors.append(bat.impulse.KeyboardSensor(bge.events.SKEY))
	movement.down.sensors.append(bat.impulse.JoystickDpadSensor(0, 4))
	movement.left.sensors.append(bat.impulse.KeyboardSensor(bge.events.LEFTARROWKEY))
	movement.left.sensors.append(bat.impulse.KeyboardSensor(bge.events.AKEY))
	movement.left.sensors.append(bat.impulse.JoystickDpadSensor(0, 8))
	movement.xaxes.append(bat.impulse.JoystickAxisSensor(0))
	movement.yaxes.append(bat.impulse.JoystickAxisSensor(1))

	camera = bat.impulse.DPad2D("CameraMovement", '^', '_', '<', '>')
	camera.up.sensors.append(bat.impulse.KeyboardSensor(bge.events.IKEY))
	camera.right.sensors.append(bat.impulse.KeyboardSensor(bge.events.LKEY))
	camera.down.sensors.append(bat.impulse.KeyboardSensor(bge.events.KKEY))
	camera.left.sensors.append(bat.impulse.KeyboardSensor(bge.events.JKEY))
	camera.xaxes.append(bat.impulse.JoystickAxisSensor(2))
	camera.yaxes.append(bat.impulse.JoystickAxisSensor(3))

	# The switch command can be "next" or "previous"; use a 1D pad to filter
	# out multiple conflicting button presses.
	switch = bat.impulse.DPad1D("Switch", 'n', 'p')
	switch.next.sensors.append(bat.impulse.KeyboardSensor(bge.events.EKEY))
	switch.next.sensors.append(bat.impulse.JoystickButtonSensor(5))
	switch.prev.sensors.append(bat.impulse.KeyboardSensor(bge.events.QKEY))
	switch.prev.sensors.append(bat.impulse.JoystickButtonSensor(4))
	#switch.axes.append(JoystickAxisSensor(0))

	btn1 = bat.impulse.Button("1", '1')
	btn1.sensors.append(bat.impulse.KeyboardSensor(bge.events.SPACEKEY))
	btn1.sensors.append(bat.impulse.KeyboardSensor(bge.events.ENTERKEY))
	btn1.sensors.append(bat.impulse.JoystickButtonSensor(2))

	btn2 = bat.impulse.Button("2", '2')
	btn2.sensors.append(bat.impulse.KeyboardSensor(bge.events.XKEY))
	btn2.sensors.append(bat.impulse.JoystickButtonSensor(1))

	btn_cam = bat.impulse.Button("CameraReset", 'c')
	btn_cam.sensors.append(bat.impulse.KeyboardSensor(bge.events.CKEY))
	btn_cam.sensors.append(bat.impulse.JoystickButtonSensor(0))

	btn_start = bat.impulse.Button("Start", 's')
	btn_start.sensors.append(bat.impulse.KeyboardSensor(bge.events.ESCKEY))
	btn_start.sensors.append(bat.impulse.JoystickButtonSensor(9))

	ip = bat.impulse.Input()
	ip.clear_buttons()
	ip.add_button(movement)
	ip.add_button(camera)
	ip.add_button(switch)
	ip.add_button(btn1)
	ip.add_button(btn2)
	ip.add_button(btn_cam)
	ip.add_button(btn_start)

	# Cheats!
	bat.impulse.Input().add_sequence("udlr12", bat.event.Event("GiveAllShells"))
	bat.impulse.Input().add_sequence("udlr21", bat.event.Event("LoseCurrentShell"))
	bat.impulse.Input().add_sequence("uuddllrr", bat.event.Event("GiveFullHealth"))
	bat.impulse.Input().add_sequence("udud22", bat.event.Event("TeleportCheat"))

configure_controls()
