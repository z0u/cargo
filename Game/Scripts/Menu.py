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

class Controller:
    def __init__(self):
        self.widgets = []
        self.current = -1

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
    
controller = Controller()

def controllerInit(c):
    render.showMouse(True)
    mOver = c.sensors['sMouseOver']
    mOver.usePulseFocus = True

def focusNext(c):
    controller.focusNext()
def focusPrevious(c):
    controller.focusPrevious()
def focusLeft(c):
    controller.focusLeft()
def focusRight(c):
    controller.focusRight()
def focusUp(c):
    controller.focusUp()
def focusDown(c):
    controller.focusDown()

currentFocus = None
def mouseMove(c):
    global currentFocus
    
    mOver = c.sensors['sMouseOver']
    newFocus = mOver.hitObject
    while newFocus != None:
        if 'Widget' in newFocus:
            break
        newFocus = newFocus.parent
    
    if newFocus != currentFocus:
        if currentFocus != None:
            currentFocus['Widget'].focus(False)
        if newFocus != None:
            newFocus['Widget'].focus(True)
    currentFocus = newFocus

class Widget:
    S_INIT = 1
    S_FOCUS = 2
    S_FOCUS_LOST = 3
    
    def __init__(self, owner):
        self.owner = owner
        self.sensitive = True
        self.active = False
        self.owner['Widget'] = self
        
        Utilities.parseChildren(self, owner)
        print('creating widget')
#        Utilities.remState(self.owner, Widget.S_INIT)
    
    def focus(self, hasFocus):
        if hasFocus:
            Utilities.addState(self.owner, Widget.S_FOCUS)
            Utilities.remState(self.owner, Widget.S_FOCUS_LOST)
        else:
            Utilities.addState(self.owner, Widget.S_FOCUS_LOST)
            Utilities.remState(self.owner, Widget.S_FOCUS)
    
    def activated(self):
        pass

class SaveButton(Widget):
    def __init__(self, owner):
        Widget.__init__(self, owner)
    
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

def createSaveButton(c):
    SaveButton(c.owner)