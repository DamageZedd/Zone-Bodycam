# Changelog

## Unreleased

### Added
- **Blur faces** (MCM **Lens > Blur faces**, on by default): the faces of stalkers the camera sees are pixelated into a coarse mosaic, like released bodycam footage.
  - Every face you can see, at any distance (up to 64 at once, nearest first), alive or dead, so faces stay pixelated through a scope. Faces behind walls are left alone (same line-of-sight rules as the ally markers), and faces only a few pixels big are too small to need it.
  - Needs Shader Bus 7 (modded exes 2026.10.11 or newer); on older exes faces are not pixelated.
  - The mosaic is applied before the lens warp, so it bends with the fisheye; it also works with the lens turned off.
  - Near faces get 8 blocks across; far faces keep blocks at least 5 px tall.
  - Test: `tools/tests/zbc_faces_test.lua`.
- **Names above the ally boxes** (MCM **Ally markers > Show names**, on by default): each box shows the stalker's name and, in smaller text under it, their faction, in the overlay font and the box colour, fading with the box. Hidden while the marker is a dot.
  - Each time a box appears, the text decodes from scrambled characters, letter by letter from the left (about a second for a long name).
  - **Identification by distance**, after the Identification UI mod: within 50 m a stalker is identified as soon as their box appears. Further out the name, faction and colour stay unknown (white, scrambled) and only decode while you look at them, at that mod's rate (about 4 s at 60 m, 28 s at 100 m, 7 s at 100 m through a 4x scope). Identified stalkers stay identified for the session.
  - Through a scope the marker range grows with the zoom, so far allies you're aiming at get a box and a name too.
- **Camera effects** (new MCM section, everything on by default):
  - **Interference**: the picture tears, jitters, rolls and drops frames during emissions and psy storms, in psy fields, in strong radiation, within 7 m of anomalies, and briefly when you take a big hit.
  - **Signal lost on death**: the feed breaks up, cuts to black and shows SIGNAL LOST (НЕТ СИГНАЛА in Russian) over the last timestamp. On exes older than Shader Bus 7 it only cuts to black.
  - **Low-light mode** (Auto / Always / Off): a grainy, nearly black-and-white infrared look at night (21:00-05:00) and in underground levels, fading in and out.
  - **Lens dirt**: rain drops bead on the lens and refract the picture while it rains, drying slowly after; blood splatters the lens when someone is hit within 2.5 m in front of you and fades over about 25 s.
  - **Event marker**: "EVENT" appears after the recording timer for 5 s when you fire or take a big hit.
  - **GPS line**: coordinates under the name in the overlay (it moves up when the name is hidden).
  - **Low-battery warning** (bodycam item): a message and a beep at 10% and again at 6%.
  - New script `zbc_fx.script`; test `tools/tests/zbc_fx_test.lua`.
- **Mutants get boxes too** (MCM **Ally markers > Mark mutants**, on by default). The label shows the species (BLOODSUCKER, SNORK, PSEUDODOG...) with MUTANT under it, in English or Russian; four-legged mutants get a wide, low box. They identify by distance like stalkers and decode to the enemy colour (or friendly, for the rare tame one). Faces of mutants are not pixelated.
- **Full Russian localization.** Every menu string, the optional Body Camera item (name, description, battery message, its MCM page) and all MCM list options (logo, time zone, text size, marker style, colours) have Russian text in `configs\text\rus`.
  - The overlay font now has Russian letters, so Russian names and factions show in the top-right overlay and above the markers, with the lens on or off. KlartextMono has no Cyrillic, so those letters come from Roboto Mono Bold (Apache-2.0), matched to KlartextMono's capital height and letter width. `tools/make_overlay_assets.py` takes it as a fourth argument and also writes the shader copy of the letters (`zbc_osd_atlas_cyr.script`).
  - Names are put in capitals correctly for Russian text too.
  - Test: `tools/tests/zbc_localization_test.lua`.
- **Every stalker gets a box, enemies included** (MCM **Ally markers > Mark enemies**, on by default). The box is white while the stalker is unknown and, once the name has decoded, fades to green for friendly (neutrals count as friendly) or red for enemy (MCM colours: friendly, enemy, companion; the old neutral colour option is gone). Dots far away show the final colour straight away.
  - Test: `tools/tests/zbc_allies_label_test.lua`.

## v1.1.0 - 2026-11-20

### Added
- **Optional bodycam item** (FOMOD checkbox "Bodycam item (battery powered)", off by default). Adds a **Body Camera** item sold by the general traders (about 5000 RU). The bodycam effect only runs while you carry a charged camera anywhere in your inventory, like the Wearable Devices items; no equipment slot is used.
  - The camera's condition is its battery. It drains in real time while recording (MCM **Zone Bodycam: Item > Battery life**, 4 real hours by default, scaled by the difficulty's battery consumption).
  - Swap batteries like vanilla devices: drag a battery onto the camera, or use **Unpack battery**.
  - With no camera or a dead battery, the lens, overlay, REC timer display and ally markers are all off. The REC timer keeps counting in the background.
  - The Body Camera has its own model (an Axon Body 4, measured from Axon's product render), texture and inventory icon. Build scripts: `tools/bodycam_item/`.
  - **First-person hand animations** (MCM **Hand animations**, on by default):
    - When the battery dies: you tap the camera on your chest, unclip it, turn it round in your hand to look at the front, give it a little shake and put it away.
    - When you put a battery on the camera in the inventory (after you close the menu): you slide the new battery into the bottom of the camera and clip it back on your chest. The camera turns back on at that moment.
    - The weapon and detector are put away first and come back afterwards; you can keep moving. The chest itself stays just below the screen.
    - New hand motions are their own file in the shared `hud_hands_animation` folder, so they work with every outfit's hands and don't replace any other mod's files.
  - **Battery gauge**: a VHS-style battery icon just above the red REC dot. Each of its 4 bars is 25% of the charge; the bar that is draining starts flashing once its 25% is half used, then goes out. Drawn with the overlay (inside the image with the lens on, as HUD with it off) and shown with the recording timer.
  - Without the optional component the mod is unchanged: the bodycam is always on.
  - Tests: `tools/tests/zbc_item_test.lua`, `tools/tests/zbc_battery_gauge_test.lua`.

### Changed
- **Shader & Lua performance pass**:
  - Halved dynamic constant-buffer atlas reads (`4 -> 2` per bilinear glyph/logo sample) in `zbc_osd.h`, reducing `postprocess.ps` and `postprocess_cm.ps` DXBC size (`-660` bytes) and temp registers (`24 -> 23`), plus added square fast-rejects on the recording dot and glyph loop.
  - Made Shader Bus lane registration and 816-row atlas upload lazy when the mod or lens is disabled.
  - Stopped `RefreshRec` from sending per-second `bus_zbc_rec` / `osd_layout` updates when the recording timer or HUD is hidden, cached actor serial/name formatting (`actor_ident`), cached `rec_text` per second, skipped redundant initial `save_var` writes, and removed the remaining `pcall(function)` closure in `rec_seed`.

### Fixed
- **Crash on start with modded exes older than 2026.10.11** ("R_constant_table::parse: unexpected shader variable type"). Those engines can't read the overlay's `uint` shader constants, so the in-shader overlay now only compiles when the engine reports Shader Bus 7 or newer. On older exes the game starts, the lens stays off and the overlay is drawn as normal HUD text. Regression test: `tools/tests/shader_uint_guard_test.lua`.
- **Missing overlay and recording timer on Shader Bus <= 6 engines**: `bus_ready()` now gates in-shader OSD mode on `set_array_uint` and Shader Bus `>= 7`, so older Shader Bus engines keep the 2D HUD overlay and recording timer visible instead of hiding both.
- **Minimized window (`0x0`), nil `ray_pick()`, and out-of-range config safety**: Added `W <= 0`/`H <= 0` guards in `fill_zoom`, `ZbcHud:Layout`, and `zbc_allies.update`; added a fallback to `actor:see` if `ray_pick()` returns `nil`; clamped `bus_zbc_rec.z` in `zbc_osd.h`; cleared `rec.last_t` when disabling the mod; and validated/clamped list & numeric MCM settings (including `NaN` protection).

## v1.0.1 - 2026-11-18

### Added
- **Recording timer (top left).** A flashing red dot and `REC HH:MM:SS` showing how long the camera has been recording in this playthrough. It uses the same font, size and text opacity as the top-right overlay and mirrors its margin.
  - Counts real time like the run timer mods. Pauses and loading screens are not counted.
  - Stored on the actor, so it carries through saves and level changes. Saves made before this version start from the time already spent in the Zone.
  - Drawn inside the image with the lens on (same colour fringing and grain as the overlay) and as HUD glyphs with the lens off.
  - New MCM option: **Recording timer (top left)**, on by default.
- **Automatic aspect-ratio scaling** for 4:3, 16:10, 16:9, 21:9 and 32:9 displays, with no extra patches:
  - no barrel-warp clipping at the sides on ultrawide;
  - 16:9 vignette framing;
  - ally markers stay lined up with the lens;
  - the top-right overlay keeps the same size and position.
- In-game preview screenshot in the README.

### Changed
- CPU/GPU optimization pass:
  - Ally-marker lens maths now precomputes per-frame constants.
  - The overlay shader skips every pixel outside the area the text and logo actually cover.
  - The lens samples the source position once and reuses it for the edge mask.
- The overlay's pixel shader area grew slightly (x from 0.55, y to 0.22), so larger text sizes and ultrawide layouts are no longer cut off.

### Fixed
- **No more black edges when raising the fisheye distortion.** The lens now zooms in automatically, just far enough to fill the screen for the current distortion and screen shape (rolling-shutter shear included). The MCM **Lens zoom** slider is now a minimum: raise it to crop in further. Ally markers follow the same zoom.
- Hiding the overlay right after changing a setting could leave the previous text on screen. Hiding now clears every glyph.
