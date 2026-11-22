<div align="center">

<sub>S.T.A.L.K.E.R. ANOMALY / G.A.M.M.A.</sub>

# ZONE BODYCAM

*See the Zone through a chest-mounted police bodycam.*

![Version](https://img.shields.io/badge/version-v1.2.0-e0a43c?style=for-the-badge) ![Author](https://img.shields.io/badge/by-Damage__Zedd-8fae5a?style=for-the-badge) ![Game](https://img.shields.io/badge/S.T.A.L.K.E.R.-Anomaly%201.5.3%20%2F%20GAMMA-555555?style=for-the-badge)

[![Zone Bodycam gameplay](docs/images/gameplay.webp)](docs/images/gameplay.mp4)

<sub>Recorded on the modded <a href="https://github.com/asuparabekon/xray-monolith-bodycam">Bodycam exes</a> (such as Slop-Ray) with their <b>Immersive Bodycam</b> camera on. The free-floating camera and weapon movement come from the Bodycam exes, <b>not from this mod</b>. Click the clip for the full-quality video with sound.</sub>

</div>

## What's new in v1.2.0

- **Front-only Face Blur (Pixelation).** Pixelates visible human faces (front, 3/4, and side profiles — never the back of heads) at true face size before the lens warp, with dual-view 3DSS PiP scope support, frame-ahead motion prediction, and a model skip list (`configs/zbc_face_models.ltx`).
- **Overhauled Entity Markers & Identification.** Skeleton-fit boxes for all stalkers and mutants, scoped head/spine fallback for partial bodies, dual-view 3DSS PiP scope magnification (keeping 1x boxes outside the lens), aim-only label text with smooth fade & quick re-decode (companions always on), lockstep name/faction decode, saved distance identification, `KIA` boxes, white-until-identified dots, and zero dots while scoped in.
- **Camera Effects.** Interference (emissions, psy storms/fields, radiation, anomalies, heavy hits), `SIGNAL LOST` death cutoff, night/underground IR mode, rain drops & blood splatter on the lens, auto-exposure lag, `EVENT` tag, GPS coordinates, and low-battery warnings.
- **Event Log & Footage Review.** Live 8 s evidence tags under `REC`, plus an interactive timeline review screen (`Delete` by default).
- **Full Russian Localization** across all MCM menus, overlay text, marker labels, and the optional Body Camera item (plus default device name `AXON BODY 4`).

Full history in [CHANGELOG.md](CHANGELOG.md).

## What you get

- **Bodycam lens.** Fisheye view with the camera housing around the edges, a small-sensor look, grain and a slight wobble when you turn fast or get hit. The lens zooms in by itself, so stronger fisheye never leaves black edges. Visible NPC faces are automatically pixelated into a coarse mosaic before the lens warp.
- **Chest-mounted feel.** The lens housing and vignette lag behind your turns, bob with your steps, and jolt when you land, shoot or get hit. The image itself only sways slightly. Your view and aim stay where the game puts them; this mod doesn't detach the camera from your weapon.
- **Bodycam overlay.**
  - **Top right:** in-game date and time, device name and serial, your character's name, optional GPS coordinates, and the logo (in English and Russian).
  - **Top left:** a flashing red dot and `REC 00:54:17` (plus `EVENT` when firing or taking a heavy hit), showing how long you've been recording this playthrough. It counts real time and is kept in your save.
- **Camera effects.** Interference in emissions, psy storms, psy fields, radiation, near anomalies and on heavy hits; `SIGNAL LOST` feed cutoff on death; automatic low-light infrared mode at night and underground; rain drops and blood splatter on the lens.
- **Entity markers.** Stalkers (friendly, neutral, companion and enemies) and mutants you can see get a box with their name/species and faction, decoding from scrambled text by distance and scope zoom (dots past a distance).
- **Every screen shape.** 4:3, 16:9, ultrawide 21:9 and 32:9 all work out of the box.
- **English & Russian.** Full localization for all MCM menus, overlay text, marker labels, mutant species, and the optional Body Camera item.

Everything can be tuned or turned off in MCM.

![Recording timer, overlay and ally markers in game](docs/images/rec_timer.webp)

## Optional: Body Camera item

Tick **Bodycam item (battery powered)** in the installer to make the bodycam a real piece of gear instead of always on.

- **Buy it from general traders.** The effect only runs while you carry a charged Body Camera anywhere in your inventory. No equipment slot is used.
- **It runs on batteries.** The battery drains while recording (4 real hours by default, set in MCM). A small VHS-style battery gauge sits above the REC dot.
- **When it dies,** the lens, overlay and markers switch off. Your character taps the camera, unclips it, checks it and puts it away.
- **Swap the battery** like any vanilla device: drag a battery onto the camera. Your character slides it in and clips the camera back on your chest.
- The REC timer keeps counting in the background while the camera is off.

<div align="center">

![The Body Camera item](docs/images/bodycam_item.webp)

[![Battery dies, swap it, back on](docs/images/bodycam_item_clip.webp)](docs/images/bodycam_item.mp4)

<sub>Click the clip for the full-quality video.</sub>

</div>

## Requirements

- S.T.A.L.K.E.R. Anomaly 1.5.3. Made and tested on G.A.M.M.A.
- **[Modded exes](https://github.com/themrdemonized/xray-monolith/releases) 2026.10.11 or newer** for the lens, face pixelation, and in-shader overlay/effects (Shader Bus 7). The [Bodycam exes](https://github.com/asuparabekon/xray-monolith-bodycam) (such as Slop-Ray) work too — G.A.M.M.A. users running the Bodycam exes also need the **Bodycam GAMMA Patch**. On older exes the lens and face pixelation are off (or Shader Bus <= 6 keeps the lens with the 2D HUD overlay fallback), while the overlay and markers still work.
- **MCM** to change settings (recommended).

## Installation

1. Install the archive with Mod Organizer 2 like any other mod. The installer asks whether you want the optional Body Camera item.
2. If another mod also replaces `postprocess.ps` or `postprocess_cm.ps`, give Zone Bodycam higher priority (put it lower in MO2's left pane).
3. Delete the contents of `Anomaly\appdata\shaders_cache` once, so the new shaders are built.
4. Start the game and open **MCM → Zone Bodycam**.

## Settings

| Section | What you can change |
|---|---|
| **Lens** | Strength, fisheye, zoom, chromatic aberration, sharpening, edge size and shape, vignette, grain, colour grade, rolling shutter, blur faces |
| **Camera effects** | Interference, signal lost on death, low-light mode (auto/always/off), lens dirt (rain & blood), EVENT marker, GPS coordinates |
| **Body motion** | Overall amount, turn lag, walking bob, camera roll, impacts, breathing |
| **Overlay** | Overlay on/off, recording timer on/off, device name, show your name, logo style, time zone, text size and opacity |
| **Ally markers** | On/off, only NPCs you can see, show names, mark enemies, mark mutants, style, friendly/enemy/companion colours, range, size, opacity |
| **Item** (optional) | Battery life, hand animations on/off |

## Good to know

- **Black edges or a broken screen after updating?** Clear `Anomaly\appdata\shaders_cache` and restart.
- **Too much fisheye?** Lower **Fisheye distortion**. The zoom adjusts by itself. **Lens zoom** only adds extra crop on top.
- **Using a run timer mod?** Run timers usually sit in the top-left corner too. Move them, or turn off the recording timer in MCM.
- **Changes** are listed in [CHANGELOG.md](CHANGELOG.md).

## Credits

- Mod by **Damage_Zedd**.
- **themrdemonized** and the modded exes contributors for the Shader Bus the lens runs on.
- **asuparabekon** for the [Bodycam exes](https://github.com/asuparabekon/xray-monolith-bodycam) (such as Slop-Ray), the engine the mod was built on.
- Body motion based on the damped camera chase from **Sludge's Intrusive 3D Masks**.

<details>
<summary><b>For modders</b></summary>

<br>

- Lens, sensor and overlay are drawn in `postprocess.ps` / `postprocess_cm.ps` (`gamedata/shaders/r3/zbc_*.h`), with values sent through the modded exes' Shader Bus (version 7: `try_register`, `set_array_uint`). On Slop-Ray this pass runs after DLSS/FSR, so the upscaler never sees the warp.
- Scripts: `zbc_bodycam.script` (settings, motion, overlay, timer), `zbc_allies.script` (markers & distance identification), `zbc_faces.script` (face pixelation), `zbc_fx.script` (interference, signal lost, low-light, lens dirt, GPS), `zbc_osd_atlas_cyr.script` (Cyrillic shader glyphs), `zbc_bodycam_mcm.script` (menu), plus optional `zbc_item.script`, `zbc_item_anim.script`, `zbc_item_mcm.script`.
- The overlay font and logo textures are generated from `tools/source_assets`. To rebuild them (needs Python and Pillow):

  ```bash
  py -I tools/make_overlay_assets.py tools/source_assets/KlartextMonoBold.ttf tools/source_assets/logo.png gamedata tools/source_assets/RobotoMono-VariableFont_wght.ttf
  ```

</details>
