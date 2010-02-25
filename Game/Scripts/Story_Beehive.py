#
# Copyright 2009 Alex Fraser <alex@phatcore.com>
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

import GameLogic
import Actor
import Utilities
import Camera

class Bucket(Actor.Actor):
    DIR_UP = 1
    DIR_DOWN = 2
    
    LOC_TOP = 1
    LOC_BOTTOM = 2
    
    PROJECTION = [0.0, 0.0, 20.0]
    
    def __init__(self, owner, camTop, camBottom):
        Actor.Actor.__init__(self, owner)
        
        scene = GameLogic.getCurrentScene()
        self.water = None
        self.waterBallTemplate = scene.objectsInactive['OB' + owner['WaterBallTemplate']]
        self.camTop = camTop
        self.camBottom = camBottom
        self.currentCamera = None
        
        self.dir = Bucket.DIR_UP
        self.loc = Bucket.LOC_BOTTOM
        self.isTouchingPlayer = False
        
        Utilities.parseChildren(self, owner)
    
    def parseChild(self, child, type):
        if type == 'BucketWater':
            self.water = child
            return True
        return False
    
    def spawnWaterBall(self):
        scene = GameLogic.getCurrentScene()
        waterBall = scene.addObject(self.waterBallTemplate, self.water)
        waterBall.setLinearVelocity(self.water.getAxisVect(Bucket.PROJECTION))
    
    def setDirection(self, dir):
        if dir == self.dir:
            return
        
        if dir == Bucket.DIR_UP:
            self.water.setVisible(True, False)
        else:
            self.water.setVisible(False, False)
            self.spawnWaterBall()
        self.dir = dir
    
    def setLocation(self, loc):
        if loc == self.loc:
            return
        
        if loc == Bucket.LOC_TOP:
            self.water.setVisible(True, False)
        else:
            self.water.setVisible(False, False)
        self.loc = loc
        self.updateCamera()
    
    def frameChanged(self):
        frame = self.Owner['Frame']
        if frame < 170:
            self.setDirection(Bucket.DIR_UP)
        else:
            self.setDirection(Bucket.DIR_DOWN)
        
        if frame > 100 and frame < 260:
            self.setLocation(Bucket.LOC_TOP)
        else:
            self.setLocation(Bucket.LOC_BOTTOM)
    
    def updateCamera(self):
        cam = None
        if self.isTouchingPlayer:
            if self.loc == Bucket.LOC_BOTTOM:
                cam = self.camBottom
            else:
                cam = self.camTop
        
        if cam == self.currentCamera:
            return
        
        if self.currentCamera != None:
            Camera.removeGoalOb(self.currentCamera)
        if cam != None:
            Camera.addGoalOb(cam)
        
        self.currentCamera = cam
    
    def setTouchingPlayer(self, isTouchingPlayer):
        if isTouchingPlayer == self.isTouchingPlayer:
            return
        
        self.isTouchingPlayer = isTouchingPlayer
        self.updateCamera()

def createBucket(c):
    camTop = c.sensors['sCameraTop'].owner
    camBottom = c.sensors['sCameraBottom'].owner
    Bucket(c.owner, camTop, camBottom)

def updateBucket(c):
    bucket = c.owner['Actor']
    bucket.frameChanged()
    
    sCollision = c.sensors['sPlayer']
    bucket.setTouchingPlayer(Actor.isTouchingMainCharacter(sCollision))
