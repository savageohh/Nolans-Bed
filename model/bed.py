#!/usr/bin/env python3
"""Parametric model of Nolan's freestanding loft bed.

Run:  python3 model/bed.py            (twin, the default)
      python3 model/bed.py --full     (full-size mattress variant)

Writes (repo-relative):
  build/model.json        every part as a box, for the viewer
  viewer/index.html       interactive 3D viewer (model embedded)
  docs/CUTLIST.md         cut list, board buying list, hardware
  docs/cutlist.csv
  docs/CALCS.md           structural checks

Units are inches and pounds. Axes: x = bed length (head end at x=0),
y = bed width (y=0 is the open "lounge"/ladder side), z = up from floor.
Every part is modelled at its *visible* size; hidden tenons and tongues are
added to the cut length via `extra`.
"""
import argparse, csv, json, math, os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ap = argparse.ArgumentParser()
ap.add_argument("--full", action="store_true", help="full-size mattress (54x75)")
ap.add_argument("--no-write", action="store_true")
ARGS = ap.parse_args()

# ----------------------------------------------------------------- parameters
MATTRESS = dict(name="Full", L=75.0, W=54.0) if ARGS.full else dict(name="Twin", L=75.0, W=38.0)
MATTRESS_T = 8.0              # max mattress thickness (label this on the bed)
LIN = MATTRESS["L"] + 0.75    # mattress pocket, length
WIN = MATTRESS["W"] + 1.25    # mattress pocket, width
PX, PY = 3.0, 3.5             # post = two 2x4 face-glued (laminations stacked in x)
HOUSE = 0.5                   # depth of routed housings for bolted members
DECK_TOP = 54.0               # top of plywood deck
LIP = 2.0                     # long rail stands this far above the deck
CAP_ABOVE_MATTRESS = 6.5      # guard cap above mattress top (code min 5")
POST_H = 72.0
LADDER_CLEAR = 14.0           # clear width between ladder stiles
LADDER_ANGLE = 70.0           # degrees from floor
N_TREADS = 5                  # plus the rail top as the last step
RIBS_PER_PANEL = 5 if ARGS.full else 4   # wider span -> closer ribs
SPINDLE_GAP = 3.0             # guard slat clear gap target (max allowed 3.5)
KERF = 0.125

# ------------------------------------------------------------------ pricing
# Estimated Menards shelf prices (low, high) in USD, late 2026. Check menards.com for
# your store and edit these -- docs/COST.md is regenerated from them.
PRICES = {
    # lumber, 8 ft, kiln-dried S4S (SPF / Doug-fir / SYP), #2 & better
    "2x2": (2.50, 4.00), "2x4": (3.50, 5.00), "2x6": (5.50, 8.00), "2x8": (8.00, 11.00),
    "2x10": (11.00, 15.00),
    # pine boards, 8 ft, #2 common (select/clear runs ~2x)
    "1x3": (4.00, 7.00), "1x4": (5.00, 9.00), "1x6": (8.00, 14.00),
    # plywood, 4x8 sheet
    "ply34": (55.00, 75.00),     # 3/4in sanded pine/birch (Baltic birch ~$70)
    "ply12": (40.00, 55.00),     # 1/2in BC sanded
    # hardware
    "insert 3/8-16 (pack of 50)": (14.00, 32.00),   # zinc knife-thread 50pk .. 2x25pk E-Z Hex softwood
    "insert 1/4-20 (pack of 25)": (8.00, 16.00),
    '3/8-16 x 3-3/4"': (1.00, 1.80), '3/8-16 x 4-1/4"': (1.20, 2.00), '3/8-16 x 2-1/4"': (0.60, 1.20),
    '1/4-20 x 1"': (0.20, 0.40), '1/4-20 x 2"': (0.25, 0.50),
    "fender washer 3/8": (0.15, 0.35), "fender washer 1/4": (0.10, 0.20),
    "leveling glide 3/8-16 (4 pack)": (8.00, 15.00), "anti-tip strap": (8.00, 15.00),
    # consumables
    "wood glue (quart)": (10.00, 20.00), "screws 1-1/4 & 2-1/2 (boxes)": (15.00, 25.00),
    "water-based poly (2 quarts)": (25.00, 45.00), "sandpaper assortment": (15.00, 25.00),
}
TOOLS = {   # optional, only if you don't already have them
    "1/2in upcut spiral bit": (20.00, 40.00), "3/4in top-bearing pattern bit": (20.00, 35.00),
    "1/2in roundover bit": (15.00, 30.00), "1/4in roundover bit": (12.00, 25.00),
    "slot cutter (panel grooves)": (25.00, 45.00), "guide bushing set": (20.00, 35.00),
    "insert drive bits": (8.00, 15.00), "jig stock (1x4s, ply scrap, clamps excluded)": (10.00, 25.00),
}
SPARE_LUMBER = 0.15            # extra boards for defects/mistakes
TAX = {"MN state only": 0.06875, "Minneapolis (combined)": 0.09025}

T = 1.5                       # 2x thickness
W2 = {"2x2": 1.5, "2x4": 3.5, "2x6": 5.5, "2x8": 7.25, "2x10": 9.25}
RAIL = "2x10"                 # long rails

# ------------------------------------------------------------ derived layout
LO = LIN + 2 * PX                         # overall length
YF0, YF1 = PY - HOUSE, PY - HOUSE + T     # front long rail
YB0, YB1 = YF1 + WIN, YF1 + WIN + T       # back long rail
WO = YB1 - HOUSE + PY                     # overall width
RAIL_TOP = DECK_TOP + LIP
RAIL_BOT = RAIL_TOP - W2[RAIL]
PLY_BOT = DECK_TOP - 0.75
RIB_BOT = PLY_BOT - W2["2x4"]
MAT_TOP = DECK_TOP + MATTRESS_T
CAP_TOP = MAT_TOP + CAP_ABOVE_MATTRESS
PINE = 0.75                   # 1x pine board thickness
SLAT_W = 2.5                  # 1x3
CAP_BOT = CAP_TOP - PINE
GF = (YF0 - T, YF0)                       # front guard plane (on rail's outer face)
GB = (YB1, YB1 + T)                       # back guard plane
STILE_BOT = RAIL_BOT + 0.25
# end-frame bands (z) on the posts' inner faces -- must not overlap the
# long-member bands (rail housing, back stretcher)
EF = {
    "lower stretcher": ("2x6", 3.0),
    "apron":           ("2x8", RAIL_BOT - 0.75 - W2["2x8"]),
    "mid rail":        ("2x6", RAIL_TOP + 0.5),
    "top rail":        ("2x4", POST_H - W2["2x4"]),
}
BACK_STRETCHER_Z = 10.0
TENON = 1.25                              # tenon length into post
OPEN0 = LO - PX - (LADDER_CLEAR + 2 * T + 0.5)   # ladder opening starts here (x)

assert MAT_TOP - 0.01 <= EF["mid rail"][1] + W2["2x6"] + 0.01, "end mid rail should reach mattress top"

parts = []
inserts = []          # (size, where, count)
def part(name, module, stock, box=None, *, extra=0.0, rot=None, cut=None, housed=(), color=None, note=""):
    """box = (x0,x1,y0,y1,z0,z1); rot = dict(center,size,angle) for rotated parts."""
    p = dict(name=name, module=module, stock=stock, box=box, extra=extra, rot=rot,
             cut=cut, housed=list(housed), note=note)
    parts.append(p)
    return p

def ins(size, where, n):
    inserts.append((size, where, n))

bolts = defaultdict(int)  # spec -> qty (one fender washer each)
def bolt(spec, n):
    bolts[spec] += n

# ------------------------------------------------------------------- posts
for end, x0 in (("head", 0.0), ("foot", LO - PX)):
    mod = f"End frame ({end})"
    for side, y0 in (("front", 0.0), ("back", WO - PY)):
        part(f"Post {end}-{side}", mod, "post", (x0, x0 + PX, y0, y0 + PY, 0, POST_H),
             note="two 2x4 face-glued; 3/8-16 insert in foot for leveling glide")
    # end-frame members, flush with the posts' inner x-face, M&T into posts
    xi0, xi1 = (PX - T, PX) if end == "head" else (LO - PX, LO - PX + T)
    for nm, (stk, z0) in EF.items():
        part(f"End {nm} ({end})", mod, stk, (xi0, xi1, PY, WO - PY, z0, z0 + W2[stk]),
             extra=2 * TENON, note="1/2in tenons both ends, glued")
    pz0 = EF["mid rail"][1] + W2["2x6"]
    pz1 = EF["top rail"][1]
    xm = (xi0 + xi1) / 2
    part(f"End panel ({end})", mod, "ply12", (xm - 0.25, xm + 0.25, PY, WO - PY, pz0, pz1),
         cut=(WO - 2 * PY + 0.75, pz1 - pz0 + 0.75), note="in 1/2in routed grooves, glued")
ins("3/8-16", "post feet (leveling glides)", 4)

# ------------------------------------------------------------ long members
for side, (y0, y1), posts in (("front", (YF0, YF1), ("front",)), ("back", (YB0, YB1), ("back",))):
    part(f"Long rail ({side})", f"Long rail ({side})", RAIL, (0, LO, y0, y1, RAIL_BOT, RAIL_TOP),
         housed=["Post"], note="sits in 1/2in housings; 2 bolts each end through post")
    ins("3/8-16", f"{side} rail outer face at posts (rail-to-post bolts)", 4)
    bolt('3/8-16 x 3-3/4"', 4)
part("Back stretcher", "Back stretcher", "2x6", (0, LO, YB0, YB1, BACK_STRETCHER_Z, BACK_STRETCHER_Z + 5.5),
     housed=["Post"], note="in 1/2in housings; 2 bolts each end through post")
ins("3/8-16", "back stretcher inner end faces (stretcher-to-post bolts)", 4)
bolt('3/8-16 x 3-3/4"', 4)

# back shear panel + top cleat
part("Back shear panel", "Back panel", "ply12",
     (PX, LO - PX, YB0 - 0.5, YB0, BACK_STRETCHER_Z, RAIL_BOT),
     cut=(LO - 2 * PX - 0.125, RAIL_BOT - BACK_STRETCHER_Z), note="glued+screwed to top cleat; 1/4-20 bolts into stretcher")
part("Back panel top cleat", "Back panel", "2x2", (PX, LO - PX, YB0, YB0 + T, RAIL_BOT - T, RAIL_BOT),
     extra=-0.125, note="glued to panel; 1/4-20 bolts up into rail bottom edge")
ins("1/4-20", "back stretcher inner face (panel bolts)", 6)
ins("1/4-20", "back rail bottom edge (panel cleat bolts)", 6)
bolt('1/4-20 x 1"', 6)
bolt('1/4-20 x 2"', 6)

# ------------------------------------------------------------------- deck
plen = (LIN - 3 * 0.0625) / 2
rib_x = []
for i in range(2):
    px0 = PX + 0.0625 + i * (plen + 0.0625)
    mod = f"Deck panel {i + 1}"
    part(f"Deck ply {i + 1}", mod, "ply34", (px0, px0 + plen, YF1 + 0.0625, YB0 - 0.0625, PLY_BOT, DECK_TOP),
         cut=(plen, WIN - 0.125), note="vent holes/slots; glued+screwed to ribs")
    step = (plen - 0.5 - T) / (RIBS_PER_PANEL - 1)
    for r in range(RIBS_PER_PANEL):
        rx = px0 + 0.25 + r * step
        rib_x.append(rx)
        part(f"Deck rib {i + 1}.{r + 1}", mod, "2x4", (rx, rx + T, YF1 - HOUSE + 0.0625, YB0 + HOUSE - 0.0625, RIB_BOT, PLY_BOT),
             housed=["Long rail"], note="ends drop into open-top stopped dados in rails")

# ---------------------------------------------------------------- guards
def guard(side, plane, x0, x1, stile_xs, flush_end=False):
    """2x4 stiles carry the bolts; the rest is 3/4in pine face-glued to their inner face:
    1x4 top and bottom rails, 1x3 slats lapped over the rails, 1x6 cap on top."""
    mod = f"Guard ({side})"
    g0, g1 = plane
    s = 1 if g0 < WO / 2 else -1                 # +1 = inward is +y (front guard)
    yi = g1 if s > 0 else g0                     # stile inner face
    band = lambda a, b: (min(yi + s * a, yi + s * b), max(yi + s * a, yi + s * b))
    yr, ys = band(0, PINE), band(PINE, 2 * PINE)  # rail plane, slat plane
    for k, sx in enumerate(stile_xs):
        part(f"Guard stile {side} {k + 1}", mod, "2x4", (sx, sx + 3.5, g0, g1, STILE_BOT, CAP_BOT),
             note="bolted to post/rail; pine rails glued+screwed to its inner face")
    part(f"Guard bottom rail ({side})", mod, "1x4", (x0, x1, *yr, RAIL_TOP, RAIL_TOP + 3.5),
         note="pine; rests on the long rail's top edge")
    part(f"Guard top rail ({side})", mod, "1x4", (x0, x1, *yr, CAP_BOT - 3.5, CAP_BOT), note="pine")
    yc = (min(g0, ys[0]) + max(g1, ys[1])) / 2
    part(f"Guard cap ({side})", mod, "1x6", (x0, x1, yc - 2.75, yc + 2.75, CAP_BOT, CAP_TOP),
         note="pine, flat; glued+screwed to stiles and top rail; 1/2in roundover")
    # slats: equal clear gaps; front guard's last slat finishes flush with the ladder opening
    L, w = x1 - x0, SLAT_W
    n = math.ceil((L - SPINDLE_GAP) / (w + SPINDLE_GAP)) if not flush_end else math.ceil(L / (w + SPINDLE_GAP))
    gap = (L - n * w) / (n + 1) if not flush_end else (L - n * w) / n
    assert gap <= 3.5, gap
    for j in range(n):
        xs = x0 + gap + j * (w + gap)
        part(f"Guard slat {side}", mod, "1x3", (xs, xs + w, *ys, RAIL_TOP, CAP_BOT),
             note=f"pine; glued+screwed over both rails; clear gap {gap:.2f}in")
    return gap

# centre stile sits 6in off centre so its rail inserts miss the two rib dados at the deck-panel seam
mid = LO / 2 + 6.0
assert all(abs(mid - (rx + T / 2)) > 1.75 + T / 2 + 0.75 for rx in rib_x), "centre stile over a rib dado"
guard("back", GB, PX, LO - PX, [PX, mid - 1.75, LO - PX - 3.5])
ins("3/8-16", "post inner x-faces (back guard stiles)", 4)
ins("3/8-16", "back rail outer face (back guard stiles)", 6)
bolt('3/8-16 x 4-1/4"', 4)
bolt('3/8-16 x 2-1/4"', 6)
guard("front", GF, PX, OPEN0, [PX, OPEN0 - 3.5], flush_end=True)
ins("3/8-16", "post inner x-face (front guard stile)", 2)
ins("3/8-16", "front rail outer face (front guard stiles)", 4)
bolt('3/8-16 x 4-1/4"', 2)
bolt('3/8-16 x 2-1/4"', 4)

# ----------------------------------------------------------------- ladder
th = math.radians(LADDER_ANGLE)
SD = 5.5                                       # 2x6 stile depth
top_y, top_z = YF0, RAIL_TOP                   # back edge of stile touches rail face at rail top
u = (math.cos(th), math.sin(th))               # up-the-ladder (y,z)
n = (-math.sin(th), math.cos(th))              # out from back edge (y,z)
Ls = top_z / math.sin(th)                      # back-edge length floor -> top
by0 = top_y - top_z / math.tan(th)
cy = by0 + u[0] * Ls / 2 + n[0] * SD / 2
cz = 0 + u[1] * Ls / 2 + n[1] * SD / 2
sx_list = [OPEN0 + 0.25, OPEN0 + 0.25 + T + LADDER_CLEAR]
for k, sx in enumerate(sx_list):
    part(f"Ladder stile {k + 1}", "Ladder", "2x6",
         rot=dict(center=(sx + T / 2, cy, cz), size=(T, SD, Ls), angle=-(90 - LADDER_ANGLE)),
         cut=None, extra=SD / math.tan(th), note=f"{LADDER_ANGLE:.0f} deg; housed tread dados; notch for header")
rise = RAIL_TOP / (N_TREADS + 1)
for k in range(1, N_TREADS + 1):
    z1 = k * rise
    yc = top_y - (top_z - z1) / math.tan(th) - (SD / 2) / math.sin(th)
    part(f"Ladder tread {k}", "Ladder", "2x6",
         (sx_list[0] + T, sx_list[1], yc - 2.75, yc + 2.75, z1 - T, z1), extra=1.0,
         note="2x6 flat, housed 1/2in each end, glued + 2 screws")
part("Ladder header", "Ladder", "2x4", (sx_list[0], sx_list[1] + T, YF0 - T, YF0, RAIL_TOP - 3.5, RAIL_TOP),
     housed=["Ladder stile"], note="let into stile notches; bolts to rail face")
part("Ladder hook lip", "Ladder", "1x4", (sx_list[0], sx_list[1] + T, YF0 - T, YF1 - 0.25, RAIL_TOP, RAIL_TOP + 0.75),
     note="glued/screwed to header top; hooks over rail")
ins("3/8-16", "front rail outer face (ladder header)", 3)
bolt('3/8-16 x 2-1/4"', 3)

# ---------------------------------------------------------------- checks
def overlap(a, b):
    return all(min(a[2*i+1], b[2*i+1]) - max(a[2*i], b[2*i]) > 1e-6 for i in range(3))

collisions = []
boxed = [p for p in parts if p["box"]]
for i, a in enumerate(boxed):
    for b in boxed[i + 1:]:
        if overlap(a["box"], b["box"]):
            ok = any(b["name"].startswith(h) for h in a["housed"]) or any(a["name"].startswith(h) for h in b["housed"])
            if not ok:
                collisions.append((a["name"], b["name"]))

# ------------------------------------------------------------------ sizes
def dims(p):
    """(thickness, width, cut length) for the cut list."""
    if p["rot"]:
        s = p["rot"]["size"]
        return (s[0], s[1], s[2] + p["extra"])
    if p["cut"]:
        return (None, p["cut"][1], p["cut"][0])
    b = p["box"]
    d = sorted([b[1] - b[0], b[3] - b[2], b[5] - b[4]])
    return (d[0], d[1], d[2] + p["extra"])

STOCK = {
    "post": ("2x4 (laminate pairs)", 1.5, 3.5),
    "2x2": ("2x2", 1.5, 1.5), "2x4": ("2x4", 1.5, 3.5), "2x6": ("2x6", 1.5, 5.5),
    "2x8": ("2x8", 1.5, 7.25), "2x10": ("2x10", 1.5, 9.25), "1x3": ("1x3 pine", 0.75, 2.5), "1x4": ("1x4 pine", 0.75, 3.5), "1x6": ("1x6 pine", 0.75, 5.5),
    "ply12": ("1/2in plywood", 0.5, None), "ply34": ("3/4in plywood", 0.75, None),
}
DENS = {"ply12": 0.020, "ply34": 0.020}     # lb/in^3 (plywood ~34 pcf)
DENS_LUMBER = 0.016                          # SPF/DF KD ~28 pcf

def volume(p):
    t, w, L = dims(p)
    if t is None:
        t = STOCK[p["stock"]][1]
    return t * w * L

def weight(p):
    return volume(p) * DENS.get(p["stock"], DENS_LUMBER)

modules = defaultdict(list)
for p in parts:
    modules[p["module"]].append(p)

def bbox(ps):
    bx = [p["box"] for p in ps if p["box"]]
    lo = [min(b[2*i] for b in bx) for i in range(3)]
    hi = [max(b[2*i+1] for b in bx) for i in range(3)]
    for p in ps:
        if p["rot"]:
            c, s, a = p["rot"]["center"], p["rot"]["size"], math.radians(p["rot"]["angle"])
            hy = abs(s[1] / 2 * math.cos(a)) + abs(s[2] / 2 * math.sin(a))
            hz = abs(s[1] / 2 * math.sin(a)) + abs(s[2] / 2 * math.cos(a))
            lo = [min(lo[0], c[0] - s[0] / 2), min(lo[1], c[1] - hy), min(lo[2], c[2] - hz)]
            hi = [max(hi[0], c[0] + s[0] / 2), max(hi[1], c[1] + hy), max(hi[2], c[2] + hz)]
    return [h - l for l, h in zip(lo, hi)]

# --------------------------------------------------------------- structure
# Design values: SPF/Hem-Fir/DF #2 -- using SPF #2 (the weakest common species), NDS Supplement.
FB, FV, FCP, E = 875.0, 135.0, 425.0, 1.4e6
CF = {"2x4": 1.5, "2x6": 1.3, "2x8": 1.2, "2x10": 1.1}
CR = 1.15                                   # repetitive member (ribs)
CFU = {"2x4": 1.1, "2x6": 1.15}             # flat-use factor
OCC = 300.0                                 # rated occupant load
IMPACT = 2.0                                # kids jumping
P = OCC * IMPACT
mattress_w = 50.0
deck_w = sum(weight(p) for p in parts if p["module"].startswith("Deck"))
empty_w = sum(weight(p) for p in parts)

def S(b, d): return b * d * d / 6
def I(b, d): return b * d ** 3 / 12

calc = []
def chk(name, demand, cap, unit, basis):
    calc.append((name, demand, cap, unit, demand / cap, basis))

# 1. long rail: point load at midspan + half of deck/mattress as UDL
span = LO - PX
w_udl = (mattress_w + deck_w) / 2 / span
M = P * span / 4 + w_udl * span ** 2 / 8
# net section where a rib dado (1/2in deep, from rib bottom to top) cuts the inner face
d_full, d_cut = RIB_BOT - RAIL_BOT, RAIL_TOP - RIB_BOT
A1, A2 = T * d_full, (T - HOUSE) * d_cut
yb = (A1 * d_full / 2 + A2 * (d_full + d_cut / 2)) / (A1 + A2)
In = I(T, d_full) + A1 * (yb - d_full / 2) ** 2 + I(T - HOUSE, d_cut) + A2 * (d_full + d_cut / 2 - yb) ** 2
Snet = In / max(yb, W2[RAIL] - yb)
chk("Long rail bending (600 lb point at midspan, net section at a dado)", M / Snet, FB * CF[RAIL], "psi",
    f"{RAIL} SPF#2, span {span:.1f}in, Fb x CF")
V = P / 2 + w_udl * span / 2
chk("Long rail shear", 1.5 * V / (T * W2[RAIL] - HOUSE * d_cut), FV, "psi", "net area at end")
defl = OCC * span ** 3 / (48 * E * In)
chk("Long rail deflection (300 lb static point)", defl, span / 360, "in", "limit L/360")
# 2. housing bearing: rail bottom edge on post shoulder (perp. to grain), 1/2 x 3 in
R = V
chk("Rail bearing on post housing shoulder", R / (HOUSE * PX), FCP, "psi", "Fc-perp of rail; bolts ignored")
# 3. ribs: one rib takes 60% of the point load at 12in spacing, pro-rated by
#    actual spacing (mattress + plywood spread the rest to neighbours)
rspan = WIN + HOUSE
share = 0.6 * step / 12
Mr = share * P * rspan / 4
chk(f"Deck rib bending ({share:.0%} of 600 lb on one rib)", Mr / S(T, 3.5), FB * CF["2x4"] * CR, "psi",
    f"2x4 on edge, span {rspan:.1f}in, plywood composite action ignored")
chk("Rib end bearing in rail dado", share * P / 2 / (HOUSE * T), FCP, "psi", "1/2 x 1-1/2 bearing")
# 4. posts: all vertical load on one post (absurd case) -- column check
Pc = P + mattress_w + empty_w
le = POST_H
Fce = 0.822 * E * 0.58 / (le / 3.0) ** 2      # Emin ~0.58E
Fc = 1150 * 1.1
r = Fce / Fc
Cp = (1 + r) / (2 * 0.8) - math.sqrt(((1 + r) / 1.6) ** 2 - r / 0.8)
chk("Post compression (everything on one post)", Pc / (PX * PY), Fc * Cp, "psi", f"unbraced {le:.0f}in, Cp={Cp:.2f}")
# 5. guard cap: 200 lb outward at middle of the longest bay
bay = max(OPEN0 - 3.5 - (PX + 3.5), (mid - 1.75) - (PX + 3.5))
Mc = 200 * bay / 4
FB_PINE = 575.0                             # Eastern white pine #2 (NDS) -- weakest pine sold as boards
chk("Guard cap bending (200 lb outward, longest bay)", Mc / S(PINE, 5.5), FB_PINE * 1.3, "psi",
    f"flat 1x6 pine bending about its 5.5in width, bay {bay:.1f}in, top rail/slats ignored")
# free guard stile at ladder opening (front stile 2): 100 lb at cap, couple from 2 bolts
lever = CAP_TOP - (RAIL_TOP - 1.25)
bolt_arm = (RAIL_TOP - 1.25) - (STILE_BOT + 1.0)   # stile-to-rail bolt spacing
chk("Ladder-side guard stile: insert withdrawal", 100 * lever / bolt_arm, 300, "lb",
    "allowable 300 lb per 3/8-16 insert in SPF face grain (verify with a pull test)")
# 6. ladder tread
tspan = LADDER_CLEAR + 0.5
chk("Ladder tread bending (600 lb mid-tread)", P * tspan / 4 / S(5.5, 1.5), FB * CF["2x6"] * CFU["2x6"], "psi", "2x6 flat")
# 7. racking, transverse (y): two end frames, posts fixed at stretcher & apron
H = 150.0
h_free = EF["apron"][1] - (EF["lower stretcher"][1] + 5.5)
k_post = 12 * E * I(PX, PY) / h_free ** 3
k_y = 4 * k_post * 0.5                       # 50% for semi-rigid M&T joints
chk("Sway, side-to-side (150 lb push at deck)", H / k_y, 0.125, "in", f"4 posts, {h_free:.1f}in free, joints at 50% fixity")
Mp = H / 4 * h_free / 2
chk("Post bending from that push", Mp / S(PX, PY), FB * CF["2x4"], "psi", "")
# 8. racking, longitudinal (x): back shear panel, 1/4-20 bolts
chk("Sway, lengthwise: shear-panel bolts (150 lb)", H / 6, 150, "lb/bolt", "6 bolts top row, 150 lb each allowable (conservative)")
# 9. tipping (empty bed, push at cap height)
tip_y = empty_w * (WO / 2) / CAP_TOP
tip_x = empty_w * (LO / 2) / CAP_TOP

summary = dict(
    variant=MATTRESS["name"], overall=(LO, WO, POST_H), lounge_clear=RAIL_BOT, rib_clear=RIB_BOT,
    deck_top=DECK_TOP, mattress_top=MAT_TOP, cap_top=CAP_TOP, empty_w=empty_w, tip_y=tip_y, tip_x=tip_x,
    pocket=(LIN, WIN), collisions=collisions,
)

# ------------------------------------------------------------------ output
def fmt(x):
    """inches -> nearest 1/16 as a mixed fraction"""
    s = round(x * 16)
    w, f = divmod(s, 16)
    if f == 0:
        return f'{w}"'
    g = math.gcd(f, 16)
    return f'{w} {f//g}/{16//g}"' if w else f'{f//g}/{16//g}"'

def write_outputs():
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    # model.json ---------------------------------------------------------
    mjson = dict(summary=summary, parts=[], mattress=[PX + 0.375, LO - PX - 0.375, YF1 + 0.625, YB0 - 0.625, DECK_TOP, MAT_TOP])
    for p in parts:
        t, w, L = dims(p)
        mjson["parts"].append(dict(name=p["name"], module=p["module"], stock=STOCK[p["stock"]][0],
                                   box=p["box"], rot=p["rot"], note=p["note"],
                                   cut=f"{fmt(w)} x {fmt(L)}"))
    with open(os.path.join(ROOT, "build", "model.json"), "w") as f:
        json.dump(mjson, f, indent=1)
    tpl = open(os.path.join(ROOT, "viewer", "template.html")).read()
    with open(os.path.join(ROOT, "viewer", "index.html"), "w") as f:
        f.write(tpl.replace("/*MODEL*/null", json.dumps(mjson)))

    # cut list ------------------------------------------------------------
    rows = defaultdict(lambda: [0, None])
    for p in parts:
        t, w, L = dims(p)
        base = p["name"].split(" (")[0]
        base = base.rstrip("0123456789. ").replace(" head-front", "").replace(" head-back", "").replace(" foot-front", "").replace(" foot-back", "")
        key = (p["module"].split(" (")[0].replace(" 1", "").replace(" 2", ""), base, STOCK[p["stock"]][0], round(w, 3), round(L, 3))
        rows[key][0] += 1
        rows[key][1] = p["note"]
    lines = ["# Cut list — " + MATTRESS["name"], "",
             "_Generated by `model/bed.py`. Lengths include hidden tenons/tongues. "
             "Posts are listed per lamination (glue two 2x4s face-to-face, then trim to length)._", "",
             "| Module | Part | Stock | Qty | Width | Length | Notes |", "|---|---|---|---:|---:|---:|---|"]
    csvrows = [["module", "part", "stock", "qty", "width_in", "length_in", "notes"]]
    for (mod, nm, stk, w, L), (q, note) in sorted(rows.items()):
        if stk.startswith("2x4 (lam"):
            q *= 2
        lines.append(f"| {mod} | {nm} | {stk} | {q} | {fmt(w)} | {fmt(L)} | {note} |")
        csvrows.append([mod, nm, stk, q, f"{w:.3f}", f"{L:.3f}", note])

    # board buying: first-fit-decreasing into 8ft boards
    need = defaultdict(list)
    board_n = {}
    for p in parts:
        stk = p["stock"]
        if stk.startswith("ply"):
            continue
        t, w, L = dims(p)
        key = "2x4" if stk == "post" else stk
        need[key] += [L + 1.0] * (2 if stk == "post" else 1)    # +1in trim allowance
    lines += ["", "## Lumber to buy", "",
              "Kiln-dried S4S construction lumber (SPF, Doug-fir or SYP), #2 or better. "
              "Hand-pick straight boards with small, tight knots — especially for posts and rails. "
              "Buy ~15% extra for defects.", "", "| Stock | 8 ft boards (min) | Cuts |", "|---|---:|---|"]
    for stk, Ls in sorted(need.items()):
        boards = []
        for L in sorted(Ls, reverse=True):
            for b in boards:
                if sum(b) + L + KERF * len(b) <= 96:
                    b.append(L); break
            else:
                boards.append([L])
        lines.append(f"| {stk} | {len(boards)} | {len(Ls)} pieces |")
        board_n[stk] = len(boards)
    ply = defaultdict(float)
    for p in parts:
        if p["stock"].startswith("ply"):
            t, w, L = dims(p)
            ply[p["stock"]] += w * L
    sheet_n = {k: math.ceil(v / (48 * 96) * 1.05) for k, v in ply.items()}
    lines += ["", "| Sheet | Sheets | Parts |", "|---|---:|---|",
              f"| 3/4in plywood (birch/maple or sanded pine, BC or better) | {math.ceil(ply['ply34'] / (48*96) * 1.05)} | 2 deck panels |",
              f"| 1/2in plywood (any cabinet/BC grade; actual ~15/32) | {math.ceil(ply['ply12'] / (48*96) * 1.05)} | back shear panel + 2 end panels |"]

    # rail layout: the measurements that must be right
    zb = lambda z: fmt(z - RAIL_BOT)
    lines += ["", "## Long rail layout", "",
              "Measure x from the **head end** of each rail; heights are up from the rail's **bottom edge**. "
              "Lay out the front and back rails as a mirrored pair (dados face each other).", "",
              f"**Rib dados** (inner face, {fmt(T + 1/16)} wide x {fmt(HOUSE)} deep, open at the top, stopped "
              f"{zb(RIB_BOT)} above the bottom edge), left edge at: " +
              ", ".join(fmt(x) for x in rib_x), "",
              "| Insert (3/8-16, rail outer face) | x from head end | up from bottom edge | Rail |",
              "|---|---|---|---|",
              f"| Rail-to-post bolts | {fmt(0.75)} & {fmt(LO - 0.75)} | {zb(RAIL_BOT + 2.25)} | both |",
              f"| Rail-to-post bolts | {fmt(2.25)} & {fmt(LO - 2.25)} | {zb(RAIL_TOP - 2.0)} | both |",
              f"| Guard stiles at posts | {fmt(PX + 2.75)} & {fmt(LO - PX - 2.75)} | {zb(STILE_BOT + 1.0)} & {zb(RAIL_TOP - 1.25)} | back (front: head end only) |",
              f"| Back guard centre stile | {fmt(mid)} | {zb(STILE_BOT + 1.0)} & {zb(RAIL_TOP - 1.25)} | back |",
              f"| Front guard stile at ladder | {fmt(OPEN0 - 1.75)} | {zb(STILE_BOT + 1.0)} & {zb(RAIL_TOP - 1.25)} | front |"]
    clear = lambda x: all(abs(x - (rx + T / 2)) > T / 2 + 0.95 for rx in rib_x)   # 5/8 edge-to-edge
    cand = [sx_list[0] + 1.5 + 0.25 * i for i in range(int((sx_list[1] - sx_list[0] - 1.5) / 0.25) + 1)]
    cand = [x for x in cand if clear(x)]
    c = (sx_list[0] + sx_list[1] + T) / 2
    lx = [cand[0], min(cand, key=lambda x: abs(x - c)), cand[-1]]
    lines += [f"| Ladder header | {', '.join(fmt(x) for x in lx)} | {zb(RAIL_TOP - 1.75)} | front |", "",
              "Rule: an insert in a rail's outer face must stay **at least 5/8in (edge to edge) clear of the rib "
              "dados** on the inner face, or sit below them. The positions above already do that.", ""]

    # hardware
    tot = defaultdict(int)
    for s, where, n in inserts:
        tot[s] += n
    lines += ["", "## Threaded inserts", "", "| Size | Where | Qty |", "|---|---|---:|"]
    for s, where, n in inserts:
        lines.append(f"| {s} | {where} | {n} |")
    lines += [f"| **3/8-16** | **total** (+6 spares) | **{tot['3/8-16'] + 6}** |",
              f"| **1/4-20** | **total** (+4 spares) | **{tot['1/4-20'] + 4}** |"]
    with open(os.path.join(ROOT, "docs", "CUTLIST.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(ROOT, "docs", "cutlist.csv"), "w", newline="") as f:
        csv.writer(f).writerows(csvrows)
    write_cost(board_n, sheet_n, tot)

def write_cost(board_n, sheet_n, ins_tot):
    rows = []   # (section, item, qty, low, high)
    for stk, n in sorted(board_n.items()):
        rows.append(("Lumber", f"{stk} x 8 ft", n, *PRICES[stk]))
        extra = math.ceil(n * SPARE_LUMBER)
        rows.append(("Lumber", f"{stk} x 8 ft — spares (~{SPARE_LUMBER:.0%})", extra, *PRICES[stk]))
    for k, nm in (("ply34", "3/4in plywood 4x8"), ("ply12", "1/2in plywood 4x8")):
        rows.append(("Plywood", nm, sheet_n[k], *PRICES[k]))
    rows.append(("Inserts & bolts", "3/8-16 inserts (packs of 50)", math.ceil((ins_tot["3/8-16"] + 6) / 50), *PRICES["insert 3/8-16 (pack of 50)"]))
    rows.append(("Inserts & bolts", "1/4-20 inserts (packs of 25)", math.ceil((ins_tot["1/4-20"] + 4) / 25), *PRICES["insert 1/4-20 (pack of 25)"]))
    for spec, n in sorted(bolts.items()):
        rows.append(("Inserts & bolts", f"bolt {spec}", n, *PRICES[spec]))
    n38 = sum(n for s, n in bolts.items() if s.startswith("3/8"))
    n14 = sum(n for s, n in bolts.items() if s.startswith("1/4"))
    rows.append(("Inserts & bolts", "fender washers 3/8", n38, *PRICES["fender washer 3/8"]))
    rows.append(("Inserts & bolts", "fender washers 1/4", n14, *PRICES["fender washer 1/4"]))
    rows.append(("Other hardware", "leveling glides 3/8-16 (4 pack)", 1, *PRICES["leveling glide 3/8-16 (4 pack)"]))
    rows.append(("Other hardware", "anti-tip strap", 1, *PRICES["anti-tip strap"]))
    for k in ("wood glue (quart)", "screws 1-1/4 & 2-1/2 (boxes)", "water-based poly (2 quarts)", "sandpaper assortment"):
        rows.append(("Consumables", k, 1, *PRICES[k]))

    money = lambda x: f"${x:,.0f}"
    out = [f"## {MATTRESS['name']}", "", "| Section | Item | Qty | Each | Line total |", "|---|---|---:|---:|---:|"]
    sec = defaultdict(lambda: [0.0, 0.0])
    for s, item, q, lo, hi in rows:
        if q == 0:
            continue
        sec[s][0] += q * lo; sec[s][1] += q * hi
        each = f"${lo:.2f}–{hi:.2f}"
        out.append(f"| {s} | {item} | {q} | {each} | {money(q * lo)}–{money(q * hi)} |")
    lo = sum(v[0] for v in sec.values()); hi = sum(v[1] for v in sec.values())
    out += ["", "| Subtotal | Low | High |", "|---|---:|---:|"]
    for s, (a, b) in sec.items():
        out.append(f"| {s} | {money(a)} | {money(b)} |")
    out.append(f"| **Materials before tax** | **{money(lo)}** | **{money(hi)}** |")
    for nm, r in TAX.items():
        out.append(f"| Total with {nm} tax ({r * 100:.3f}%) | {money(lo * (1 + r))} | {money(hi * (1 + r))} |")
    tlo = sum(v[0] for v in TOOLS.values()); thi = sum(v[1] for v in TOOLS.values())
    out += ["", f"Optional tools & jig stock if you don't own them: **{money(tlo)}–{money(thi)}** "
            "(" + ", ".join(TOOLS) + ").", ""]
    with open(os.path.join(ROOT, "build", f"cost_{MATTRESS['name'].lower()}.md"), "w") as f:
        f.write("\n".join(out) + "\n")
    summary["cost"] = (lo, hi)

def calc_md():
    s = summary
    out = [f"## {s['variant']} variant", "",
           f"- Overall: **{fmt(s['overall'][0])} L x {fmt(s['overall'][1])} W x {fmt(s['overall'][2])} H**; mattress pocket {fmt(s['pocket'][0])} x {fmt(s['pocket'][1])}",
           f"- Deck top {fmt(s['deck_top'])}, mattress top {fmt(s['mattress_top'])}, guard cap {fmt(s['cap_top'])} "
           f"(**{CAP_TOP - MAT_TOP:.1f}in above an {MATTRESS_T:.0f}in mattress**; standard minimum is 5in)",
           f"- Lounge headroom: {fmt(s['lounge_clear'])} under the rails, {fmt(s['rib_clear'])} under the deck ribs",
           f"- Empty weight ≈ **{s['empty_w']:.0f} lb** (without mattress)",
           f"- Geometry collision check: {'**PASS** — no unintended overlaps' if not s['collisions'] else s['collisions']}", "",
           "| Check | Demand | Capacity | Unit | Use | Basis |", "|---|---:|---:|---|---:|---|"]
    for name, d, c, u, r, basis in calc:
        out.append(f"| {name} | {d:,.2f} | {c:,.2f} | {u} | {'**' if r > 1 else ''}{r:.0%}{'**' if r > 1 else ''} | {basis} |")
    out += ["", f"Tipping (empty bed, someone pulling sideways on the guard cap): ≈ **{s['tip_y']:.0f} lb** side-to-side, "
            f"≈ {s['tip_x']:.0f} lb end-to-end. With a kid on the deck the bed gets more stable, not less, but a "
            "furniture anti-tip strap to a wall stud is cheap insurance (it carries no structural load).", ""]
    return out

if __name__ == "__main__":
    print(json.dumps({k: v for k, v in summary.items()}, indent=1, default=str))
    for name, d, c, u, r, basis in calc:
        print(f"{r:6.0%}  {name}: {d:.2f}/{c:.2f} {u}")
    for k, v in modules.items():
        print(f"{k:28s} {len(v):3d} parts  {sum(weight(p) for p in v):5.0f} lb  bbox {[round(x,1) for x in bbox(v)]}")
    if not ARGS.no_write:
        write_outputs()
        path = os.path.join(ROOT, "build", f"calcs_{MATTRESS['name'].lower()}.md")
        mods = ["", "### Modules (for transport)", "", "| Module | Parts | Weight | Size L x W x H |", "|---|---:|---:|---|"]
        for k, v in modules.items():
            bb = bbox(v)
            mods.append(f"| {k} | {len(v)} | {sum(weight(p) for p in v):.0f} lb | {' x '.join(fmt(x) for x in bb)} |")
        with open(path, "w") as f:
            f.write("\n".join(calc_md() + mods) + "\n")
