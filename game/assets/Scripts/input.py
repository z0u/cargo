#
# Copyright 2013 Alex Fraser <alex@phatcore.com>
#

import collections
import logging
import re

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

    # Mouse sensitivity
    bat.impulse.MouseLookSensor.multiplier = 15

    # Acquire movement from a 2D directional pad.
    ip.add_controller(bat.impulse.DPad2D("Movement", 'u', 'd', 'l', 'r'))
    ip.add_controller(bat.impulse.DPad2D("CameraMovement", '^', '_', '<', '>'))
    # The switch command can be "next" or "previous"; use a 1D pad to filter
    # out multiple conflicting button presses.
    ip.add_controller(bat.impulse.DPad1D("Switch", 'n', 'p'))
    ip.add_controller(bat.impulse.Button("1", '1'))
    ip.add_controller(bat.impulse.Button("2", '2'))
    ip.add_controller(bat.impulse.Button("CameraReset", 'c'))
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


def gather_button_bindings(name, all_bindings):
    bindings = []
    for k in all_bindings.keys():
        if k == name or k.startswith(name + '/'):
            bindings.extend(all_bindings[k])
    return format_bindings(bindings)


def format_bindings(bindings):
    # group
    binding_groups = collections.defaultdict(list)
    for b in bindings:
        binding_groups[b[0]].append(b[1:])

    def keyboard(bs):
#             if len(bs) == 1:
#                 yield 'Key'
#             else:
#                 yield 'Keys'
        for b in bs:
            if b[0] == 'retkey':
                yield 'return'
            elif b[0] == 'esckey':
                yield 'escape'
            else:
                yield re.match(r'(.*?)(arrow)?key', b[0]).group(1)

    def mousebutton(bs):
        yield 'mouse'
        for b in bs:
            yield re.match(r'(.*)mouse', b[0]).group(1)

    def mouselook(bs):
        yield 'mouse'
        for b in bs:
            yield str(b[0] + 1)

    def joydpad(bs):
        yield 'joypad'
        dgroups = collections.defaultdict(int)
        for hatindex, flag in bs:
            dgroups[hatindex + 1] |= flag
        for hatindex, flag in dgroups.items():
            if flag == 1 | 2 | 4 | 8:
                yield str(hatindex)
                continue
            hflags = []
            if flag & 1:
                hflags.append("up")
            if flag & 4:
                hflags.append("down")
            if flag & 2:
                hflags.append("right")
            if flag & 8:
                hflags.append("left")
            yield "%d(%s)" % (hatindex, ' '.join(hflags))

    def joybutton(bs):
        if len(bs) == 1:
            yield 'button'
        else:
            yield 'buttons'
        for b in bs:
            yield str(b[0] + 1)

    def joystick(bs):
        if len(bs) == 1:
            yield 'joystick'
        else:
            yield 'joystick'
        for b in bs:
            yield str(b[0] + 1)

    sensor_types = {
        'keyboard': (keyboard, 0),
        'mousebutton': (mousebutton, 1),
        'mouselook': (mouselook, 2),
        'joydpad': (joydpad, 3),
        'joybutton': (joybutton, 4),
        'joystick': (joystick, 5),
        }

    def group_key(group):
        return sensor_types[group[0]][1]

    binding_groups = list(binding_groups.items())
    binding_groups.sort(key=group_key)
    human_bindings = []
    for k, bs in binding_groups:
        fn, _ = sensor_types[k]
        bs.sort()
        bs = fn(bs)
        human_bindings.append(' '.join(bs))

    return ', '.join(human_bindings)
