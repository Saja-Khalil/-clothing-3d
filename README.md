# Clothing module (Saja)

Part of the virtual-fitting graduation project. On the working machine this folder lives at
`C:\Users\hp\NewAvatar\clothing`, next to Baraah's avatar module.

A photo of a garment → a 3D dress (GLB) on the avatar. Everything runs locally; no photo is sent to an online
service. The shape comes from a dress template sized by the photos and tape measurements, the look from the
photos themselves, and the drape from Blender's cloth simulation (`modelSource: "template_parametric"`).

## Current method: flat-lay photos

Lay the dress on a plain sheet, shoot it from straight above (front, then back), and measure its length and shoulder
width with a tape.

```
cd C:\Users\hp\NewAvatar\clothing
.venv\Scripts\python.exe backend\flat_dress.py --avatar output\avatar.glb ^
    --front samples\flat_front.jpg --back samples\flat_back.jpg ^
    --length-cm 130 --shoulder-cm 42 --hem-cm 118 --sleeve-cm 60 --sleeve-from neck --name dress01_flat
```

Needs Blender 4.2 LTS at `C:\Users\hp\tools\blender-4.2.23-windows-x64` (path in `backend/template_dress.py`).
Takes 3–7 minutes on an 8 GB laptop.

### Shop page (camera or file upload)

```
.venv\Scripts\python.exe backend\server.py
```
then open `http://127.0.0.1:8010/viewer/`. Each request gets its own folder `jobs/<uuid>/` (not in Git).

## Files

| File | What it does |
| --- | --- |
| `backend/flat_dress.py` | Main script: flat-lay photos + measurements → draped GLB |
| `backend/flat_lay.py` | Reads a flat-laid garment: collar, shoulders, armpits, sleeves, hem, scale; rejects unusable photos |
| `backend/template_dress.py` | Template parts: sleeves, ruffles (collar, cuffs), skirt folds |
| `backend/blender_drape.py` | Runs inside Blender: cloth simulation (tweed settings), GLB export (Y up) |
| `backend/blender_render.py` | Runs inside Blender: front / 35° / side / back renders |
| `backend/server.py` | Local server for the shop page: uploads, one job at a time |
| `backend/photo_to_garment.py` | Background removal (rembg u2net) and avatar measuring, shared; also the first, photo-projected version |
| `backend/photo_to_hanger.py` | Earlier attempt: the dress on a hanger, from photos against a wall |
| `backend/render_preview.py` | Quick CPU preview of a GLB (no Blender) |
| `viewer/index.html` | three.js viewer + "new dress" panel (camera / file, measurements) |
| `samples/flat_front.jpg`, `samples/flat_back.jpg` | Input photos of dress01 |
| `results/` | Final outputs kept in Git (see below) |

`output/` holds every intermediate result and is not in Git.

## Results in Git (`results/`)

| File | |
| --- | --- |
| `dress01_flat.glb` | The final dress |
| `dress01_flat_on_avatar.glb` | The dress on the test avatar |
| `dress01_flat_render.png` | Renders from four sides |
| `dress01_flat_compare.png` | The photo next to the 3D dress |
| `avatar_athletic.glb`, `avatar_athletic.png` | Athletic adult female avatar (experiment, see below) |

## Avatar experiment

`avatar/athletic_female_preview.py` fits an adult, athletic female body: age 0.67–0.8, muscle 0.55–0.72,
narrower shoulders, slimmer hips and legs, natural bust (Anny cup size 0.62). It runs inside Baraah's avatar module
(it imports its fit and measurement code), so copy it to `NewAvatar/backend/tools/` and run it from `backend/` with
the avatar `.venv`. It does not change her production fit or API.

## Reports

- Slides: https://claude.ai/artifact/7FJ8Kv8zsrE33TVTGj7qVD
- Report: https://claude.ai/artifact/R5srUrxveN7xBbNCXHivGA
