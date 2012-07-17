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
    return co;
}

vec4 get_colour(vec2 co) {
    return texture2D(bgl_RenderedTexture, co);
}

float get_depth(vec2 co) {
    return texture2D(bgl_DepthTexture, co).r;
}

float get_blur(float depth) {
    // Depth buffer is inverse linear. Find the difference between this
    // and the focal depth, and convert back to something like world
    // units (linear).
    return 10.0 * abs((depth - focalDepth) / 1.0);
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
    vec4 col;
    vec2 co;

    // Use the focus of the current point to drive the filter radius.
    offset *= blur * blurRadius;
    co = nearest_texel(get_coord(offset));

    col = get_colour(co);

    // If the sample is closer than the current pixel (depth-wise), modulate its
    // influence by how blurry it is. I.e. if it is fully in-focus, it will not
    // contribute at all. This part was taken from the paper "Real-Time Depth
    // of Field Simulation", from "From ShaderX2 \u2013 Shader Programming Tips
    // and Tricks with DirectX 9".
    // http://developer.amd.com/media/gpu_assets/ShaderX2_Real-TimeDepthOfFieldSimulation.pdf

    idepth = get_depth(co);
    if (idepth < depth)
        contrib = get_blur(idepth);
    else
        contrib = 1.0;

    influence += contrib;
    return col * contrib;
}

void main(void) {
    dimensions = vec2(bgl_RenderedTextureWidth, bgl_RenderedTextureHeight);

    // Hack for incorrect texture size
    dimensions += vec2(1.0);

    dimensions_inv = vec2(1.0) / dimensions;
    halftexel = vec2(0.5) / dimensions;
    maxcoord = vec2(1.0) - halftexel;

    float depth = get_depth(gl_TexCoord[0].st);
    float aspect = dimensions.x / dimensions.y;
    vec2 blur = vec2(get_blur(depth)) * vec2(1.0, aspect);
    vec4 col = vec4(0.0);
    float influence = 0.000001;

    // Bokeh: Spiral (18 samples)
    col += blur_sample(depth, blur, vec2(-0.842387, 0.253423), influence);
    col += blur_sample(depth, blur, vec2(-0.822194, -0.185772), influence);
    col += blur_sample(depth, blur, vec2(-0.584927, -0.559341), influence);
    col += blur_sample(depth, blur, vec2(-0.176021, -0.746126), influence);
    col += blur_sample(depth, blur, vec2(0.263175, -0.660306), influence);
    col += blur_sample(depth, blur, vec2(0.566068, -0.337219), influence);
    col += blur_sample(depth, blur, vec2(0.571117, 0.112073), influence);
    col += blur_sample(depth, blur, vec2(0.248030, 0.420015), influence);
    col += blur_sample(depth, blur, vec2(-0.191166, 0.329147), influence);
    col += blur_sample(depth, blur, vec2(-0.862580, 0.033825), influence);
    col += blur_sample(depth, blur, vec2(-0.721229, -0.407894), influence);
    col += blur_sample(depth, blur, vec2(-0.398143, -0.683023), influence);
    col += blur_sample(depth, blur, vec2(0.058722, -0.743601), influence);
    col += blur_sample(depth, blur, vec2(0.444911, -0.524004), influence);
    col += blur_sample(depth, blur, vec2(0.608978, -0.117621), influence);
    col += blur_sample(depth, blur, vec2(0.439863, 0.306430), influence);
    col += blur_sample(depth, blur, vec2(0.008239, 0.435159), influence);
    col += blur_sample(depth, blur, vec2(-0.287082, 0.104501), influence);

    gl_FragColor = col / influence;

    // For debugging the blur factor
    //gl_FragColor = mix(vec4(get_blur(depth)), gl_FragColor, 0.0000001);
    //gl_FragColor = mix(vec4(depth), gl_FragColor, 0.0000001);

    // Diff against original colour
    //gl_FragColor = abs(gl_FragColor - texture2D(bgl_RenderedTexture, gl_TexCoord[0].st));
}