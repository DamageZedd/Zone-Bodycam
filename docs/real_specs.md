# Real Axon Body 1-5 specs

The camera generations (optional bodycam item) follow these published specs one to one. Researched Nov 2026; Body 5 was announced 24 Oct 2026 and is not on general sale, so most of its specs are unpublished.

## Sources
- [S1] Axon Body 2 spec sheet, Axon, Rev 10.0, 1 Oct 2018: https://axon-2.cdn.prismic.io/axon-2/93a03ad8-7a59-4afc-807d-76b2daa92017_Spec+Sheet+-+Axon+Body+2+-+ENG+-+UK.PDF
- [S2] TASER Axon Body product page + comparison table (officer.com, 5 Aug 2013): https://www.officer.com/on-the-street/body-cameras/product/11078012/axon-axon-body-camera
- [S3] Axon Body 2 product page + table (officer.com, 9 Dec 2015): https://www.officer.com/on-the-street/body-cameras/product/12147960/axon-axon-body-2
- [S4] Axon Body 3 product card, Axon (c) 2022, via Radiocoms: https://www.radiocoms.co.uk/wp-content/uploads/2026/03/Axon-Body-3-Product-Card-Radiocoms.pdf
- [S5] Axon Body 3 product card, Axon (c) 2019: https://axon-static-site.s3.us-west-1.amazonaws.com/images/axon-2/e33f4af8-36ec-41e0-b391-4f276ca0cfcd_ab3-product-card_logistics.pdf
- [S6] Axon Body 3 announcement (officer.com, 8 Oct 2018): https://www.officer.com/on-the-street/body-cameras/product/21026239/axon-axon-body-3-body-worn-camera
- [S7] Axon Body 4 product card, Axon (c) 2023: https://a.storyblok.com/f/198504/x/97ef6d53db/100_en-intl_axon_productcards_ab4.pdf
- [S8] Axon Body 4 product page: https://www.axon.com/products/axon-body-4
- [S9] Axon Body 4 launch release, 11 Apr 2023: https://prnewswire.com/news-releases/axon-launches-next-generation-body-camera-with-more-features-to-never-miss-a-moment-301795014.html
- [S10] Axon Body 5 press release, 24 Oct 2026: https://www.axon.com/newsroom/press-releases/axon-announces-body-5
- [S11] Axon Body 5 / 5 Pro product page: https://www.axon.com/products/axon-body-5-pro
- [S12] Axon Body 4 user guide (buffer default 30 s), my.axon.com, via search snippet only
- [S13] Axon Body 3 user guide: https://cdn.mediavalet.com/usva/axon/zqyi9vVldUGZZdL_VHFKtA/cdBX6hSjp06Ox-grwro7Uw/Original/Axon%20Body%203%20User%20Guide%20EN_US.pdf (buffer 0-120 s, default 30 s, no buffer audio by default; watermark = date, time, serial, upper-right; no FOV figure)

## Real specs ((i) = inferred, not sourced)
| | Body 1 | Body 2 | Body 3 | Body 4 | Body 5 |
|---|---|---|---|---|---|
| Year | 2013 [S2] | 2015 ann. [S3] | 2018 ann., ship 2019 [S6] | 2023 [S9] | ann. 24 Oct 2026, not GA [S10] |
| Resolution | 480p [S2] | 1080/720/480, <=30 fps [S1] | 1080/720H/720L/480 [S4] | 1440/1080/720/480, 5 MP [S7] | up to 4K [S11] |
| Bitrate | ~1.5 Mbps (i: 8 GB / 12 h [S2]) | 1080p 12 Mbps, 720p 6, 480p 1.8-4 (from GB/h [S1]), H.264 | as Body 2 (i) | not published | not published |
| FOV | 130 deg [S2] | 143 diag / 118.6 h / 63 v [S1] | not published (i: ~143) | 160 deg, 4:3 [S7]; 120 deg option [S8] | not published (i: 160, same accessories [S11]) |
| Low light | "retina" low light, no figure [S2] | <0.1 lux, CMOS [S1] | "improved low-light", "reduced motion blur" [S4] | 5 MP sensor, no lux [S7] | "better low-light" [S10] |
| IR | none | none | none | none | none (no Axon Body has IR) |
| Stabilization | not stated | not stated | not stated | not stated | not stated |
| Audio | not stated | stereo 2-ch [S1] | multi-mic + wind noise reduction [S4] | not stated (bi-dir talk [S7]) | upgraded audio [S10] |
| Pre-event buffer | 30 s [S2], audio not listed | 0-120 s [S1], audio configurable [S3] | up to 120 s, audio configurable [S4]; Video Recall 18 h [S4] | up to 120 s [S7], default 30 s [S12] | not stated |
| Battery | 12+ h [S2] | >12 h, 3000 mAh [S1] | 12 h [S4] | 14 h [S7] (13+ [S9]), 4300 mAh | +20% vs Body 4 [S10] (i: ~16.8 h) |
| GPS | phone app (Axon Mobile) [S2] | GPS tagging via phone over Bluetooth [S1] | onboard GPS + Wi-Fi positioning, live maps [S4] | improved GPS, live maps [S8][S9] | more precise; Pro dual-band [S11] |
| LTE / live | Bluetooth live view to phone [S2] | Wi-Fi streaming via phone app [S1] | LTE, livestream to Respond, alerts (weapon drawn) [S4], gunshot alerts [S6] | Respond live map, alerts, Watch Me, two-way talk [S7] | 5G + Wi-Fi 7, Guardian escalation alerts, live translation, 25x AI [S10][S11] |
| Signal activation | no [S2] | yes [S1] | yes [S4] | yes [S8] | (i) yes |
| Display / LEDs / haptics | not stated | battery LED, op LED, vibration [S1] | top display, auto-brightness front LED [S4] | prompts/reminders [S7] | not stated |
| IP / drop | IPX2 or IP55 (conflict) [S2], 6 ft | IP67, 6 ft [S1] | IP67, 6 ft [S4] | IP67 [S7] (IP68 on [S8]), 6 ft | not stated |
| Watermark | not stated | date + time embedded [S1] | (i) same | (i) same | (i) same |


## How the mod uses them (zbc_tiers.script)
Multipliers on the MCM values; Body 4's picture is the identity. Zoom is the exception: it multiplies the final lens zoom (after the distortion fill), so the field-of-view ratio holds exactly. (i) = estimated.

| In-game | Real basis | B1 | B2 | B3 | B4 | B5 |
|---|---|---|---|---|---|---|
| sharpen x | lines vs 1440: 480 / 1080 / 1080 / 1440 / 2160 | 0.33 | 0.75 | 0.75 | 1 | 1.5 |
| edge_soft_blur x | inverse of the above, kept in range | 2.2 | 1.3 | 1.3 | 1 | 0.7 |
| compression x | bits per pixel: B1 ~0.12 vs B2 ~0.22 [S1][S2] | 2.4 | 1.4 | 1.3 (i) | 1 | 0.7 (i) |
| zoom x | FOV 160 deg / 130, 143, 143 (i), 160, 160 (i) | 1.23 | 1.12 | 1.12 | 1 | 1 |
| dark_grain | B1 and B2 same low-light claim; B3 improved; B5 better | 0.35 | 0.35 | 0.15 (i) | 0 | -0.2 (i) |
| rolling_shutter x | B3 "reduced motion blur" [S4] | 1.6 (i) | 1.35 (i) | 1.1 | 1 | 0.85 (i) |
| grain, aberration, highlight_blowout x | unpublished, sensor-generation estimate | (i) | (i) | (i) | 1 | (i) |
| walk_bob, impacts, fx_glitch_strength | no generation publishes stabilization or shielding | 1 | 1 | 1 | 1 | 1 |
| battery drain_mult (zbc_item) | 14 h / real hours: 12, 12, 12, 14, 16.8 (i) | 1.167 | 1.167 | 1.167 | 1 | 0.833 |
| wearer's name line | game feature (the real watermark is date, time, serial [S1][S13]) | off | on | on | on | on |
| GPS line | onboard GPS from B3 [S4]; B1-B2 tagged GPS through a phone | off | off | on | on | on |
| IR night look | no Axon Body has IR | MCM | MCM | MCM | MCM | MCM |
| auto-exposure, footage review, face blur | every generation (face blur = MCM choice; real redaction is in Evidence.com) | on | on | on | on | on |
| markers, companion dots, alerts log | LTE live map and alerts from B3 [S4][S6] | off | off | on | on | on |
| marker range cap | LTE: none | - | - | none | none | none |
| enemies / mutants identified | AI identification (interpretation) | - | - | enemies | both | both |
| scope tags (allies_pip) | Watch Me / two-way video, B4 [S7] | off | off | off | on | on |
| identification speed | B5 25x AI compute (interpretation) | - | - | 0.75 | 1 | 1.5 |

No in-game equivalent: frame rate, the 4:3 aspect, Body 4's 120-deg option, pre-event buffer length and audio, Video Recall, microphones and wind-noise reduction, Signal activation, display / LEDs / haptics, IP and drop ratings, storage, encryption, fast charging, Flex POV, license scanning, translation, 5G.
