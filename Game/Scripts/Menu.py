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

import Utilities
from bge import render
from bge import logic

class EventListener:
    def onEvent(self, sender, message, body = None):
        pass

class _EventBus:
    def __init__(self):
        self.listeners = set()

    def addListener(self, listener):
        self.listeners.add(listener)
    
    def remListener(self, listener):
        self.listeners.remove(listener)
    
    def notify(self, sender, message, body):
        print('Event "%s" from "%s": %s' % (message, sender, body))
        for listener in self.listeners:
            listener.onEvent(sender, message, body)

eventBus = _EventBus()

class _InputHandler:
    def __init__(self):
        self.widgets = []
        self.current = None
        self.downCurrent = None
        self.savedGames = []
    
    def addWidget(self, widget):
        self.widgets.append(widget)
        
        if 'Type' in widget.owner and widget.owner['Type'] == 'SaveButton':
            self.savedGames.append(widget)
            if len(self.savedGames) == 3:
                self.initSaveButtons()
    
    def initSaveButtons(self):
        self.savedGames.sort(key=Utilities.ZKeyActor())
        self.savedGames.reverse()
        #for i, button in enumerate(self.savedGames):
        for i, button in zip([1, 'new', 'new'], self.savedGames):
            button.setId(i)
    
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
        in addition to the up event.'''
        if self.downCurrent != None:
            self.downCurrent['Widget'].up()
            if self.current == self.downCurrent:
                self.downCurrent['Widget'].click()
        self.downCurrent = None

    def focusNext(self):
        # TODO
        pass
    def focusPrevious(self):
        # TODO
        pass
    def focusLeft(self):
        # TODO
        pass
    def focusRight(self):
        # TODO
        pass
    def focusUp(self):
        # TODO
        pass
    def focusDown(self):
        # TODO
        pass

inputHandler = _InputHandler()

def controllerInit(c):
    render.showMouse(True)
    mOver = c.sensors['sMouseOver']
    mOver.usePulseFocus = True

def focusNext(c):
    inputHandler.focusNext()
def focusPrevious(c):
    inputHandler.focusPrevious()
def focusLeft(c):
    inputHandler.focusLeft()
def focusRight(c):
    inputHandler.focusRight()
def focusUp(c):
    inputHandler.focusUp()
def focusDown(c):
    inputHandler.focusDown()

def mouseMove(c):
    if not Utilities.allSensorsPositive(c):
        return
    mOver = c.sensors['sMouseOver']
    inputHandler.mouseOver(mOver)

def mouseButton(c):
    if Utilities.someSensorPositive(c):
        inputHandler.mouseDown()
    else:
        inputHandler.mouseUp()

class _AsyncAdoptionHelper:
    def __init__(self):
        self.waitingList = {}
        self.containers = {}
    
    def requestAdoption(self, child, parentName):
        if parentName in self.containers:
            container = self.containers[parentName]
            container.addChild(child)
        else:
            if not parentName in self.waitingList:
                self.waitingList[parentName] = []
            self.waitingList[parentName].append(child)
    
    def registerAdopter(self, parent, parentName):
        self.containers[parentName] = parent
        
        # Assign all children waiting on this container.
        if parentName in self.waitingList:
            for child in self.waitingList[parentName]:
                parent.addChild(child)
            del self.waitingList[parentName]

asyncAdoptionHelper = _AsyncAdoptionHelper()

class UIObject:
    def show(self):
        pass
    
    def hide(self):
        pass

class Container(UIObject):
    def __init__(self):
        self.children = []
    
    def addChild(self, uiObject):
        self.children.append(uiObject)
    
    def show(self):
        for child in self.children:
            child.show()
    
    def hide(self):
        for child in self.children:
            child.hide()

class Widget(UIObject):
    S_HIDDEN = 2
    S_FOCUS = 3
    S_ACTIVE = 4
    
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
    
    def enter(self):
        Utilities.addState(self.owner, Widget.S_FOCUS)
        self.updateTargetFrame()
    
    def exit(self):
        Utilities.remState(self.owner, Widget.S_FOCUS)
        self.updateTargetFrame()
    
    def down(self):
        Utilities.addState(self.owner, Widget.S_ACTIVE)
        self.updateTargetFrame()
    
    def up(self):
        Utilities.remState(self.owner, Widget.S_ACTIVE)
        self.updateTargetFrame()
    
    def click(self):
        if 'onClickMsg' in self.owner:
            msg = self.owner['onClickMsg']
            body = ''
            if 'onClickBody' in self.owner:
                body = self.owner['onClickBody']
            eventBus.notify(self, msg, body)
    
    def hide(self):
        Utilities.addState(self.owner, Widget.S_HIDDEN)
        Utilities.remState(self.owner, Widget.S_ACTIVE)
        Utilities.remState(self.owner, Widget.S_FOCUS)
        self.updateTargetFrame()
    
    def show(self):
        Utilities.remState(self.owner, Widget.S_HIDDEN)
        self.updateTargetFrame()
    
    def updateTargetFrame(self):
        targetFrame = Widget.IDLE_FRAME
        if Utilities.hasState(self.owner, Widget.S_HIDDEN):
            targetFrame = Widget.HIDDEN_FRAME
        elif Utilities.hasState(self.owner, Widget.S_FOCUS):
            if Utilities.hasState(self.owner, Widget.S_ACTIVE):
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
        self.owner.visible = visible

def updateWidget(c):
    c.owner['Widget'].update()
    c.activate(c.actuators[0])

def createButton(c):
    inputHandler.addWidget(Widget(c.owner))

class SaveButton(Widget):
    def __init__(self, owner):
        Widget.__init__(self, owner)
        
        self.postMark.visible = False
        self.stamp = None
    
    def parseChild(self, child, type):
        if type == 'StampHook':
            self.stampHook = child
            return True
        elif type == 'IDCanvas':
            self.idCanvas = child
            return True
        elif type == 'Postmark':
            self.postMark = child
            return True
        else:
            return False
    
    def setId(self, id):
        self.idCanvas['Content'] = str(id)
    
    def updateVisibility(self, visible):
        # Should do something special with the post mark, stamp and canvas.
        Widget.updateVisibility(self, visible)

def createSaveButton(c):
    inputHandler.addWidget(SaveButton(c.owner))

class Subtitle(EventListener):
    def __init__(self, owner):
        self.owner = owner
        eventBus.addListener(self)
    
    def onEvent(self, sender, message, body):
        if message == 'showScreen':
            self.owner['Content'] = body

def createSubtitle(c):
    Subtitle(c.owner)
