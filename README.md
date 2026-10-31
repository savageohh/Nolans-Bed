# Nolan's Bed

A freestanding loft bed with a lounge/hideout underneath. It's built from standard S4S lumber
with a router, and joined with **threaded inserts** so it breaks down into 11 flat modules
for a truck or trailer. Rated **300 lb**, and checked at 600 lb for kids jumping.

![loft bed](docs/img/iso.png)

| | |
|---|---|
| **[Design & build guide](docs/DESIGN.md)** | How it stands up without a wall, every joint, router jigs, insert technique, build & assembly order, safety checklist |
| **[Cut list & rail layout](docs/CUTLIST.md)** | Parts, boards to buy, inserts, dado/insert positions ([CSV](docs/cutlist.csv)) |
| **[Structural checks](docs/CALCS.md)** | Twin and full variants |
| **[Material cost](docs/COST.md)** | Itemized Menards estimate with MN sales tax: **about $480–780 for the twin** |
| **[3D viewer](viewer/index.html)** | Download and open in a browser: orbit, explode, click any part for its cut size |

**Twin (default):** 81-3/4" L × 48-1/4" W × 72" H · deck at 54" · 46-3/4" lounge headroom ·
guard cap 6-1/2" above an 8" mattress.

## Changing the design

All dimensions come from one parametric model:

```bash
python3 model/bed.py --no-write          # print checks only
python3 model/bed.py --full --no-write   # full-size mattress
./model/build.sh                         # regenerate viewer, cut list, calcs
node model/render.js                     # re-render docs/img (needs playwright)
```

Parameters (mattress size and thickness, deck height, post size, ladder angle and width, rib
count, guard slat gap) are at the top of `model/bed.py`. The script checks every part for
unintended overlaps and prints a demand/capacity ratio for each structural check, so if a
change breaks something you'll see it.

![exploded](docs/img/exploded.png)
