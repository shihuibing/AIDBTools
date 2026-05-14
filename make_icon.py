"""
生成 AIDBTools 图标
图标造型：参照 'S形卷曲丝带' -- 左侧大圆弧向右收拢，整体呈蓝色深浅渐变
"""
import math
from PIL import Image, ImageDraw, ImageFilter

# ──────────────────────────────────────────────
# 核心绘制：用多段宽带绘制S形卷曲曲线
# ──────────────────────────────────────────────
def lerp(a, b, t):
    return a + (b - a) * t

def lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(4))

def cubic_bezier(p0, p1, p2, p3, t):
    mt = 1 - t
    x = mt**3*p0[0] + 3*mt**2*t*p1[0] + 3*mt*t**2*p2[0] + t**3*p3[0]
    y = mt**3*p0[1] + 3*mt**2*t*p1[1] + 3*mt*t**2*p2[1] + t**3*p3[1]
    return (x, y)

def draw_ribbon(draw, pts, widths, colors, shadow=False):
    """沿路径绘制渐变宽带"""
    n = len(pts)
    for i in range(n - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        w0 = widths[i]
        w1 = widths[i + 1]
        col0 = colors[i]
        col1 = colors[i + 1]

        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy) or 1e-9
        nx, ny = -dy / length, dx / length

        if shadow:
            # 阴影偏移
            ox, oy = 3, 4
            poly = [
                (x0 + nx*w0/2 + ox, y0 + ny*w0/2 + oy),
                (x1 + nx*w1/2 + ox, y1 + ny*w1/2 + oy),
                (x1 - nx*w1/2 + ox, y1 - ny*w1/2 + oy),
                (x0 - nx*w0/2 + ox, y0 - ny*w0/2 + oy),
            ]
            draw.polygon(poly, fill=(0, 0, 80, 50))
        else:
            # 分四段细化颜色
            for sub in range(4):
                ts = sub / 4
                te = (sub + 1) / 4
                ps = (lerp(x0,x1,ts), lerp(y0,y1,ts))
                pe = (lerp(x0,x1,te), lerp(y0,y1,te))
                ws = lerp(w0, w1, ts)
                we = lerp(w0, w1, te)
                cs = lerp_color(col0, col1, ts)
                ce = lerp_color(col0, col1, te)
                # 两段混色
                cmid = lerp_color(cs, ce, 0.5)
                dxs, dys = pe[0]-ps[0], pe[1]-ps[1]
                Ls = math.hypot(dxs, dys) or 1e-9
                nxs, nys = -dys/Ls, dxs/Ls
                poly = [
                    (ps[0] + nxs*ws/2, ps[1] + nys*ws/2),
                    (pe[0] + nxs*we/2, pe[1] + nys*we/2),
                    (pe[0] - nxs*we/2, pe[1] - nys*we/2),
                    (ps[0] - nxs*ws/2, ps[1] - nys*ws/2),
                ]
                draw.polygon(poly, fill=cmid)


def make_icon(size=256):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    S = size / 256.0  # 缩放因子

    # ── 颜色定义 ──
    C_DARK   = (10,  45, 110, 255)   # 最深蓝（背光侧）
    C_MID    = (25,  90, 175, 255)   # 中蓝
    C_LIGHT  = (60, 150, 215, 255)   # 亮蓝（受光侧）
    C_PALE   = (100,185, 235, 255)   # 最浅（高光区）

    # ── 路径定义（参照图片：左侧大圆弧+右侧收拢尾端）──
    # 使用3段贝塞尔曲线拼合，坐标基于256x256
    cx, cy = 128, 128

    def sc(v): return v * S  # 坐标缩放

    STEPS = 200

    # 段1：左大环 顶部（从左上开始，顺时针）
    seg1 = [
        cubic_bezier(
            (sc(70),  sc(50)),   # P0
            (sc(180), sc(20)),   # P1
            (sc(230), sc(110)),  # P2
            (sc(160), sc(155)),  # P3
            i / STEPS
        ) for i in range(STEPS + 1)
    ]

    # 段2：中间交叉过渡（从左大环底部到右侧上方）
    seg2 = [
        cubic_bezier(
            (sc(160), sc(155)),  # P0
            (sc(100), sc(195)),  # P1
            (sc(50),  sc(180)),  # P2
            (sc(70),  sc(145)),  # P3
            i / STEPS
        ) for i in range(STEPS + 1)
    ]

    # 段3：左侧下环 回到起点
    seg3 = [
        cubic_bezier(
            (sc(70),  sc(145)),  # P0
            (sc(85),  sc(120)),  # P1
            (sc(90),  sc(80)),   # P2
            (sc(70),  sc(50)),   # P3
            i / STEPS
        ) for i in range(STEPS + 1)
    ]

    # 段4：右侧收拢的尾钩（从交叉点向右上延伸）
    seg4 = [
        cubic_bezier(
            (sc(160), sc(155)),  # 接 seg1 终点
            (sc(195), sc(170)),  # P1
            (sc(220), sc(145)),  # P2
            (sc(210), sc(115)),  # P3
            i / STEPS
        ) for i in range(STEPS + 1)
    ]

    all_segs = [
        (seg1, 0.0,  0.5),   # (路径, 颜色t起, 颜色t终)
        (seg2, 0.5,  0.75),
        (seg3, 0.75, 1.0),
        (seg4, 0.4,  0.6),
    ]

    # ── 宽度分布 ──
    def ribbon_width(t, base=28):
        # 中间较粗，两端渐细
        return (base * (0.55 + 0.45 * math.sin(math.pi * t))) * S

    def color_at(t):
        # 循环颜色表：暗→亮→暗→中
        keyframes = [C_DARK, C_LIGHT, C_PALE, C_MID, C_DARK]
        kt = t * (len(keyframes) - 1)
        i = int(kt)
        f = kt - i
        i = min(i, len(keyframes) - 2)
        return lerp_color(keyframes[i], keyframes[i+1], f)

    # ── 先画阴影 ──
    shadow_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    for seg, t0, t1 in all_segs:
        n = len(seg)
        widths = [ribbon_width(lerp(t0, t1, i/(n-1))) for i in range(n)]
        cols   = [color_at(lerp(t0, t1, i/(n-1))) for i in range(n)]
        draw_ribbon(sd, seg, widths, cols, shadow=True)
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=4*S))
    img = Image.alpha_composite(img, shadow_layer)

    # ── 画主体（段倒序：先远后近，模拟遮挡）──
    main_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    md = ImageDraw.Draw(main_layer)
    for seg, t0, t1 in [all_segs[1], all_segs[0], all_segs[3], all_segs[2]]:
        n = len(seg)
        widths = [ribbon_width(lerp(t0, t1, i/(n-1))) for i in range(n)]
        cols   = [color_at(lerp(t0, t1, i/(n-1))) for i in range(n)]
        draw_ribbon(md, seg, widths, cols, shadow=False)

    # 轻微边缘柔化
    main_layer = main_layer.filter(ImageFilter.GaussianBlur(radius=1.2*S))
    img = Image.alpha_composite(img, main_layer)

    # ── 高光层 ──
    hl = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hl)
    # 左大环上方高光椭圆
    hx, hy = int(sc(115)), int(sc(85))
    for r in range(int(sc(22)), 0, -1):
        alpha = int(70 * (1 - r / sc(22)))
        hd.ellipse([hx-r, hy-r, hx+r, hy+r], fill=(220, 240, 255, alpha))
    img = Image.alpha_composite(img, hl)

    return img


def save_ico(out_dir="D:\\Users\\bing\\Desktop\\AIDBTools"):
    import os
    base = make_icon(256)

    ico_path = os.path.join(out_dir, "icon.ico")
    png_path = os.path.join(out_dir, "icon.png")

    sizes = [256, 128, 64, 48, 32, 16]
    imgs = [base.resize((s, s), Image.LANCZOS) for s in sizes]
    imgs[0].save(ico_path, format="ICO",
                 sizes=[(s, s) for s in sizes],
                 append_images=imgs[1:])
    base.save(png_path, "PNG")
    print("icon.ico saved:", ico_path)
    print("icon.png saved:", png_path)


if __name__ == "__main__":
    save_ico()
