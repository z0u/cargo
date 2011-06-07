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

//
// Uniforms provided by Blender
//
uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;
uniform float bgl_RenderedTextureWidth;
uniform float bgl_RenderedTextureHeight;

//
// Uniforms set as game object properties (see logic buttons)
//
uniform float focalDistance;
uniform float blurRadius;

vec4 get_colour(vec2 offset) {
    return texture2D(bgl_RenderedTexture, gl_TexCoord[0].xy + offset);
}
float get_depth(vec2 offset) {
    return texture2D(bgl_DepthTexture, gl_TexCoord[0].xy + offset).r;
}
float get_blur(float depth) {
    return abs(depth * 2.0 - (2.0 * focalDistance));
}

//
// Take a single sample from the image to contribute to the blur filter.
//
// @param depth The depth of the current pixel.
// @param blur  The amount to blur; used to scale the radius. Should be
//              related to the depth.
// @param offset The coordinates to sample, relative to the current pixel.
//              Factor of the filter radius.
// @param influence In: the total strength of the samples up to this point.
//              Out: the strength of the samples, including this one. This
//              is effectively a sample count: if all samples were equally
//              applied, each one would add 1 to the influence. However,
//              due to occlusion and different z-depths, a sample may
//              contribute a smaller fraction of its colour.
//
vec4 blur_sample(float depth, vec2 blur, vec2 offset, inout float influence) {
    float idepth;
    float contrib;

    // Use the focus of the current point to drive the filter radius.
    offset *= blur * blurRadius;

    // If the sample is closer than the current pixel (depth-wise), modulate its
    // influence by how blurry it is. I.e. if it is fully in-focus, it will not
    // contribute at all. This part was taken from the paper "Real-Time Depth
    // of Field Simulation", from "From ShaderX2 \u2013 Shader Programming Tips
    // and Tricks with DirectX 9".
    // http://developer.amd.com/media/gpu_assets/ShaderX2_Real-TimeDepthOfFieldSimulation.pdf

    idepth = get_depth(offset);
    if (idepth < depth)
        contrib = get_blur(idepth);
    else
        contrib = 1.0;

    influence += contrib;
    return get_colour(offset) * contrib;
}

void main(void) {
    vec4 col = get_colour(vec2(0.0));
    float depth = get_depth(vec2(0.0));
    float aspect = bgl_RenderedTextureWidth / bgl_RenderedTextureHeight;
    vec2 blur = vec2(get_blur(depth)) * vec2(1.0, aspect);
    float influence = 1.0;

    // Bokeh: Spiral
    col += blur_sample(depth, blur, vec2(0.727598, -0.083846), influence);
    col += blur_sample(depth, blur, vec2(-0.232845, 0.369841), influence);
    col += blur_sample(depth, blur, vec2(-0.361229, 0.069334), influence);
    col += blur_sample(depth, blur, vec2(-0.248693, -0.230454), influence);
    col += blur_sample(depth, blur, vec2(-0.851074, 0.000078), influence);
    col += blur_sample(depth, blur, vec2(-0.829571, 0.398621), influence);
    col += blur_sample(depth, blur, vec2(-0.713448, -0.372055), influence);
    col += blur_sample(depth, blur, vec2(-0.450084, -0.616818), influence);
    col += blur_sample(depth, blur, vec2(-0.118037, -0.736375), influence);
    col += blur_sample(depth, blur, vec2(0.196000, -0.728203), influence);
    col += blur_sample(depth, blur, vec2(0.457748, -0.601702), influence);
    col += blur_sample(depth, blur, vec2(0.654456, -0.384559), influence);
    col += blur_sample(depth, blur, vec2(0.652880, 0.223744), influence);
    col += blur_sample(depth, blur, vec2(0.484907, 0.429292), influence);
    col += blur_sample(depth, blur, vec2(0.260309, 0.523052), influence);
    col += blur_sample(depth, blur, vec2(0.005869, 0.522435), influence);
    col += blur_sample(depth, blur, vec2(-0.799039, -0.202063), influence);
    col += blur_sample(depth, blur, vec2(-0.286281, -0.691932), influence);
    col += blur_sample(depth, blur, vec2(0.332811, -0.678216), influence);
    col += blur_sample(depth, blur, vec2(0.711320, -0.245884), influence);
    col += blur_sample(depth, blur, vec2(0.707670, 0.080424), influence);
    col += blur_sample(depth, blur, vec2(0.380423, 0.488774), influence);
    col += blur_sample(depth, blur, vec2(-0.117451, 0.472880), influence);
    col += blur_sample(depth, blur, vec2(-0.320076, 0.230215), influence);
    col += blur_sample(depth, blur, vec2(-0.341791, -0.091123), influence);
    col += blur_sample(depth, blur, vec2(-0.116627, -0.311663), influence);
    col += blur_sample(depth, blur, vec2(-0.801338, 0.488685), influence);
    col += blur_sample(depth, blur, vec2(-0.862699, 0.209245), influence);
    col += blur_sample(depth, blur, vec2(-0.596620, -0.510339), influence);
    col += blur_sample(depth, blur, vec2(0.045917, -0.748743), influence);
    col += blur_sample(depth, blur, vec2(0.566514, -0.502467), influence);
    col += blur_sample(depth, blur, vec2(0.574893, 0.341632), influence);
    col += blur_sample(depth, blur, vec2(0.132835, 0.533804), influence);

    gl_FragColor = col / influence;

    // For debugging the blur factor
    //gl_FragColor = vec4(get_blur(depth));
}
