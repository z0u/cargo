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
const float radius = 5.0/512.0;
const float maxdepth = 1.0;
const float focus = 0.5;
const float nsamples = 32;
//const float contribution = 1.0 / nsamples;
const float contribution = 1.0;

vec4 get_colour(vec2 offset) {
    return texture2D(bgl_RenderedTexture, gl_TexCoord[0].xy + offset);
}
float get_depth(vec2 offset) {
    return texture2D(bgl_DepthTexture, gl_TexCoord[0].xy + offset).r;
}
float get_focus(float depth) {
    return abs(depth * 2 - 1);
}

vec4 blur_sample(float depth, float depthNorm, vec2 offset, out float influence) {
    float focusFactor;

    offset *= radius * get_focus(depth);
    float idepth = get_depth(offset);
    float focus = get_focus(idepth);
    float contrib;
    if (idepth < depth)
        contrib = focus;
    else
        contrib = 1.0;
    //float sw = step(0, depth - idepth);
    //influence += contribution * sw * focus;
    //return get_colour(offset) * contribution * sw * focus;
    influence += contrib;
    return get_colour(offset) * contrib;
}

void main(void) {
    vec4 blur = vec4(0.0);
    vec4 result = texture2D(bgl_RenderedTexture, gl_TexCoord[0].xy);
    float depth = get_depth(vec2(0));
    float depthNorm = depth * 100 - 99;
    float influence = 0;
    vec2 offset;

    blur = result;
    influence = 1.0;
    blur += blur_sample(depth, depthNorm, vec2(0.220308, 0.190851), influence);
    blur += blur_sample(depth, depthNorm, vec2(0.009629, 0.891577), influence);
    blur += blur_sample(depth, depthNorm, vec2(0.484737, 0.344041), influence);
    blur += blur_sample(depth, depthNorm, vec2(0.093412, 0.766928), influence);
    blur += blur_sample(depth, depthNorm, vec2(0.508705, 0.597546), influence);
    blur += blur_sample(depth, depthNorm, vec2(0.147513, 0.539470), influence);
    blur += blur_sample(depth, depthNorm, vec2(0.746857, 0.347826), influence);
    blur += blur_sample(depth, depthNorm, vec2(0.601831, -0.453539), influence);
    blur += blur_sample(depth, depthNorm, vec2(0.069247, -0.078927), influence);
    blur += blur_sample(depth, depthNorm, vec2(0.663293, -0.088260), influence);
    blur += blur_sample(depth, depthNorm, vec2(0.190517, -0.103302), influence);
    blur += blur_sample(depth, depthNorm, vec2(0.528019, 0.138705), influence);
    blur += blur_sample(depth, depthNorm, vec2(0.355210, -0.237941), influence);
    blur += blur_sample(depth, depthNorm, vec2(-0.617317, 0.319847), influence);
    blur += blur_sample(depth, depthNorm, vec2(-0.096463, 0.919791), influence);
    blur += blur_sample(depth, depthNorm, vec2(-0.288909, 0.280413), influence);
    blur += blur_sample(depth, depthNorm, vec2(-0.157119, 0.787627), influence);
    blur += blur_sample(depth, depthNorm, vec2(-0.031250, 0.442411), influence);
    blur += blur_sample(depth, depthNorm, vec2(-0.336061, 0.600733), influence);
    blur += blur_sample(depth, depthNorm, vec2(-0.104189, 0.139011), influence);
    blur += blur_sample(depth, depthNorm, vec2(0.311419, -0.621612), influence);
    blur += blur_sample(depth, depthNorm, vec2(-0.462600, -0.800826), influence);
    blur += blur_sample(depth, depthNorm, vec2(0.068910, -0.396675), influence);
    blur += blur_sample(depth, depthNorm, vec2(-0.335844, -0.729556), influence);
    blur += blur_sample(depth, depthNorm, vec2(-0.234761, -0.376287), influence);
    blur += blur_sample(depth, depthNorm, vec2(-0.081222, -0.683535), influence);
    blur += blur_sample(depth, depthNorm, vec2(-0.494954, -0.488265), influence);
    blur += blur_sample(depth, depthNorm, vec2(-0.904582, 0.192490), influence);
    blur += blur_sample(depth, depthNorm, vec2(-0.355966, -0.188117), influence);
    blur += blur_sample(depth, depthNorm, vec2(-0.797630, 0.093962), influence);
    blur += blur_sample(depth, depthNorm, vec2(-0.430415, 0.106992), influence);
    blur += blur_sample(depth, depthNorm, vec2(-0.675179, -0.133977), influence);

    result = blur / influence;
    //blur = result * (1 - influence) + blur;
    //result = mix(result, blur, depth * 100 - 99);

    gl_FragColor = result;
    //gl_FragColor = vec4(get_focus(depth));
}