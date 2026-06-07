import math, sys, random
from OpenGL.GL   import *
from OpenGL.GLU  import *
from OpenGL.GLUT import *

W, H = 1200, 800

# Intersection
IX1, IX2 = 510, 690    # intersection X range
IY1, IY2 = 310, 490    # intersection Y range
H_STOP_X  = 505
V_STOP_Y  = 305

# State
phase    = 0
cooldown = 0
COOL     = 80
night    = False
paused   = False
wheel_a  = 0.0

random.seed(42)
STAR_LIST  = [(random.randint(0,W), random.randint(510,H-10), random.uniform(0.8,2.0)) for _ in range(70)]
random.seed(13)
GRASS_SEED = 13

INIT_CARS = [
    {"x":-200,"y":430,"spd":3.2,"col":(0.90,0.22,0.22),"dir":"H"},
    {"x":-520,"y":370,"spd":3.8,"col":(0.20,0.48,0.92),"dir":"H"},
    {"x":-820,"y":340,"spd":2.9,"col":(0.92,0.75,0.12),"dir":"H"},
    {"x": 535,"y":-80,"spd":3.0,"col":(0.18,0.82,0.40),"dir":"V"},
    {"x": 595,"y":-320,"spd":3.5,"col":(0.92,0.38,0.80),"dir":"V"},
    {"x": 650,"y":-560,"spd":2.7,"col":(0.95,0.58,0.12),"dir":"V"},
]
cars = [dict(c) for c in INIT_CARS]

# Cohen-Sutherland
# কী করছে: headlight beam কে road bounds-এ clip করছে
# কেন লাগছে: off-screen geometry discard করতে
# real world-এ: GPU frustum culling, every game engine
def _oc(x,y, x0,x1,y0,y1):
    c=0
    if x<x0: c|=1
    elif x>x1: c|=2
    if y<y0: c|=4
    elif y>y1: c|=8
    return c

def cs_clip(x0,y0,x1,y1, bx0,bx1,by0,by1):
    c0=_oc(x0,y0,bx0,bx1,by0,by1)
    c1=_oc(x1,y1,bx0,bx1,by0,by1)
    while True:
        if not(c0|c1): return x0,y0,x1,y1
        if c0&c1: return None
        co=c0 if c0 else c1
        if co&8:   x=x0+(x1-x0)*(by1-y0)/(y1-y0+1e-9); y=float(by1)
        elif co&4: x=x0+(x1-x0)*(by0-y0)/(y1-y0+1e-9); y=float(by0)
        elif co&2: y=y0+(y1-y0)*(bx1-x0)/(x1-x0+1e-9); x=float(bx1)
        else:      y=y0+(y1-y0)*(bx0-x0)/(x1-x0+1e-9); x=float(bx0)
        if co==c0: x0,y0=x,y; c0=_oc(x0,y0,bx0,bx1,by0,by1)
        else:      x1,y1=x,y; c1=_oc(x1,y1,bx0,bx1,by0,by1)

# Bezier
# কী করছে: cubic Bezier curve points generate করছে
# কেন লাগছে: car roof smooth curve ও cloud shape আঁকতে
# real world-এ: font rendering, Adobe Illustrator, automotive CAD
def bez(p0,p1,p2,p3,n=30):
    pts=[]
    for i in range(n+1):
        t=i/n; m=1-t
        x=m**3*p0[0]+3*m**2*t*p1[0]+3*m*t**2*p2[0]+t**3*p3[0]
        y=m**3*p0[1]+3*m**2*t*p1[1]+3*m*t**2*p2[1]+t**3*p3[1]
        pts.append((x,y))
    return pts

def bez_fill(p0,p1,p2,p3,base_y,col):
    pts=bez(p0,p1,p2,p3)
    glColor3f(*col)
    glBegin(GL_TRIANGLE_STRIP)
    for px,py in pts:
        glVertex2f(px,base_y); glVertex2f(px,py)
    glEnd()

def bez_line(p0,p1,p2,p3,col,w=1.5):
    pts=bez(p0,p1,p2,p3)
    glColor3f(*col); glLineWidth(w)
    glBegin(GL_LINE_STRIP)
    for p in pts: glVertex2f(*p)
    glEnd(); glLineWidth(1.0)

# Primitives
def rect(x1,y1,x2,y2,col):
    # কী করছে: filled rectangle আঁকছে
    # কেন লাগছে: সব architecture ও furniture তৈরিতে
    # real world-এ: সব 2D game engine sprite box
    glColor3f(*col)
    glBegin(GL_QUADS)
    glVertex2f(x1,y1); glVertex2f(x2,y1)
    glVertex2f(x2,y2); glVertex2f(x1,y2)
    glEnd()

def quad4(p1,p2,p3,p4,col):
    glColor3f(*col)
    glBegin(GL_QUADS)
    for p in (p1,p2,p3,p4): glVertex2f(*p)
    glEnd()

def circ(cx,cy,r,col,seg=40):
    # কী করছে: filled circle আঁকছে
    # কেন লাগছে: wheels, traffic lights, sun, trees
    # real world-এ: game physics, weather apps
    glColor3f(*col)
    glBegin(GL_TRIANGLE_FAN)
    glVertex2f(cx,cy)
    for i in range(seg+1):
        a=2*math.pi*i/seg
        glVertex2f(cx+r*math.cos(a),cy+r*math.sin(a))
    glEnd()

def ring(cx,cy,ro,ri,col,seg=40):
    glColor3f(*col)
    glBegin(GL_TRIANGLE_STRIP)
    for i in range(seg+1):
        a=2*math.pi*i/seg
        glVertex2f(cx+ro*math.cos(a),cy+ro*math.sin(a))
        glVertex2f(cx+ri*math.cos(a),cy+ri*math.sin(a))
    glEnd()

def text(x,y,s,col=(1,1,1),font=GLUT_BITMAP_HELVETICA_18):
    glColor3f(*col)
    glRasterPos2f(x,y)
    for c in s: glutBitmapCharacter(font,ord(c))


# SCENE
def draw_sky():
    # কী করছে: দিন ও রাতের আকাশ আঁকছে
    # কেন লাগছে: দিন/রাত পরিবেশ তৈরি করতে
    # real world-এ: skybox in Unity/Unreal Engine
    if night:
        # NIGHT SKY
        # Deep dark blue gradient sky
        rect(0, 490, W, H, (0.02, 0.03, 0.10))
        rect(0, 600, W, H, (0.04, 0.05, 0.15))
        rect(0, 700, W, H, (0.06, 0.07, 0.20))

        # Stars — use pre-generated list so they are stable
        for sx, sy, sr in STAR_LIST:
            # Twinkle effect: slight brightness variation based on position
            brightness = 0.85 + 0.15 * math.sin(sx * 0.1 + sy * 0.07)
            circ(sx, sy, sr, (brightness, brightness, brightness * 0.92))

        # Moon (crescent illusion: white circle + dark overlay)
        circ(1100, 740, 38, (1.00, 0.97, 0.82))
        circ(1118, 750, 29, (0.02, 0.03, 0.10))  # dark overlay for crescent

        # Moon soft glow
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        for r_glow, alpha in [(70, 0.04), (55, 0.07), (45, 0.10)]:
            glColor4f(1.0, 0.97, 0.82, alpha)
            glBegin(GL_TRIANGLE_FAN)
            glVertex2f(1100, 740)
            for i in range(37):
                a = 2 * math.pi * i / 36
                glVertex2f(1100 + r_glow * math.cos(a), 740 + r_glow * math.sin(a))
            glEnd()
        glDisable(GL_BLEND)

    else:
        # DAY SKY
        rect(0, 490, W, H,  (0.46, 0.76, 0.97))
        rect(0, 640, W, H,  (0.60, 0.86, 1.00))

        # Sun with rays
        circ(1100, 730, 44, (1.0, 0.92, 0.28))
        circ(1100, 730, 34, (1.0, 0.96, 0.50))
        glColor3f(1.0, 0.88, 0.20); glLineWidth(2.5)
        for i in range(12):
            a = 2 * math.pi * i / 12
            glBegin(GL_LINES)
            glVertex2f(1100 + 50 * math.cos(a), 730 + 50 * math.sin(a))
            glVertex2f(1100 + 66 * math.cos(a), 730 + 66 * math.sin(a))
            glEnd()
        glLineWidth(1.0)

        # Clouds(Bezier bumps)
        for ox, oy in [(120,720),(380,700),(700,725),(950,708)]:
            for cr, dx, dy in [(24,0,0),(19,28,7),(16,-22,6),(13,48,3),(15,-40,4)]:
                circ(ox + dx, oy + dy, cr, (0.97, 0.97, 1.00))


def draw_ground():
    # কী করছে: ঘাসের মাঠ আঁকছে দিন/রাত রঙে
    # কেন লাগছে: urban environment ground plane
    # real world-এ: terrain rendering in SimCity
    if night:
        gc = (0.06, 0.16, 0.06)
        gs = (0.04, 0.12, 0.04)
    else:
        gc = (0.24, 0.62, 0.22)
        gs = (0.20, 0.54, 0.18)

    rect(0,    0,   IX1, IY1, gc)
    rect(IX2,  0,   W,   IY1, gc)
    rect(0,   IY2,  IX1, 490, gs)
    rect(IX2, IY2,  W,   490, gs)

    # Grass texture lines
    glColor3f(*gs); glLineWidth(0.5)
    for gx in range(0, W, 40):
        if IX1 <= gx <= IX2: continue
        glBegin(GL_LINES)
        glVertex2f(gx, 0);   glVertex2f(gx, IY1)
        glVertex2f(gx, IY2); glVertex2f(gx, 490)
        glEnd()
    glLineWidth(1.0)


def draw_buildings():
    # কী করছে: city buildings আঁকছে floors ও windows সহ
    # কেন লাগছে: Smart City urban context দেখাতে
    # real world-এ: city runner games, urban planning software
    bdata = [
        (10,  490, 120, 680, (0.52, 0.28, 0.28)),
        (125, 490, 225, 720, (0.22, 0.42, 0.72)),
        (230, 490, 315, 660, (0.65, 0.55, 0.18)),
        (320, 490, 410, 700, (0.45, 0.22, 0.62)),
        (720, 490, 820, 690, (0.20, 0.55, 0.45)),
        (825, 490, 935, 730, (0.68, 0.28, 0.48)),
        (940, 490,1040, 680, (0.24, 0.38, 0.72)),
        (1045,490,1190, 710, (0.50, 0.38, 0.22)),
    ]
    rng = random.Random(13)  # stable RNG same seed every frame

    for x1, y1, x2, y2, bc in bdata:
        shade = 0.45 if night else 1.0
        col   = (bc[0]*shade, bc[1]*shade, bc[2]*shade)
        rect(x1, y1, x2, y2, col)
        # Roof parapet
        rect(x1, y2, x2, y2+8,
             (bc[0]*0.55*shade, bc[1]*0.55*shade, bc[2]*0.55*shade))

        # Windows
        for wy in range(y1+18, y2-8, 30):
            for wx in range(x1+8, x2-14, 22):
                if wy + 16 > y2: break
                if night:
                    # Most windows lit at night (warm yellow glow)
                    lit = rng.random() > 0.30
                    if lit:
                        wc = (1.0, 0.92, 0.55)
                        rect(wx, wy, wx+14, wy+16, wc)
                        # Small inner bright spot
                        rect(wx+3, wy+3, wx+11, wy+13, (1.0, 0.98, 0.78))
                    else:
                        rect(wx, wy, wx+14, wy+16, (0.08, 0.10, 0.14))
                else:
                    rect(wx, wy, wx+14, wy+16, (0.22, 0.25, 0.32))


def draw_roads():
    # কী করছে: রাস্তা ও lane markings আঁকছে
    # কেন লাগছে: vehicle movement path define করতে
    # real world-এ: Google Maps road renderer
    rc = (0.14, 0.14, 0.14) if night else (0.18, 0.18, 0.18)
    rl = (0.18, 0.18, 0.18) if night else (0.22, 0.22, 0.22)

    rect(0,    IY1, W,   IY2, rc)
    rect(IX1,  0,   IX2, H,   rc)
    rect(IX1, IY1,  IX2, IY2, rl)

    # Road edge lines
    ec = (0.55, 0.55, 0.55) if night else (0.75, 0.75, 0.75)
    glColor3f(*ec); glLineWidth(2.0)
    for yy in (IY1, IY2):
        glBegin(GL_LINES)
        glVertex2f(0, yy);   glVertex2f(IX1, yy)
        glVertex2f(IX2, yy); glVertex2f(W,   yy)
        glEnd()
    for xx in (IX1, IX2):
        glBegin(GL_LINES)
        glVertex2f(xx, 0);   glVertex2f(xx, IY1)
        glVertex2f(xx, IY2); glVertex2f(xx, 490)
        glEnd()
    glLineWidth(1.0)

    # Centre dashed lines (yellow)
    glColor3f(1.0, 0.82, 0.0)
    glEnable(GL_LINE_STIPPLE); glLineStipple(2, 0x0F0F); glLineWidth(3.0)
    glBegin(GL_LINES)
    glVertex2f(0, 400);   glVertex2f(IX1, 400)
    glVertex2f(IX2, 400); glVertex2f(W,   400)
    glVertex2f(600, 0);   glVertex2f(600, IY1)
    glVertex2f(600, IY2); glVertex2f(600, 490)
    glEnd()
    glDisable(GL_LINE_STIPPLE); glLineWidth(1.0)

    # Sidewalks
    sw = (0.35, 0.35, 0.38) if night else (0.62, 0.62, 0.66)
    rect(0, 487, W, 495, sw)
    rect(0, 305, W, 312, sw)


def draw_zebra():
    zc = (0.70, 0.70, 0.70) if night else (0.95, 0.95, 0.95)
    for i in range(8):
        dx = IX2 + 4 + i * 22
        rect(dx, IY1+4, dx+14, IY2-4, zc)
    for i in range(8):
        dy = IY2 + 4 + i * 22
        rect(IX1+4, dy, IX2-4, dy+14, zc)


def draw_tree(x, y, scale=1.0):
    # কী করছে: detailed tree আঁকছে multi-layer foliage সহ
    # কেন লাগছে: urban greenery দেখাতে
    # real world-এ: city simulation (SimCity), road design software
    s = scale
    if night:
        tc  = (0.10, 0.06, 0.02)
        lc1 = (0.04, 0.18, 0.05)
        lc2 = (0.05, 0.22, 0.06)
        lc3 = (0.03, 0.14, 0.04)
    else:
        tc  = (0.36, 0.20, 0.06)
        lc1 = (0.16, 0.58, 0.18)
        lc2 = (0.22, 0.68, 0.24)
        lc3 = (0.12, 0.46, 0.14)

    rect(x-6*s, y, x+6*s, y+38*s, tc)
    circ(x,      y+48*s, 22*s, lc1)
    circ(x-14*s, y+40*s, 16*s, lc2)
    circ(x+14*s, y+40*s, 16*s, lc3)
    circ(x,      y+62*s, 16*s, lc2)


def draw_streetlight(x, y):
    # কী করছে: streetlight pole ও night glow আঁকছে
    # কেন লাগছে: রাতের রাস্তা আলোকিত দেখাতে
    # real world-এ: smart city IoT street lighting
    pc = (0.20, 0.20, 0.24)
    rect(x-3, y,    x+3,  y+72, pc)
    rect(x-3, y+72, x+26, y+76, pc)

    if night:
        # Lamp head—bright warm yellow
        circ(x+26, y+76, 8, (1.0, 0.95, 0.70))
        # Glow halo (3 layers)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        for r_glow, alpha in [(55, 0.04), (38, 0.09), (22, 0.16)]:
            glColor4f(1.0, 0.93, 0.60, alpha)
            glBegin(GL_TRIANGLE_FAN)
            glVertex2f(x+26, y+76)
            for i in range(37):
                ang = 2 * math.pi * i / 36
                glVertex2f(x+26 + r_glow * math.cos(ang), y+76 + r_glow * math.sin(ang))
            glEnd()
        # Cone of light downward
        glColor4f(1.0, 0.92, 0.55, 0.07)
        glBegin(GL_TRIANGLES)
        glVertex2f(x+26, y+76)
        glVertex2f(x-30, y)
        glVertex2f(x+82, y)
        glEnd()
        glDisable(GL_BLEND)
    else:
        circ(x+26, y+76, 5, (0.72, 0.70, 0.55))


def draw_signal_pole(px, py, r_on, g_on):
    # কী করছে: traffic signal pole ও 3-light box আঁকছে
    # কেন লাগছে: intersection traffic control visualise করতে
    # real world-এ: Smart City IoT, autonomous vehicle systems
    rect(px, py, px+10, py+110, (0.20, 0.20, 0.22))
    rect(px-10, py+70, px+28, py+112, (0.08, 0.08, 0.10))
    rect(px- 8, py+72, px+26, py+110, (0.12, 0.12, 0.14))
    lx = px + 8

    # RED
    circ(lx, py+105, 8, (1.0 if r_on else 0.24, 0.05, 0.05))
    # YELLOW (dim)
    circ(lx, py+90,  8, (0.28, 0.24, 0.0))
    # GREEN
    circ(lx, py+76,  8, (0.04, 1.0 if g_on else 0.22, 0.04))

    if night:
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        if g_on:
            glColor4f(0.1, 1.0, 0.1, 0.22)
            glBegin(GL_TRIANGLE_FAN); glVertex2f(lx, py+76)
            for i in range(37):
                a = 2*math.pi*i/36
                glVertex2f(lx+20*math.cos(a), py+76+20*math.sin(a))
            glEnd()
        if r_on:
            glColor4f(1.0, 0.1, 0.1, 0.22)
            glBegin(GL_TRIANGLE_FAN); glVertex2f(lx, py+105)
            for i in range(37):
                a = 2*math.pi*i/36
                glVertex2f(lx+20*math.cos(a), py+105+20*math.sin(a))
            glEnd()
        glDisable(GL_BLEND)


def draw_signals():
    h_green = (phase == 0)
    v_green = (phase == 1)
    draw_signal_pole(470, IY2,   r_on=not h_green, g_on=h_green)
    draw_signal_pole(IX2+8, 160, r_on=not v_green, g_on=v_green)

# CARS
def draw_wheel(wx, wy, spin):
    # কী করছে: glRotatef দিয়ে wheel spinning animate করছে
    # কেন লাগছে: realistic movement illusion
    # real world-এ: all 2D/3D vehicle games
    glPushMatrix()
    glTranslatef(wx, wy, 0)
    glRotatef(spin, 0, 0, 1)
    circ(0, 0, 9,  (0.10, 0.10, 0.12))
    ring(0, 0, 9, 6, (0.46, 0.46, 0.48))
    glColor3f(0.60, 0.60, 0.62); glLineWidth(1.2)
    for sp in range(4):
        a = math.radians(sp * 45)
        glBegin(GL_LINES)
        glVertex2f(0, 0); glVertex2f(6*math.cos(a), 6*math.sin(a))
        glEnd()
    glLineWidth(1.0)
    glPopMatrix()


def draw_h_car(x, y, col):
    """
    কী করছে: horizontal car আঁকছে Bezier roof, windows, headlight beam সহ
    কেন লাগছে: horizontal lane vehicle
    real world-এ: 2D top-down traffic simulation
    """
    r, g, b = col
    # Shadow
    glColor3f(0, 0, 0)
    glBegin(GL_TRIANGLE_FAN); glVertex2f(x+45, y-2)
    for i in range(37):
        a = 2*math.pi*i/36
        glVertex2f(x+45 + 40*math.cos(a), y-2 + 8*math.sin(a))
    glEnd()
    # Body
    quad4((x,y+8),(x+95,y+8),(x+92,y+42),(x+3,y+42), col)
    # Bumpers
    rect(x+90, y+12, x+98, y+38, (r*0.65, g*0.65, b*0.65))
    rect(x,    y+12, x+5,  y+38, (r*0.65, g*0.65, b*0.65))
    # Cabin
    quad4((x+14,y+40),(x+80,y+40),(x+76,y+62),(x+18,y+62),
          (r*0.82, g*0.82, b*0.82))
    # Bezier roof
    bez_fill((x+18,y+62),(x+28,y+72),(x+66,y+72),(x+76,y+62),
             y+62, (r*0.78, g*0.78, b*0.78))
    # Windows
    rect(x+17, y+42, x+44, y+60, (0.50, 0.78, 0.95))
    rect(x+48, y+42, x+75, y+60, (0.50, 0.78, 0.95))
    rect(x+20, y+43, x+30, y+59, (0.70, 0.90, 1.00))
    rect(x+50, y+43, x+60, y+59, (0.70, 0.90, 1.00))
    # Headlights
    lc = (1.0, 0.95, 0.55) if night else (0.92, 0.88, 0.65)
    rect(x+90, y+18, x+98, y+28, lc)
    rect(x+90, y+30, x+98, y+40, lc)
    # Tail lights (red at back)
    rect(x, y+18, x+5, y+28, (0.9, 0.1, 0.1))
    rect(x, y+30, x+5, y+40, (0.9, 0.1, 0.1))
    # Night headlight beam (Cohen-Sutherland clipped)
    if night:
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        # Wide cone beam
        glColor4f(1.0, 0.95, 0.50, 0.15)
        glBegin(GL_TRIANGLES)
        glVertex2f(x+98, y+23)
        glVertex2f(x+200, y+8)
        glVertex2f(x+200, y+42)
        glEnd()
        glDisable(GL_BLEND)
        for beam_y in (y+22, y+34):
            r2 = cs_clip(x+98, beam_y, x+190, beam_y, 0, W, IY1, IY2)
            if r2:
                glColor3f(1.0, 0.95, 0.50); glLineWidth(1.8)
                glBegin(GL_LINES)
                glVertex2f(r2[0], r2[1]); glVertex2f(r2[2], r2[3])
                glEnd()
                glLineWidth(1.0)
    # Wheels
    spin = wheel_a
    draw_wheel(x+18, y+8, spin)
    draw_wheel(x+76, y+8, spin)


def draw_v_car(x, y, col):
    """
    কী করছে: vertical car আঁকছে Bezier roof, windows, headlights সহ
    কেন লাগছে: vertical lane vehicle
    real world-এ: top-down traffic simulation vehicle
    """
    r, g, b = col
    # Shadow
    glColor3f(0, 0, 0)
    glBegin(GL_TRIANGLE_FAN); glVertex2f(x+25, y-2)
    for i in range(37):
        a = 2*math.pi*i/36
        glVertex2f(x+25 + 16*math.cos(a), y-2 + 36*math.sin(a))
    glEnd()
    # Body
    quad4((x+2,y),(x+48,y),(x+46,y+95),(x+4,y+95), col)
    # Bumpers
    rect(x+4, y+90, x+46, y+98, (r*0.65, g*0.65, b*0.65))
    rect(x+4, y,    x+46, y+6,  (r*0.65, g*0.65, b*0.65))
    # Cabin
    quad4((x+8,y+22),(x+42,y+22),(x+40,y+72),(x+10,y+72),
          (r*0.82, g*0.82, b*0.82))
    # Bezier roof top
    bez_fill((x+10,y+72),(x+16,y+82),(x+34,y+82),(x+40,y+72),
             y+72, (r*0.78, g*0.78, b*0.78))
    # Windows
    rect(x+10, y+52, x+40, y+70, (0.50, 0.78, 0.95))
    rect(x+10, y+24, x+40, y+42, (0.50, 0.78, 0.95))
    rect(x+12, y+54, x+22, y+68, (0.70, 0.90, 1.00))
    # Headlights
    lc = (1.0, 0.95, 0.55) if night else (0.92, 0.88, 0.65)
    rect(x+8,  y+88, x+20, y+96, lc)
    rect(x+30, y+88, x+42, y+96, lc)
    # Tail lights
    rect(x+8,  y,    x+20, y+6, (0.9, 0.1, 0.1))
    rect(x+30, y,    x+42, y+6, (0.9, 0.1, 0.1))
    # Night beam (clipped to vertical road)
    if night:
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glColor4f(1.0, 0.95, 0.50, 0.15)
        glBegin(GL_TRIANGLES)
        glVertex2f(x+25, y+96)
        glVertex2f(x+2,  y+200)
        glVertex2f(x+48, y+200)
        glEnd()
        glDisable(GL_BLEND)
        for beam_x in (x+14, x+36):
            r2 = cs_clip(beam_x, y+96, beam_x, y+190, IX1, IX2, 0, H)
            if r2:
                glColor3f(1.0, 0.95, 0.50); glLineWidth(1.8)
                glBegin(GL_LINES)
                glVertex2f(r2[0], r2[1]); glVertex2f(r2[2], r2[3])
                glEnd()
                glLineWidth(1.0)
    # Wheels
    spin = -wheel_a
    draw_wheel(x+8,  y+14, spin)
    draw_wheel(x+42, y+14, spin)
    draw_wheel(x+8,  y+72, spin)
    draw_wheel(x+42, y+72, spin)


# SIGNAL LOGIC
def h_should_stop(car):
    if phase == 1 and car["x"] + 95 < H_STOP_X: return True
    return False

def v_should_stop(car):
    if phase == 0 and car["y"] + 95 < V_STOP_Y: return True
    return False

def h_cleared():
    for c in cars:
        if c["dir"] == "H" and c["x"] < IX2 and c["x"]+95 > IX1: return False
    return True

def v_cleared():
    for c in cars:
        if c["dir"] == "V" and c["y"] < IY2 and c["y"]+95 > IY1: return False
    return True


# NIGHT AMBIENCE—road glow strip
def draw_night_road_ambience():
    """
    কী করছে: রাতে রাস্তায় আলোর আভা দেখাচ্ছে
    কেন লাগছে: night immersion বাড়াতে
    real world-এ: bloom effect in post-processing pipelines
    """
    if not night:
        return
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    # Faint orange glow on horizontal road surface
    glColor4f(0.6, 0.45, 0.10, 0.06)
    glBegin(GL_QUADS)
    glVertex2f(0,   IY1); glVertex2f(W,   IY1)
    glVertex2f(W,   IY2); glVertex2f(0,   IY2)
    glEnd()
    # Faint glow on vertical road
    glColor4f(0.6, 0.45, 0.10, 0.06)
    glBegin(GL_QUADS)
    glVertex2f(IX1, 0); glVertex2f(IX2, 0)
    glVertex2f(IX2, H); glVertex2f(IX1, H)
    glEnd()
    glDisable(GL_BLEND)


# UPDATE & DISPLAY
def update(v):
    global phase, cooldown, wheel_a
    if not paused:
        for car in cars:
            if car["dir"] == "H":
                if not h_should_stop(car): car["x"] += car["spd"]
                if car["x"] > W + 200: car["x"] = -350
            else:
                if not v_should_stop(car): car["y"] += car["spd"]
                if car["y"] > H + 200: car["y"] = -350
        if cooldown > 0:
            cooldown -= 1
        else:
            if phase == 0 and h_cleared(): phase = 1; cooldown = COOL
            elif phase == 1 and v_cleared(): phase = 0; cooldown = COOL
        wheel_a = (wheel_a + 5) % 360
    glutPostRedisplay()
    glutTimerFunc(16, update, 0)


def display():
    glClear(GL_COLOR_BUFFER_BIT)
    glLoadIdentity()

    draw_sky()
    draw_ground()
    draw_buildings()

    # Trees
    for tx, ty, ts in [
        (60,380,1.0),(180,360,0.9),(360,380,1.1),
        (730,370,0.95),(900,385,1.0),(1080,360,0.9),(1160,375,1.0),
        (70,190,0.85),(200,210,1.0),(360,200,0.9),
        (740,195,1.0),(900,215,0.88),(1090,200,0.95)
    ]:
        draw_tree(tx, ty, ts)

    # Streetlights
    for slx, sly in [(460, IY2),(IX2+10, 290),(IX2+10, 50),(460, 50)]:
        draw_streetlight(slx, sly)

    draw_roads()
    draw_night_road_ambience()   # ← extra glow layer for night
    draw_zebra()
    draw_signals()

    for car in cars:
        if car["dir"] == "H": draw_h_car(car["x"], car["y"], car["col"])
        else:                  draw_v_car(car["x"], car["y"], car["col"])

    glutSwapBuffers()


def keyboard(key, x, y):
    global night, paused, cars, phase, cooldown
    if key in (b'n', b'N'):   night = not night
    elif key in (b'p', b'P'): paused = not paused
    elif key in (b'r', b'R'):
        cars = [dict(c) for c in INIT_CARS]; phase = 0; cooldown = 0
    elif key == b'\x1b': sys.exit(0)
    glutPostRedisplay()


def init_gl():
    glClearColor(0, 0, 0, 1)
    glMatrixMode(GL_PROJECTION); glLoadIdentity()
    gluOrtho2D(0, W, 0, H)
    glMatrixMode(GL_MODELVIEW); glLoadIdentity()
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)


def main():
    glutInit(sys.argv)
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB)
    glutInitWindowSize(W, H)
    glutInitWindowPosition(60, 40)
    glutCreateWindow(b"Smart City Traffic Visualizer")
    init_gl()
    glutDisplayFunc(display)
    glutKeyboardFunc(keyboard)
    glutTimerFunc(0, update, 0)
    print("Controls: N=Night/Day  P=Pause  R=Reset  ESC=Quit")
    glutMainLoop()

if __name__ == "__main__":
    main()