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
  - **Identification by distance**, after the Identification UI mod at GAMMA's speed (0.5). Nobody is identified instantly: the name, faction and colour stay unknown (white, scrambled) and only decode while you look at them, taking at least 2 s up close and that mod's rate further out (about 11 s at 100 m, 3 s at 100 m through a 4x scope). Look away and the progress waits for you.
  - **Picture-in-picture scopes** (3DSS): while the scope view is up, only people inside the lens are marked and face-blurred, magnified by the scope's power (3DSS zoom factors are read as fields of view: a 30 is about 4x), so the box fits the magnified body and the label sits above it. A body that fills the lens gets a box clipped to the lens instead of none.
  - **Info line** under the faction: identification progress while unknown ("IDENT 45%  142 M"), then rank and distance ("VETERAN  88 M", distance only for mutants), in English or Russian.
  - **Labels stay readable**: all labels are laid out together each frame. They move below the box when someone is so close their head is off the top of the screen, stay inside the screen edges, and stack instead of overlapping (the aimed-at target first, then nearest first).
  - **KIA**: someone killed while marked keeps a grey box with KIA for 5 s before it fades.
  - **Boxes fit the body**: built from the skeleton (head, neck, pelvis, elbows, hands, knees, feet, the top of the head and the ground) with a little room around the joints, so the box hugs the pose a stalker or mutant is in, crouching or prone included. Models without those bones use the head and feet as before. (The engine's bounding box was tried first but covers every pose a model can take, so boxes came out far too big.)
  - **Face blur through scopes**: faces too far away to see in the normal view are now blurred when a scope magnifies them, and a face near the lens edge is no longer skipped.
  - **Bodycam exes, decoupled camera**: the target and the "looking at them" check follow where the gun really points (first_person's aim pose), through glass and foliage; the camera centre counts while unarmed, sprinting or in freelook. Through a picture-in-picture scope the view is magnified about the gun's aim point, at 100 / zoom factor, and each scope's lens size is read from the exes' own measurement (pip.log, diagnostics on only while measuring), with 12% of the screen height as the fallback.
  - **Never marked**: cloaked bloodsuckers, poltergeists and ghost zombies.
  - **Saved with the game**: identified stalkers stay identified after loading a save or changing level (the last 256).
  - **Companions** fade toward grey as they get hurt.
  - **Face blur** also covers traders, and `configs\zbc_face_models.ltx` can list models to skip (full face masks) or to limit it to.
  - **Identified stalkers are remembered** for the session: look away and back and their name, faction and box colour are there at once.
  - **The one you aim at** (Identification UI's crosshair target) gets a full box and label at any distance, through a scope too, and keeps it while you stay on them.
  - The decode itself is slower and easier to follow: about 1.2 s for a 10-letter name, with the colour changing after it.
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
- **Event log** (MCM **Overlay > Event log**, on): short evidence tags under the recording timer for 8 s: SHOTS FIRED, CONTACT n (more hostiles on camera), OFFICER HIT, OFFICER DOWN (a companion killed), SUBJECT DOWN (someone you killed), EMISSION, in English or Russian. New `zbc_eventlog.script`.
- **Footage review screen** (MCM key, Delete by default): a timeline of the recording with a coloured tick for every logged event (identifications too) and the list around the selected one; left / right scrub, Home / End jump, Esc closes. New `zbc_review.script`, drawn with a plain procedural fill shader (`hud\zbc_fill`, no new texture).
- **Auto-exposure** (MCM, on): exposure follows the light where you stand with a small sensor's lag and a slight overshoot, so stepping from a dark room into daylight blows out for a moment and settles.
- **Face blur placed a frame ahead** from each face's own on-screen motion, so the mosaic no longer trails fast turns (capped so jumps are never overshot).
- **Companions off screen**: a dot at the screen edge pointing toward them (MCM, on).
- **Marker options**: random decode order, names only once you have talked to someone (UNKNOWN until then, saved with the game), and a scope lens size slider for unusual scopes (0 = measured).
- Test: `tools/tests/zbc_round3_test.lua`.
- **Mutants get boxes too** (MCM **Ally markers > Mark mutants**, on by default). The label shows the species (BLOODSUCKER, SNORK, PSEUDODOG...) with MUTANT under it, in English or Russian; four-legged mutants get a wide, low box. They identify by distance like stalkers and decode to the enemy colour (or friendly, for the rare tame one). Faces of mutants are not pixelated.
- **Full Russian localization.** Every menu string, the optional Body Camera item (name, description, battery message, its MCM page) and all MCM list options (logo, time zone, text size, marker style, colours) have Russian text in `configs\text\rus`.
  - The overlay font now has Russian letters, so Russian names and factions show in the top-right overlay and above the markers, with the lens on or off. KlartextMono has no Cyrillic, so those letters come from Roboto Mono Bold (Apache-2.0), matched to KlartextMono's capital height and letter width. `tools/make_overlay_assets.py` takes it as a fourth argument and also writes the shader copy of the letters (`zbc_osd_atlas_cyr.script`).
  - Names are put in capitals correctly for Russian text too.
  - Test: `tools/tests/zbc_localization_test.lua`.
- **Every stalker gets a box, enemies included** (MCM **Ally markers > Mark enemies**, on by default). The box is white while the stalker is unknown and, once the name has decoded, fades to green for friendly (neutrals count as friendly) or red for enemy (MCM colours: friendly, enemy, companion; the old neutral colour option is gone). Dots far away show the final colour straight away.
  - Test: `tools/tests/zbc_allies_label_test.lua`.

### Changed
- **Front-of-face blur filter (`zbc_faces.script`)**:
  - Face pixelation now checks whether each stalker's face is actually oriented toward the camera (`face_visible_to_cam` with `FACING_COS = 0.15`), so the back of a head and back-3/4 views are left unblurred.
  - Resolves true 3D face orientation and centers the mosaic on the face plane using `eye_left`, `eye_right`, and `jaw_1` bones (working for both alive head-turning stalkers and ragdolled corpses), with `head_orientation()` / `direction()` fallback for alive NPCs without eye bones.
- **Aim-gated marker labels (`zbc_allies.script`)**:
  - Non-companion stalkers and mutants keep their bounding box visible whenever on screen and in line of sight, but their name, faction, and info/distance label text is shown only while looking at them (`aimed` or `is_target`) and hidden when looking away (preserving identification progress and `known` state).
  - Companions (`npcx_is_companion`) show both their bounding box and label text at all times from frame 1 while on screen and in line of sight.
- **Ally marker scope, decode & dot behaviour (`zbc_allies.script`)**:
  - Gated head-tracking and spine fallback strictly on being scoped in (`pip_active()` or `view_zoom() > 1.05`), so unscoped close-up/clipped targets stay on `project_full_box()` and smoothly morph back from `head_t` when unscoping.
  - Aligned faction label decoding with the name line (`total_t` in `decode_text()`, `FACTION_DELAY` removed) so both start and finish decoding together regardless of string length.
  - Kept distant dot markers white until the target is identified/decoded, and hid dot markers while scoped in.
- **Script & shader bus optimization pass**:
  - `zbc_faces.script` & `zbc_bodycam.script`: packed padded union face AABB `(min_u, min_v, max_u, max_v)` into `bus_zbc_faces.yzw` for shader early-out, distance-culled face candidates by FOV before bone/projection lookups, staggered initial 10 Hz `ray_pick` checks, and avoided redundant `zbc_faces.reset()` calls while face blur is disabled.
  - `zbc_allies.script`: cached label font metrics per screen resolution instead of allocating a closure per frame, cached per-entity `box_aspect` and quadruped status, reused a module buffer in `decode_text()`, relaxed the vertical height floor (`0.15 m` vs `0.5 m`) for small four-legged mutants, and staggered initial `next_los` checks.
  - `zbc_item.script`: cached MCM, `item_device`, and `game_difficulties` settings on load/`on_option_change` instead of reading them every frame, and skipped `zbc_item_anim.update()` when the mod is disabled.
  - `zbc_fx.script`: cached `underground()` once per frame.

### Fixed
- **Permanent mod lockout after first death (`zbc_bodycam.script`)**: hoisted `dead` and `fx_last` locals above `actor_on_first_update()` and reset them in `actor_on_net_destroy()`, plus added live-actor recovery in `actor_on_update()` when another mod cancels death or revives the actor.
- **Cancelled death signal loss (`zbc_fx.script`)**: respected `flags.ret_value == false` in `actor_on_before_death` and cleared `F.death_t` when the actor is alive.
- **Shader Bus `<= 6` compatibility (`zbc_bodycam.script`)**: gated registration of the three Bus-7 `uint4` lanes (`osd_chars`, `osd_atlas`, `face_rows`) on `supports_uint_bus()` (`version() >= 7`) so older Shader Bus engines keep the lens and 2D HUD fallback cleanly, and added the `version() >= 7` guard to `upload_osd_chars()`.
- **Bodycam item animation safety & detector holster wait (`zbc_item_anim.script`)**: made `reset()` perform safe hand/FOV/lock cleanup only without touching stale `prev_slot` or `det` userdata on save load/level change, re-fetched `det` by ID with `parent():id() == AC_ID` in `finish()`, and waited for `actor:active_detector() == nil` alongside `active_item() == nil` before playing motions.
- **Bodycam item battery warning, drain & ownership (`zbc_item.script`)**: silently seeded `warned_low` on load and camera swaps (preventing false low-battery alerts on save load), gated drain on `has_power()` rather than `cam_charged` during battery-insert animations, and verified `parent:id() == AC_ID` in `battery_level()`.
- **Stale identification cache across loads (`zbc_allies.script`)**: cleared `known` and `id_progress` on save load / level exit while keeping them intact when opening inventory/PDA.
- **Documentation & repo hygiene**: updated `README.md` (enemy/mutant markers, face blur, camera effects, Russian localization, Bodycam exes + Bodycam GAMMA Patch note, script list, 4-arg `make_overlay_assets.py` command) and marked `*.mp4` and `*.webp` as `binary` in `.gitattributes`.
- **Marker visibility, label clamping, inventory state & FX decay (`zbc_allies.script`, `zbc_fx.script`, `zbc_bodycam.script`)**: decoupled `allies_mutants` from `allies_enemies` and `allies_color_enemy = 7` (with red fallback), clamped marker label positions inside `[0..1024, 0..768]`, preserved tracked marker `states` across `visible == false` (inventory/PDA), and kept `wet`/`ir`/`glitch` decay ticking while unpowered.
- **Follow-up edge cases (`zbc_item.script`, `zbc_allies.script`, `postprocess.ps`, `postprocess_cm.ps`)**: cleared `last_t`, `last_charge`, and `next_scan` when `zone_bodycam/enabled` is toggled off (preventing drain spikes or delayed battery-insert animations on re-enable without `main_menu_on_quit`), added safe fallbacks for nil/friendly mutant relations when `allies_color_friend = 7`, and snapped glitch RGB-split offsets through `zbc_face_snap()` so blurred faces do not leak un-pixelated red/blue channels during heavy interference.
- **Partial-body / close-up head-tracking markers (`zbc_allies.script`)**: switched markers smoothly to head-tracking (with hysteresis and `head_t` morphing, plus a `bip01_spine` mid-body fallback and point-blank size cap) whenever feet fail to project, lower body clips off-screen, or a target fills the frame up close or through a scope; updated `aimed_at()` to check `bip01_head`, added `project_dot()` position fallback, and sorted draw ties by distance.
- **Full QA bug-fix pass (`zbc_bodycam.script`, `zbc_faces.script`, `zbc_fx.script`, `zbc_item_anim.script`)**: hid the shader battery gauge in pause/MCM (`main_menu_on_init()`), prevented MCM changes while dead from resurrecting the HUD/lens (`settings_changed()`), nil-guarded camera/actor vectors in `motion_update()`, widened face-blur screen bounds with `-side` edge fallback and corpse height adjustment in `zbc_faces.script`, nil-guarded `psi_storm_manager.get_psi_storm_manager()` in `zbc_fx.script`, and aborted active bodycam hand animations + camera effectors immediately if the actor dies mid-animation.
- **Footage review self-close & default keybind (`zbc_review.script`, `zbc_bodycam.script`)**: debounced the review key on open (`150 ms`) so X-Ray's same-keypress `OnKeyboard` dispatch no longer closes the dialog on the frame it opens, registered/unregistered `ZbcReview` with `Register_UI`/`Unregister_UI` (and `SetAutoDelete(true)`), guarded `on_key_press` against menus/other UIs, and changed the default keybind from `Insert` (`210`) to `Delete` (`211`).
- **3DSS PiP dual-view markers & face blur + scoped dot suppression (`zbc_allies.script`, `zbc_faces.script`)**: kept normal 1x main-camera full-body boxes and 1x face pixelation for people visible outside the circular 3DSS PiP scope lens while preserving magnified in-lens boxes/face blur inside the lens (with mode-aware frame-ahead prediction and smooth outside-lens fade-out), and suppressed all dot markers (distant, morphing, dead, and companion edge dots) while scoped in.
- **Label fade, quick reappear decode & uniform font size (`zbc_allies.script`)**: added smooth fade-in/fade-out (`label_vis`) when marker labels appear/hide, triggered a quick `0.30 s` re-decode sweep when remembered names/factions pop back in, and matched the name font size to the faction and info lines (`0.62 vw`).
- **Face-sized blur square (`zbc_faces.script`)**: tightened `HEAD_HALF` from `0.17 m` (34 cm) to `0.105 m` (~21 cm) and centered the mosaic between eyes and jaw (`0.65 * eye_mid + 0.35 * jaw_1`) so the blur tightly matches the face without spilling onto helmets or shoulders.

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
- The default device name in the overlay is now **AXON BODY 4**, matching the Body Camera item. A name you set yourself in MCM is kept.
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
