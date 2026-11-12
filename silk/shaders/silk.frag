#version 440
// The silk under everything (his ask, 2026-11-12: "textured and tangible"; his pick: silk you
// can touch). A fine weave, slow flowing folds lit by a light that follows the mouse (a copper
// glint near it), and ripples where he clicks. `offset` is where this panel sits in the
// window, so the cloth runs on unbroken from the sidebar to the page.
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float time;
    float level;
    vec2 size;
    vec2 mouse;
    vec2 offset;
    vec4 r0;
    vec4 r1;
    vec4 r2;
    vec4 r3;
};

float ripple(vec2 p, vec4 r) {
    float age = time - r.z;
    if (r.w <= 0.0 || age < 0.0 || age > 3.2) return 0.0;
    float d = distance(p, r.xy);
    float front = age * 240.0;
    float ring = exp(-pow((d - front) / 30.0, 2.0));
    return ring * sin((d - front) * 0.2) * (1.0 - age / 3.2) * r.w;
}

void main() {
    vec2 p = qt_TexCoord0 * size + offset;
    float rip = ripple(p, r0) + ripple(p, r1) + ripple(p, r2) + ripple(p, r3);
    vec2 q = p + vec2(rip * 5.0);
    float fold = 0.5 * sin(q.x * 0.010 + q.y * 0.017 + time * 0.21)
               + 0.35 * sin(q.x * 0.023 - q.y * 0.009 - time * 0.13 + 1.7)
               + 0.6 * sin((q.x + q.y) * 0.004 + time * 0.07);
    float h = fold + rip * 1.6;
    vec2 grad = vec2(dFdx(h), dFdy(h));
    vec3 n = normalize(vec3(-grad * 45.0, 1.0));
    vec3 L = normalize(vec3(mouse - p, 280.0));
    float diff = max(dot(n, L), 0.0);
    vec3 H = normalize(L + vec3(0.0, 0.0, 1.0));
    float spec = pow(max(dot(n, H), 0.0), 30.0);
    // the weave: threads over and under in a checker of tiny cells
    vec2 w = q * 0.9;
    float cell = mod(floor(w.x / 2.0) + floor(w.y / 2.0), 2.0);
    float thread = cell > 0.5 ? 0.5 + 0.5 * sin(w.x * 3.1416) : 0.5 + 0.5 * sin(w.y * 3.1416);
    float weave = mix(0.9, 1.07, thread);
    float near = exp(-distance(p, mouse) / 320.0);
    vec3 base = vec3(0.050, 0.104, 0.084) * level;
    vec3 col = base * weave * (0.72 + 0.5 * diff);
    col += vec3(0.10, 0.22, 0.17) * pow(clamp(0.5 + 0.3 * fold, 0.0, 1.0), 4.0) * 0.4 * level;
    col += vec3(0.34, 0.21, 0.12) * spec * near * 0.6;
    col += vec3(0.05, 0.03, 0.02) * near * 0.3;
    col += vec3(0.12, 0.08, 0.05) * max(rip, 0.0) * 0.25;
    fragColor = vec4(col, 1.0) * qt_Opacity;
}
