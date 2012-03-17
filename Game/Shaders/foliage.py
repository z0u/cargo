from string import Template

import bge
import mathutils

from . import shaderlib

DEBUG = False

def wave_vert_shader(axes="xyz", frequency=4.0, amplitude=1.0):

	if len(axes) == 1:
		datatype = "float"
	else:
		datatype = "vec%d" % len(axes)

	verts = Template("""
	const float PI2 = 2.0 * 3.14159;
	const ${datatype} FREQ = ${datatype}(${frequency});
	const float AMPLITUDE = ${amplitude};

	uniform ${datatype} phase;

	varying vec3 normal;
	varying vec4 position;
	varying vec4 lightCol;

	""" + shaderlib.calc_light + """

	void main() {
		// Shift position of vertex using a sine generator.
		${datatype} waveAmp = gl_Vertex.${axes} * FREQ + phase * PI2;
		${datatype} disp = sin(waveAmp) * AMPLITUDE;

		// Limit displacement by vertex colour (black = stationary).
		disp *= gl_Color.x;

		vec4 pos = gl_Vertex;
		pos.${axes} += disp;
		position = gl_ModelViewMatrix * pos;
		gl_Position = gl_ModelViewProjectionMatrix * pos;

		// Transfer tex coords.
		gl_TexCoord[0] = gl_MultiTexCoord0;

		// Lighting
		normal = normalize(gl_NormalMatrix * gl_Normal);
		lightCol = calc_light(position, normal);
	}
	""")
	return verts.substitute(datatype=datatype, axes=axes, frequency=frequency,
			amplitude=amplitude)

def print_code(text):
	for i, line in enumerate(text.splitlines()):
		print(i + 1, line)

def shader_init(c):
	'''Sets up a GLSL shader for animated foliage, such as grass and tree
	leaves.'''

	ob = c.owner
	me = ob.meshes[0]
	mat = me.materials[0]

	if not hasattr(mat, "getShader"):
		return

	verts = wave_vert_shader(ob["SH_axes"], ob["SH_freq"], ob["SH_amp"])
	if DEBUG:
		print_code(verts)
		print_code(shaderlib.frag_gouraud)

	shader = mat.getShader()
	if shader != None:
		if not shader.isValid():
			shader.setSource(verts, shaderlib.frag_gouraud, True)
		shader.setSampler("tCol", 0)

	for axis in ob["SH_axes"]:
		ob["_phase{}".format(axis)] = 0.0

PHASE_STEP = mathutils.Vector((1.0/3.0, 1.0/4.5, 1.0/9.0))

def shader_step(c):
	'''Makes the leaves move.'''

	ob = c.owner
	me = ob.meshes[0]
	mat = me.materials[0]

	if not hasattr(mat, "getShader"):
		return

	speed = PHASE_STEP * ob['SH_speed']
	phases = []
	for i, axis in enumerate(ob["SH_axes"]):
		var = "_phase{}".format(axis)
		val = ob[var]
		val += speed[i]
		val %= 1.0
		phases.append(val)
		ob[var] = val

	shader = mat.getShader()
	if shader != None:
		# pass uniform to the shader
		if len(phases) == 1:
			shader.setUniform1f("phase", phases[0])
		else:
			shader.setUniformfv("phase", phases)
