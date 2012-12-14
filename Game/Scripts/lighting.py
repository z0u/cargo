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
	def __init__(self, index, pos, colour):
		self.index = index
		self.neighbours = set()
		self.pos = pos
		self.colour = colour

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

	def gather_lamps(self):
		self.lamps = []
		sce = self.scene
		for i in range(LightNetwork.MAX_LAMPS):
			try:
				lamp = sce.objects['UserLight%d' % (i + 1)]
				lamp['_default_colour'] = lamp.color
				lamp['_default_energy'] = lamp.energy
				self.lamps.append(lamp)
			except KeyError:
				pass
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
					colours.append(vert.color.copy())

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
		if node is None or node is self.current_node:
			return

		self.activate_node(node)

	def find_closest_node(self, pos):
		def distance_key(_n):
			return (pos - _n.pos).magnitude
		self.nodes.sort(key=distance_key)
		n = self.nodes[0]

		dist = (n.pos - pos).magnitude
		hit_ob, _, _ = self.rayCast(n.pos, pos, dist, 'Ray')
		if hit_ob is None or hit_ob is self:
			LightNetwork.log.debug('Hit node %d', n.index)
			return n
		else:
			LightNetwork.log.debug('Missed node %d, dist: %f, hit %s', n.index, dist, hit_ob.name)
			return None

	def activate_node(self, node):
		LightNetwork.log.info('Activating node %d', node.index)
		self.current_node = node
		nodes = [node]
		nodes.extend(node.neighbours)
		for n, lamp in zip(nodes, self.lamps):
			lamp.worldPosition = n.pos
			lamp.energy = lamp['_default_energy']
			if self.use_colours:
				lamp.color = node.colour

		LightNetwork.log.info('Using %d lamps', len(nodes))
		if len(self.lamps) < len(nodes):
			LightNetwork.log.warn('Not enough user lights to satisfy node. %d lights required.', len(nodes))

		# Deactivate remaining lamps.
		for lamp in self.lamps[len(nodes):]:
			lamp.energy = 0.0
