#
# Copyright 2013 Alex Fraser <alex@phatcore.com>
#

import logging

import bat.store
import bat.impulse

log = logging.getLogger(__name__)

DEFAULT_BINDINGS = {
	'Movement/up': [
		('keyboard', 'wkey'),
		('joydpad', 0, 1)],
	'Movement/right': [
		('keyboard', 'dkey'),
		('joydpad', 0, 2)],
	'Movement/down': [
		('keyboard', 'skey'),
		('joydpad', 0, 4)],
	'Movement/left': [
		('keyboard', 'akey'),
		('joydpad', 0, 8)],
	'Movement/xaxis': [
		('joystick', 0)],
	'Movement/yaxis': [
		('joystick', 1)],

	'CameraMovement/up': [
		('keyboard', 'uparrowkey')],
	'CameraMovement/right': [
		('keyboard', 'rightarrowkey')],
	'CameraMovement/down': [
		('keyboard', 'downarrowkey')],
	'CameraMovement/left': [
		('keyboard', 'leftarrowkey')],
	'CameraMovement/xaxis': [
		('joystick', 2),
		('mouselook', 0)],
	'CameraMovement/yaxis': [
		('joystick', 3),
		('mouselook', 1)],

	'Switch/next': [
		('keyboard', 'ekey'),
		('joybutton', 5),
		('mousebutton', 'wheeldownmouse')],
	'Switch/prev': [
		('keyboard', 'qkey'),
		('joybutton', 4),
		('mousebutton', 'wheelupmouse')],

	'1': [
		('keyboard', 'spacekey'),
		('keyboard', 'retkey'),
		('joybutton', 2),
		('mousebutton', 'leftmouse')],

	'2': [
		('keyboard', 'xkey'),
		('joybutton', 1),
		('mousebutton', 'rightmouse')],

	'CameraReset': [
		('keyboard', 'ckey'),
		('joybutton', 0),
		('mousebutton', 'middlemouse')],

	'Start': [
		('keyboard', 'esckey'),
		('joybutton', 9)]
	}

def create_controls():
	'''Create controllers for each of the inputs.'''

	ip = bat.impulse.Input()
	ip.clear_buttons()
	ip.clear_sequences()

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
	ip.add_sequence("udlr11", bat.event.Event("GiveAllShells"))
	ip.add_sequence("udlr22", bat.event.Event("LoseCurrentShell"))
	ip.add_sequence("uuddllrr", bat.event.Event("GiveFullHealth"))
	ip.add_sequence("udud22", bat.event.Event("TeleportCheat"))

def get_bindings():
	return bat.store.get('/opt/bindings', DEFAULT_BINDINGS)

def set_bindings(bindings):
	bat.store.put('/opt/bindings', bindings)

def reset_bindings():
	bat.store.put('/opt/bindings', DEFAULT_BINDINGS)

def apply_bindings():
	'''Bind keys and buttons to the interfaces.'''
	log.info('Applying user key bindings')
	ip = bat.impulse.Input()
	ip.unbind_all()
	add_bindings(get_bindings())

def add_bindings(bindings_map):
	log.info('Adding key bindings')
	ip = bat.impulse.Input()
	for path, sensors in bindings_map.items():
		for sensor_def in sensors:
			try:
				ip.unbind(*sensor_def)
			except:
				log.error('Failed to unbind input for %s', path, exc_info=1)
			try:
				ip.bind(path, *sensor_def)
			except:
				log.error('Failed to bind input for %s', path, exc_info=1)
