//
// Copyright 2011 Alex Fraser. All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are met:
//
//   1. Redistributions of source code must retain the above copyright notice,
//      this list of conditions and the following disclaimer.
//
//   2. Redistributions in binary form must reproduce the above copyright
//      notice, this list of conditions and the following disclaimer in the
//      documentation and/or other materials provided with the distribution.
//
// THIS SOFTWARE IS PROVIDED BY ALEX FRASER ``AS IS'' AND ANY EXPRESS OR IMPLIED
// WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
// MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO
// EVENT SHALL ALEX FRASER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
// INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
// LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
// OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
// LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
// NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
// EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
//
// The views and conclusions contained in the software and documentation are
// those of the authors and should not be interpreted as representing official
// policies, either expressed or implied, of Alex Fraser.
//

// Fragment shader

//
// Uniforms provided by Blender
//
uniform sampler2D bgl_RenderedTexture;
uniform sampler2D bgl_DepthTexture;
uniform float bgl_RenderedTextureWidth;
uniform float bgl_RenderedTextureHeight;

vec2 dimensions;
vec2 dimensions_inv;
vec2 halftexel;
vec2 maxcoord;

//
// Uniforms set as game object properties (see logic buttons). focalDepth should
// be set as:
//
//     1.0 - zNear / z
//
// Where zNear is the distance to the near clip plane, and the z is the distance
// to the focal plane, both in world units.
//
uniform float focalDepth;
uniform float blurRadius;

//
// Get the coordinates that should be sampled for a given offset.
// These will be clamped to be within the image, to prevent fuzzy
// black borders from appearing around the image.
//
vec2 get_coord(in vec2 offset) {
    vec2 co = gl_TexCoord[0].st + offset;
    return co;
}
// Round to the nearest texel to prevent colour bleeding.
vec2 nearest_texel(in vec2 coord) {
    vec2 co = floor(coord * dimensions) + vec2(0.5);
    co *= dimensions_inv;
    co = clamp(co, halftexel, maxcoord);
    //vec2 co = clamp(coord, halftexel, maxcoord);
    return co;
}

vec4 get_colour(in vec2 co) {
    return texture2D(bgl_RenderedTexture, co);
}

float get_depth(in vec2 co) {
    return texture2D(bgl_DepthTexture, co).r;
}

float get_blur(in float depth) {
    // Find the difference between this and the focal depth.
    // Add a small safety margin to avoid division by zero later.
    return abs(depth - focalDepth) + 0.001;
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

vec4 blur_sample(in vec2 blur, in vec2 offset, inout float influence) {
    float idepth;
    float contrib;
    vec4 col;
    vec2 co;

    // Use the focus of the current point to drive the filter radius.
    offset *= blur;
    co = nearest_texel(get_coord(offset));

    col = get_colour(co);

    // Modulate the strength of the influence by how near the sample is
    // to the focal plane. Samples that are further from the focal plane
    // will have more influence, but that is OK, because the blur radius
    // will be smaller when computing in-focus pixels.
    idepth = get_depth(co);
    contrib = get_blur(idepth);

    influence += contrib;
    return col * contrib;
}

void main(void) {
    dimensions = vec2(bgl_RenderedTextureWidth, bgl_RenderedTextureHeight);

    dimensions_inv = vec2(1.0) / dimensions;
    halftexel = vec2(0.5) / dimensions;
    maxcoord = vec2(1.0) - halftexel;

    float depth = get_depth(gl_TexCoord[0].st);
    float aspect = dimensions.x / dimensions.y;
    vec2 blur = vec2(1.0, aspect) * get_blur(depth) * blurRadius;
    vec4 col = vec4(0.0);
    float influence = 0.000001;

    // Bokeh: Spiral2 (19 samples)
    col += blur_sample(blur, vec2(0.511072, -0.000000), influence);
    col += blur_sample(blur, vec2(0.533611, -0.194219), influence);
    col += blur_sample(blur, vec2(0.478504, -0.401513), influence);
    col += blur_sample(blur, vec2(0.340714, -0.590135), influence);
    col += blur_sample(blur, vec2(0.128190, -0.727000), influence);
    col += blur_sample(blur, vec2(-0.138051, -0.782923), influence);
    col += blur_sample(blur, vec2(-0.425893, -0.737668), influence);
    col += blur_sample(blur, vec2(-0.696006, -0.584019), influence);
    col += blur_sample(blur, vec2(-0.907139, -0.330172), influence);
    col += blur_sample(blur, vec2(-1.000000, -0.000000), influence);
    col += blur_sample(blur, vec2(-0.053361, 0.019422), influence);
    col += blur_sample(blur, vec2(-0.087001, 0.073002), influence);
    col += blur_sample(blur, vec2(-0.085179, 0.147534), influence);
    col += blur_sample(blur, vec2(-0.039443, 0.223692), influence);
    col += blur_sample(blur, vec2(0.049304, 0.279615), influence);
    col += blur_sample(blur, vec2(0.170357, 0.295067), influence);
    col += blur_sample(blur, vec2(0.304503, 0.255508), influence);
    col += blur_sample(blur, vec2(0.426889, 0.155375), influence);
    col += blur_sample(blur, vec2(0.000000, 0.000000), influence);

    gl_FragColor = col / influence;
    gl_FragColor.a = 1.0;

    // For debugging the blur factor
    //gl_FragColor = mix(vec4(get_blur(depth)), gl_FragColor, 0.0000001);
    //gl_FragColor = mix(vec4(depth), gl_FragColor, 0.0000001);

    // Diff against original colour
    //gl_FragColor = abs(gl_FragColor - texture2D(bgl_RenderedTexture, gl_TexCoord[0].st));
}