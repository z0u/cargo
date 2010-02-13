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
'''
Created on 13/02/2010

@author: alex
'''

import Utilities
import Actor
import Mathutils

class ForceField(Actor.Actor):
    def __init__(self, owner):
        Actor.Actor.__init__(self, owner)
    
    def getEffectLinear(self, distance, limit):
        '''
        To visualise this function, try it in gnuplot:
            f(d, l) = d / l
            plot [0:10][0:1] f(x, 10)
        '''
        return distance / limit
    
    def getEffectSquare(self, distance, limit):
        '''
        To visualise this function, try it in gnuplot:
            f(d, l) = (d*d) / (l*l)
            plot [0:10][0:1] f(x, 10)
        '''
        return (distance * distance) / (limit * limit)
    
    def modulateMagnitude(self, distance):
        effect = 0.0
        if distance < self.Owner['FFDist1']:
            effect = self.getEffectSquare(distance, self.Owner['FFDist1'])
        else:
            effect = 1.0 - self.getEffectSquare(distance - self.Owner['FFDist1'],
                                                self.Owner['FFDist2'])
        return self.Owner['FFMagnitude'] * effect
    
    def Touched(self, actor):
        '''Called when an object is inside the force field.'''
        pass

class Vortex(ForceField):
    '''Propels objects around the force field's origin.'''
    
    def __init__(self, owner):
        ForceField.__init__(self, owner)
    
    def getTangent(self, pos):
        tan = Mathutils.Vector((pos.y, 0.0 - pos.x, 0.0))
        return tan
    
    def Touched(self, actor):
        pos = Mathutils.Vector(actor.Owner.worldPosition)
        pos = Utilities._toLocal(self.Owner, pos)
        if pos.z > 0.0 and self.Owner['FFZCut']:
            return
        
        dir = self.getTangent(pos)
        radius = dir.magnitude
        if radius != 0.0:
            dir.normalize()
        magnitude = self.modulateMagnitude(radius)
        dir *= magnitude
        dir = Utilities._toWorldVec(self.Owner, dir)
        
        print dir
        
        linV = Mathutils.Vector(actor.Owner.getLinearVelocity(False))
        linV += dir
        actor.Owner.setLinearVelocity(linV, False)

def CreateVortex(c):
    Vortex(c.owner)

def OnTouched(c):
    ffield = c.owner['Actor']
    
    actors = set()
    for s in c.sensors:
        if not s.positive:
            continue
        for ob in s.hitObjectList:
            print ob
            if ob.has_key('Actor'):
                actors.add(ob['Actor'])
        
    for a in actors: 
        ffield.Touched(a)
