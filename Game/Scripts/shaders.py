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

DEBUG = True

LAMPDIR = (0.0, 0.0, 1.0)
XAXIS = mathutils.Vector((1.0, 0.0, 0.0))
YAXIS = mathutils.Vector((0.0, 1.0, 0.0))
ZAXIS = mathutils.Vector((0.0, 0.0, 1.0))

Shaderdef = namedtuple('Shaderdef', ['shader', 'callback'])

class ShaderCtrl(metaclass=bxt.types.Singleton):
	'''Looks after special GLSL materials in this scene.'''

	_prefix=""

	def __init__(self):
		self.shaders = set()

	def add_shader(self, shader, callback=None):
		self.shaders.add(Shaderdef(shader, callback))

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
		# CUSTOM LIGHT 1
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
			else:
				cust_light1_pos = world_to_camera * light.worldPosition
				cust_light1_pos.resize_4d()
				cust_light1_pos.w = 1.0
			if (light.type == light.SPOT):
				cust_light1_spotcutoff = light.spotsize / 2.0
				cust_light1_spotcoscutoff = math.cos(math.radians(
						cust_light1_spotcutoff))
				cust_light1_spotexponent = light.spotblend * 128.0
			else:
				cust_light1_spotcutoff = 180.0
				cust_light1_spotcoscutoff = -1.0
				cust_light1_spotexponent = light.spotblend * 128.0

		# CUSTOM LIGHT 2
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
			else:
				cust_light2_pos = world_to_camera * light.worldPosition
				cust_light2_pos.resize_4d()
				cust_light2_pos.w = 1.0
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

			if num_user_lights < 2:
				continue
			shader.setUniformfv("cust_light2_pos", cust_light2_pos)
			shader.setUniformfv("cust_light2_dir", cust_light2_dir)
			shader.setUniformfv("cust_light2_col", cust_light2_col)
			shader.setUniform1f("cust_light2_spotcutoff", cust_light2_spotcutoff)
			shader.setUniform1f("cust_light2_spotcoscutoff", cust_light2_spotcoscutoff)
			shader.setUniform1f("cust_light2_spotexponent", cust_light2_spotexponent)

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
		ShaderCtrl().add_shader(shader, callback)
	return shader


def _print_code(text):
	for i, line in enumerate(text.splitlines()):
		print(i + 1, line)


@bxt.utils.all_sensors_positive
@bxt.utils.owner
def set_phong(ob):
	'''Uses a standard Phong shader.'''
	_set_shader(ob, vert_basic, frag_phong)


@bxt.utils.all_sensors_positive
@bxt.utils.owner
def set_gouraud(ob):
	'''Uses a standard Phong shader.'''
	_set_shader(ob, vert_basic, frag_gouraud)


@bxt.utils.all_sensors_positive
@bxt.utils.owner
def set_windy(ob):
	'''Makes the vertices on a mesh wave as if blown by the wind.'''

	verts = wave_vert_shader(ob["SH_axes"], ob["SH_freq"], ob["SH_amp"])
	cb = WindCallback(ob["SH_speed"], ob["SH_axes"])
	shader = _set_shader(ob, verts, frag_gouraud, cb)
	if shader is not None:
		# Third texture slot is for displacement.
		shader.setSampler("tDisp", 2)


class WindCallback:
	'''
	Makes the leaves move. Called once per frame per instance of the shader.
	'''

	PHASE_STEPX = (1.0/3.0) * 0.001
	PHASE_STEPY = (1.0/4.5) * 0.001

	def __init__(self, speed, axes):
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

	uniform vec4 cust_light2_pos;
	uniform vec3 cust_light2_dir;
	uniform vec4 cust_light2_col;
	uniform float cust_light2_spotcutoff;
	uniform float cust_light2_spotcoscutoff;
	uniform float cust_light2_spotexponent;

	float intensity(vec3 nor, vec3 direction) {
		return max(dot(nor, direction), 0.0);
	}

	float intensity_hemi(vec3 nor, vec3 direction) {
		return max(dot(nor, direction) * 0.5 + 0.5, 0.0);
	}

	float intensity_user(vec3 nor, vec4 pos, vec4 lightpos, vec3 dir,
			float cutoff, float coscutoff, float exponent) {

		float attenuation;
		vec3 viewLight;

		if (pos.w == 0.0) {
			// Directional
			viewLight = pos.xyz;
			attenuation = 1.0;

		} else {
			// Point
			viewLight = normalize(lightpos.xyz - pos.xyz);

			if (cutoff <= 90.0) {
				// Spotlight
				float cosCone = max(0.0, dot(-viewLight, dir.xyz));
				if (cosCone < coscutoff) {
					// outside of spotlight cone
					attenuation = 0.0;
				} else {
					attenuation = pow(cosCone - coscutoff, exponent / 128.0);
				}

			} else {
				// Point light
				attenuation = 1.0;
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
				cust_light1_spotexponent);
		lightCol += cust_light2_col * intensity_user(nor, pos,
				cust_light2_pos,
				cust_light2_dir,
				cust_light2_spotcutoff,
				cust_light2_spotcoscutoff,
				cust_light2_spotexponent);

		return lightCol;
	}
"""

vert_basic = """

	// Basic vertex shader

	varying vec3 normal;
	varying vec4 position;
 
 	void main() {
 		gl_Position = gl_ModelViewProjectionMatrix * gl_Vertex;
 
 		// Transfer tex coords.
 		gl_TexCoord[0] = gl_MultiTexCoord0;
 
 		// Lighting (note: no perspective transform)
		position = gl_ModelViewMatrix * gl_Vertex;
 		normal = normalize(gl_NormalMatrix * gl_Normal);
 	}
"""

# Simple Phong shader; no specular.
frag_phong = calc_light + """

	// Phong fragment shader

	uniform sampler2D tCol;

	varying vec3 normal;
	varying vec4 position;

	void main() {
		vec4 col = texture2D(tCol, gl_TexCoord[0].st);
		// Prevent z-fighting by using a clip alpha test.
		if (col.a < 0.5)
			discard;

		vec3 norm = normalize(normal);
		//if (!gl_FrontFacing)
		//	norm = -norm;
		vec4 lightCol = calc_light(position, norm);

		gl_FragColor = col * lightCol;
		// Debugging
		//gl_FragColor = mix(gl_FragColor, vec4(1.0, 0.0, 1.0, 1.0), 0.9999);

		// Prevent pure black, as it messes with the DoF shader.
		gl_FragColor.g += 0.01;

		// Using clip alpha; see above.
		gl_FragColor.a = 1.0;
	}
"""

vert_gouraud = calc_light + """

	// Basic vertex shader

	varying vec4 lightCol;

	void main() {
		gl_Position = gl_ModelViewProjectionMatrix * gl_Vertex;

		// Transfer tex coords.
		gl_TexCoord[0] = gl_MultiTexCoord0;

		// Lighting (note: no perspective transform)
		vec4 position = gl_ModelViewMatrix * gl_Vertex;
		vec3 normal = normalize(gl_NormalMatrix * gl_Normal);
		lightCol = calc_light(position, normal);
	}
"""

# Simple Gouraud (interpolated) shader; no specular.
frag_gouraud = """

	// Gouraud fragment shader

	uniform sampler2D tCol;

	varying vec4 lightCol;

	void main() {
		vec4 col = texture2D(tCol, gl_TexCoord[0].st);

		// Prevent z-fighting by using a clip alpha test.
		if (col.a < 0.5)
			discard;

		gl_FragColor = col * lightCol;

		// Prevent pure black, as it messes with the DoF shader.
		gl_FragColor.g += 0.01;

		// Using clip alpha; see above.
		gl_FragColor.a = 1.0;
	}
"""

def wave_vert_shader(axes="xyz", frequency=4.0, amplitude=1.0):

	if len(axes) == 1:
		datatype = "float"
	else:
		datatype = "vec%d" % len(axes)

	verts = Template(calc_light + """

	// Wavy vertex shader

	const float PI2 = 2.0 * 3.14159;
	const float FREQ = ${frequency};
	const float AMPLITUDE = ${amplitude};

	uniform sampler2D tDisp;
	uniform vec3 worldViewX;
	uniform vec3 worldViewY;
	uniform vec3 worldViewZ;

	uniform vec2 phase;

	varying vec3 normal;
	varying vec4 position;
	varying vec4 lightCol;

	void main() {
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
		gl_Position = gl_ProjectionMatrix * position;

		// Transfer tex coords.
		gl_TexCoord[0] = gl_MultiTexCoord0;

		// Lighting
		normal = normalize(gl_NormalMatrix * gl_Normal);
		lightCol = calc_light(position, normal);
	}
	""")
	return verts.substitute(datatype=datatype, axes=axes, frequency=frequency,
			amplitude=amplitude)
