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
import mathutils
import GameTypes

YAXIS = (0.0, 1.0, 0.0)

class ForceField(Actor.Actor):
    def __init__(self, owner):
        Actor.Actor.__init__(self, owner)
        
    def isInsideWorld(self):
        return True
    
    def modulate(self, distance, limit):
        '''
        To visualise this function, try it in gnuplot:
            f(d, l) = (d*d) / (l*l)
            plot [0:10][0:1] f(x, 10)
        '''
        return (distance * distance) / (limit * limit)
    
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
    
    def touched(self, actor, factor = 1.0):
        '''Called when an object is inside the force field.'''
        pos = mathutils.Vector(actor.Owner.worldPosition)
        
        if (Utilities._manhattanDist(pos, self.Owner.worldPosition) >
            self.Owner['FFDist2']):
            return
        
        pos = Utilities._toLocal(self.Owner, pos)
        if 'FFZCut' in self.Owner and self.Owner['FFZCut'] and (pos.z > 0.0):
            return
        
        dir = self.getForceDirection(pos)
        dist = dir.magnitude
        if dist != 0.0:
            dir.normalize()
        magnitude = self.getMagnitude(dist)
        dir *= magnitude * factor
        dir = Utilities._toWorldVec(self.Owner, dir)
        
        linV = mathutils.Vector(actor.Owner.getLinearVelocity(False))
        linV += dir
        actor.Owner.setLinearVelocity(linV, False)
        
    def getForceDirection(self, localPos):
        '''Returns the Vector along which the acceleration will be applied, in
        local space.'''
        pass
    
class Linear(ForceField):
    def __init__(self, owner):
        ForceField.__init__(self, owner)
        self.direction = mathutils.Vector(YAXIS)
    
    def getForceDirection(self, posLocal):
        return self.direction
    
    def modulate(self, distance, limit):
        '''
        To visualise this function, try it in gnuplot:
            f(d, l) = d / l
            plot [0:10][0:1] f(x, 10)
        '''
        return distance / limit

class Repeller3D(ForceField):
    '''
    Repels objects away from the force field's origin.
    
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
        ForceField.__init__(self, owner)
    
    def getForceDirection(self, posLocal):
        return posLocal

class Repeller2D(ForceField):
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
        ForceField.__init__(self, owner)
    
    def getForceDirection(self, posLocal):
        dir = mathutils.Vector(posLocal)
        dir.z = 0.0
        return dir

class Vortex2D(ForceField):
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
        ForceField.__init__(self, owner)
    
    def getForceDirection(self, posLocal):
        tan = mathutils.Vector((posLocal.y, 0.0 - posLocal.x, 0.0))
        return tan

def create(obOrController):
    '''Create a new force field from an object, or from the object attached to a
    controller. After completion, the object will have its state set to 2.
    
    Object properties:
    FFType: The type of force field to create; must match the name of a subclass
        of ForceField.
    Other properties, as required by the force field type (see class
        documentation).'''
    o = None
    if obOrController.isA(GameTypes.KX_GameObject):
        o = obOrController
    elif obOrController.isA(GameTypes.SCA_IController):
        o = obOrController.owner
    
    ffClass = globals()[o['FFType']]
    ffInstance = ffClass(o)
    Utilities.setState(o, 2)
    return ffInstance

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
            if 'Actor' in ob:
                actors.add(ob['Actor'])
        
    for a in actors: 
        ffield.touched(a)

def onRender(c):
    '''Activate the force field. This is like onTouched, but should be used by
    force fields with a very long range (i.e. those that affect the whole
    level).
    
    Controller owner: a ForceField, created with one of the Create functions
        above.
    
    Sensors:
    <any>: One or more of any kind of sensor. While the force field is active,
        these should fire every logic tic.
    '''
    if not Utilities.someSensorPositive(c):
        return
    
    ffield = c.owner['Actor']
    for a in Actor.Director.Actors:
        ffield.touched(a)
