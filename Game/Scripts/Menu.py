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

class Controller:
    def __init__(self, owner):
        owner['Controller'] = self
        self.owner = owner
        self.widgets = []
        self.current = None
        self.downCurrent = None
        self.savedGames = []
        
        Utilities.parseChildren(self, owner)
        self.initSaveButtons()
    
    def parseChild(self, child, type):
        scene = logic.getCurrentScene()
        if type == 'SaveButton':
            button = SaveButton(child)
            self.savedGames.append(button)
            button.owner.setParent(self.owner)
            child.endObject()
            return True
        else:
            return False
    
    def initSaveButtons(self):
        self.savedGames.sort(key=Utilities.ZKeyActor())
        self.savedGames.reverse()
        for i, button in enumerate(self.savedGames):
            button.setId(i + 1)
    
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
        print('down')
        if self.current != None:
            self.current['Widget'].down()
            self.downCurrent = self.current
    
    def mouseUp(self):
        '''Send a mouse up event to the widget under the cursor. If that widget
        also received the last mouse down event, it will be sent a click event
        in addition to the up event.'''
        print('up')
        if self.downCurrent != None:
            self.downCurrent['Widget'].up()
            if self.current == self.downCurrent:
                self.downCurrent['Widget'].click()
        self.downCurrent = None

    def focusNext(self):
        pass
    def focusPrevious(self):
        pass
    def focusLeft(self):
        pass
    def focusRight(self):
        pass
    def focusUp(self):
        pass
    def focusDown(self):
        pass

class Screen:
    def show(self):
        pass
    def hide(self):
        pass

class LoadGameScreen(Screen):
    def __init__(self, savedGameButtons):
        self.savedGameButtons = savedGameButtons
    
    def show(self):
        pass

def controllerInit(c):
    render.showMouse(True)
    mOver = c.sensors['sMouseOver']
    mOver.usePulseFocus = True
    Controller(c.owner)

def focusNext(c):
    c.owner['Controller'].focusNext()
def focusPrevious(c):
    c.owner['Controller'].focusPrevious()
def focusLeft(c):
    c.owner['Controller'].focusLeft()
def focusRight(c):
    c.owner['Controller'].focusRight()
def focusUp(c):
    c.owner['Controller'].focusUp()
def focusDown(c):
    c.owner['Controller'].focusDown()

def mouseMove(c):
    if not Utilities.allSensorsPositive(c):
        return
    mOver = c.sensors['sMouseOver']
    c.owner['Controller'].mouseOver(mOver)

def mouseButton(c):
    if Utilities.someSensorPositive(c):
        c.owner['Controller'].mouseDown()
    else:
        c.owner['Controller'].mouseUp()

class Widget:
    S_FOCUS = 2
    S_FOCUS_LOST = 3
    S_ACTIVE = 4
    S_INACTIVE = 5
    
    FRAME_RATE = 25.0 / logic.getLogicTicRate()
    
    def __init__(self, owner):
        self.owner = owner
        self.sensitive = True
        self.active = False
        self.owner['Widget'] = self
        
        Utilities.parseChildren(self, owner)
    
    def enter(self):
        Utilities.addState(self.owner, Widget.S_FOCUS)
        Utilities.remState(self.owner, Widget.S_FOCUS_LOST)
        self.updateTargetFrame()
    
    def exit(self):
        Utilities.addState(self.owner, Widget.S_FOCUS_LOST)
        Utilities.remState(self.owner, Widget.S_FOCUS)
        self.updateTargetFrame()
    
    def down(self):
        Utilities.addState(self.owner, Widget.S_ACTIVE)
        Utilities.remState(self.owner, Widget.S_INACTIVE)
        self.updateTargetFrame()
    
    def up(self):
        Utilities.addState(self.owner, Widget.S_INACTIVE)
        Utilities.remState(self.owner, Widget.S_ACTIVE)
        self.updateTargetFrame()
    
    def click(self):
        pass
    
    def updateTargetFrame(self):
        targetFrame = 5.0
        if Utilities.hasState(self.owner, Widget.S_FOCUS):
            if Utilities.hasState(self.owner, Widget.S_ACTIVE):
                targetFrame = 12.0
            else:
                targetFrame = 9.0
        else:
            targetFrame = 5.0
        self.owner['targetFrame'] = targetFrame
    
    def update(self):
        targetFrame = self.owner['targetFrame']
        frame = self.owner['frame']
        if frame < targetFrame:
            frame = min(frame + Widget.FRAME_RATE, targetFrame)
        else:
            frame = max(frame - Widget.FRAME_RATE, targetFrame)
        self.owner['frame'] = frame

class SaveButton(Widget):
    def __init__(self, referential):
        self.owner = logic.getCurrentScene().addObject('SaveButton_T', referential)
        Widget.__init__(self, self.owner)
        
        self.postMark.visible = False
        self.stamp = None
        self.id = None
    
    def parseChild(self, child, type):
        if type == 'StampHook':
            self.stampHook = child
            return True
        elif type == 'IDHook':
            self.idHook = child
            return True
        elif type == 'Postmark':
            self.postMark = child
            return True
        else:
            return False
    
    def setId(self, id):
        if self.id != None:
            self.id.endObject()
        scene = logic.getCurrentScene()
        self.id = scene.addObject('SG_ID_%d' % id, self.idHook)
        self.id.localScale = self.owner.localScale
        self.id.setParent(self.owner)

def createSaveButton(c):
    SaveButton(c.owner)

def updateWidget(c):
    c.owner['Widget'].update()
    c.activate(c.actuators[0])
