//
// Copyright 2011 Alex Fraser <alex@phatcore.com>
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.
//

// Fragment shader

uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;
const float radius = 1.0/512.0;
const float maxdepth = 1.0;
const float focus = 0.5;
const float nsamples = 8;
const float contribution = 1.0 / nsamples;

vec4 get_colour(vec2 offset) {
    return texture2D(bgl_RenderedTexture, gl_TexCoord[0].xy + offset);
}
float get_depth(vec2 offset) {
    return texture2D(bgl_DepthTexture, gl_TexCoord[0].xy + offset).r;
}

vec4 blur_sample(float depth, float depthNorm, vec2 offset, out float influence) {
    offset *= radius * depthNorm;
    float ndepth = get_depth(offset);
    float sw = step(0, ndepth - depth);
    influence += contribution * sw;
    return get_colour(offset) * contribution * sw;
}

void main(void) {
    vec4 blur = vec4(0.0);
    vec4 result = texture2D(bgl_RenderedTexture, gl_TexCoord[0].xy);
    float depth = get_depth(vec2(0));
    float depthNorm = depth * 100 - 99;
    float influence = 0;
    vec2 offset;

    offset = vec2(-0.707107, 0.707107);
    blur += blur_sample(depth, depthNorm, offset, influence);

    offset = vec2(0, 1);
    blur += blur_sample(depth, depthNorm, offset, influence);

    offset = vec2(0.707107, 0.707107);
    blur += blur_sample(depth, depthNorm, offset, influence);

    offset = vec2(1, 0);
    blur += blur_sample(depth, depthNorm, offset, influence);

    offset = vec2(0.707107, -0.707107);
    blur += blur_sample(depth, depthNorm, offset, influence);

    offset = vec2(0, -1);
    blur += blur_sample(depth, depthNorm, offset, influence);

    offset = vec2(-0.707107, -0.707107);
    blur += blur_sample(depth, depthNorm, offset, influence);

    offset = vec2(-1, 0);
    blur += blur_sample(depth, depthNorm, offset, influence);

    blur = result * (1 - influence) + blur;
    result = mix(result, blur, depth * 100 - 99);

    gl_FragColor = result;
}
