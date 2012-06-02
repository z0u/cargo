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
import math

import bge
import mathutils

import bxt
from . import store
from . import ui
from . import snail
from . import impulse

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
			bxt.types.Event('pushScreen', 'LoadDetailsScreen'). send()

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
			bxt.types.Event('setScreen', 'LoadingScreen').send()

		elif event.message == 'quit':
			cbEvent = bxt.types.Event('reallyQuit')
			bxt.types.Event('ShowLoadingScreen', (True, cbEvent)).send()

		elif event.message == 'reallyQuit':
			bge.logic.endGame()

class MenuController(impulse.Handler, bxt.types.BX_GameObject,
		bge.types.KX_GameObject):

	'''Manages UI elements: focus and click events.'''

	_prefix = 'MC_'

	current = bxt.types.weakprop("current")
	downCurrent = bxt.types.weakprop("downCurrent")

	def __init__(self, old_owner):
		self.screen_stack = []
		impulse.Input().add_handler(self, 'MENU')

		bxt.types.EventBus().add_listener(self)
		bxt.types.Event('setScreen', 'LoadingScreen').send()
		bxt.types.Event('GameModeChanged', 'Menu').send()

	def on_event(self, evt):
		if evt.message == 'setScreen':
			self.screen_stack = [evt.body]
			self.update_screen()
		elif evt.message == 'pushScreen':
			if evt.body in self.screen_stack:
				self.screen_stack.remove(evt.body)
			self.screen_stack.append(evt.body)
			self.update_screen()
		elif evt.message == 'popScreen':
			if len(self.screen_stack) > 0:
				self.screen_stack.pop()
			self.update_screen()

	def update_screen(self):
		if len(self.screen_stack) > 0:
			screen_name = self.screen_stack[-1]
		else:
			screen_name = 'LoadingScreen'
		bxt.types.Event('showScreen', screen_name).send()

		# Previous widget is probably hidden now; switch to default for this
		# screen.
		widget = None
		if screen_name == 'LoadingScreen':
			gamenum = store.getSessionId()
			for ob in self.scene.objects:
				if ob.name == 'SaveButton_T' and ob['onClickBody'] == gamenum:
					widget = ob
					break
		elif screen_name == 'CreditsScreen':
			widget = self.scene.objects['Btn_Crd_Load']
		elif screen_name == 'OptionsScreen':
			widget = self.scene.objects['Btn_Opt_Load']
		elif screen_name == 'LoadDetailsScreen':
			widget = self.scene.objects['Btn_StartGame']
		elif screen_name == 'ConfirmationDialogue':
			widget = self.scene.objects['Btn_Cancel']

		if widget is not None:
			self.focus(widget)

	@bxt.types.expose
	@bxt.utils.controller_cls
	def mouseMove(self, c):
		bge.render.showMouse(True)
		mOver = c.sensors['sMouseOver']
		mOver.usePulseFocus = True
		self.mouseOver(mOver)

	@bxt.types.expose
	def mouseOver(self, mOver):
		newFocus = mOver.hitObject

		# Bubble up to ancestor if need be
		while newFocus != None:
			if 'Widget' in newFocus:
				break
			newFocus = newFocus.parent

		self.focus(newFocus)

	@bxt.types.expose
	@bxt.utils.controller_cls
	def mouseButton(self, c):
		if bxt.utils.someSensorPositive():
			self.press()
		else:
			self.release()

	def focus(self, widget):
		if widget is self.current:
			return

		self.current = widget
		bxt.types.WeakEvent("FocusChanged", widget).send()

	def press(self):
		'''Send a mouse down event to the widget under the cursor.'''
		if self.current:
			self.current.down()
			self.downCurrent = self.current

	def release(self):
		'''Send a mouse up event to the widget under the cursor. If that widget
		also received the last mouse down event, it will be sent a click event
		in addition to (after) the up event.'''
		if self.downCurrent:
			self.downCurrent.up()
			if self.current == self.downCurrent:
				self.downCurrent.click()
		self.downCurrent = None

	def handle_bt_1(self, state):
		'''Activate current widget (keyboard/joypad).'''
		if state.triggered:
			if state.positive:
				self.press()
			else:
				self.release()
		return True

	def handle_bt_2(self, state):
		'''Escape from current screen (keyboard/joypad).'''
		if state.activated:
			bxt.types.Event('popScreen').send()
		return True

	def handle_movement(self, state):
		'''Switch to neighbouring widgets (keyboard/joypad).'''
		if not state.triggered or state.bias.magnitude < 0.1:
			return True

		bge.render.showMouse(False)

		widget = self.find_next_widget(state.bias)
		if widget is not None:
			self.focus(widget)
		return True

	def find_next_widget(self, direction):
		cam = self.scene.active_camera
		if self.current is not None:
			loc = self.current.worldPosition
		else:
			loc = mathutils.Vector((0.0, 0.0, 0.0))
		world_direction = bxt.bmath.to_world_vec(cam, direction.resized(3))
		world_direction.normalize()

		# Iterate over widgets, assigning each one a score - based on the
		# direction of the movement and the location of the current widget.
		best_widget = None
		best_score = 0.0
		for ob in self.scene.objects:
			if not 'Widget' in ob or not ob.is_visible or not ob.sensitive:
				continue
			ob_dir = ob.worldPosition - loc
			dist = ob_dir.magnitude
			if dist == 0.0:
				continue
			score_dist = 1.0 / (dist * dist)

			ob_dir.normalize()
			score_dir = ob_dir.dot(world_direction)
			if score_dir < 0.0:
				continue
			score_dir = math.pow(score_dir, 0.5)

			score = score_dir * score_dist
			if score > best_score:
				best_score = score
				best_widget = ob

		return best_widget


################
# Widget classes
################

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
		self['Widget'] = True
		self.show()

		bxt.types.EventBus().add_listener(self)
		bxt.types.EventBus().replay_last(self, 'showScreen')

	def enter(self):
		if not self.sensitive:
			return
		if self.has_state(Widget.S_FOCUS):
			return
		self.add_state(Widget.S_FOCUS)
		self.rem_state(Widget.S_DEFOCUS)
		self.updateTargetFrame()

	def leave(self):
		if not self.has_state(Widget.S_FOCUS):
			return
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

		elif evt.message == 'FocusChanged':
			if evt.body is not self:
				self.leave()
			else:
				self.enter()

	def hide(self):
		self.setVisible(False, False)
		self.add_state(Widget.S_HIDDEN)
		self.rem_state(Widget.S_VISIBLE)
		self.rem_state(Widget.S_DOWN)
		self.rem_state(Widget.S_FOCUS)
		self.updateTargetFrame()
		self.is_visible = False

	def show(self):
		self.setVisible(True, False)
		self.add_state(Widget.S_VISIBLE)
		self.rem_state(Widget.S_HIDDEN)
		self.updateTargetFrame()
		self.is_visible = True

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
			bxt.types.Event('pushScreen', 'ConfirmationDialogue').send()

		elif event.message == 'confirm':
			if self.visible:
				bxt.types.Event('popScreen').send()
				bxt.types.Event(self.onConfirm, self.onConfirmBody).send()
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

class MenuSnail(bxt.types.BX_GameObject, bge.types.KX_GameObject):

	def __init__(self, old_owner):
		arm = bxt.types.add_and_mutate_object(self.scene, "SlugArm_Min",
				self.children["SlugSpawnPos"])
		arm.setParent(self)
		arm.look_at("Camera")
		arm.playAction("MenuSnail_Rest", 1, 1)
		self.arm = arm
		#self.arm.localScale = (0.75, 0.75, 0.75)

		bxt.types.EventBus().add_listener(self)

	def on_event(self, evt):
		if evt.message == "FocusChanged":
			if evt.body is None:
				self.arm.look_at("Camera")
			else:
				self.arm.look_at(evt.body)

