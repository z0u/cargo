#
# Copyright 2009-2012 Alex Fraser <alex@phatcore.com>
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

import mathutils
import mathutils.geometry

import bat.bmath
import bat.bats

class SurfaceAttitude:
    def __init__(self, target, ray0, ray1, ray2, ray3):
        self.rays = (ray0, ray1, ray2, ray3)
        self.counter = bat.bats.Counter()
        self.target = target

    @bat.bats.profile("Scripts.attitude.SurfaceAttitude.apply")
    def apply(self):
        self.counter.__init__()
        counter = self.counter
        avNormal = bat.bmath.ZEROVEC.copy()
        hit_points = []
        for ray in self.rays:
            ob, co, nor = ray.getHitPosition()
            if ob:
                avNormal += nor
                counter.add(ob)
            hit_points.append(co)

        #
        # Inherit the angular velocity of a nearby surface. The object that was
        # hit by the most rays (above) is used.
        # TODO: The linear velocity should probably be set, too: fast-moving
        # objects can be problematic.
        #
        touched_object = counter.mode
        if touched_object is not None:
            angV = touched_object.worldAngularVelocity
            if angV.length_squared < bat.bmath.EPSILON:
                angV = bat.bmath.MINVECTOR
            self.target.worldAngularVelocity = angV

        if counter.n > 0:
            avNormal /= counter.n

        if counter.n == 1:
            # Only one ray hit; use it to try to snap to a sane orientation.
            # Subsequent frames should then have more rays hit.
            self.target.alignAxisToVect(avNormal, 2)
        elif counter.n > 1:
            #
            # Derive normal from hit points and update orientation. This gives a
            # smoother transition than just averaging the normals returned by the
            # rays. Rays that didn't hit will use their last known value.
            #
            normal = mathutils.geometry.normal(*hit_points)
            if normal.dot(avNormal) < 0.0:
                normal.negate()
            self.target.alignAxisToVect(normal, 2)

        return touched_object, counter.n

class Engine:
    def __init__(self, target):
        self.target = target

        self.max_rot = 0.02
        self.rot_factor = 0.2

        self.speed = 0.0
        self.turn_factor = 0.0
        self.rot_speed = 0.0

    @bat.bats.profile("Scripts.attitude.Engine.apply")
    def apply(self, world_direction, speed):
        turn_factor = world_direction.dot(self.target.getAxisVect(bat.bmath.XAXIS))
        agreement = world_direction.dot(self.target.getAxisVect(bat.bmath.YAXIS))

        # Turning
        target_rot_speed = -self.max_rot * turn_factor
        rot_speed = bat.bmath.lerp(self.rot_speed, target_rot_speed, self.rot_factor)
        oRot = mathutils.Matrix.Rotation(rot_speed, 3, bat.bmath.ZAXIS)
        self.target.localOrientation = self.target.localOrientation * oRot

        # Forward motion
        if agreement < -0.3:
            speed = -speed
        self.target.applyMovement((0.0, speed, 0.0), True)

        self.speed = speed
        self.turn_factor = turn_factor
        self.rot_speed = rot_speed
