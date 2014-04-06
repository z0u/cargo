#
# Copyright 2009-2012 Alex Fraser <alex@phatcore.com>
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

import logging
import os
import platform
import time
import webbrowser

import bge
import bgl

import bat.bats
import bat.event
import bat.store
import bat.impulse

import Scripts.credits
import Scripts.gui
import Scripts.input

CREDITS = [(title, ', '.join(details)) for (title, details) in Scripts.credits.CREDITS]
CREDITS += [
    ("Licence", "Cargo is free software: you can redistribute it and/or modify "
            "it under the terms of the GNU General Public License as published by "
            "the Free Software Foundation, either version 3 of the License, or "
            "(at your option) any later version."),
    ("Licence (cont.)", "Cargo is distributed in the hope that it will be useful, "
            "but WITHOUT ANY WARRANTY; without even the implied warranty of "
            "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the "
            "GNU General Public License for more details. "),
    ("Licence (cont.)", "You should have received a copy of the GNU General Public License "
            "along with Cargo.  If not, see http://www.gnu.org/licenses/."),
    ("Licence (cont.)", "In addition, the artwork (models, animations, textures, "
            "music and sound effects) is licensed under the Creative Commons "
            "Attribution-ShareAlike 3.0 Australia License. To view a copy of "
            "this license, visit http://creativecommons.org/licenses/by-sa/3.0/au/"),]

STORY_SUMMARIES = {
    # 95 characters is probably about as many as will currently fit on the save
    # game page.
    'newGame':
            "Start a new game.",
    'wormMissionStarted':
            "I have a letter \[envelope] to deliver to the lighthouse keeper.",
    'lkMissionStarted':
            "The lighthouse keeper wants some black bean sauce from the Sauce Bar.",
    'birdTookShell':
            "A bird has taken my shell \[shell] and wants three shiny red things in exchange.",
    'slugBottleCapConv1':
            "I'm off to a small island in search of a bright red bottle cap \[bottlecap].",
    'gotBottleCap':
            "I found a bottle cap \[bottlecap], but still need two more shiny red things.",
    'spiderWelcome1':
            "The spider says I can have the wheel \[wheel], if only I can reach it.",
    'gotNut':
            "I found a heavy nut \[nut]. That must be useful for something...",
    'gotWheel':
            "The spider gave me the wheel \[wheel]. It's very strong and can break things.",
    'treeDoorBroken':
            "I've broken into the tree and am following the ant inside.",
    'AntStranded':
            "The ant needs my help to get out of the honey.",
    'gotThimble':
            "I found a third shiny thing! It's a thimble \[thimble] that's impervious to sharp objects.",
    }

# Some systems are buggy with the depth of field filter. Systems matching an
# item in this blacklist will have DoF disabled by default.
DOF_BLACKLIST = [
    ('windows', 'intel'),
    #('linux', 'ati'),
    ]

class SessionManager(bat.bats.BX_GameObject, bge.types.KX_GameObject):
    '''Responds to some high-level messages.'''

    MENU_KEY_BINDINGS = {
        'Movement/up': [
            ('keyboard', 'uparrowkey')],
        'Movement/right': [
            ('keyboard', 'rightarrowkey')],
        'Movement/down': [
            ('keyboard', 'downarrowkey')],
        'Movement/left': [
            ('keyboard', 'leftarrowkey')],

        '1': [
            ('keyboard', 'retkey'),
            ('mousebutton', 'leftmouse')],

        '2': [
            ('mousebutton', 'rightmouse')],

        'Start': [
            ('keyboard', 'esckey')]
        }

    def __init__(self, old_owner):
        bat.event.EventBus().add_listener(self)
        bat.event.Event('KeyBindingsChanged').send(1)

    def on_event(self, event):
        if event.message == 'showSavedGameDetails':
            # The session ID indicates which saved game is being used.
            bat.store.set_session_id(event.body)
            if len(bat.store.get('/game/name', '')) == 0:
                bat.event.Event('pushScreen', 'NameScreen').send()
            else:
                bat.event.Event('pushScreen', 'LoadDetailsScreen').send()

        elif event.message == 'startGame':
            # Show the loading screen and send another message to start the game
            # after the loading screen has shown.
            cbEvent = bat.event.Event('MenuLoadLevel')
            bat.event.Event('ShowLoadingScreen', (True, cbEvent, True)).send()

        elif event.message == 'MenuLoadLevel':
            # Load the level indicated in the save game. This is called after
            # the loading screen has been shown.
            level = bat.store.get('/game/levelFile', '//Outdoors.blend')
            bat.store.save()
            bge.logic.startGame(level)

        elif event.message == 'deleteGame':
            # Remove all stored items that match the current path.
            for key in bat.store.search('/game/'):
                bat.store.unset(key)
            bat.event.Event('setScreen', 'LoadingScreen').send()

        elif event.message == 'quit':
            cbEvent = bat.event.Event('reallyQuit')
            bat.event.Event('ShowLoadingScreen', (True, cbEvent)).send()

        elif event.message == 'reallyQuit':
            bge.logic.endGame()

        elif event.message == 'OpenWeb':
            if event.body == 'home':
                webbrowser.open('http://cargo.smidginsoftware.com', autoraise=True)
            elif event.body == 'gpl':
                webbrowser.open('http://www.gnu.org/licenses/gpl.html', autoraise=True)
            elif event.body == 'cc':
                webbrowser.open('http://creativecommons.org/licenses/by-sa/3.0/au/', autoraise=True)
            else:
                return
            bat.event.Event('confirmation', "The web page has been opened in your browser.::::").send()

        elif event.message == 'KeyBindingsChanged':
            self.set_up_key_bindings()

    def set_up_key_bindings(self):
        # Apply user-defined keybindings
        Scripts.input.apply_bindings()
        # Override key bindings for this level: the prevents the menu from
        # becoming unusable due to a broken key map.
        Scripts.input.add_bindings(SessionManager.MENU_KEY_BINDINGS)


class MenuController(Scripts.gui.UiController):

    log = logging.getLogger(__name__ + '.MenuController')

    def __init__(self, old_owner):
        Scripts.gui.UiController.__init__(self, old_owner)

        bat.event.EventBus().add_listener(self)

        self.update_version_text()

        # TODO: for some reason setScreen seems to interfere with the menu. If
        # send delay is set to 2, it might not work... but 200 does! Weird.
        bat.event.Event('setScreen', 'LoadingScreen').send(0)
#         bat.event.Event('setScreen', 'Controls_Actions').send(0)
        bat.event.Event('GameModeChanged', 'Menu').send()

        # Menu music. Note that the fade rate is set higher than the default, so
        # that the music completely fades out before the game starts.
        bat.sound.Jukebox().play_files('menu', self, 1,
                '//Sound/Music/01-TheStart_loop1.ogg',
                '//Sound/Music/01-TheStart_loop2.ogg',
                introfile='//Sound/Music/01-TheStart_intro.ogg',
                fade_in_rate=1, volume=0.6)

    def on_event(self, evt):
        Scripts.gui.UiController.on_event(self, evt)
        if evt.message in {'startGame', 'quit'}:
            bat.sound.Jukebox().stop_all(fade_rate=0.05)

    def get_default_widget(self, screen_name):
        if screen_name == 'LoadingScreen':
            gamenum = bat.store.get_session_id()
            for ob in self.scene.objects:
                if ob.name == 'SaveButton_T' and ob['onClickBody'] == gamenum:
                    return ob
        elif screen_name == 'CreditsScreen':
            return self.scene.objects['Btn_Crd_Load']
        elif screen_name == 'OptionsScreen':
            return self.scene.objects['Btn_ControlConfig']
#        elif screen_name == 'Controls_Actions':
#            return self.scene.objects['Btn_CC_ActionsTab']
#        elif screen_name == 'Controls_Movement':
#            return self.scene.objects['Btn_CC_MovementTab']
#        elif screen_name == 'Controls_Camera':
#            return self.scene.objects['Btn_CC_CameraTab']
        elif screen_name == 'VideoOptions':
            return self.scene.objects['Btn_ReturnVC']
        elif screen_name == 'VideoConfirm':
            return self.scene.objects['Btn_VC_No']
        elif screen_name == 'LoadDetailsScreen':
            return self.scene.objects['Btn_StartGame']
        elif screen_name == 'ConfirmationDialogue':
            return self.scene.objects['Btn_Cancel']
        elif screen_name == 'NameScreen':
            for ob in self.scene.objects:
                if ob.name == 'CharButton_T' and ob._orig_name == 'Btn_Char.FIRST':
                    return ob

        return None

    def update_version_text(self):
        ob = self.scene.objects['VersionText']
        currentdir = bge.logic.expandPath('//')
        version = '???'
        try:
            with open(os.path.join(currentdir, '../VERSION.txt'), 'rU') as f:
                version = f.read(128)
        except IOError:
            try:
                with open(os.path.join(currentdir, '../../VERSION.txt'), 'rU') as f:
                    version = f.read(128)
            except IOError:
                MenuController.log.warn('Could not read VERSION.txt')
                version = '???'

        ob['Content'] = '%s' % version

################
# Widget classes
################

class Camera(bat.bats.BX_GameObject, bge.types.KX_Camera):
    '''A camera that adjusts its position depending on which screen is
    visible.'''

    _prefix = 'cam_'

    FRAME_MAP = {'OptionsScreen': 1.0,
                 'LoadingScreen': 9.0,
                 'CreditsScreen': 17.0}
    '''A simple mapping is used here. The camera will interpolate between the
    nominated frame numbers when the screen changes. Set the animation using
    an f-curve.'''

    FRAME_RATE = 25.0 / bge.logic.getLogicTicRate()

    def __init__(self, old_owner):
        bat.event.EventBus().add_listener(self)
        bat.event.EventBus().replay_last(self, 'showScreen')

    def on_event(self, event):
        if event.message == 'showScreen' and event.body in Camera.FRAME_MAP:
            self['targetFrame'] = Camera.FRAME_MAP[event.body]

    @bat.bats.expose
    def update(self):
        '''Update the camera animation frame. Should be called once per frame
        when targetFrame != frame.'''

        targetFrame = self['targetFrame']
        frame = self['frame']
        if frame < targetFrame:
            frame = min(frame + Camera.FRAME_RATE, targetFrame)
        else:
            frame = max(frame - Camera.FRAME_RATE, targetFrame)
        self['frame'] = frame

class SaveButton(Scripts.gui.Button):
    def __init__(self, old_owner):
        bat.bats.mutate(self.children['IDCanvas'])
        Scripts.gui.Button.__init__(self, old_owner)

    def updateVisibility(self, visible):
        super(SaveButton, self).updateVisibility(visible)
        self.children['IDCanvas'].setVisible(visible, True)
        if not visible:
            return

        name = bat.store.get('/game/name', '', session=self['onClickBody'])
        self.children['IDCanvas'].set_text(name)

class Checkbox(Scripts.gui.Button):
    def __init__(self, old_owner):
        self.checked = False
        Scripts.gui.Button.__init__(self, old_owner)
        if 'dataBinding' in self:
            checked = bat.store.get(self['dataBinding'], self['dataDefault'])
            self.checked = checked

        # Create a clickable box around the text.
        canvas = self.childrenRecursive['CheckBoxCanvas']
        canvas = bat.bats.mutate(canvas)
        canvas['Content'] = self['label']
        canvas['colour'] = self['colour']
        canvas.render()
        hitbox = self.childrenRecursive['Checkbox_hitbox']
        hitbox.localScale.x = canvas.textwidth * canvas.localScale.x
        hitbox.localScale.y = canvas.textheight * canvas.localScale.y

    @property
    def checked(self):
        return self._checked
    @checked.setter
    def checked(self, value):
        self._checked = value
        self.updateCheckFace()

    def click(self):
        self.checked = not self.checked
        if 'dataBinding' in self:
            bat.store.put(self['dataBinding'], self.checked)
        super(Checkbox, self).click()

    def updateVisibility(self, visible):
        super(Checkbox, self).updateVisibility(visible)
        self.updateCheckFace()

    def updateCheckFace(self):
        if self.visible:
            self.childrenRecursive['CheckOff'].setVisible(not self.checked, True)
            self.childrenRecursive['CheckOn'].setVisible(self.checked, True)
        else:
            self.childrenRecursive['CheckOff'].setVisible(False, True)
            self.childrenRecursive['CheckOn'].setVisible(False, True)

    def updateTargetFrame(self):
        start, end = self.get_anim_range(self.children['CB_animref'])
        Scripts.gui.Button.updateTargetFrame(self, self.children['CB_animref'])
        self.childrenRecursive['CheckOff'].playAction("Button_OnlyColour", start, end)
        self.childrenRecursive['CheckOn'].playAction("Button_OnlyColour", start, end)

class ConfirmationPage(Scripts.gui.Widget):
    def __init__(self, old_owner):
        self.cancelbtn = bat.bats.mutate(self.children['Btn_Cancel'])
        self.confirmbtn = bat.bats.mutate(self.children['Btn_Confirm'])
        self.lastScreen = ''
        self.currentScreen = ''
        self.onConfirm = ''
        self.onConfirmBody = ''
        Scripts.gui.Widget.__init__(self, old_owner)
        self.setSensitive(False)

    def on_event(self, event):
        super(ConfirmationPage, self).on_event(event)
        if event.message == 'showScreen':
            # Store the last screen name so it can be restored later.
            if self.currentScreen != event.body:
                self.lastScreen = self.currentScreen
                self.currentScreen = event.body

        elif event.message == 'confirmation':
            text, self.onConfirm, self.onConfirmBody = event.body.split('::')
            self.children['ConfirmText']['Content'] = text
            bat.event.Event('pushScreen', 'ConfirmationDialogue').send()

        elif event.message == 'confirm':
            if self.visible:
                bat.event.Event('popScreen').send()
                bat.event.Event(self.onConfirm, self.onConfirmBody).send()
                self.children['ConfirmText']['Content'] = ""

    def hide(self):
        super(ConfirmationPage, self).hide()
        self.cancelbtn.hide()
        self.confirmbtn.hide()

    def show(self):
        super(ConfirmationPage, self).show()
        if self.onConfirm == "":
            self.cancelbtn.hide()
            self.confirmbtn.children[0].set_text('OK')
        else:
            self.cancelbtn.show()
            self.confirmbtn.children[0].set_text('Yes')
        self.confirmbtn.show()

class GameDetailsPage(Scripts.gui.Widget):
    '''A dumb widget that can show and hide itself, but doesn't respond to
    mouse events.'''
    def __init__(self, old_owner):
        bat.bats.mutate(self.childrenRecursive['GameName'])
        bat.bats.mutate(self.children['StoryDetails'])
        Scripts.gui.Widget.__init__(self, old_owner)
        self.setSensitive(False)

    def updateVisibility(self, visible):
        super(GameDetailsPage, self).updateVisibility(visible)
        for child in self.children:
            child.setVisible(visible, True)

        if visible:
            name = bat.store.get('/game/name', '')
            summary = bat.store.get('/game/storySummary', 'newGame')
            self.childrenRecursive['GameName'].set_text(name)
            try:
                    summary_text = STORY_SUMMARIES[summary]
            except KeyError:
                    summary_text = ''
            self.children['StoryDetails'].set_text(summary_text)

class OptionsPage(Scripts.gui.Widget):
    '''A dumb widget that can show and hide itself, but doesn't respond to
    mouse events.'''
    def __init__(self, old_owner):
        Scripts.gui.Widget.__init__(self, old_owner)
        self.setSensitive(False)

class ControlsConfPage(bat.impulse.Handler, Scripts.gui.Widget):
    _prefix = 'CC_'

    log = logging.getLogger(__name__ + '.ControlsConfPage')

    PROTECTED_BINDINGS = {
        ('keyboard', 'esckey'),
        ('keyboard', 'delkey'),
        ('keyboard', 'backspacekey')}

    def __init__(self, old_owner):
        Scripts.gui.Widget.__init__(self, old_owner)
        self.setSensitive(False)
        self.bindings_map = Scripts.input.get_bindings()
        self.binvertcamx = bat.bats.mutate(self.children['Btn_InvertCamX'])
        self.binvertcamy = bat.bats.mutate(self.children['Btn_InvertCamY'])
        self.redraw_bindings()
        self.active_binding = None

    def show(self):
        self.redraw_bindings()
        Scripts.gui.Widget.show(self)
        self.children['CC_Note'].setVisible(True, True)

    def hide(self):
        Scripts.gui.Widget.hide(self)
        self.children['CC_Note'].setVisible(False, True)

    def on_event(self, evt):
        if evt.message == 'CaptureBinding':
            self.initiate_capture(evt.body)
        elif evt.message == 'CaptureDelayStart':
            self.start_capture(evt.body)
        elif evt.message == 'InputCaptured':
            self.record_capture(evt.body)
        elif evt.message == 'StopCapture':
            self.stop_capture()
        elif evt.message == 'ResetBindings':
            self.reset_bindings()
        elif evt.message == 'SaveBindings':
            self.save_bindings()
        else:
            Scripts.gui.Widget.on_event(self, evt)

    def can_handle_input(self, state):
        return True

    def initiate_capture(self, path):
        ControlsConfPage.log.info('Initating capture')
        bat.impulse.Input().add_handler(self, 'MAINMENU')
        if 'xaxis' in path:
            desc = 'Move the joystick or mouse left or right.'
        elif 'yaxis' in path:
            desc = 'Move the joystick or mouse up or down.'
        else:
            desc = 'Push a button.'
        canvas =  self.children['CC_Instructions'].children['CC_Instructions_Label']
        canvas.set_text(desc)
        bat.event.Event('pushScreen', 'Controls_Capture').send()
        bat.event.Event('CaptureDelayStart', path).send(30)

    def start_capture(self, path):
        ControlsConfPage.log.info('Capturing')
        self.active_binding = path
        bat.impulse.Input().start_capturing_for(path)

    @bat.bats.expose
    def poll(self):
        '''
        While capturing, poll keyboard events directly to allow the user to
        cancel capturing. This can't be left to the impulse module, because
        capturing is filtered by button type (i.e. while capturing mouse and
        joystick axes, button presses will be ignored).
        '''
        ControlsConfPage.log.debug('Capturing for %s', self.active_binding)
        if self.active_binding is None:
            return

        active_events = bge.logic.keyboard.active_events
        ControlsConfPage.log.debug('Events: %s', active_events)
        ControlsConfPage.log.debug('%d, %d', bge.events.DELKEY, bge.events.BACKSPACEKEY)
        if bge.events.ESCKEY in active_events:
            # Escape cancels
            bat.event.Event('StopCapture').send(1)
        if bge.events.DELKEY in active_events or bge.events.BACKSPACEKEY in active_events:
            # Del or Backspace clears bindings.
            bindings = self.bindings_map[self.active_binding]
            for binding in bindings[:]:
                if binding not in ControlsConfPage.PROTECTED_BINDINGS:
                    bindings.remove(binding)
            self.redraw_bindings()
            bat.event.Event('StopCapture').send(1)

    def stop_capture(self):
        ControlsConfPage.log.info('Stopping capture')
        if self.active_binding is None:
            return
        self.active_binding = None
        bat.impulse.Input().stop_capturing()
        bat.impulse.Input().remove_handler(self)
        bat.event.Event('popScreen').send()

    def record_capture(self, sensor_def):
        '''Called in response to event from bat.impulse.Input.'''
        ControlsConfPage.log.info('Captured %s', sensor_def)
        if self.active_binding is None:
            return

        try:
            if sensor_def in ControlsConfPage.PROTECTED_BINDINGS:
                ControlsConfPage.log.warn('Can not change binding for %s', sensor_def)
                return

            if self.active_binding not in self.bindings_map:
                ControlsConfPage.log.error('No binding %s', self.active_binding)
                return

            for bindings in self.bindings_map.values():
                if sensor_def not in bindings:
                    continue
                bindings.remove(sensor_def)
            self.bindings_map[self.active_binding].append(sensor_def)
            self.redraw_bindings()
        finally:
            bat.event.Event('StopCapture').send(1)

    def save_bindings(self):
        ControlsConfPage.log.info('Saving bindings')
        Scripts.input.set_bindings(self.bindings_map)
        bat.store.put('/opt/cam_invert_x', self.binvertcamx.checked)
        bat.store.put('/opt/cam_invert_y', self.binvertcamy.checked)
        bat.event.Event('KeyBindingsChanged').send(1)
        bat.event.Event('popScreen').send(1)

    def reset_bindings(self):
        ControlsConfPage.log.info('Resetting bindings')
        Scripts.input.reset_bindings()
        self.bindings_map = Scripts.input.get_bindings()
        self.redraw_bindings()
        bat.event.Event('KeyBindingsChanged').send(1)

    def redraw_bindings(self):
        ControlsConfPage.log.info('Redrawing')
        for label in self.children['CC_BindingsGrp'].children:
            label = bat.bats.mutate(label)
            canvas = bat.bats.mutate(label.children[0])
            path = label['BindingPath']
            try:
                bindings = self.bindings_map[path]
            except KeyError:
                ControlsConfPage.log.error('No binding %s', path)
                canvas.set_text('??')
                continue
            canvas.set_text(Scripts.input.format_bindings(bindings))
        self.binvertcamx.checked = bat.store.get('/opt/cam_invert_x', False)
        self.binvertcamy.checked = bat.store.get('/opt/cam_invert_y', True)

class VideoConfPage(bat.impulse.Handler, Scripts.gui.Widget):
    _prefix = 'VC_'

    log = logging.getLogger(__name__ + '.VideoConfPage')

    NAMED_RESOLUTIONS = {
            '1280x720': 'HD 720p',
            '1920x1080': 'HD 1080p'
        }
    CONFIRM_TIMEOUT = 20

    def __init__(self, old_owner):
        Scripts.gui.Widget.__init__(self, old_owner)
        self.setSensitive(False)
        self.confirm_deadline = None
        self.bfoliage = bat.bats.mutate(self.children['Btn_Foliage'])
        self.bdof = bat.bats.mutate(self.children['Btn_DoF'])
        #self.bfull = bat.bats.mutate(self.children['Btn_Fullscreen'])

        self.resolution_buttons = [
            bat.bats.mutate(btn) for btn in self.children if btn.name.startswith('Btn_VC')
            ]

        # Hide resolution buttons when on a platform that doesn't support mode
        # switching.
        norestext = bat.bats.mutate(self.children['VC_NoResolutionText'])
#         if True:
        if not self.can_change_resolution:
            for btn in self.resolution_buttons:
                btn.can_display = False
            bat.bats.mutate(self.children['VC_ResolutionText']).can_display = False
            norestext.children[0]['Content'] = (
                "Can not change resolutions on this platform. If the game " +
                "runs slowly, try changing the resolution in your operating " +
                "system properties.")
        else:
            norestext.can_display = False

        self.update_res_labels()
        self.revert()

        # This sets the resolution for the rest of the game!
        self.apply_resolution()

    @property
    def can_change_resolution(self):
        if not bge.render.getFullScreen():
            return True
        else:
            # Can't change resolution on Mac when full-screen. See:
            # https://projects.blender.org/tracker/?func=detail&atid=306&aid=36501&group_id=9
            return platform.system not in {'Darwin'}

    @property
    def dof_recommended(self):
        '''Depth of field filter causes issues on some platforms.'''
        vendor = bgl.glGetString(bgl.GL_VENDOR).lower()
        pform = platform.system().lower()
        return not any((v in vendor and p in pform) for (p, v) in DOF_BLACKLIST)

    def on_event(self, evt):
        if evt.message == 'RevertVideo':
            self.revert()
        elif evt.message == 'SaveVideo':
            if self.res_is_different(self.res):
                bat.event.Event('switchScreen', 'VideoConfirm').send()
                self.begin_confirmation()
            else:
                self.save()
                bat.event.Event('popScreen').send(1)
        elif evt.message == 'VideoResolutionClick':
            self.res = evt.body
        elif evt.message == 'VideoConfirm':
            if evt.body == 'yes':
                self.end_confirmation(True)
                bat.event.Event('popScreen').send()
            else:
                self.end_confirmation(False)
                bat.event.Event('switchScreen', 'VideoOptions').send()
        elif evt.message == 'popScreen':
            if self.confirm_deadline is not None:
                self.end_confirmation(False)
        elif evt.message == 'dofChanged':
            if self.bdof.checked and not self.dof_recommended:
                bat.event.Event('confirmation', 'Warning: this setting may be buggy on your computer.::::').send()
        else:
            Scripts.gui.Widget.on_event(self, evt)

    def res_is_different(self, res):
        own_dims = res.split('x')
        own_dims = int(own_dims[0]), int(own_dims[1])
        current_dims = bge.render.getWindowWidth(), bge.render.getWindowHeight()
        return own_dims != current_dims

    def update_res_labels(self):
        for btn in self.resolution_buttons:
            res = btn['onClickBody']
            if res in VideoConfPage.NAMED_RESOLUTIONS:
                text = VideoConfPage.NAMED_RESOLUTIONS[res]
            else:
                text = res
            btn.children[0]['Content'] = text

    def revert(self):
        VideoConfPage.log.info('Reverting video settings')
        self.bfoliage.checked = bat.store.get('/opt/foliage', True)
        self.bdof.checked = bat.store.get(
            '/opt/depthOfField', self.dof_recommended)
        self.revert_resolution()

    def revert_resolution(self):
        if not self.can_change_resolution:
            current_dims = bge.render.getWindowWidth(), bge.render.getWindowHeight()
            self.res = "{}x{}".format(*current_dims)
        else:
            #self.bfull.checked = bat.store.get('/opt/fullscreen', True)
            self.res = bat.store.get('/opt/resolution', '800x600')

    def apply_resolution(self):
        if not self.can_change_resolution:
            return
        width, height = self.res.split('x')
        width = int(width)
        height = int(height)
        bge.render.setWindowSize(width, height)
        #bge.render.setFullScreen(self.bfull.checked)

    def save(self):
        VideoConfPage.log.info('Saving video settings.')
        VideoConfPage.log.info('foliage: %s', self.bfoliage.checked)
        bat.store.put('/opt/foliage', self.bfoliage.checked)
        VideoConfPage.log.info('dof: %s', self.bdof.checked)
        bat.store.put('/opt/depthOfField', self.bdof.checked)
        #VideoConfPage.log.info('fullscreen: %s', self.bfull.checked)
        #bat.store.put('/opt/fullscreen', self.bfull.checked)
        VideoConfPage.log.info('resolution: %s', self.res)
        bat.store.put('/opt/resolution', self.res)

    def begin_confirmation(self):
        self.confirm_deadline = time.time() + VideoConfPage.CONFIRM_TIMEOUT
        self.apply_resolution()

    def end_confirmation(self, confirmed):
        self.confirm_deadline = None
        if confirmed:
            self.save()
        else:
            self.revert_resolution()
            self.apply_resolution()

    @bat.bats.expose
    def update(self):
        highlight = self.children['VC_res_highlight']
        if self.selected_button is not None:
            selected_button = self.children[self.selected_button]
            highlight.visible = True
            highlight.localPosition = selected_button.localPosition
        else:
            highlight.visible = False

        if self.confirm_deadline is None:
            return
        remaining_time = self.confirm_deadline - time.time()
        if remaining_time < 0:
            bat.event.Event('VideoConfirm', 'no').send()
            self.confirm_deadline = None
        else:
            time_text = self.childrenRecursive['VC_Instructions_Timer']
            time_text.set_text('Aborting in %ds' % int(remaining_time))

    @property
    def res(self):
        return self._res
    @res.setter
    def res(self, resolution):
        self._res = resolution
        VideoConfPage.log.info('window shape: %s', resolution)
        self.selected_button = None
        for btn in self.resolution_buttons:
            if btn['onClickBody'] == resolution:
                self.selected_button = btn.name
                break


class NamePage(Scripts.gui.Widget):
    MODEMAP = {
        'LOWERCASE':  "abcdefghij""klmnopqrs""tuvwxyz",
        'UPPERCASE':  "ABCDEFGHIJ""KLMNOPQRS""TUVWXYZ",
        'NUMBERWANG': "1234567890""@$%&*-+!?""()\"':;/"
        }
    MAX_NAME_LEN = 6

    def __init__(self, old_owner):
        bat.bats.mutate(self.children['NamePageName'])
        self.mode = 'UPPERCASE'
        Scripts.gui.Widget.__init__(self, old_owner)
        self.setSensitive(False)

    def on_event(self, evt):
        if evt.message == 'characterEntered':
            self.add_character(evt.body)
            if self.mode == 'UPPERCASE':
                self.mode = 'LOWERCASE'
            self.lay_out_keymap()

        elif evt.message == 'acceptName':
            name = self.children['NamePageName'].get_text()
            if len(name) > 0:
                bat.store.put('/game/name', name)
                bat.event.Event('popScreen').send()
                bat.event.Event('pushScreen', 'LoadDetailsScreen').send()

        elif evt.message == 'capsLockToggle':
            if self.mode == 'UPPERCASE':
                self.mode = 'LOWERCASE'
            else:
                self.mode = 'UPPERCASE'
            self.lay_out_keymap()

        elif evt.message == 'numLockToggle':
            if self.mode == 'NUMBERWANG':
                self.mode = 'LOWERCASE'
            else:
                self.mode = 'NUMBERWANG'
            self.lay_out_keymap()

        elif evt.message == 'backspace':
            self.pop_character()

        else:
            Scripts.gui.Widget.on_event(self, evt)

    def add_character(self, char):
        name = self.children['NamePageName'].get_text()
        name += char
        name = name[:NamePage.MAX_NAME_LEN]
        self.children['NamePageName'].set_text(name)

    def pop_character(self):
        name = self.children['NamePageName'].get_text()
        self.children['NamePageName'].set_text(name[0:-1])

    def updateVisibility(self, visible):
        Scripts.gui.Widget.updateVisibility(self, visible)
        self.children['NamePageTitle'].setVisible(visible, True)
        self.children['NamePageName'].setVisible(visible, True)
        if visible:
            name = bat.store.get('/game/name', '')
            self.children['NamePageName'].set_text(name)
            self.mode = 'LOWERCASE'
            # Lay out keys later - once the buttons have had a change to draw
            # once; otherwise the order can get stuffed up.
            bat.event.Event('capsLockToggle').send(1.0)

    def lay_out_keymap(self):
        def grid_key(ob):
            '''Sorting function for a grid, left-right, top-bottom.'''
            pos = ob.worldPosition
            score = pos.x + -pos.z * 100.0
            return score

        keymap = NamePage.MODEMAP[self.mode]
        buttons = [b for b in self.children if isinstance(b, CharButton)]
        buttons.sort(key=grid_key)
        for i, child in enumerate(buttons):
            try:
                char = keymap[i]
            except IndexError:
                char = ''
            child.set_char(char)

class CharButton(Scripts.gui.Button):
    '''A button for the on-screen keyboard.'''
    def __init__(self, old_owner):
        Scripts.gui.Button.__init__(self, old_owner)

    def updateVisibility(self, visible):
        super(CharButton, self).updateVisibility(visible)
        self.children['CharCanvas'].setVisible(visible, True)

    def set_char(self, char):
        self.children['CharCanvas'].set_text(char)
        self['onClickBody'] = char

class CreditsPage(Scripts.gui.Widget):
    '''Controls the display of credits.'''
    DELAY = 180

    def __init__(self, old_owner):
        Scripts.gui.Widget.__init__(self, old_owner)
        self.setSensitive(False)
        self.index = 0
        self.delayTimer = 0

    def updateVisibility(self, visible):
        super(CreditsPage, self).updateVisibility(visible)
        for child in self.children:
            child.setVisible(visible, True)

        if not visible:
            self.children['Role']['Content'] = ""
            self.children['People']['Content'] = ""
            self.index = 0
            self.delayTimer = 0

    def drawNext(self):
        role, people = CREDITS[self.index]
        self.children['Role']['Content'] = role
        self.children['People']['Content'] = people
        self.index += 1
        self.index %= len(CREDITS)

    @bat.bats.expose
    def draw(self):
        if self.children['People']['Rendering'] or self.children['Role']['Rendering']:
            self.delayTimer = CreditsPage.DELAY
        else:
            self.delayTimer -= 1
            if self.delayTimer <= 0:
                self.drawNext()

class Subtitle(bat.bats.BX_GameObject, bge.types.KX_GameObject):
    SCREENMAP = {
            'LoadingScreen': 'Load',
            'LoadDetailsScreen': '',
            'OptionsScreen': 'Options',
            'CreditsScreen': 'Credits',
            'ConfirmationDialogue': 'Confirm'
        }

    def __init__(self, old_owner):
        bat.event.EventBus().add_listener(self)
        bat.event.EventBus().replay_last(self, 'showScreen')

    def on_event(self, event):
        if event.message == 'showScreen':
            text = ""
            try:
                text = Subtitle.SCREENMAP[event.body]
            except KeyError:
                text = ""
            self.children['SubtitleCanvas']['Content'] = text

class MenuSnail(bat.bats.BX_GameObject, bge.types.KX_GameObject):

    def __init__(self, old_owner):
        arm = bat.bats.add_and_mutate_object(self.scene, "SlugArm_Min",
                self.children["SlugSpawnPos"])
        arm.setParent(self)
        arm.look_at("Camera")
        arm.playAction("MenuSnail_Rest", 1, 120, play_mode=bge.logic.KX_ACTION_MODE_LOOP, speed=0.3)
        self.arm = arm

        bat.event.EventBus().add_listener(self)

    def on_event(self, evt):
        if evt.message == "FocusChanged":
            if evt.body is None:
                self.arm.look_at("Camera")
            else:
                self.arm.look_at(evt.body)
