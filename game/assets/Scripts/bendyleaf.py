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

import bge

import bat.bats
import bat.utils
import bat.bmath

class BendyLeaf(bat.bats.BX_GameObject, bge.types.BL_ArmatureObject):
    _prefix = ""

    S_SENSING = 1
    S_UPDATING = 2

    def __init__(self, old_owner):
        self.skin = self.find_descendant([('Type', 'Skin')])
        self.bend_angle = self['MinAngle']
        self.target_influence = 0.0
        self.influence = 0.0
        self.velocity = 0.0
        self.add_state(BendyLeaf.S_UPDATING)

    @bat.bats.expose
    @bat.utils.controller_cls
    def on_hit(self, c):
        sensors = c.sensors

        #
        # Pass one: Find out which objects are touching the leaf.
        #
        hit_obs = set()
        for s in sensors:
            if not s.positive:
                continue
            for ob in s.hitObjectList:
                hit_obs.add(ob)

        #
        # Pass two: add up the effect of all touching objects.
        #
        total_influence = 0.0
        for ob in hit_obs:
            distance = (ob.worldPosition - self.worldPosition).magnitude
            influence = bat.bmath.unlerp(self['MinDist'], self['MaxDist'], distance)
            influence = influence * ob['DynamicMass']
            total_influence = total_influence + influence
        total_influence = total_influence * self['InfluenceMultiplier']
        self.target_influence = total_influence

        self.add_state(BendyLeaf.S_UPDATING)

    @bat.bats.expose
    def update(self):
        self.influence = bat.bmath.lerp(self.influence, self.target_influence, 0.5)
        target_bend_angle = bat.bmath.lerp(self['MinAngle'], self['MaxAngle'], self.influence)

        difference = target_bend_angle - self.bend_angle
        self.bend_angle, self.velocity = bat.bmath.integrate(
                self.bend_angle, self.velocity,
                difference * self['acceleration'], self['damping'])

        self.playAction('LeafBend', self.bend_angle, self.bend_angle)

        if abs(self.velocity) < 0.0001 and abs(difference) < 0.0001:
            # At rest
            self.rem_state(BendyLeaf.S_UPDATING)
