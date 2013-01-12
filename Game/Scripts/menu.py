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

import bge

import bat.bats
import bat.event

import Scripts.gui
import bat.store

CREDITS = [
	("Director/Producer", "Alex Fraser"),
	("Story", "Alex Fraser, Lev Lafayette, Lara Micocki, Jodie Fraser"),
	("Modelling", "Alex Fraser, Junki Wano"),
	("Animation", "Alex Fraser"),
	("Textures", "Alex Fraser, Junki Wano"),
	("Music", "Robert Leigh"),
	("Programming", "Alex Fraser, Mark Triggs, Campbell Barton, Ben Sturmfels"),
	("Sound Effects", "Alex Fraser, Ben Sturmfels, freesound.org users: "
			"3bagbrew, FreqMan, HerbertBoland, Percy Duke, klakmart, aUREa, "
			"qubodup, thetruwu, nsp, kangaroovindaloo, ERH, Corsica_S, "
			"batchku, satrebor, gherat, ZeSoundResearchInc., CGEffex"),
	("Testing", "Jodie Fraser, Lachlan Kanaley, Damien Elmes, Mark Triggs"),
	("Made With", "Blender, Bullet, The GIMP and Inkscape")]

class SessionManager(metaclass=bat.bats.Singleton):
	'''Responds to some high-level messages.'''

	def __init__(self):
		bat.event.EventBus().add_listener(self)

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
			cbEvent = bat.event.Event('LoadLevel')
			bat.event.Event('ShowLoadingScreen', (True, cbEvent)).send()

		elif event.message == 'LoadLevel':
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


class MenuController(Scripts.gui.UiController):

	def __init__(self, old_owner):
		Scripts.gui.UiController.__init__(self, old_owner)

		bat.event.EventBus().add_listener(self)

		# TODO: for some reason setScreen seems to interfere with the menu. If
		# send delay is set to 2, it might not work... but 200 does! Weird.
		bat.event.Event('setScreen', 'LoadingScreen').send(0)
		bat.event.Event('GameModeChanged', 'Menu').send()

		# Menu music. Note that the fade rate is set higher than the default, so
		# that the music completely fades out before the game starts.
		bat.sound.Jukebox().play_files('menu', self, 1,
				'//Sound/Music/01-TheStart_loop1.ogg',
				'//Sound/Music/01-TheStart_loop2.ogg',
				introfile='//Sound/Music/01-TheStart_intro.ogg',
				fade_in_rate=1, fade_out_rate=0.05, volume=0.6)

	def on_event(self, evt):
		Scripts.gui.UiController.on_event(self, evt)
		if evt.message in {'startGame', 'quit'}:
			bat.sound.Jukebox().stop('menu')

	def get_default_widget(self, screen_name):
		if screen_name == 'LoadingScreen':
			gamenum = bat.store.get_session_id()
			for ob in self.scene.objects:
				if ob.name == 'SaveButton_T' and ob['onClickBody'] == gamenum:
					return ob
		elif screen_name == 'CreditsScreen':
			return self.scene.objects['Btn_Crd_Load']
		elif screen_name == 'OptionsScreen':
			return self.scene.objects['Btn_Opt_Load']
		elif screen_name == 'LoadDetailsScreen':
			return self.scene.objects['Btn_StartGame']
		elif screen_name == 'ConfirmationDialogue':
			return self.scene.objects['Btn_Cancel']
		elif screen_name == 'NameScreen':
			for ob in self.scene.objects:
				if ob.name == 'CharButton_T' and ob._orig_name == 'Btn_Char.FIRST':
					return ob

		return None

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
			self.checked = bat.store.get(self['dataBinding'], self['dataDefault'])
		self.updateCheckFace()

		# Create a clickable box around the text.
		canvas = self.children['CheckBoxCanvas']
		canvas = bat.bats.mutate(canvas)
		canvas['Content'] = self['label']
		canvas['colour'] = self['colour']
		canvas.render()
		hitbox = self.children['Checkbox_hitbox']
		hitbox.localScale.x = canvas.textwidth * canvas.localScale.x
		hitbox.localScale.y = canvas.textheight * canvas.localScale.y

	def click(self):
		self.checked = not self.checked
		self.updateCheckFace()
		if 'dataBinding' in self:
			bat.store.put(self['dataBinding'], self.checked)
		super(Checkbox, self).click()

	def updateVisibility(self, visible):
		super(Checkbox, self).updateVisibility(visible)
		self.updateCheckFace()

	def updateCheckFace(self):
		if self.visible:
			self.children['CheckOff'].setVisible(not self.checked, True)
			self.children['CheckOn'].setVisible(self.checked, True)
		else:
			self.children['CheckOff'].setVisible(False, True)
			self.children['CheckOn'].setVisible(False, True)

	def updateTargetFrame(self):
		start, end = self.get_anim_range()
		Scripts.gui.Button.updateTargetFrame(self)
		self.children['CheckOff'].playAction("Button_OnlyColour", start, end)
		self.children['CheckOn'].playAction("Button_OnlyColour", start, end)

class ConfirmationPage(Scripts.gui.Widget):
	def __init__(self, old_owner):
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
			summary = bat.store.get('/game/storySummary', 'Start a new game.')
			self.childrenRecursive['GameName'].set_text(name)
			self.children['StoryDetails'].set_text(summary)

class OptionsPage(Scripts.gui.Widget):
	'''A dumb widget that can show and hide itself, but doesn't respond to
	mouse events.'''
	def __init__(self, old_owner):
		Scripts.gui.Widget.__init__(self, old_owner)
		self.setSensitive(False)

class NamePage(Scripts.gui.Widget):
	'''A dumb widget that can show and hide itself, but doesn't respond to
	mouse events.'''

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
		arm.playAction("MenuSnail_Rest", 1, 1)
		self.arm = arm

		bat.event.EventBus().add_listener(self)

	def on_event(self, evt):
		if evt.message == "FocusChanged":
			if evt.body is None:
				self.arm.look_at("Camera")
			else:
				self.arm.look_at(evt.body)

