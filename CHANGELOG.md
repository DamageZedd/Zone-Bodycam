# Changelog

## Unreleased

### Changed
- **Camera generations follow the real Axon Body specs one to one** (`zbc_tiers.script`, `zbc_item.script`; sources in `docs/real_specs.md`): sharpness from the real resolution (480p / 1080p / 1080p / 1440p / 4K), lens zoom from the real field of view (130 / 143 / 143 / 160 / 160 deg), compression from the real bitrates (Body 1 at about half Body 2's bits per pixel), night noise (Body 1 and 2 the same), less motion blur from Body 3, battery life 12 / 12 / 12 / 14 h and +20% for Body 5. Live-map markers, off-screen companion dots and the alerts log need LTE (Body 3 on), with no range cap; scope tags need Watch Me (Body 4 on). Auto-exposure, footage review and face blur are on every camera. Walking shake and interference no longer differ by camera (no generation publishes a difference). Like the real watermark (date, time and serial), no camera draws the GPS line or the wearer's name. Test: `tools/tests/zbc_tiers_test.lua`.
- **IR night look is an MCM option on every camera, off by default** (no Axon Body has infrared; was auto, and missing on Body 1 and 2).

### Added
- **HD inventory icons** (FOMOD step "Bodycam item icons", option "HD icons"): for HD Inventory Icons Framework (GAMMA), 100x100 icons of the five Axon Body cameras from their original 800 px renders, drawn in a single 1x1 slot (`inv_grid_scale = 2`, DLTX patch in `optional/bodycam_item_hd_icons`). Without the framework the cameras take 2x2 cells. Test: `tools/tests/zbc_item_icons_test.lua`.
- **Charge bar on the bodycam items' icons**: the five Axon Body cameras show the small blue battery bar like the torch, detectors and PDA (`use_condition` + `condition_bar = power_progess_bar` in `items_zbc_bodycam.ltx`; works with the 1x1 and HD icons). Test: `tools/tests/zbc_item_battery_bar_test.lua`.

### Fixed
- **Compression built up and then vanished in a snap, most visibly while turning** (`zbc_lens.h`, `zbc_fx.script`, `zbc_bodycam.script`): the shadow blocking restarted on every keyframe (every 1.6 s) and the turning boost dropped off in a third of a second. Compression now holds a steady amount set by the camera (Body 1 the most, Body 5 the least; without the item, the MCM value), builds up over about a quarter second while the camera turns, and eases back to that amount over about a second.
- **The battery-insert animation only played on Axon Body 5** (`zbc_item.script`, bodycam item component): a new battery was spotted only as a charge jump on the active camera. With several dead cameras carried the active one is the highest generation, so a battery put into any other camera made that camera the active one and the jump was never seen. Every carried camera's charge is now remembered, so a battery in any of them plays the insert with that camera's own animation. Test: `tools/tests/zbc_item_test.lua` (each camera alone, and all five carried with a battery into each in turn).
- **The bodycam items could stop draining** (`zbc_item.script`): the engine stores the charge as a float32, and with a long battery life, an easy difficulty and a high frame rate one frame of drain was smaller than half a float step near full charge, so it rounded back and the camera never used its battery. The exact charge is now kept in the script and only rounded when written; a battery put in is still picked up. Test: `tools/tests/zbc_item_battery_bar_test.lua`.

### Changed
- **The bodycam items take one inventory cell** instead of 2x2, with 50x50 icons cut from the same art (`items_zbc_bodycam.ltx`, `make_item_textures.py --atlas-1x1`).
- **The bodycam item component is on by default** in the FOMOD installer (untick it to keep the bodycam always on).

## v1.4.0 - 2026-11-25

### Fixed
- **Overlay error while loading or changing level** (`zbc_bodycam.script`): the overlay window was added to the game HUD without checking it was up, so a load or level change could throw `attempt to index a nil value` and the overlay never came back. Nothing is created until the HUD is there, and it is retried every update. Test: `tools/tests/zbc_hud_guard_test.lua`.
- **"cannot access class member Alive!" log spam** (`zbc_allies.script`): the ally markers called `alive()` on whatever the camera pointed at, so barrels, crates, artefacts and stashes logged an error every frame. The aimed-at object is now checked to be a stalker or mutant first. Test: `tools/tests/zbc_allies_aim_target_test.lua`.
- **No death screen at all without the Shader Bus** (`zbc_bodycam.script`, `zbc_fx.script`): with signal lost on, Death Like Romeo's death handler is taken over, but on exes without the Shader Bus signal lost cannot play and returned silently, so neither screen showed. `signal_lost` now says whether it played, and Romeo's screen plays when it did not. Test: `tools/tests/zbc_death_screen_nobus_test.lua`.
- **Identified people were forgotten on every load and level change** (`zbc_bodycam.script`): its first update cleared `zbc_allies`' identifications right after `load_state` had restored them from the save. `zbc_allies` already clears them itself for a game started without the saved data. Test: `tools/tests/zbc_saved_ids_test.lua`.
- **The left wrist stayed bent after pushing the battery in** (all cameras, `hud_anim2.py`): after the push it now straightens into line with the forearm over about 0.4 s instead of keeping the pushing angle until the hand leaves the screen.
- **Signal lost never played with a death screen mod that stops time** (`zbc_bodycam.script`, `zbc_lens.h`): Death Like Romeo (CLIKRΔD Romeo) sets `time_factor 0` the moment you die, which also stops the shader's game clock, so the break-up stayed at 0 s and only Romeo's death screen showed. The seconds since death now also run on the real clock (`time_continual`), sent in the `zbc_glitch` lane's w by a small HUD window that keeps updating while time is stopped; the shader uses whichever age is larger, and its animation clock keeps going after death. Test: `tools/tests/zbc_signal_lost_clock_test.lua`.
- **Interference, grain and compression noise froze after ~15 minutes of play** (`zbc_lens.h`, `zbc_osd.h`, `zbc_ring.ps`): the noise was seeded from the game clock, which in 32-bit floats stops changing in the hash once the game has run a while, so tearing showed the same bands every frame and the grain slid one fixed pattern across the screen. All animated effects now run on a wrapped clock and a hash that keeps its precision, with fresh noise every frame.
- **Markers through a variable-zoom scope were wrong at its highest zoom** (`zbc_allies.script`, also the face blur): a zoom factor of 8 or less was read as a plain power, so the 24x top of a 3-24x scope was placed as 4x. Every zoom step now uses 100 / zoom factor, as the Bodycam exes render it.

### Changed
- **The lens wipe plays the visor-wipe hand animation** (`zbc_fx.script`): the mask-wipe key (Zoom in, T by default) now plays the game's mask-wipe animation for the camera lens too, with or without a mask, and the drops are wiped in step with the hand. When the animation cannot start, the drops are simply cleared as before.
- **Signal lost is the only death screen while it is on** (`zbc_fx.script`): another death screen mod's death handler is taken off `actor_on_before_death` on load, so Death Like Romeo's black screen, time stop, mute, logo and quote no longer cover the camera's own death. Romeo's files are not touched; its handler is only called by us when signal lost does not play (camera off or out of power, or a death another mod cancels, such as a Soulslike respawn), and it is given back when signal lost is switched off. Test: `tools/tests/zbc_death_screen_test.lua`.
- **Every camera effect moves** instead of sitting still:
  - **Interference** swells and fades around its level from the source, gets short random spikes (more often and stronger the more interference there is), tracking bands roll through the picture, a hum wobble scrolls up it and the colour split jitters. An **emission or psy storm builds up** over its first 40 s instead of switching straight to one flat level.
  - **Hard hits** jolt the picture 2-4 times, each weaker, instead of one smooth fade.
  - **Signal lost**: the picture stutters, collapses to a bright line and a dot, and goes black over faint snow that dies down with a noise line still rolling; SIGNAL LOST tears in, then flickers with a short glitch now and then. Timed by the shader, so it plays out even after the scripts stop.
  - **Night mode (IR)**: the gain hunts a little and a faint hum bar drifts up the picture; it has its own per-frame noise when the lens grain is off.
  - **Blood on the lens** hits as an irregular splash with side lobes and droplets flung outward (no more star shapes), and its drips run like viscous blood on glass, out of the middle of the splat: the head, a teardrop bulb, stays pinned while blood gathers in it, then slips down to the next stop (faster for heavier drips, and faster while the camera swings); the thin, even rivulet behind it stays where it was laid. A splat's size decides how it drips: small ones don't, mid-sized ones run a short way and stop, large ones run all the way off the bottom of the lens. The splats drain a little as their drips run; the blood still dries and fades as before. **Blood now stacks**: every hit in front of the camera adds a new splatter instead of restarting the old one, and each stays until it has faded (up to 4 at once; with 4 up the oldest gives way). Each splatter is worked out once per pixel instead of twice, so the post shader is smaller than in v1.3.0. Needs the new `zbc_blood` Shader Bus lane. The blood is also softer, out of focus this close to the lens, with a faint red glow against bright light.
  - **Compression** blocks up a little while the camera swings, like a real bodycam encoder.
  - **EVENT** after REC flashes three times, then blinks (also on the HUD-drawn timer).
- Tests: storm build-up, swells, spike and hit-jolt timing, drip speed, camera swing, EVENT blink, and a check that no shader seeds noise from the raw game clock (`tools/tests/zbc_dynamic_fx_test.lua`).

### Added
- **Camera generations: Axon Body 1 is the worst camera, Axon Body 5 the best** (`zbc_tiers.script`, hooked into `zbc_bodycam.script` through `set_tier_source`; bodycam item component only). The carried camera decides what the feed can do, and the look changes the moment you carry a different one:
  - **Features** need the MCM switch AND a camera that has them. Body 1: date and device line only; no auto-exposure, IR night mode, identification, GPS, event log, face blur or footage review (the review key says so). Body 2: adds the name line, auto-exposure, and identification of friendly stalkers within 15 m at half speed. Body 3: adds GPS, the event log, IR night mode, footage review, enemies within 25 m at 3/4 speed and companion markers at the screen edge. Body 4: everything, as before. Body 5: everything, identification 1.5x faster.
  - **Picture quality** = MCM slider x the camera's multiplier, clamped to the MCM range (a slider at 0 stays off): grain, compression, sharpening, edge softness, colour fringing, rolling shutter, highlight blowout, walk bob and impacts, and interference (Body 1 up to 1.5x the MCM strength). Old cameras also get grainier in the dark (+60% on Body 1), Body 5 cleaner (-20%). Lens geometry (distortion, zoom, housing, vignette) stays the MCM's.
  - **Axon Body 4 is the reference** and changes nothing, so without the item the core mod is exactly as before. MCM: **Camera generations** (bodycam item page) off makes every camera work like Body 4; only the battery life differs.
- **How you get the cameras** (bodycam item component):
  - **Axon Body 1**: 5,000 at every trader (always in stock from the first supply level), and every faction starts a new game with one (`mod_new_game_loadouts_zbc_bodycam.ltx`). It can also be crafted with a basic toolkit and no recipe book.
  - **Axon Body 2-5 are craft-only**, removed from all 21 trader lists. They are crafted in the workshop's Devices tab like GAMMA's night vision goggles, each from the generation before, behind the same electronics recipe books (`mod_craft_zbc_bodycam.ltx`): Body 2 basic toolkit + basic electronics recipes; Body 3 and 4 advanced toolkit + advanced recipes; Body 5 expert toolkit + expert recipes. Parts: resistors, capacitors, copper, transistors, textolite, dead batteries.
  - Prices follow the generation: 5,000 / 8,000 / 12,000 / 16,000 / 24,000.
- **Every camera has its own battery animations** (bodycam item component): the battery-dead and new-battery hand animations were fitted to each Axon Body's shell instead of all using Body 4's. Both grips are re-fitted by contact on each camera (palm seated, fingers closed on it, thumb on the matching spot), the battery seats in each camera's bottom the way it does on Body 4, and the left hand lets go of the battery a little further out on the smaller cameras (or pushes on the camera's bottom on Body 3 and 5) so no finger goes into the camera. Checked on every frame you can see: nothing clips on any camera. New hand motions `zbc_bodycam_<N>_dead` / `_insert` in `zbc_bodycam_<N>_hud_animation.omf` for Body 1, 2, 3 and 5; each camera's in-hand model has its own battery motions. Tools: `tools/bodycam_item/hud/per_shell.py` (fit, clipping report, key-pose sheets, grip close-ups, videos) and `export_shell.py` (game files, each checked by re-import). Test: `tools/tests/zbc_item_test.lua` checks every camera's motions and their stop-at-end flag.
- Tests: tier profiles and how they meet the MCM (identity on Body 4 and without the item, every generation at least as good as the last), which tier each camera is, the trade, recipe and new-game configs, and the new text (`tools/tests/zbc_tiers_test.lua`); interference strength cap and darkness level (`zbc_fx_test.lua`).
- **Full 5-generation Axon Body camera item & 3D model suite (`optional/bodycam_item`)**: expanded the optional physical bodycam item component into all five real-world Axon Body generations while keeping `[zbc_bodycam_item]` (`Axon Body 4`) 100% save-compatible:
  - **Axon Body (Gen 1, `#73002`)** (`[zbc_bodycam_1]`): `0.20 kg`, `5000 RU`, Tier 1, `~3.0 h` battery endurance (`drain_mult = 1.333`), `AXON BODY` OSD watermark.
  - **Axon Body 2 (`#74001`)** (`[zbc_bodycam_2]`): `0.24 kg`, `8000 RU`, Tier 2, `~3.5 h` battery endurance (`drain_mult = 1.143`), `AXON BODY 2` OSD watermark.
  - **Axon Body 3** (`[zbc_bodycam_3]`): `0.30 kg`, `12000 RU`, Tier 3, `~3.8 h` battery endurance (`drain_mult = 1.053`), `AXON BODY 3` OSD watermark.
  - **Axon Body 4** (`[zbc_bodycam_item]`): `0.32 kg`, `16000 RU`, Tier 4, `4.0 h` baseline battery endurance (`drain_mult = 1.000`), `AXON BODY 4` OSD watermark.
  - **Axon Body 5 Pro** (`[zbc_bodycam_5]`): `0.33 kg`, `24000 RU`, Tier 5, `4.8 h` (+20%) battery endurance (`drain_mult = 0.833`), `AXON BODY 5` OSD watermark.
  - **Bespoke 1:1 3D world & first-person HUD models**: procedural Blender builders (`tools/bodycam_item/build_model_{1,2,3,5}.py` alongside `build_model.py`), world physics meshes (`zbc_bodycam_{1,2,3,5}.ogf`), in-hand animated battery-swap HUD meshes (`zbc_bodycam_{1,2,3,5}_hud.ogf` bound to `[zbc_bodycam_{1,2,3,5}_anim_hud]`), uncompressed mipmapped BGRA material textures, and a `512×128` RGBA 5-camera inventory icon atlas (`ui_icon_zbc_bodycam.dds`, built via `make_item_textures.py --atlas`).
  - **Smart multi-camera selection, endurance & dynamic OSD watermark (`zbc_item.script`, `zbc_item_anim.script`, `zbc_bodycam.script`)**: automatically runs the fullest carried camera with generation tie-breaking (`best_index(charges, gens)`) and `0.2%` active-camera hysteresis (`STICKY_EPS`) to prevent 1 Hz ping-ponging between two full cameras, routes `"dead"` and `"insert"` hand animations to the matching camera's HUD section, and dynamically updates the default top-right OSD device watermark (`set_device_source` / `effective_device_label()`) while still honoring custom MCM device labels.
  - **English and Russian** names and descriptions for all five cameras (Russian in `windows-1251`).

## v1.3.0 - 2026-11-22

### Changed
- **Rain on the lens is now the game's own visor drops** (`zbc_fx.script`): our procedural lens drops are removed. While the camera records with **Rain on the lens** on, the game's visor rain (Dynamic Visor Drops in GAMMA, or the base game's) is shown on the camera with or without a mask, and even with the game's rain droplets option off; it is still that mod that decides when rain builds up, slides and dries. With a mask on it is the same single effect, so nothing doubles up.
  - The game draws visor drops only inside the mask glass pass, so without a mask (or with Mask HUD off) the intact visor glass is switched on for them; it can add a faint glass edge and some speckle in the screen corners. The bodycam overlay, markers and labels stay on top of the drops.
  - Needs **Dynamic Smoother Droplets** disabled: it replaces the visor drops' update with one whose values Dynamic Visor Drops' shader cannot read.
  - Glossy dripping blood from v1.2.0 is unchanged.
- **Interference toned down in psy fields** (`zbc_fx.script`): a steady psy field (such as around the Yantar lab) now only flickers the picture; it breaks up heavily only once psy health is nearly gone. Before, it rose straight with psy damage to about 90%, so the picture was torn apart the whole time you stood in the field. Emissions, psy storms, radiation and anomalies are unchanged.

### Added
- **Wipe the drops with the mask-wipe key** (Zoom in, T by default): with a mask on the game's animated wipe runs as before; without one (or with Mask HUD off) the visor drops' own wipe clears them.
- **Interference strength** slider (MCM, under Interference, default full): scales all camera interference, hit bursts included; 0 turns it off while keeping signal lost on death.
- **Every effect can be switched off in the MCM**: new switches for **Rain on the lens**, the **Lens housing edge** (the picture fills the screen; the vignette keeps its own slider) and the **Battery gauge**. **Lens dirt** is now **Blood on the lens** (blood only; your saved setting carries over). Everything else already had a switch, an Off choice or a slider down to 0.
- Tests: driving the visor drops (forced only during their update and always restored), the wipe key, and every setting being in the MCM with English and Russian labels (`tools/tests/zbc_fx_test.lua`).

## v1.2.0 - 2026-11-22

### Hotfix
- **Upgraded lens raindrops & blood splatter (`zbc_lens.h`)**: replaced static dark-rimmed rain circles and flat red blood circles with multi-layer stick-slip sliding raindrop streams (tapered liquid trails, wake micro-beads, stationary 2×2 micro-beads, analytic surface-gradient refraction, and glass meniscus glint) and glossy, refractive, gravity-dripping blood splatter with Beer-Lambert crimson absorption, wet specular highlights, and gradual drying.

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
- **Face-sized blur square & front-facing fix (`zbc_faces.script`)**: tightened `HEAD_HALF` to `0.105 m` (~21 cm), widened `FACING_COS` to `-0.25` (~104°, covering front and side profiles while skipping the back of the head), used `obj:head_orientation()` / `direction()` directly for alive stalkers, and used the left-handed triangle normal `(eye_right - eye_left) x (eye_mid - jaw_1)` for corpses.

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
