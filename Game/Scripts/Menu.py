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

from . import Utilities
from bge import logic
from bge import render
import mathutils
from . import Store

DEBUG = False

CREDITS = [
    ("Most Things", "Alex Fraser"),
    ("Story", "Alex Fraser, Lara Micocki"),
    ("Music", "Robert Leigh"),
    ("Sound Effects", "Alex Fraser, freesound.org users: anamorphosis, tigersound, HerbertBoland, MeltyMcFace, kijjaz, arnaud, FreqMan"),
    ("Testing", "Jodie Fraser, Lachlan Kanaley, Damien Elmes, Mark Triggs"),
    ("Made With", "Blender, Bullet, The GIMP and Inkscape")]

class EventListener:
    '''Interface for an object that can receive messages.'''
    def onEvent(self, sender, message, body):
        pass

@Utilities.singleton
class EventBus:
    '''Delivers messages to listeners.'''
    
    def __init__(self):
        self.listeners = set()
        self.eventCache = {}

    def addListener(self, listener):
        self.listeners.add(listener)
    
    def remListener(self, listener):
        self.listeners.remove(listener)
    
    def notify(self, sender, message, body):
        '''Send a message.'''
        
        if DEBUG:
            print("Message: %s\n\t%s" % (message, body))

        for listener in self.listeners:
            listener.onEvent(sender, message, body)
        self.eventCache[message] = (sender, body)
    
    def replayLast(self, target, message):
        '''Re-send a message. This should be used by new listeners that missed
        out on the last message, so they know what state the system is in.'''
        
        if message in self.eventCache:
            sender, body = self.eventCache[message]
            target.onEvent(sender, message, body)

@Utilities.singleton
class SessionManager(EventListener):
    '''Responds to some high-level messages.'''
    
    def __init__(self):
        EventBus().addListener(self)
    
    def onEvent(self, sender, message, body):
        if message == 'showSavedGameDetails':
            Store.setSessionId(body)
            EventBus().notify(self, 'showScreen', 'LoadDetailsScreen')
        
        elif message == 'startGame':
            # Load the level indicated in the save game.
            logic.startGame(Store.get('/game/level', 'Outdoors.blend'))
        
        elif message == 'deleteGame':
            # Remove all stored items that match the current path.
            for key in Store.list('/game'):
                Store.unset(key)
            EventBus().notify(self, 'showScreen', 'LoadingScreen')
        
        elif message == 'quit':
            logic.endGame()

# Nothing else uses this directly, so we have to instantiate it.
SessionManager()

@Utilities.singleton
class InputHandler(EventListener):
    '''Manages UI elements: focus and click events.'''
    
    def __init__(self):
        self.widgets = []
        self.current = None
        self.downCurrent = None
    
    def addWidget(self, widget):
        self.widgets.append(widget)
    
    def mouseOver(self, mOver):
        newFocus = mOver.hitObject
        
        # Bubble up to ancestor if need be
        while newFocus != None:
            if 'Widget' in newFocus:
                break
            newFocus = newFocus.parent
        
        if newFocus == self.current:
            return
        
        if self.current != None and not self.current.invalid:
            self.current['Widget'].exit()
        if newFocus != None:
            newFocus['Widget'].enter()
        self.current = newFocus
    
    def mouseDown(self):
        '''Send a mouse down event to the widget under the cursor.'''
        if self.current != None:
            self.current['Widget'].down()
            self.downCurrent = self.current
    
    def mouseUp(self):
        '''Send a mouse up event to the widget under the cursor. If that widget
        also received the last mouse down event, it will be sent a click event
        in addition to (after) the up event.'''
        if self.downCurrent != None:
            self.downCurrent['Widget'].up()
            if self.current == self.downCurrent:
                self.downCurrent['Widget'].click()
        self.downCurrent = None
    
    def onEvent(self, sender, message, body):
        if message == 'sensitivityChanged':
            # Not implemented. Eventually, this should update the visual state
            # of the current button.
            pass

    def focusNext(self):
        '''Switch to the next widget according to tab-order.'''
        # TODO
        pass
    def focusPrevious(self):
        '''Switch to the previous widget according to tab-order.'''
        # TODO
        pass
    def focusLeft(self):
        '''Switch to the widget to the left of current.'''
        # TODO
        pass
    def focusRight(self):
        '''Switch to the widget to the right of current.'''
        # TODO
        pass
    def focusUp(self):
        '''Switch to the widget above current.'''
        # TODO
        pass
    def focusDown(self):
        '''Switch to the widget below current.'''
        # TODO
        pass

@Utilities.singleton
class AsyncAdoptionHelper:
    '''Creates parent-child relationships between widgets asynchronously. This
    is required because the order that widgets are created in is undefined.'''
    
    def __init__(self):
        self.waitingList = {}
        self.containers = {}
    
    def requestAdoption(self, child, parentName):
        '''Add a child to the registry. If the child's parent is already
        registered, the hierarchy will be implemented immediately. Otherwise,
        the child will be attached later, when the parent registers.'''
        
        if parentName in self.containers:
            container = self.containers[parentName]
            container.addChild(child)
        else:
            if not parentName in self.waitingList:
                self.waitingList[parentName] = []
            self.waitingList[parentName].append(child)
    
    def registerAdopter(self, parent):
        '''Add a parent to the registry. Any children waiting for this parent
        will be attached.'''
        
        self.containers[parent.name] = parent
        
        # Assign all children waiting on this container.
        if parent.name in self.waitingList:
            for child in self.waitingList[parent.name]:
                parent.addChild(child)
            del self.waitingList[parent.name]

################
# Global sensors
################

@Utilities.controller
def controllerInit(c):
    '''Initialise the menu'''
    render.showMouse(True)
    mOver = c.sensors['sMouseOver']
    mOver.usePulseFocus = True

@Utilities.all_sensors_positive
def focusNext():
    InputHandler().focusNext()

@Utilities.all_sensors_positive
def focusPrevious():
    InputHandler().focusPrevious()

@Utilities.all_sensors_positive
def focusLeft():
    InputHandler().focusLeft()

@Utilities.all_sensors_positive
def focusRight():
    InputHandler().focusRight()

@Utilities.all_sensors_positive
def focusUp():
    InputHandler().focusUp()

@Utilities.all_sensors_positive
def focusDown():
    InputHandler().focusDown()

@Utilities.all_sensors_positive
@Utilities.controller
def mouseMove(c):
    mOver = c.sensors['sMouseOver']
    InputHandler().mouseOver(mOver)

def mouseButton(c):
    if Utilities.someSensorPositive():
        InputHandler().mouseDown()
    else:
        InputHandler().mouseUp()

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
        self.children = []
        self.name = name
        AsyncAdoptionHelper().registerAdopter(self)
    
    def addChild(self, uiObject):
        '''Adds a child to this container. Usually you should use the
        asyncAdoptionHandler instead of calling this directly.'''
        self.children.append(uiObject)
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

class Screen(Container, EventListener):
    '''A collection of UIObjects. Only one screen can be visible at a time. To
    display a Screen, send a showScreen message on the EventBus.'''
    
    def __init__(self, name, title):
        Container.__init__(self, name)
        EventBus().addListener(self)
        self.title = title
    
    def onEvent(self, sender, message, body):
        if message == 'showScreen':
            if body == self.name:
                self.show()
                EventBus().notify(self, 'screenShown', self.getTitle())
            else:
                self.hide()
    
    def getTitle(self):
        return self.title
        
Screen('LoadingScreen', 'Load')
Screen('LoadDetailsScreen', '')
Screen('OptionsScreen', 'Options')
Screen('CreditsScreen', 'Credits')
Screen('ConfirmationDialogue', 'Confirm')
EventBus().notify(None, 'showScreen', 'LoadingScreen')

class Camera(EventListener):
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
        self.owner = owner
        self.owner['Camera'] = self
        EventBus().addListener(self)
        EventBus().replayLast(self, 'showScreen')
    
    def onEvent(self, sender, message, body):
        if message == 'showScreen' and body in Camera.FRAME_MAP:
            self.owner['targetFrame'] = Camera.FRAME_MAP[body]
    
    def update(self):
        '''Update the camera animation frame. Should be called once per frame
        when targetFrame != frame.'''
        
        targetFrame = self.owner['targetFrame']
        frame = self.owner['frame']
        if frame < targetFrame:
            frame = min(frame + Camera.FRAME_RATE, targetFrame)
        else:
            frame = max(frame - Camera.FRAME_RATE, targetFrame)
        self.owner['frame'] = frame

@Utilities.owner
def createCamera(o):
    Camera(o)

@Utilities.owner
def updateCamera(o):
    o['Camera'].update()

class Widget(UIObject):
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
        self.owner = owner
        self.sensitive = True
        self.active = False
        self.owner['Widget'] = self
        self.state = Widget.S_HIDDEN
        
        Utilities.parseChildren(self, owner)
        
        if 'parentName' in self.owner:
            AsyncAdoptionHelper().requestAdoption(self, self.owner['parentName'])
        
    def parseChild(self, child, type):
        # No children of basic widgets. Note: this is about object hierarchies
        # the Blender scene, which is different to the Container-UIObject
        # relationship.
        return False
    
    def enter(self):
        if not self.sensitive:
            return
        Utilities.addState(self.owner, Widget.S_FOCUS)
        Utilities.remState(self.owner, Widget.S_DEFOCUS)
        self.updateTargetFrame()
    
    def exit(self):
        Utilities.remState(self.owner, Widget.S_FOCUS)
        Utilities.addState(self.owner, Widget.S_DEFOCUS)
        self.updateTargetFrame()
    
    def down(self):
        if not self.sensitive:
            return
        Utilities.addState(self.owner, Widget.S_DOWN)
        Utilities.remState(self.owner, Widget.S_UP)
        self.updateTargetFrame()
    
    def up(self):
        Utilities.remState(self.owner, Widget.S_DOWN)
        Utilities.addState(self.owner, Widget.S_UP)
        self.updateTargetFrame()
    
    def click(self):
        if not self.sensitive:
            return
        if 'onClickMsg' in self.owner:
            msg = self.owner['onClickMsg']
            body = ''
            if 'onClickBody' in self.owner:
                body = self.owner['onClickBody']
            EventBus().notify(self, msg, body)
    
    def hide(self):
        super(Widget, self).hide()
        Utilities.addState(self.owner, Widget.S_HIDDEN)
        Utilities.remState(self.owner, Widget.S_VISIBLE)
        Utilities.remState(self.owner, Widget.S_DOWN)
        Utilities.remState(self.owner, Widget.S_FOCUS)
        self.updateTargetFrame()
    
    def show(self):
        super(Widget, self).show()
        Utilities.remState(self.owner, Widget.S_HIDDEN)
        Utilities.addState(self.owner, Widget.S_VISIBLE)
        self.updateTargetFrame()
    
    def updateTargetFrame(self):
        targetFrame = Widget.IDLE_FRAME
        if Utilities.hasState(self.owner, Widget.S_HIDDEN):
            targetFrame = Widget.HIDDEN_FRAME
        elif Utilities.hasState(self.owner, Widget.S_FOCUS):
            if Utilities.hasState(self.owner, Widget.S_DOWN):
                targetFrame = Widget.ACTIVE_FRAME
            else:
                targetFrame = Widget.FOCUS_FRAME
        else:
            targetFrame = Widget.IDLE_FRAME
        self.owner['targetFrame'] = targetFrame
    
    def update(self):
        targetFrame = self.owner['targetFrame']
        frame = self.owner['frame']
        oldFrame = frame
        if frame < targetFrame:
            frame = min(frame + Widget.FRAME_RATE, targetFrame)
        else:
            frame = max(frame - Widget.FRAME_RATE, targetFrame)
        self.owner['frame'] = frame
        
        if frame == 1.0:
            self.updateVisibility(False)
        elif oldFrame == 1.0:
            self.updateVisibility(True)
    
    def updateVisibility(self, visible):
        self.owner.setVisible(visible, True)
    
    def setSensitive(self, sensitive):
        oldv = self.sensitive
        self.sensitive = sensitive
        if oldv != sensitive:
            EventBus().notify(self, 'sensitivityChanged', self.sensitive)

@Utilities.controller
def updateWidget(c):
    c.owner['Widget'].update()
    c.activate(c.actuators[0])

class Button(Widget):
    # A Widget has everything needed for a simple button.
    def __init__(self, owner):
        Widget.__init__(self, owner)

@Utilities.owner
def createButton(o):
    InputHandler().addWidget(Button(o))

class SaveButton(Button):
    def __init__(self, owner):
        Button.__init__(self, owner)
        self.id = 0
    
    def parseChild(self, child, type):
        if type == 'IDCanvas':
            self.idCanvas = child
            return True
        else:
            return False
        
    def updateVisibility(self, visible):
        super(SaveButton, self).updateVisibility(visible)
        self.idCanvas.setVisible(visible, True)

@Utilities.owner
def createSaveButton(o):
    obj = Utilities.replaceObject('SaveButton_T', o)
    button = SaveButton(obj)
    InputHandler().addWidget(button)

@Utilities.gameobject()
class Checkbox(Button):
    def __init__(self, owner):
        Button.__init__(self, owner)
        self.checked = False
        if 'dataBinding' in self.owner:
            self.checked = Store.get(self.owner['dataBinding'], self.owner['dataDefault'])
        self.updateCheckFace()
        self.label['Content'] = self.owner['label']
        self.label['colour'] = self.owner['colour']
        InputHandler().addWidget(self)
    
    def parseChild(self, child, type):
        if type == 'CheckOff':
            self.checkOff = child
            return True
        elif type == 'CheckOn':
            self.checkOn = child
            return True
        elif type == 'Canvas':
            self.label = child
            return True
        else:
            return False
    
    def click(self):
        self.checked = not self.checked
        self.updateCheckFace()
        if 'dataBinding' in self.owner:
            Store.set(self.owner['dataBinding'], self.checked)
        super(Checkbox, self).click()
    
    def updateVisibility(self, visible):
        super(Checkbox, self).updateVisibility(visible)
        self.label.setVisible(visible, True)
        self.updateCheckFace()
    
    def updateCheckFace(self):
        if self.visible:
            self.checkOff.setVisible(not self.checked, True)
            self.checkOn.setVisible(self.checked, True)
        else:
            self.checkOff.setVisible(False, True)
            self.checkOn.setVisible(False, True)
    
    def update(self):
        super(Checkbox, self).update()
        self.checkOff['frame'] = self.owner['frame']
        self.checkOn['frame'] = self.owner['frame']

@Utilities.gameobject()
class ConfirmationPage(Widget, EventListener):
    def __init__(self, owner):
        Widget.__init__(self, owner)
        self.setSensitive(False)
        
        self.lastScreen = ''
        self.currentScreen = ''
        self.onConfirm = ''
        self.onConfirmBody = ''
        
        EventBus().addListener(self)
        EventBus().replayLast(self, 'showScreen')
    
    def parseChild(self, child, type):
        if type == 'Text':
            self.text = child
            return True
        else:
            return False
    
    def onEvent(self, sender, message, body):
        super(ConfirmationPage, self).onEvent(sender, message, body)
        if message == 'showScreen':
            # Store the last screen name so it can be restored later.
            if self.currentScreen != body:
                self.lastScreen = self.currentScreen
                self.currentScreen = body
        
        elif message == 'confirmation':
            text, self.onConfirm, self.onConfirmBody = body.split('::')
            self.text['Content'] = text
            EventBus().notify(self, 'showScreen', 'ConfirmationDialogue')
            
        elif message == 'cancel':
            if self.visible:
                EventBus().notify(self, 'showScreen', self.lastScreen)
                self.text['Content'] = ""
        
        elif message == 'confirm':
            if self.visible:
                EventBus().notify(self, 'showScreen', self.lastScreen)
                EventBus().notify(self, self.onConfirm, self.onConfirmBody)
                self.text['Content'] = ""

@Utilities.gameobject()
class GameDetailsPage(Widget):
    '''A dumb widget that can show and hide itself, but doesn't respond to
    mouse events.'''
    def __init__(self, owner):
        Widget.__init__(self, owner)
        self.setSensitive(False)
    
    def parseChild(self, child, type):
        if type == 'Title':
            self.title = child
            return True
        elif type == 'StoryDetails':
            self.storyDetails = child
            return True
        else:
            return False
    
    def updateVisibility(self, visible):
        super(GameDetailsPage, self).updateVisibility(visible)
        for child in self.owner.children:
            child.setVisible(visible, True)
        
        if visible:
            self.title['Content'] = Store.get('/game/title', 'Game %d' % (Store.getSessionId() + 1))
            self.storyDetails['Content'] = Store.get('/game/storySummary', 'Start a new game.')

@Utilities.gameobject('draw')
class CreditsPage(Widget):
    '''Controls the display of credits.'''
    DELAY = 180
    
    def __init__(self, owner):
        Widget.__init__(self, owner)
        self.setSensitive(False)
        self.index = 0
        self.delayTimer = 0
    
    def parseChild(self, child, type):
        if type == 'Role':
            self.title = child
            return True
        if type == 'People':
            self.people = child
            return True
        else:
            return False
    
    def updateVisibility(self, visible):
        super(CreditsPage, self).updateVisibility(visible)
        for child in self.owner.children:
            child.setVisible(visible, True)
        
        if not visible:
            self.title['Content'] = ""
            self.people['Content'] = ""
            self.index = 0
            self.delayTimer = 0
    
    def drawNext(self):
        role, people = CREDITS[self.index]
        self.title['Content'] = role
        self.people['Content'] = people
        self.index += 1
        self.index %= len(CREDITS)
    
    def draw(self):
        if self.people['Rendering'] or self.title['Rendering']:
            self.delayTimer = CreditsPage.DELAY
        else:
            self.delayTimer -= 1
            if self.delayTimer <= 0:
                self.drawNext()

@Utilities.gameobject()
class Subtitle(EventListener):
    def __init__(self, owner):
        self.owner = owner
        EventBus().addListener(self)
        EventBus().replayLast(self, 'screenShown')
    
    def onEvent(self, sender, message, body):
        if message == 'screenShown':
            self.owner['Content'] = body

@Utilities.gameobject('update')
class MenuSnail:
    def __init__(self, owner):
        self.owner = owner
        self.armature = self.owner.children['SnailArm_Min']
        self.EyeLocL = self.armature.children['Eyeref_L']
        self.EyeLocR = self.armature.children['Eyeref_R']
        self.HeadLoc = self.armature.children['HeadLoc']
        # Store the current orientation of the head bone. This is used to
        # reduce the movement of the head, so that the eyes do most of the
        # turning.
        self.HeadLoc_rest = mathutils.Quaternion(self.armature.channels[
                self.HeadLoc['channel']].rotation_quaternion)
    
    def update(self):
        target = None
        if InputHandler().current:
            target = InputHandler().current
        else:
            target = logic.getCurrentScene().objects['Camera']
        self.lookAt(target)
    
    def lookAt(self, target):
        '''Turn the eyes to face the target.'''
        # This code is similar to Snail.Snail.lookAt. But there's probably not
        # much scope for reuse.

        def look(bone, target, restOrn = None):
            channel = self.armature.channels[bone['channel']]
            _, gVec, _ = bone.getVectTo(target)
            bone.alignAxisToVect(bone.parent.getAxisVect(Utilities.ZAXIS), 2)
            bone.alignAxisToVect(gVec, 1)
            orn = bone.localOrientation.to_quat()
            
            if restOrn:
                orn = orn.slerp(restOrn, 0.6)
            
            oldOrn = mathutils.Quaternion(channel.rotation_quaternion)
            channel.rotation_quaternion = oldOrn.slerp(orn, 0.1)
        
        look(self.EyeLocL, target)
        look(self.EyeLocR, target)
        look(self.HeadLoc, target, self.HeadLoc_rest)
        
        self.armature.update()
