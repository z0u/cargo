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
    
    def getMagnitude(self, distance):
        effect = 0.0
        if distance < self.Owner['FFDist1']:
            effect = self.modulate(distance, self.Owner['FFDist1'])
        else:
            effect = 1.0 - self.modulate(distance - self.Owner['FFDist1'],
                                         self.Owner['FFDist2'])
        if effect > 1.0:
            effect = 1.0
        if effect < 0.0:
            effect = 0.0
        return self.Owner['FFMagnitude'] * effect
    
    def touched(self, actor):
        '''Called when an object is inside the force field.'''
        pass

class RadialForceField2D(ForceField):
    def __init__(self, owner):
        ForceField.__init__(self, owner)
    
    def getForceDirection(self, posLocal):
        dir = Mathutils.Vector(posLocal)
        dir.z = 0.0
        return dir
    
    def modulate(self, distance, limit):
        '''
        To visualise this function, try it in gnuplot:
            f(d, l) = (d*d) / (l*l)
            plot [0:10][0:1] f(x, 10)
        '''
        return (distance * distance) / (limit * limit)
    
    def touched(self, actor):
        pos = Mathutils.Vector(actor.Owner.worldPosition)
        pos = Utilities._toLocal(self.Owner, pos)
        if pos.z > 0.0 and self.Owner['FFZCut']:
            return
        
        dir = self.getForceDirection(pos)
        radius = dir.magnitude
        if radius != 0.0:
            dir.normalize()
        magnitude = self.getMagnitude(radius)
        dir *= magnitude
        dir = Utilities._toWorldVec(self.Owner, dir)
        
        linV = Mathutils.Vector(actor.Owner.getLinearVelocity(False))
        linV += dir
        actor.Owner.setLinearVelocity(linV, False)

class Repeller2D(RadialForceField2D):
    '''
    Repels objects away from the force field's origin on the local XY axis.
    
    Object properties:
    FFMagnitude: The maximum acceleration.
    FFDist1: The distance from the origin at which the maximum acceleration will
        be applied.
    FFDist2: The distance from the origin at which the acceleration will be
        zero.
    FFZCut: If True, force will only be applied to objects underneath the force
        field's XY plane (in force field local space).
    '''
    def __init__(self, owner):
        RadialForceField2D.__init__(self, owner)

class Vortex2D(RadialForceField2D):
    '''
    Propels objects around the force field's origin, so that the rotate around
    the Z-axis. Rotation will be clockwise for positive magnitudes. Force is
    applied tangentially to a circle around the Z-axis, so the objects will tend
    to spiral out from the centre. The magnitude of the acceleration varies
    depending on the distance of the object from the origin: at the centre, the
    acceleration is zero. It ramps up slowly (r-squared) to the first distance
    marker; then ramps down (1 - r-squared) to the second.
    
    Object properties:
    FFMagnitude: The maximum acceleration.
    FFDist1: The distance from the origin at which the maximum acceleration will
        be applied.
    FFDist2: The distance from the origin at which the acceleration will be
        zero.
    FFZCut: If True, force will only be applied to objects underneath the force
        field's XY plane (in force field local space).
    '''
    
    def __init__(self, owner):
        RadialForceField2D.__init__(self, owner)
    
    def getForceDirection(self, posLocal):
        tan = Mathutils.Vector((posLocal.y, 0.0 - posLocal.x, 0.0))
        return tan

def createRepeller2D(c):
    Repeller2D(c.owner)
    
def createVortex2D(c):
    Vortex2D(c.owner)

def onTouched(c):
    '''Activate the force field.
    
    Controller owner: a ForceField, created with one of the Create functions
        above.
    
    Sensors:
    <any>: Near sensors (also includes Collision) that detect objects in range
        to act upon.
    '''
    ffield = c.owner['Actor']
    
    actors = set()
    for s in c.sensors:
        if not s.positive:
            continue
        for ob in s.hitObjectList:
            if ob.has_key('Actor'):
                actors.add(ob['Actor'])
        
    for a in actors: 
        ffield.touched(a)
