import bge

def shader_init(c):
    '''Sets up a GLSL shader for animated waves on the water.'''

    verts = """
    const float PI2 = 2.0 * 3.14159;
    const vec3 FREQ = vec3(4.0);
    const float AMPLITUDE = 1.0;

    uniform vec3 phase;

    varying vec3 normal;

    void main() {
        // Shift position of vertex using a sine generator.
        vec3 waveAmp = gl_Vertex.xyz * FREQ + phase * PI2;
        vec3 disp = sin(waveAmp) * AMPLITUDE;

        // Limit displacement by vertex colour (black = stationary).
        disp *= gl_Color.x;

        gl_Position = gl_ModelViewProjectionMatrix * (gl_Vertex + vec4(disp, 0.0));

        // Transfer tex coords.
        gl_TexCoord[0] = gl_MultiTexCoord0;

        // Lighting
        normal = normalize(gl_NormalMatrix * gl_Normal);
    }
    """

    fragments = """
    uniform sampler2D tCol;

    varying vec3 normal;

    void main() {
        vec4 col = texture2D(tCol, gl_TexCoord[0].st);
        // Prevent z-fighting by using a clip alpha test.
        if (col.a < 0.5)
            discard;

        vec4 lightCol = vec4(0.0);
        for (int i = 0; i < 4; i++) {
            vec3 viewLight = normalize(gl_LightSource[i].position.xyz);
            vec3 norm = normalize(normal);
            float angle = clamp(dot(norm, viewLight), 0.0, 1.0);
            lightCol += gl_LightSource[i].diffuse * angle;
        }
        lightCol.xyz += vec3(0.1);
        lightCol.a = 1.0;

        gl_FragColor = col * lightCol;

        // Prevent pure black, as it messes with the DoF shader.
        gl_FragColor.g += 0.01;

        // Using clip alpha; see above.
        gl_FragColor.a = 1.0;
    }
    """

    ob = c.owner
    me = ob.meshes[0]
    mat = me.materials[0]

    if not hasattr(mat, "getShader"):
        return

    shader = mat.getShader()
    if shader != None:
        if not shader.isValid():
            shader.setSource(verts, fragments, True)
        shader.setSampler("tCol", 0)
    ob["off_low_x"] = 0.0
    ob["off_low_y"] = 0.0
    ob["off_low_z"] = 0.0

PHASE_STEP = (0.003333333333333333, 0.002222222222222, 0.00111111111111111)

def shader_step(c):
    '''Makes the leaves move.'''

    ob = c.owner
    me = ob.meshes[0]
    mat = me.materials[0]

    if not hasattr(mat, "getShader"):
        return

    ob["off_low_x"] += PHASE_STEP[0]
    ob["off_low_x"] %= 1.0
    ob["off_low_y"] += PHASE_STEP[1]
    ob["off_low_y"] %= 1.0
    ob["off_low_z"] += PHASE_STEP[2]
    ob["off_low_z"] %= 1.0

    shader = mat.getShader()
    if shader != None:
        # pass uniform to the shader
        shader.setUniform3f("phase",
                ob["off_low_x"],
                ob["off_low_y"],
                ob["off_low_z"])
