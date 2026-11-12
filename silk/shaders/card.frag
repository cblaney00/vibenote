#version 440
// A note card of silk (his pick, 2026-11-12: "notes with weight"): rounded, finely woven, a
// sheen that slides across it towards the mouse, and a copper edge that glows as it lifts.
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float time;
    float lift;
    vec2 size;
    vec2 mouse;
    vec4 tint;
    vec4 edge;
};

void main() {
    vec2 p = qt_TexCoord0 * size;
    vec2 hsz = size * 0.5 - vec2(1.0);
    vec2 d2 = abs(p - size * 0.5) - (hsz - vec2(11.0));
    float d = length(max(d2, 0.0)) + min(max(d2.x, d2.y), 0.0) - 11.0;
    float alpha = 1.0 - smoothstep(-1.0, 0.5, d);
    vec2 w = p * 0.9;
    float cell = mod(floor(w.x / 2.0) + floor(w.y / 2.0), 2.0);
    float thread = cell > 0.5 ? 0.5 + 0.5 * sin(w.x * 3.1416) : 0.5 + 0.5 * sin(w.y * 3.1416);
    float fold = 0.5 + 0.5 * sin(p.x * 0.02 + p.y * 0.035 + time * 0.3);
    vec3 col = tint.rgb * mix(0.9, 1.08, thread) * (0.92 + 0.14 * fold);
    // the sheen: a soft diagonal band through the mouse
    vec2 dir = normalize(vec2(1.0, -0.55));
    float band = exp(-pow(dot(p - mouse, dir) / 46.0, 2.0));
    float reach = exp(-distance(p, mouse) / 260.0);
    col += vec3(0.30, 0.22, 0.15) * band * reach * (0.12 + 0.3 * lift);
    // top light, as if it catches the light from above when lifted
    col += vec3(0.05, 0.08, 0.06) * (1.0 - p.y / size.y) * (0.3 + lift);
    float rim = exp(-abs(d) / 1.4);
    col = mix(col, edge.rgb, rim * (0.35 + 0.65 * lift) * edge.a);
    fragColor = vec4(col, 1.0) * alpha * qt_Opacity;
}
