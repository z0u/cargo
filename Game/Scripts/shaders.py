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

from string import Template
import math
from collections import namedtuple

import bge
import mathutils

import bxt

DEBUG = False

LAMPDIR = (0.0, 0.0, 1.0)
XAXIS = mathutils.Vector((1.0, 0.0, 0.0))
YAXIS = mathutils.Vector((0.0, 1.0, 0.0))
ZAXIS = mathutils.Vector((0.0, 0.0, 1.0))

Shaderdef = namedtuple('Shaderdef', ['shader', 'callback', 'uses_lights'])

class ShaderCtrl(metaclass=bxt.types.Singleton):
	'''Looks after special GLSL materials in this scene.'''

	_prefix=""

	def __init__(self):
		self.shaders = set()
		self.set_mist_colour(mathutils.Vector((1.0, 1.0, 1.0)))

		sce = bge.logic.getCurrentScene()
		cam = sce.active_camera
		self.set_mist_depth(cam.far)

	def add_shader(self, shader, callback=None, uses_lights=True):
		self.shaders.add(Shaderdef(shader, callback, uses_lights))
		self.update_globals_single(shader)

	def update_globals_single(self, shader):
		print("mist_colour", self._mist_colour)
		shader.setUniformfv("mist_colour", self._mist_colour)
		shader.setUniform1f("mist_depth", -self._mist_depth)

	def update_globals(self):
		for sc in self.shaders:
			shader = sc.shader
			if shader.invalid:
				continue
			self.update_globals_single(shader)

	def set_mist_colour(self, colour):
		self._mist_colour = colour.copy()
		self.update_globals()
		bge.render.setMistColor(colour)

	def set_mist_depth(self, depth):
		self._mist_depth = depth
		self.update_globals()
		bge.render.setMistStart(0.0)
		bge.render.setMistEnd(depth)

	@bxt.types.expose
	def update(self):
		if len(self.shaders) == 0:
			return

		sce = bge.logic.getCurrentScene()
		cam = sce.active_camera
		world_to_camera = cam.world_to_camera
		world_to_camera_vec = world_to_camera.to_quaternion()

		# SUN LIGHT (always sun)
		light = sce.objects["KeyLight"]
		key_light_dir = world_to_camera_vec * light.getAxisVect(LAMPDIR)
		key_light_col = mathutils.Vector(light.color) * light.energy
		key_light_col.resize_4d()
		key_light_col.w = 1.0

		# SKY LIGHT (always hemi)
		light = sce.objects["FillLight1"]
		fill_light1_dir = world_to_camera_vec * light.getAxisVect(LAMPDIR)
		fill_light1_col = mathutils.Vector(light.color) * light.energy
		fill_light1_col.resize_4d()
		fill_light1_col.w = 1.0

		# GROUND LIGHT (always hemi)
		light = sce.objects["FillLight2"]
		fill_light2_dir = world_to_camera_vec * light.getAxisVect(LAMPDIR)
		fill_light2_col = mathutils.Vector(light.color) * light.energy
		fill_light2_col.resize_4d()
		fill_light2_col.w = 1.0

		num_user_lights = 0
		# CUSTOM LIGHT 1 - Anything other than Hemi (undetectable)
		try:
			light = sce.objects["UserLight1"]
		except KeyError:
			pass
		else:
			num_user_lights += 1
			cust_light1_dir = world_to_camera_vec * -light.getAxisVect(LAMPDIR)
			cust_light1_col = mathutils.Vector(light.color) * light.energy
			cust_light1_col.resize_4d()
			if (light.type == light.SUN):
				cust_light1_pos = cust_light1_dir.copy()
				cust_light1_pos.resize_4d()
				cust_light1_pos.w = 0.0
				cust_light1_dist = 0.0
			else:
				cust_light1_pos = world_to_camera * light.worldPosition
				cust_light1_pos.resize_4d()
				cust_light1_pos.w = 1.0
				cust_light1_dist = light.distance
			if (light.type == light.SPOT):
				cust_light1_spotcutoff = light.spotsize / 2.0
				cust_light1_spotcoscutoff = math.cos(math.radians(
						cust_light1_spotcutoff))
				cust_light1_spotexponent = light.spotblend * 128.0
			else:
				cust_light1_spotcutoff = 180.0
				cust_light1_spotcoscutoff = -1.0
				cust_light1_spotexponent = light.spotblend * 128.0

		# CUSTOM LIGHT 2 - Anything other than Hemi (undetectable)
		try:
			light = sce.objects["UserLight2"]
		except KeyError:
			pass
		else:
			num_user_lights += 1
			cust_light2_dir = world_to_camera_vec * -light.getAxisVect(LAMPDIR)
			cust_light2_col = mathutils.Vector(light.color) * light.energy
			cust_light2_col.resize_4d()
			if (light.type == light.SUN):
				cust_light2_pos = cust_light2_dir.copy()
				cust_light2_pos.resize_4d()
				cust_light2_pos.w = 0.0
				cust_light2_dist = 0.0
			else:
				cust_light2_pos = world_to_camera * light.worldPosition
				cust_light2_pos.resize_4d()
				cust_light2_pos.w = 1.0
				cust_light2_dist = light.distance
			if (light.type == light.SPOT):
				cust_light2_spotcutoff = light.spotsize / 2.0
				cust_light2_spotcoscutoff = math.cos(math.radians(
						cust_light2_spotcutoff))
				cust_light2_spotexponent = light.spotblend * 128.0
			else:
				cust_light2_spotcutoff = 180.0
				cust_light2_spotcoscutoff = -1.0
				cust_light2_spotexponent = light.spotblend * 128.0

		# Iterate over all registered materials and update uniforms

		deadShaders = []
		for sc in self.shaders:
			shader = sc.shader
			if shader.invalid:
				deadShaders.append(sc)

			if sc.callback is not None:
				sc.callback(shader, world_to_camera, world_to_camera_vec)

			if not sc.uses_lights:
				continue

			shader.setUniform3f("key_light_dir", key_light_dir.x, key_light_dir.y, key_light_dir.z)
			shader.setUniform4f("key_light_col", key_light_col.x, key_light_col.y, key_light_col.z, 1.0)

			shader.setUniformfv("fill_light1_dir", fill_light1_dir)
			shader.setUniformfv("fill_light1_col", fill_light1_col)

			shader.setUniformfv("fill_light2_dir", fill_light2_dir)
			shader.setUniformfv("fill_light2_col", fill_light2_col)

			if num_user_lights < 1:
				continue
			shader.setUniformfv("cust_light1_pos", cust_light1_pos)
			shader.setUniformfv("cust_light1_dir", cust_light1_dir)
			shader.setUniformfv("cust_light1_col", cust_light1_col)
			shader.setUniform1f("cust_light1_spotcutoff", cust_light1_spotcutoff)
			shader.setUniform1f("cust_light1_spotcoscutoff", cust_light1_spotcoscutoff)
			shader.setUniform1f("cust_light1_spotexponent", cust_light1_spotexponent)
			shader.setUniform1f("cust_light1_dist", cust_light1_dist)

			if num_user_lights < 2:
				continue
			shader.setUniformfv("cust_light2_pos", cust_light2_pos)
			shader.setUniformfv("cust_light2_dir", cust_light2_dir)
			shader.setUniformfv("cust_light2_col", cust_light2_col)
			shader.setUniform1f("cust_light2_spotcutoff", cust_light2_spotcutoff)
			shader.setUniform1f("cust_light2_spotcoscutoff", cust_light2_spotcoscutoff)
			shader.setUniform1f("cust_light2_spotexponent", cust_light2_spotexponent)
			shader.setUniform1f("cust_light2_dist", cust_light2_dist)

		for sc in deadShaders:
			self.shaders.remove(sc)


def _set_shader(ob, vert_shader, frag_shader, callback=None):
	me = ob.meshes[0]
	mat = me.materials[0]

	if not hasattr(mat, "getShader"):
		return

	if DEBUG:
		_print_code(vert_shader)
		_print_code(frag_shader)

	shader = mat.getShader()
	if shader != None:
		if not shader.isValid():
			shader.setSource(vert_shader, frag_shader, True)
		shader.setSampler("tCol", 0)
		uses_lights = ("key_light_dir" in vert_shader or
				"key_light_dir" in frag_shader)
		ShaderCtrl().add_shader(shader, callback, uses_lights)
	return shader


def _print_code(text):
	for i, line in enumerate(text.splitlines()):
		print(i + 1, line)


@bxt.utils.all_sensors_positive
@bxt.utils.owner
def set_basic_shader(ob):
	'''Uses a standard shader.'''

	if 'SH_alpha' in ob:
		alpha = ob['SH_alpha']
	else:
		alpha = 'CLIP'

	if 'SH_model' in ob:
		model = ob['SH_model']
	else:
		model = 'PHONG'

	if 'SH_twosided' in ob:
		twosided = ob['SH_twosided']
	else:
		twosided = False

	_set_shader(ob, create_vert_shader(model=model),
			create_frag_shader(model=model, alpha=alpha, twosided=twosided))


@bxt.utils.all_sensors_positive
@bxt.utils.owner
def set_windy(ob):
	'''Makes the vertices on a mesh wave as if blown by the wind.'''

	if 'SH_alpha' in ob:
		alpha = ob['SH_alpha']
	else:
		alpha = 'CLIP'
	if 'SH_model' in ob:
		model = ob['SH_model']
	else:
		model = 'GOURAUD'
	if 'SH_twosided' in ob:
		twosided = ob['SH_twosided']
	else:
		twosided = False

	POSITION_FN = Template("""
	const float PI2 = 2.0 * 3.14159;
	const float FREQ = ${frequency};
	const float AMPLITUDE = ${amplitude};

	uniform sampler2D tDisp;
	uniform vec3 worldViewX;
	uniform vec3 worldViewY;
	uniform vec3 worldViewZ;

	uniform vec2 phase;

	vec4 getPosition() {
		// Shift position of vertex using a displacement texture.
		vec2 texcoords = gl_Vertex.xy * 0.0005 * FREQ + phase;
		vec3 disp = texture2D(tDisp, texcoords).xyz;
		disp = (disp - 0.5) * 2.0 * AMPLITUDE;

		// Limit displacement by vertex colour (black = stationary).
		disp *= gl_Color.xyz;

		// Can't combine these into one vector, or we lose the ability to limit
		// individual axes.
		vec3 dispView = worldViewX * disp.x + worldViewY * disp.y + worldViewZ * disp.z;

		position = (gl_ModelViewMatrix * gl_Vertex) + vec4(dispView, 0.0);
		return gl_ProjectionMatrix * position;
	}
	""")
	position_fn = POSITION_FN.substitute(frequency=ob["SH_freq"],
			amplitude=ob["SH_amp"])

	verts = create_vert_shader(model=model, position_fn=position_fn)
	frags = create_frag_shader(model=model, alpha=alpha, twosided=twosided)
	cb = WindCallback(ob["SH_speed"])
	shader = _set_shader(ob, verts, frags, cb)
	if shader is not None:
		# Third texture slot is for displacement.
		shader.setSampler("tDisp", 2)


class WindCallback:
	'''
	Makes the leaves move. Called once per frame per instance of the shader.
	'''

	PHASE_STEPX = (1.0/3.0) * 0.001
	PHASE_STEPY = (1.0/4.5) * 0.001

	def __init__(self, speed):
		self.speedx = WindCallback.PHASE_STEPX * speed
		self.speedy = WindCallback.PHASE_STEPY * speed
		self.phasex = self.phasey = 0.0

	def __call__(self, shader, world_to_cam, world_to_cam_vec):
		# Set displacement texture lookup offset
		self.phasex = (self.phasex + self.speedx) % 1.0
		self.phasey = (self.phasey + self.speedy) % 1.0
		shader.setUniform2f("phase", self.phasex, self.phasey)

		shader.setUniformfv("worldViewX", world_to_cam_vec * XAXIS)
		shader.setUniformfv("worldViewY", world_to_cam_vec * YAXIS)
		shader.setUniformfv("worldViewZ", world_to_cam_vec * ZAXIS)


calc_light = """

	// Lighting calculation

	uniform vec3 key_light_dir;
	uniform vec4 key_light_col;

	uniform vec3 fill_light1_dir;
	uniform vec4 fill_light1_col;

	uniform vec3 fill_light2_dir;
	uniform vec4 fill_light2_col;

	uniform vec4 cust_light1_pos;
	uniform vec3 cust_light1_dir;
	uniform vec4 cust_light1_col;
	uniform float cust_light1_spotcutoff;
	uniform float cust_light1_spotcoscutoff;
	uniform float cust_light1_spotexponent;
	uniform float cust_light1_dist;

	uniform vec4 cust_light2_pos;
	uniform vec3 cust_light2_dir;
	uniform vec4 cust_light2_col;
	uniform float cust_light2_spotcutoff;
	uniform float cust_light2_spotcoscutoff;
	uniform float cust_light2_spotexponent;
	uniform float cust_light2_dist;

	float intensity(vec3 nor, vec3 direction) {
		return max(dot(nor, direction), 0.0);
	}

	float intensity_hemi(vec3 nor, vec3 direction) {
		return max(dot(nor, direction) * 0.5 + 0.5, 0.0);
	}

	float intensity_user(vec3 nor, vec4 pos, vec4 lightpos, vec3 dir,
			float cutoff, float coscutoff, float exponent, float maxdist) {

		float attenuation;
		vec3 viewLight;

		if (pos.w == 0.0) {
			// Directional (sun)
			viewLight = pos.xyz;
			attenuation = 1.0;

		} else {
			// Point or spot
			viewLight = lightpos.xyz - pos.xyz;
			float dist = length(viewLight);
			attenuation = clamp((maxdist - dist) / maxdist, 0.0, 1.0);

			viewLight = normalize(viewLight);

			if (cutoff <= 90.0) {
				// Spotlight; adjust attenuation.
				float cosCone = max(0.0, dot(-viewLight, dir.xyz));
				if (cosCone < coscutoff) {
					// outside of spotlight cone
					attenuation = 0.0;
				} else {
					attenuation *= pow(cosCone - coscutoff, exponent / 128.0);
				}
			}
		}
		return max(dot(nor, viewLight), 0.0) * attenuation;
	}

	vec4 calc_light(vec4 pos, vec3 nor) {
		vec3 viewLight;
		vec4 lightCol = vec4(0.0);

		// Key light
		lightCol += key_light_col * intensity(nor, key_light_dir);

		// Fill lights
		lightCol += fill_light1_col * intensity_hemi(nor, fill_light1_dir);
		lightCol += fill_light2_col * intensity_hemi(nor, fill_light2_dir);

		// User lights
		lightCol += cust_light1_col * intensity_user(nor, pos,
				cust_light1_pos,
				cust_light1_dir,
				cust_light1_spotcutoff,
				cust_light1_spotcoscutoff,
				cust_light1_spotexponent,
				cust_light1_dist);
		lightCol += cust_light2_col * intensity_user(nor, pos,
				cust_light2_pos,
				cust_light2_dir,
				cust_light2_spotcutoff,
				cust_light2_spotcoscutoff,
				cust_light2_spotexponent,
				cust_light2_dist);

		return lightCol;
	}
"""

def create_vert_shader(model='PHONG', position_fn=None):

	if model == 'PHONG':
		light_header = ""
		varying = ""
		lighting = """
		normal = normalize(gl_NormalMatrix * gl_Normal);
		"""
	elif model == 'GOURAUD':
		light_header = calc_light
		varying = """
		varying vec4 lightCol;
		"""
		lighting = """
		normal = normalize(gl_NormalMatrix * gl_Normal);
		lightCol = calc_light(position, normal);
		"""
	else:
		light_header = ""
		varying = ""
		lighting = ""

	if position_fn is None:
		position_fn = """
		vec4 getPosition() {
			position = gl_ModelViewMatrix * gl_Vertex;
			return gl_ModelViewProjectionMatrix * gl_Vertex;
		}
		"""

	verts = Template("""
	${light_header}

	// ${model} vertex shader

	// Position and normal in view space.
	varying vec4 position;
	// Always declared, but not always needed.
	varying vec3 normal;

	${varying}
	${position_fn}
 
 	void main() {
		gl_Position = getPosition();
 
 		// Transfer tex coords.
 		gl_TexCoord[0] = gl_MultiTexCoord0;
 
 		// Lighting (note: no perspective transform)
		${lighting}
 	}
	""")
	return verts.substitute(light_header=light_header, model=model,
			varying=varying, position_fn=position_fn, lighting=lighting)

def create_frag_shader(model='PHONG', alpha='CLIP', twosided=False):
	if alpha == 'CLIP':
		alpha1 = """
		// Prevent z-fighting by using a clip alpha test.
		if (col.a < 0.5)
			discard;
		"""
		alpha2 = """
		// Using clip alpha; see above.
		gl_FragColor.a = 1.0;
		"""
	elif alpha == 'BLEND':
		alpha1 = ""
		alpha2 = """
		gl_FragColor.a = col.a;
		"""
	else:
		alpha1 = ""
		alpha2 = """
		gl_FragColor.a = 1.0;
		"""

	if model == 'PHONG':
		light_header = calc_light
		varying = """
		varying vec3 normal;
		"""
		if not twosided:
			lighting = """
			vec3 norm = normalize(normal);
			vec4 lightCol = calc_light(position, norm);
			gl_FragColor = col * lightCol;
			"""
		else:
			lighting = """
			vec3 norm = normalize(normal);
			if (!gl_FrontFacing)
				norm = -norm;
			vec4 lightCol = calc_light(position, norm);
			gl_FragColor = col * lightCol;
			"""
	elif model == 'GOURAUD':
		light_header = ""
		varying = """
		varying vec4 lightCol;
		"""
		lighting = """
		gl_FragColor = col * lightCol;
		"""
	else:
		light_header = ""
		varying = ""
		lighting = """
		gl_FragColor = col;
		"""

	frag = Template("""
	${light_header}

	// ${model} fragment shader

	uniform sampler2D tCol;
	uniform vec3 mist_colour;
	uniform float mist_depth;

	${varying}
	varying vec4 position;

	void main() {
		vec4 col = texture2D(tCol, gl_TexCoord[0].st);

		${alpha1}
		${lighting}
		${alpha2}

		gl_FragColor.xyz = mix(gl_FragColor.xyz, mist_colour,
				position.z / mist_depth);

		// Prevent pure black, as it messes with the DoF shader.
		gl_FragColor.g += 0.01;
	}
	""")
	return frag.substitute(model=model, light_header=light_header,
			varying=varying, lighting=lighting,
			alpha1=alpha1, alpha2=alpha2)
