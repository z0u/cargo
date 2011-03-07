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

import bxt
from . import Store

from bge import logic
from bge import render
import mathutils

import weakref

CREDITS = [
	("Most Things", "Alex Fraser"),
	("Story", "Alex Fraser, Lara Micocki"),
	("Music", "Robert Leigh"),
	("Sound Effects", "Alex Fraser, freesound.org users: anamorphosis, tigersound, HerbertBoland, MeltyMcFace, kijjaz, arnaud, FreqMan"),
	("Testing", "Jodie Fraser, Lachlan Kanaley, Damien Elmes, Mark Triggs"),
	("Made With", "Blender, Bullet, The GIMP and Inkscape")]

@bxt.utils.singleton()
class SessionManager(bxt.utils.EventListener):
	'''Responds to some high-level messages.'''
	
	def __init__(self):
		bxt.utils.EventBus().addListener(self)
	
	def onEvent(self, event):
		if event.message == 'showSavedGameDetails':
			Store.setSessionId(event.body)
			evt = bxt.utils.Event('showScreen', 'LoadDetailsScreen')
			bxt.utils.EventBus().notify(evt)
		
		elif event.message == 'startGame':
			# Load the level indicated in the save game.
			logic.startGame(Store.get('/game/level', 'Outdoors.blend'))
		
		elif event.message == 'deleteGame':
			# Remove all stored items that match the current path.
			for key in Store.list('/game'):
				Store.unset(key)
			evt = bxt.utils.Event('showScreen', 'LoadingScreen')
			bxt.utils.EventBus().notify(evt)
		
		elif event.message == 'quit':
			logic.endGame()

@bxt.utils.singleton('focusNext', 'focusPrevious', 'focusUp', 'focusDown',
					'focusLeft', 'focusRight', 'mouseMove', 'mouseButton',
					prefix='IH_')
class InputHandler(bxt.utils.EventListener):
	'''Manages UI elements: focus and click events.'''
	
	def __init__(self):
		self.widgets = weakref.WeakSet()
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

	@bxt.utils.all_sensors_positive
	@bxt.utils.controller_cls
	def mouseMove(self, c):
		mOver = c.sensors['sMouseOver']
		InputHandler().mouseOver(mOver)

	def mouseOver(self, mOver):
		newFocus = mOver.hitObject

		# Bubble up to ancestor if need be
		while newFocus != None:
			if 'Widget' in newFocus:
				break
			newFocus = newFocus.parent

		if newFocus != None:
			newFocus = bxt.types.get_wrapper(newFocus)

		if newFocus == self.current:
			return

		if self.current:
			self.current.exit()
		if newFocus != None:
			newFocus.enter()
		self.current = newFocus

	@bxt.utils.controller_cls
	def mouseButton(self, c):
		if bxt.utils.someSensorPositive():
			InputHandler().mouseDown()
		else:
			InputHandler().mouseUp()
	
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
	
	def onEvent(self, event):
		if event.message == 'sensitivityChanged':
			# Not implemented. Eventually, this should update the visual state
			# of the current button.
			pass

	@bxt.utils.all_sensors_positive
	def focusNext(self):
		'''Switch to the next widget according to tab-order.'''
		# TODO
		pass

	@bxt.utils.all_sensors_positive
	def focusPrevious(self):
		'''Switch to the previous widget according to tab-order.'''
		# TODO
		pass

	@bxt.utils.all_sensors_positive
	def focusLeft(self):
		'''Switch to the widget to the left of current.'''
		# TODO
		pass

	@bxt.utils.all_sensors_positive
	def focusRight(self):
		'''Switch to the widget to the right of current.'''
		# TODO
		pass

	@bxt.utils.all_sensors_positive
	def focusUp(self):
		'''Switch to the widget above current.'''
		# TODO
		pass

	@bxt.utils.all_sensors_positive
	def focusDown(self):
		'''Switch to the widget below current.'''
		# TODO
		pass

@bxt.utils.singleton()
class AsyncAdoptionHelper:
	'''Creates parent-child relationships between widgets asynchronously. This
	is required because the order that widgets are created in is undefined.'''
	
	def __init__(self):
		self.pendingChildren = {}
		self.containers = weakref.WeakValueDictionary()
	
	def requestAdoption(self, child, parentName):
		'''Add a child to the registry. If the child's parent is already
		registered, the hierarchy will be implemented immediately. Otherwise,
		the child will be attached later, when the parent registers.'''
		
		if parentName in self.containers:
			container = self.containers[parentName]
			container.addChild(child)
		else:
			if not parentName in self.pendingChildren:
				self.pendingChildren[parentName] = weakref.WeakSet()
			self.pendingChildren[parentName].add(child)
	
	def registerAdopter(self, parent):
		'''Add a parent to the registry. Any children pendingChildren for this parent
		will be attached.'''
		
		self.containers[parent.name] = parent
		
		# Assign all children pendingChildren on this container.
		if parent.name in self.pendingChildren:
			for child in self.pendingChildren[parent.name]:
				parent.addChild(child)
			del self.pendingChildren[parent.name]

################
# Global sensors
################

@bxt.utils.controller
def controllerInit(c):
	'''Initialise the menu'''
	render.showMouse(True)
	mOver = c.sensors['sMouseOver']
	mOver.usePulseFocus = True

################
# Widget classes
################

class UIObject:
	'''A visual object that has some dynamic properties.'''
	
	def __init__(self):
		self.show()
	
	def show(self):
		self.visible = True
	
	def hide(self):
		self.visible = False

class Container(UIObject):
	'''Contains other UIObjects.'''
	
	def __init__(self, name):
		self.children = weakref.WeakSet()
		self.name = name
		AsyncAdoptionHelper().registerAdopter(self)
	
	def addChild(self, uiObject):
		'''Adds a child to this container. Usually you should use the
		asyncAdoptionHandler instead of calling this directly.'''
		self.children.add(uiObject)
		if self.visible:
			uiObject.show()
		else:
			uiObject.hide()
	
	def show(self):
		super(Container, self).show()
		for child in self.children:
			child.show()
	
	def hide(self):
		super(Container, self).hide()
		for child in self.children:
			child.hide()

class Screen(Container, bxt.utils.EventListener):
	'''A collection of UIObjects. Only one screen can be visible at a time. To
	display a Screen, send a showScreen message on the EventBus.'''
	
	def __init__(self, name, title):
		Container.__init__(self, name)
		bxt.utils.EventBus().addListener(self)
		self.title = title
	
	def onEvent(self, event):
		if event.message == 'showScreen':
			if event.body == self.name:
				self.show()
				evt = bxt.utils.Event('screenShown', self.getTitle())
				bxt.utils.EventBus().notify(evt)
			else:
				self.hide()
	
	def getTitle(self):
		return self.title

# These need to be stored in a list - the EventBus only keeps weak references to
# listeners.
screens = []
screens.append(Screen('LoadingScreen', 'Load'))
screens.append(Screen('LoadDetailsScreen', ''))
screens.append(Screen('OptionsScreen', 'Options'))
screens.append(Screen('CreditsScreen', 'Credits'))
screens.append(Screen('ConfirmationDialogue', 'Confirm'))
bxt.utils.EventBus().notify(
		bxt.utils.Event('showScreen', 'LoadingScreen'))

@bxt.types.gameobject('update', prefix='cam_')
class Camera(bxt.utils.EventListener, bxt.types.ProxyGameObject):
	'''A camera that adjusts its position depending on which screen is
	visible.'''
	
	FRAME_MAP = {'OptionsScreen': 1.0,
				 'LoadingScreen': 9.0,
				 'CreditsScreen': 17.0}
	'''A simple mapping is used here. The camera will interpolate between the
	nominated frame numbers when the screen changes. Set the animation using
	an f-curve.'''
		
	FRAME_RATE = 25.0 / logic.getLogicTicRate()
	
	def __init__(self, owner):
		bxt.types.ProxyGameObject.__init__(self, owner)
		bxt.utils.EventBus().addListener(self)
		bxt.utils.EventBus().replayLast(self, 'showScreen')
	
	def onEvent(self, event):
		if event.message == 'showScreen' and event.body in Camera.FRAME_MAP:
			self['targetFrame'] = Camera.FRAME_MAP[event.body]
	
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

@bxt.types.gameobject('update')
class Widget(UIObject, bxt.types.ProxyGameObject):
	'''An interactive UIObject. Has various states (e.g. focused, up, down) to
	facilitate interaction. Some of the states map to a frame to allow a
	visual progression.'''
	
	S_FOCUS = 2
	S_DEFOCUS = 3
	S_DOWN = 4
	S_UP = 5
	S_HIDDEN = 6
	S_VISIBLE = 7
	
	FRAME_RATE = 25.0 / logic.getLogicTicRate()
	
	# These should be matched to the FCurve or action of the object associated
	# with this widget. The animation is not actually driven by this script; it
	# just sets the object's 'frame' property, which should be observed by an
	# actuator.
	HIDDEN_FRAME = 1.0
	IDLE_FRAME = 5.0
	FOCUS_FRAME = 9.0
	ACTIVE_FRAME = 12.0
	
	def __init__(self, owner):
		bxt.types.ProxyGameObject.__init__(self, owner)
		self.sensitive = True
		self.active = False
		self['Widget'] = True
		self.show()
		
		if 'parentName' in self:
			AsyncAdoptionHelper().requestAdoption(self, self['parentName'])

		InputHandler().addWidget(self)
	
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
			evt = bxt.utils.Event(msg, body)
			bxt.utils.EventBus().notify(evt)
	
	def hide(self):
		UIObject.hide(self)
		self.add_state(Widget.S_HIDDEN)
		self.rem_state(Widget.S_VISIBLE)
		self.rem_state(Widget.S_DOWN)
		self.rem_state(Widget.S_FOCUS)
		self.updateTargetFrame()
	
	def show(self):
		UIObject.show(self)
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

		c = logic.getCurrentController()
		c.activate(c.actuators[0])
	
	def updateVisibility(self, visible):
		self.setVisible(visible, True)
	
	def setSensitive(self, sensitive):
		oldv = self.sensitive
		self.sensitive = sensitive
		if oldv != sensitive:
			evt = bxt.utils.Event('sensitivityChanged', self.sensitive)
			bxt.utils.EventBus().notify(evt)

@bxt.types.gameobject()
class Button(Widget):
	# A Widget has everything needed for a simple button.
	def __init__(self, owner):
		Widget.__init__(self, owner)

@bxt.types.gameobject()
class SaveButton(Button):
	def __init__(self, owner):
		Button.__init__(self, owner)
		self.id = 0
		
	def updateVisibility(self, visible):
		super(SaveButton, self).updateVisibility(visible)
		self.children['IDCanvas'].setVisible(visible, True)

@bxt.types.gameobject()
class Checkbox(Button):
	def __init__(self, owner):
		Button.__init__(self, owner)
		self.checked = False
		if 'dataBinding' in self:
			self.checked = Store.get(self['dataBinding'], self['dataDefault'])
		self.updateCheckFace()
		self.children['Canvas']['Content'] = self['label']
		self.children['Canvas']['colour'] = self['colour']
	
	def click(self):
		self.checked = not self.checked
		self.updateCheckFace()
		if 'dataBinding' in self:
			Store.set(self['dataBinding'], self.checked)
		super(Checkbox, self).click()
	
	def updateVisibility(self, visible):
		super(Checkbox, self).updateVisibility(visible)
		self.children['Canvas'].setVisible(visible, True)
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

@bxt.types.gameobject()
class ConfirmationPage(Widget, bxt.utils.EventListener):
	def __init__(self, owner):
		Widget.__init__(self, owner)
		self.setSensitive(False)
		
		self.lastScreen = ''
		self.currentScreen = ''
		self.onConfirm = ''
		self.onConfirmBody = ''
		
		bxt.utils.EventBus().addListener(self)
		bxt.utils.EventBus().replayLast(self, 'showScreen')
	
	def onEvent(self, event):
		super(ConfirmationPage, self).onEvent(event)
		if event.message == 'showScreen':
			# Store the last screen name so it can be restored later.
			if self.currentScreen != event.body:
				self.lastScreen = self.currentScreen
				self.currentScreen = event.body
		
		elif event.message == 'confirmation':
			text, self.onConfirm, self.onConfirmBody = event.body.split('::')
			self.children['ConfirmText']['Content'] = text
			evt = bxt.utils.Event('showScreen', 'ConfirmationDialogue')
			bxt.utils.EventBus().notify(evt)
			
		elif event.message == 'cancel':
			if self.visible:
				evt = bxt.utils.Event('showScreen', self.lastScreen)
				bxt.utils.EventBus().notify(evt)
				self.children['ConfirmText']['Content'] = ""
		
		elif event.message == 'confirm':
			if self.visible:
				evt = bxt.utils.Event('showScreen', self.lastScreen)
				bxt.utils.EventBus().notify(evt)
				evt = bxt.utils.Event(self.onConfirm, self.onConfirmBody)
				bxt.utils.EventBus().notify(evt)
				self.children['ConfirmText']['Content'] = ""

@bxt.types.gameobject()
class GameDetailsPage(Widget):
	'''A dumb widget that can show and hide itself, but doesn't respond to
	mouse events.'''
	def __init__(self, owner):
		Widget.__init__(self, owner)
		self.setSensitive(False)
	
	def updateVisibility(self, visible):
		super(GameDetailsPage, self).updateVisibility(visible)
		for child in self.children:
			child.setVisible(visible, True)
		
		if visible:
			self.children['GameName']['Content'] = Store.get(
				'/game/title', 'Game %d' % (Store.getSessionId() + 1))
			self.children['StoryDetails']['Content'] = Store.get(
				'/game/storySummary', 'Start a new game.')

@bxt.types.gameobject('draw')
class CreditsPage(Widget):
	'''Controls the display of credits.'''
	DELAY = 180
	
	def __init__(self, owner):
		Widget.__init__(self, owner)
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
	
	def draw(self):
		if self.children['People']['Rendering'] or self.children['Role']['Rendering']:
			self.delayTimer = CreditsPage.DELAY
		else:
			self.delayTimer -= 1
			if self.delayTimer <= 0:
				self.drawNext()

@bxt.types.gameobject()
class Subtitle(bxt.utils.EventListener, bxt.types.ProxyGameObject):
	def __init__(self, owner):
		bxt.types.ProxyGameObject.__init__(self, owner)
		bxt.utils.EventBus().addListener(self)
		bxt.utils.EventBus().replayLast(self, 'screenShown')
	
	def onEvent(self, event):
		if event.message == 'screenShown':
			self['Content'] = event.body

@bxt.types.gameobject('update')
class MenuSnail(bxt.types.ProxyGameObject):
	def __init__(self, owner):
		bxt.types.ProxyGameObject.__init__(self, owner)
		self.armature = self.children['SnailArm_Min']
		self.EyeLocL = self.armature.children['Eyeref_L']
		self.EyeLocR = self.armature.children['Eyeref_R']
		self.HeadLoc = self.armature.children['HeadLoc']
		# Store the current orientation of the head bone. This is used to
		# reduce the movement of the head, so that the eyes do most of the
		# turning.
		self.HeadLoc_rest = mathutils.Quaternion(self.armature.channels[
				self.HeadLoc['channel']].rotation_quaternion)
	
	def update(self):
		target = InputHandler().current
		if not target:
			target = logic.getCurrentScene().objects['Camera']
		self.lookAt(target)
	
	def lookAt(self, target):
		'''Turn the eyes to face the target.'''
		# This code is similar to Snail.Snail.lookAt. But there's probably not
		# much scope for reuse.

		def look(bone, target, restOrn = None):
			channel = self.armature.channels[bone['channel']]
			_, gVec, _ = bone.getVectTo(bxt.types.unwrap(target))
			bone.alignAxisToVect(bone.parent.getAxisVect(bxt.math.ZAXIS), 2)
			bone.alignAxisToVect(gVec, 1)
			orn = bone.localOrientation.to_quaternion()
			
			if restOrn:
				orn = orn.slerp(restOrn, 0.6)
			
			oldOrn = mathutils.Quaternion(channel.rotation_quaternion)
			channel.rotation_quaternion = oldOrn.slerp(orn, 0.1)
		
		look(self.EyeLocL, target)
		look(self.EyeLocR, target)
		look(self.HeadLoc, target, self.HeadLoc_rest)
		
		self.armature.update()
