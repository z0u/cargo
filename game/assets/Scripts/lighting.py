#
# Copyright 2012 Alex Fraser <alex@phatcore.com>
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

import logging

import bge

import bat.containers
import bat.event
import bat.bmath
import bat.utils
import bat.bats

import Scripts.director

class LightNode:
    lamp = bat.containers.weakprop('lamp')

    def __init__(self, index, pos, colour):
        self.index = index
        self.neighbours = set()
        self.pos = pos
        self.colour = colour

    def __str__(self):
        return "LightNode(%d)" % self.index


class Lamp:
    log = logging.getLogger(__name__ + '.Lamp')

    FADE_RATE = 0.04

    def __init__(self, ob):
        self.ob = ob
        self.default_energy = ob.energy
        self.instant = True
        self.current_node = None
        self.target_node = None

    @property
    def invalid(self):
        return self.ob is not None and not self.ob.invalid

    def update(self):
        ob = self.ob

        if self.instant:
            self.relocate()
            self.instant = False
            return

        if self.current_node is not self.target_node:
            if ob.energy <= 0.0:
                # Lamp is currently off; relocation is OK.
                self.relocate()
            else:
                self.fade_out()
        elif self.target_node is None:
            self.fade_out()
        else:
            self.fade_in()

    def fade_in(self):
        ob = self.ob
        if ob.energy >= self.default_energy:
            return

        ob.energy += Lamp.FADE_RATE
        if ob.energy >= self.default_energy:
            # Transfer finished.
            Lamp.log.debug("%s fade in complete at %s.", ob.name, self.current_node)
            ob.energy = self.default_energy

    def fade_out(self):
        ob = self.ob
        if ob.energy <= 0.0:
            return

        ob.energy -= Lamp.FADE_RATE
        if ob.energy <= 0.0:
            # Transfer.
            Lamp.log.debug("%s fade out complete at %s.", self, self.current_node)
            ob.energy = 0.0
            self.relocate()

    def relocate(self):
        ob = self.ob
        self.current_node = self.target_node
        if self.target_node is not None:
            Lamp.log.debug("%s fading in at %s.", self, self.current_node)
            ob.worldPosition = self.target_node.pos
            if self.target_node.colour is not None:
                ob.color = self.target_node.colour
            if self.instant:
                ob.energy = self.default_energy
        else:
            ob.energy = 0.0

    def __str__(self):
        return "Lamp(%s)" % self.ob.name


class LightNetwork(bat.bats.BX_GameObject, bge.types.KX_GameObject):
    '''
    Allows lights to be moved and reused between several rooms.

    This should be applied to a mesh object that is in the form of a network. As
    the player moves around the level, there will always be one active node: the
    closest node that is visible to the player. Lights will be placed at that
    node and each adjacent node (its neighbours).

    Each polygon should have two pairs of close vertices. Those pairs will be
    merged into a node, which is shared with the next polygon. Thus vertex pairs
    are nodes, and polygons are edges in the network.

    Lights will be taken from a pool of lights and will be reused. They must all
    have the name "UserLightN", where N is a number from 1-MAX_LAMPS. The number
    of lights required is equal to the maximum degree of any node in the network
    + 2, i.e. if the network has a 3-way intersection there should be 5 lights.
    '''

    _prefix = 'LN_'

    log = logging.getLogger(__name__ + '.LightNetwork')

    MERGE_THRESHOLD = 3.0
    MAX_LAMPS = 10

    def __init__(self, old_owner):
        self.current_node = None
        self.use_colours = 'UseVcol' in self and self['UseVcol']
        self.construct_node_graph()
        self.gather_lamps()
        bat.event.EventBus().add_listener(self)

    def on_event(self, evt):
        if evt.message in {'TeleportSnail'}:
            for lamp in self.lamps:
                lamp.instant = True
            self.update()

    def gather_lamps(self):
        self.lamps = []
        sce = self.scene
        for i in range(LightNetwork.MAX_LAMPS):
            try:
                lamp_ob = sce.objects['UserLight%d' % (i + 1)]
            except KeyError:
                continue
            self.lamps.append(Lamp(lamp_ob))
        LightNetwork.log.info("Found %d lamps", len(self.lamps))
        if len(self.lamps) < 3:
            LightNetwork.log.info("Found few lamps. Lamp objects should be named UserLightN.")

    def construct_node_graph(self):
        # Create list of vertices and their connections.
        # Would be nice to put this into a BSP tree one day...
        self.nodes = []
        me = self.meshes[0]
        index = 0
        mat = self.worldTransform.copy()
        for poly in self.polys:
            # Each polygon is expected to be elongated, with one vertex or two
            # close vertices at either end. The close vertices will be merged;
            # thus each polygon is a single edge connecting two nodes in the
            # network.
            positions = []
            colours = []
            for vert in bat.utils.iterate_poly_verts(me, poly):
                pos = mat * vert.getXYZ()
                dup = False
                for p in positions:
                    if (pos - p).magnitude < LightNetwork.MERGE_THRESHOLD:
                        dup = True
                        break
                if not dup:
                    positions.append(pos)
                    if self.use_colours:
                        colours.append(vert.color.xyz)
                    else:
                        colours.append(None)

            if len(positions) != 2:
                raise ValueError("Edge has %d vertices: %s" % (len(positions), positions))

            nodes = []
            for pos, col in zip(positions, colours):
                node = None
                for n in self.nodes:
                    if (pos - n.pos).magnitude < LightNetwork.MERGE_THRESHOLD:
                        node = n
                        break
                if node is None:
                    node = LightNode(index, pos, col)
                    index += 1
                    self.nodes.append(node)
                nodes.append(node)
            nodes[0].neighbours.add(nodes[1])
            nodes[1].neighbours.add(nodes[0])

        LightNetwork.log.debug("Created network with %d nodes", len(self.nodes))

    @bat.bats.expose
    def update(self):
        player = Scripts.director.Director().mainCharacter
        if player is None:
            return
        pos = player.worldPosition.copy()
        node = self.find_closest_node(pos)
        if node is not None and node is not self.current_node:
            self.activate_node(node)

        for lamp in self.lamps:
            lamp.update()

    def find_closest_node(self, pos):
        def distance_key(_n):
            return (pos - _n.pos).magnitude
        self.nodes.sort(key=distance_key)

        # Just test closest node. Testing further nodes would result in an
        # unstable state: the lights flicker when the node becomes obscured
        # momentarily.
        n = self.nodes[0]

        dist = (n.pos - pos).magnitude
        hit_ob, _, _ = self.rayCast(n.pos, pos, dist, 'Ray')
        if hit_ob is None or hit_ob is self:
            return n
        else:
            return None

    def activate_node(self, node):
        LightNetwork.log.info('Activating node %d', node.index)
        self.current_node = node

        # Position a light at the current node, and all of its neighbours.
        nodes = set()
        nodes.add(node)
        nodes.update(node.neighbours)

        # Find out which lamps need to move. Don't just reassign them, or they
        # will all turn off and then back on.
        occupied_nodes = set()
        available_lamps = []
        for lamp in self.lamps:
            if lamp.target_node is None:
                # Prefer to assign unused lamps.
                LightNetwork.log.debug('%s is unused.', lamp)
                available_lamps.insert(0, lamp)
            elif lamp.target_node in nodes:
                # Can't assign this lamp.
                LightNetwork.log.debug('%s can not be moved.', lamp)
                occupied_nodes.add(lamp.target_node)
            else:
                # Reassign lamp that is already in use.
                LightNetwork.log.debug('%s can be moved.', lamp)
                available_lamps.append(lamp)

        unoccupied_nodes = nodes.difference(occupied_nodes)
        LightNetwork.log.debug('Using %d, reusing %d, moving %d', len(nodes),
                len(occupied_nodes), len(unoccupied_nodes))

        # Assign lamps, starting with the ones that are not currently being
        # used.
        for n in unoccupied_nodes.copy():
            try:
                lamp = available_lamps.pop(0)
            except IndexError:
                LightNetwork.log.warn('Not enough user lights to satisfy node. %d lights required.', len(nodes))
                break
            lamp.target_node = n

        # Deactivate remaining lamps.
        for lamp in available_lamps:
            lamp.target_node = None
