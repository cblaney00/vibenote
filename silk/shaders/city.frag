#version 440
// The living night city on the horizon (his pick, 2026-11-12): silk ribbons in the sky,
// stars, an odd flying light, three layers of towers with copper and peach windows, fog
// drifting along the horizon, and a glossy floor in perspective that mirrors it all, with
// lights streaming along its lanes. `par` slides the layers for depth as the mouse moves.
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float time;
    float par;
    vec2 size;
    vec4 paper;
};

float hash(float n) { return fract(sin(n * 127.1) * 43758.5453); }
float hash2(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash2(i), hash2(i + vec2(1.0, 0.0)), f.x),
               mix(hash2(i + vec2(0.0, 1.0)), hash2(i + vec2(1.0, 1.0)), f.x), f.y);
}
float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 4; i++) { v += a * noise(p); p *= 2.03; a *= 0.5; }
    return v;
}

vec3 scene(vec2 p, float hy, bool mirrored) {
    float t = time;
    float yy = clamp(p.y / hy, 0.0, 1.0);
    vec3 col = mix(vec3(0.020, 0.045, 0.035), vec3(0.075, 0.150, 0.115), pow(yy, 1.6));
    float gx = p.x / size.x - 0.58;
    col += vec3(0.20, 0.12, 0.07) * exp(-pow((hy - p.y) / 42.0, 2.0)) * exp(-gx * gx * 3.0) * 0.6;
    if (!mirrored) {
        float s = hash2(floor(p / 3.0));
        if (s > 0.996 && yy < 0.75)
            col += vec3(0.6, 0.55, 0.45) * (0.45 + 0.55 * sin(t * 1.3 + s * 90.0)) * 0.3;
        for (int k = 0; k < 2; k++) {
            float fk = float(k);
            float cy = hy * (0.28 + 0.22 * fk)
                     + sin(p.x * 0.006 + t * (0.12 + 0.05 * fk) + fk * 2.0) * hy * 0.12
                     + sin(p.x * 0.017 - t * 0.09) * hy * 0.04;
            float th = hy * 0.07 * (0.25 + 0.75 * abs(sin(p.x * 0.004 + t * 0.07 + fk * 1.3)));
            float d = abs(p.y - cy) / th;
            vec3 rc = k == 0 ? vec3(0.10, 0.26, 0.19) : vec3(0.22, 0.15, 0.09);
            col += rc * exp(-d * d * 2.0) * 0.45 * (0.75 + 0.25 * sin(p.x * 0.05 + t * 0.6));
        }
        float cyc = mod(t, 16.0);
        if (cyc < 5.0) {
            vec2 fp = vec2(mix(-0.1, 1.1, cyc / 5.0) * size.x,
                           hy * 0.32 + sin(cyc * 1.2) * hy * 0.08);
            float d = distance(p, fp);
            col += vec3(0.85, 0.6, 0.42) * exp(-d * d / 16.0) * 0.9;
            float along = fp.x - p.x;
            if (along > 0.0 && along < 130.0)
                col += vec3(0.5, 0.32, 0.2) * exp(-pow((p.y - fp.y) / 1.4, 2.0))
                     * (1.0 - along / 130.0) * 0.35;
        }
    }
    for (int i = 0; i < 3; i++) {
        float fi = float(i);
        float w = 14.0 + fi * 12.0;
        float x = p.x + par * (6.0 + fi * 16.0) + fi * 1000.0;
        float c = floor(x / w);
        float fx = fract(x / w);
        float hgt = (0.16 + 0.5 * pow(hash(c + fi * 31.0), 1.5) - fi * 0.07) * hy;
        if (hash(c * 3.1 + fi) > 0.82 && abs(fx - 0.5) < 0.12) hgt += hy * 0.12;
        if (p.y > hy - hgt && fx > 0.08 && fx < 0.94) {
            vec3 bc = vec3(0.030, 0.064, 0.050) * (1.0 - fi * 0.3);
            vec2 wp = vec2(x, p.y);
            vec2 cell = floor(wp / vec2(4.0, 5.0));
            vec2 inside = fract(wp / vec2(4.0, 5.0));
            float lit = step(0.92 - fi * 0.03, hash2(cell + fi * 17.0));
            float flick = 0.6 + 0.4 * sin(t * 0.5 + hash2(cell) * 40.0);
            float win = lit * step(0.3, inside.x) * step(inside.x, 0.8)
                      * step(0.3, inside.y) * step(inside.y, 0.75);
            vec3 wc = mix(vec3(0.55, 0.34, 0.2), vec3(0.75, 0.52, 0.36), hash2(cell * 1.7));
            col = bc + wc * win * flick * (0.45 + fi * 0.15);
        }
    }
    float fog = fbm(vec2(p.x * 0.004 + t * 0.025, p.y * 0.02 - t * 0.01));
    float band = exp(-pow((p.y - hy * 0.86) / (hy * 0.13), 2.0));
    col = mix(col, vec3(0.09, 0.15, 0.12), fog * band * 0.5);
    return col;
}

void main() {
    vec2 p = qt_TexCoord0 * size;
    float hy = size.y * 0.64;
    vec3 col;
    if (p.y < hy) {
        col = scene(p, hy, false);
    } else {
        float dy = p.y - hy;
        float z = 1.0 / max(dy, 0.6);
        float vx = size.x * 0.58 - par * 22.0;
        float fx = (p.x - vx) * z;
        float fz = 40.0 * z;
        float wob = (noise(vec2(p.x * 0.03, fz * 0.6 - time * 0.4)) - 0.5) * 7.0
                  * clamp(dy / 40.0, 0.0, 1.0);
        vec2 rp = vec2(p.x + wob, hy - dy * 1.25);
        vec3 refl = rp.y > 0.0 ? scene(rp, hy, true) : vec3(0.02, 0.045, 0.035);
        col = vec3(0.036, 0.070, 0.058) + refl * 0.5 * exp(-dy / 80.0);
        float near = clamp(dy / 26.0, 0.0, 1.0);
        float lx = fx * 0.09, lz = fz * 0.45;
        float gxl = 1.0 - min(abs(fract(lx - 0.5) - 0.5) / fwidth(lx), 1.0);
        float gzl = 1.0 - min(abs(fract(lz - 0.5) - 0.5) / fwidth(lz), 1.0);
        col += vec3(0.30, 0.20, 0.12) * max(gxl, gzl) * 0.22 * near;
        for (int k = 0; k < 4; k++) {
            float fk = float(k);
            float lane = (fk - 1.5) * 4.2;
            float dir = k < 2 ? 1.0 : -1.0;
            float d = abs(fx - lane) / (fwidth(fx) * 1.6 + 0.03);
            float seg = fract(fz * 0.11 + time * 0.32 * dir + fk * 0.37);
            float dash = smoothstep(0.0, 0.02, seg) * (1.0 - smoothstep(0.02, 0.09, seg));
            vec3 lc = k < 2 ? vec3(0.85, 0.62, 0.45) : vec3(0.75, 0.42, 0.26);
            col += lc * dash * exp(-d * d) * 0.9 * near;
        }
    }
    col = mix(col, paper.rgb, smoothstep(size.y - 70.0, size.y, p.y));
    fragColor = vec4(col, 1.0) * qt_Opacity;
}
