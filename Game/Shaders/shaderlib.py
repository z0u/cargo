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

#
# These shaders developed with the help of the excellent GLSL Programming
# Wikibook, primarily authored by Martin Kraus:
#
# http://en.wikibooks.org/wiki/GLSL_Programming/Blender/Diffuse_Reflection
#
# Which states, "Unless stated otherwise, all example source code on this page
# is granted to the public domain."
#

calc_light = """
	const int NUM_LIGHTS = gl_MaxLights;

	vec4 calc_light(vec4 pos, vec3 nor) {
		vec4 lightCol = vec4(0.0);
		for (int i = 0; i < NUM_LIGHTS; i++) {
			vec3 viewLight;
			float attenuation;
			if (gl_LightSource[i].position.w == 0.0) {
				// Directional
				viewLight = normalize(gl_LightSource[i].position.xyz);
				attenuation = 1.0;

			} else {
				// Point
				viewLight = vec3(normalize(gl_LightSource[i].position - pos));
				
				if (gl_LightSource[0].spotCutoff <= 90.0) {
					// spotlight
					float cosCone = max(0.0, dot(-viewLight, gl_LightSource[i].spotDirection.xyz));
					if (cosCone < gl_LightSource[i].spotCosCutoff) {
						// outside of spotlight cone
						attenuation = 0.0;
					} else {
						attenuation = pow(cosCone, gl_LightSource[i].spotExponent);
					}

				} else {
					// point light
					attenuation = 1.0;
				}
			}
			float angle = max(dot(nor, viewLight), 0.0);
			lightCol += gl_LightSource[i].diffuse * angle * attenuation;
		}
		return lightCol;
	}
"""

# Simple Phong shader; no specular.
frag_phong = """
	uniform sampler2D tCol;

	varying vec3 normal;
	varying vec4 position;

	""" + calc_light + """

	void main() {
		vec4 col = texture2D(tCol, gl_TexCoord[0].st);
		// Prevent z-fighting by using a clip alpha test.
		if (col.a < 0.5)
			discard;

		vec3 norm = normalize(normal);
		//if (!gl_FrontFacing)
		//	norm = -norm;
		vec4 lightCol = calc_light(position, norm);
		//lightCol.xyz += vec3(0.1);
		lightCol.a = 1.0;

		gl_FragColor = col * lightCol;

		// Prevent pure black, as it messes with the DoF shader.
		//gl_FragColor.g += 0.01;

		// Using clip alpha; see above.
		gl_FragColor.a = 1.0;
	}
"""

frag_gouraud = """
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
