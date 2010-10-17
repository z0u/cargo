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
        
        if newFocus != self.current:
            if self.current != None and not self.current.invalid:
                self.current['Widget'].focus(False)
            if newFocus != None:
                newFocus['Widget'].focus(True)
        self.current = newFocus

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
    mOver = c.sensors['sMouseOver']
    c.owner['Controller'].mouseOver(mOver)

class Widget:
    S_FOCUS = 2
    S_FOCUS_LOST = 3
    
    def __init__(self, owner):
        self.owner = owner
        self.sensitive = True
        self.active = False
        self.owner['Widget'] = self
        
        Utilities.parseChildren(self, owner)
    
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
        self.id.setParent(self.owner)

def createSaveButton(c):
    SaveButton(c.owner)
