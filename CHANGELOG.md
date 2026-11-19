# Changelog

## Unreleased

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
