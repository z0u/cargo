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

import weakref

import bge
import mathutils

import bxt
from . import store
from . import ui
from . import snail

CREDITS = [
	("Director/Producer", "Alex Fraser"),
	("Story", "Alex Fraser, Lev Lafayette, Lara Micocki"),
	("Modelling", "Alex Fraser, Junki Wano"),
	("Animation", "Alex Fraser"),
	("Textures", "Alex Fraser, Junki Wano"),
	("Music", "Robert Leigh"),
	("Programming", "Alex Fraser, Mark Triggs"),
	("Sound Effects", "Alex Fraser, freesound.org users: 3bagbrew, FreqMan, HerbertBoland, Percy Duke, klakmart, aUREa, qubodup, thetruwu, nsp, kangaroovindaloo, ERH"),
	("Testing", "Jodie Fraser, Lachlan Kanaley, Damien Elmes, Mark Triggs"),
	("Made With", "Blender, Bullet, The GIMP and Inkscape")]

class SessionManager(metaclass=bxt.types.Singleton):
	'''Responds to some high-level messages.'''

	def __init__(self):
		bxt.types.EventBus().add_listener(self)

	def on_event(self, event):
		if event.message == 'showSavedGameDetails':
			# The session ID indicates which saved game is being used.
			store.setSessionId(event.body)
			evt = bxt.types.Event('showScreen', 'LoadDetailsScreen')
			bxt.types.EventBus().notify(evt)

		elif event.message == 'startGame':
			# Show the loading screen and send another message to start the game
			# after the loading screen has shown.
			cbEvent = bxt.types.Event('LoadLevel')
			bxt.types.Event('ShowLoadingScreen', (True, cbEvent)).send()

		elif event.message == 'LoadLevel':
			# Load the level indicated in the save game. This is called after
			# the loading screen has been shown.
			level = store.get('/game/levelFile', '//Outdoors.blend')
			store.save()
			bge.logic.startGame(level)

		elif event.message == 'deleteGame':
			# Remove all stored items that match the current path.
			for key in store.list('/game/'):
				store.unset(key)
			evt = bxt.types.Event('showScreen', 'LoadingScreen')
			bxt.types.EventBus().notify(evt)

		elif event.message == 'quit':
			cbEvent = bxt.types.Event('reallyQuit')
			bxt.types.Event('ShowLoadingScreen', (True, cbEvent)).send()

		elif event.message == 'reallyQuit':
			bge.logic.endGame()

class InputHandler(metaclass=bxt.types.Singleton):
	'''Manages UI elements: focus and click events.'''

	_prefix = 'IH_'

	def __init__(self):
		self.widgets = bxt.types.SafeSet()
		self._current = None
		self._downCurrent = None

	# Getter and setter to allow use of weakref
	def _getCurrent(self):
		if self._current == None:
			return None
		else:
			return self._current()
	def _setCurrent(self, current):
		if current == None:
			self._current = None
		else:
			self._current = weakref.ref(current)
	current = property(_getCurrent, _setCurrent)

	# Getter and setter to allow use of weakref
	def _getDownCurrent(self):
		if self._downCurrent == None:
			return None
		else:
			return self._downCurrent()
	def _setDownCurrent(self, downcurrent):
		if downcurrent == None:
			self._downCurrent = None
		else:
			self._downCurrent = weakref.ref(downcurrent)
	downCurrent = property(_getDownCurrent, _setDownCurrent)

	def addWidget(self, widget):
		self.widgets.add(widget)

	@bxt.types.expose
	@bxt.utils.controller_cls
	def mouseMove(self, c):
		mOver = c.sensors['sMouseOver']
		self.mouseOver(mOver)

	@bxt.types.expose
	def mouseOver(self, mOver):
		newFocus = mOver.hitObject

		# Bubble up to ancestor if need be
		while newFocus != None:
			if 'Widget' in newFocus:
				break
			newFocus = newFocus.parent

		if newFocus == self.current:
			return

		if self.current:
			self.current.exit()
		if newFocus != None:
			newFocus.enter()
		self.current = newFocus

	@bxt.types.expose
	@bxt.utils.controller_cls
	def mouseButton(self, c):
		if bxt.utils.someSensorPositive():
			self.mouseDown()
		else:
			self.mouseUp()

	def mouseDown(self):
		'''Send a mouse down event to the widget under the cursor.'''
		if self.current:
			self.current.down()
			self.downCurrent = self.current

	def mouseUp(self):
		'''Send a mouse up event to the widget under the cursor. If that widget
		also received the last mouse down event, it will be sent a click event
		in addition to (after) the up event.'''
		if self.downCurrent:
			self.downCurrent.up()
			if self.current == self.downCurrent:
				self.downCurrent.click()
		self.downCurrent = None

	def on_event(self, event):
		if event.message == 'sensitivityChanged':
			# Not implemented. Eventually, this should update the visual state
			# of the current button.
			pass

	@bxt.types.expose
	@bxt.utils.all_sensors_positive
	def focusNext(self):
		'''Switch to the next widget according to tab-order.'''
		# TODO
		pass

	@bxt.types.expose
	@bxt.utils.all_sensors_positive
	def focusPrevious(self):
		'''Switch to the previous widget according to tab-order.'''
		# TODO
		pass

	@bxt.types.expose
	@bxt.utils.all_sensors_positive
	def focusLeft(self):
		'''Switch to the widget to the left of current.'''
		# TODO
		pass

	@bxt.types.expose
	@bxt.utils.all_sensors_positive
	def focusRight(self):
		'''Switch to the widget to the right of current.'''
		# TODO
		pass

	@bxt.types.expose
	@bxt.utils.all_sensors_positive
	def focusUp(self):
		'''Switch to the widget above current.'''
		# TODO
		pass

	@bxt.types.expose
	@bxt.utils.all_sensors_positive
	def focusDown(self):
		'''Switch to the widget below current.'''
		# TODO
		pass

################
# Global sensors
################

@bxt.utils.controller
def controllerInit(c):
	'''Initialise the menu'''
	bge.render.showMouse(True)
	mOver = c.sensors['sMouseOver']
	mOver.usePulseFocus = True
	evt = bxt.types.Event('GameModeChanged', 'Menu')
	bxt.types.EventBus().notify(evt)

################
# Widget classes
################

bxt.types.EventBus().notify(bxt.types.Event('showScreen', 'LoadingScreen'))

class Camera(bxt.types.BX_GameObject, bge.types.KX_Camera):
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
		bxt.types.EventBus().add_listener(self)
		bxt.types.EventBus().replay_last(self, 'showScreen')

	def on_event(self, event):
		if event.message == 'showScreen' and event.body in Camera.FRAME_MAP:
			self['targetFrame'] = Camera.FRAME_MAP[event.body]

	@bxt.types.expose
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

class Widget(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	'''An interactive UIObject. Has various states (e.g. focused, up, down) to
	facilitate interaction. Some of the states map to a frame to allow a
	visual progression.'''

	S_FOCUS = 2
	S_DEFOCUS = 3
	S_DOWN = 4
	S_UP = 5
	S_HIDDEN = 6
	S_VISIBLE = 7

	FRAME_RATE = 25.0 / bge.logic.getLogicTicRate()

	# These should be matched to the FCurve or action of the object associated
	# with this widget. The animation is not actually driven by this script; it
	# just sets the object's 'frame' property, which should be observed by an
	# actuator.
	HIDDEN_FRAME = 1.0
	IDLE_FRAME = 5.0
	FOCUS_FRAME = 9.0
	ACTIVE_FRAME = 12.0

	def __init__(self, old_owner):
		self.sensitive = True
		self.active = False
		self['Widget'] = True
		self.show()

		InputHandler().addWidget(self)
		bxt.types.EventBus().add_listener(self)
		bxt.types.EventBus().replay_last(self, 'showScreen')

	def enter(self):
		if not self.sensitive:
			return
		self.add_state(Widget.S_FOCUS)
		self.rem_state(Widget.S_DEFOCUS)
		self.updateTargetFrame()

	def exit(self):
		self.add_state(Widget.S_DEFOCUS)
		self.rem_state(Widget.S_FOCUS)
		self.updateTargetFrame()

	def down(self):
		if not self.sensitive:
			return
		self.add_state(Widget.S_DOWN)
		self.rem_state(Widget.S_UP)
		self.updateTargetFrame()

	def up(self):
		self.add_state(Widget.S_UP)
		self.rem_state(Widget.S_DOWN)
		self.updateTargetFrame()

	def click(self):
		if not self.sensitive:
			return
		if 'onClickMsg' in self:
			msg = self['onClickMsg']
			body = ''
			if 'onClickBody' in self:
				body = self['onClickBody']
			evt = bxt.types.Event(msg, body)
			bxt.types.EventBus().notify(evt)

	def on_event(self, evt):
		if evt.message == 'showScreen':
			if not 'screenName' in self:
				self.show()
			elif evt.body == self['screenName']:
				self.show()
			else:
				self.hide()

	def hide(self):
		self.setVisible(False, False)
		self.add_state(Widget.S_HIDDEN)
		self.rem_state(Widget.S_VISIBLE)
		self.rem_state(Widget.S_DOWN)
		self.rem_state(Widget.S_FOCUS)
		self.updateTargetFrame()

	def show(self):
		self.setVisible(True, False)
		self.add_state(Widget.S_VISIBLE)
		self.rem_state(Widget.S_HIDDEN)
		self.updateTargetFrame()

	def updateTargetFrame(self):
		targetFrame = Widget.IDLE_FRAME
		if self.has_state(Widget.S_HIDDEN):
			targetFrame = Widget.HIDDEN_FRAME
		elif self.has_state(Widget.S_FOCUS):
			if self.has_state(Widget.S_DOWN):
				targetFrame = Widget.ACTIVE_FRAME
			else:
				targetFrame = Widget.FOCUS_FRAME
		else:
			targetFrame = Widget.IDLE_FRAME
		self['targetFrame'] = targetFrame

	@bxt.types.expose
	def update(self):
		targetFrame = self['targetFrame']
		frame = self['frame']
		oldFrame = frame
		if frame < targetFrame:
			frame = min(frame + Widget.FRAME_RATE, targetFrame)
		else:
			frame = max(frame - Widget.FRAME_RATE, targetFrame)
		self['frame'] = frame

		if frame == 1.0:
			self.updateVisibility(False)
		elif oldFrame == 1.0:
			self.updateVisibility(True)

		c = bge.logic.getCurrentController()
		c.activate(c.actuators[0])

	def updateVisibility(self, visible):
		self.setVisible(visible, True)

	def setSensitive(self, sensitive):
		oldv = self.sensitive
		self.sensitive = sensitive
		if oldv != sensitive:
			evt = bxt.types.Event('sensitivityChanged', self.sensitive)
			bxt.types.EventBus().notify(evt)

class Button(Widget):
	# A Widget has everything needed for a simple button.
	def __init__(self, old_owner):
		Widget.__init__(self, old_owner)

class SaveButton(Button):
	def __init__(self, old_owner):
		Button.__init__(self, old_owner)
		self.id = 0

	def updateVisibility(self, visible):
		super(SaveButton, self).updateVisibility(visible)
		self.children['IDCanvas'].setVisible(visible, True)

class Checkbox(Button):
	def __init__(self, old_owner):
		Button.__init__(self, old_owner)
		self.checked = False
		if 'dataBinding' in self:
			self.checked = store.get(self['dataBinding'], self['dataDefault'])
		self.updateCheckFace()
		self.children['CheckBoxCanvas']['Content'] = self['label']
		self.children['CheckBoxCanvas']['colour'] = self['colour']

	def click(self):
		self.checked = not self.checked
		self.updateCheckFace()
		if 'dataBinding' in self:
			store.set(self['dataBinding'], self.checked)
		super(Checkbox, self).click()

	def updateVisibility(self, visible):
		super(Checkbox, self).updateVisibility(visible)
		self.children['CheckBoxCanvas'].setVisible(visible, True)
		self.updateCheckFace()

	def updateCheckFace(self):
		if self.visible:
			self.children['CheckOff'].setVisible(not self.checked, True)
			self.children['CheckOn'].setVisible(self.checked, True)
		else:
			self.children['CheckOff'].setVisible(False, True)
			self.children['CheckOn'].setVisible(False, True)

	def update(self):
		super(Checkbox, self).update()
		self.children['CheckOff']['frame'] = self['frame']
		self.children['CheckOn']['frame'] = self['frame']

class ConfirmationPage(Widget):
	def __init__(self, old_owner):
		self.lastScreen = ''
		self.currentScreen = ''
		self.onConfirm = ''
		self.onConfirmBody = ''
		Widget.__init__(self, old_owner)
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
			evt = bxt.types.Event('showScreen', 'ConfirmationDialogue')
			bxt.types.EventBus().notify(evt)

		elif event.message == 'cancel':
			if self.visible:
				evt = bxt.types.Event('showScreen', self.lastScreen)
				bxt.types.EventBus().notify(evt)
				self.children['ConfirmText']['Content'] = ""

		elif event.message == 'confirm':
			if self.visible:
				evt = bxt.types.Event('showScreen', self.lastScreen)
				bxt.types.EventBus().notify(evt)
				evt = bxt.types.Event(self.onConfirm, self.onConfirmBody)
				bxt.types.EventBus().notify(evt)
				self.children['ConfirmText']['Content'] = ""

class GameDetailsPage(Widget):
	'''A dumb widget that can show and hide itself, but doesn't respond to
	mouse events.'''
	def __init__(self, old_owner):
		Widget.__init__(self, old_owner)
		self.setSensitive(False)

	def updateVisibility(self, visible):
		super(GameDetailsPage, self).updateVisibility(visible)
		for child in self.children:
			child.setVisible(visible, True)

		if visible:
			self.children['GameName']['Content'] = store.get(
				'/game/title', 'Game %d' % (store.getSessionId() + 1))
			self.children['StoryDetails']['Content'] = store.get(
				'/game/storySummary', 'Start a new game.')

class CreditsPage(Widget):
	'''Controls the display of credits.'''
	DELAY = 180

	def __init__(self, old_owner):
		Widget.__init__(self, old_owner)
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

	@bxt.types.expose
	def draw(self):
		if self.children['People']['Rendering'] or self.children['Role']['Rendering']:
			self.delayTimer = CreditsPage.DELAY
		else:
			self.delayTimer -= 1
			if self.delayTimer <= 0:
				self.drawNext()

class Subtitle(bxt.types.BX_GameObject, bge.types.KX_GameObject):
	SCREENMAP = {
			'LoadingScreen': 'Load',
			'LoadDetailsScreen': '',
			'OptionsScreen': 'Options',
			'CreditsScreen': 'Credits',
			'ConfirmationDialogue': 'Confirm'
		}

	def __init__(self, old_owner):
		bxt.types.EventBus().add_listener(self)
		bxt.types.EventBus().replay_last(self, 'showScreen')

	def on_event(self, event):
		if event.message == 'showScreen':
			text = ""
			try:
				text = Subtitle.SCREENMAP[event.body]
			except KeyError:
				text = ""
			self.children['SubtitleCanvas']['Content'] = text

class MenuSnail(snail.NPCSnail):

	_prefix = 'MS_'

	def __init__(self, old_owner):
		snail.NPCSnail.__init__(self, old_owner)

	@bxt.types.expose
	def look(self):
		target = InputHandler().current
		if target is None:
			target = bge.logic.getCurrentScene().active_camera
		self.look_at(target)
