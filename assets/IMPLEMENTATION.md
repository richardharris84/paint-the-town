# Paint the Town: C++ first-person game asset guide

## What this package is

This folder contains the project's source artwork, source/reference artwork,
music and an engine-neutral export of its nine-venue Doom campaign. Copy this
entire folder into another workspace; Copilot can use [AGENTS.md](AGENTS.md) and
this guide to implement the content in a C++ first-person game.

The export is content, not a C++ game, renderer or replacement Doom engine.
Native engine rules must be implemented or deliberately adapted. No commercial
IWAD, stock face/font artwork, stock monsters, installed executable, save files,
Google map tiles, or third-party reference art is bundled by the exporter.
The images retain the palette-converted appearance of the project WAD.
This guide does not establish a new license or clear third-party rights; check
the project's provenance before redistributing.

## Directory and version contract

| Location | Purpose |
|---|---|
| PNG files directly in this folder | Original working source atlases moved from the workspace root |
| `art_sources` | Original source sheets, cleanup metadata and generated overworld references |
| `music` | Original procedural Ogg loops and MIDI source scores, in their source-map naming order |
| `music/paint_the_town` | Current nine-track original synthesized venue soundtrack |
| `Game` | Portable runtime content; music here is renamed into current campaign order |
| `Game/manifest.json` | Schema version, source WAD hash, published hash and output-file hashes |
| `Game/source_images.json` | Every relocated root PNG, dimensions, alpha mode, usage and hash |
| `Game/scripts.json` | Every Python script, category and top-level function/class inventory |

The candidate and published WAD may differ. The export defaults to the candidate,
including the overhead mallet, tiered NPC markers and latest HUD/venue
revisions. The HUD removes static control hints and supplies project-owned
face expressions, number glyphs and automatically selected static level plans.
`source_is_published` explicitly records whether it matches the main WAD.
Never describe a candidate export as a published release when this is false.

From the original workspace root:

```powershell
py -B scripts\export_game_assets.py
py -B scripts\export_game_assets.py --wad Paint_the_Town.wad --output assets\PublishedGame
py -B -m unittest discover -s scripts -p test_game_assets.py -v
```

Default output is `assets\Game`; paths inside its JSON are relative to that
directory, not the current working directory. Re-exporting does not build or
publish a WAD. Python generation requires the root `requirements.txt`, a legally
installed Doom IWAD for local palette/build operations, and Windows fonts used
by the existing generators. The exported PNG/WAV/JSON files themselves do not
require Python, KEX, an IWAD or those fonts at runtime.

The published export command requires an existing verified Paint the Town
release. During development only the candidate exists. The exporter rejects a
WAD whose embedded music differs from the current source soundtrack rather than
silently combining historical audio with new metadata.

## Suggested C++ implementation order

1. Load and validate JSON, file hashes and all referenced resources.
2. Implement coordinates, camera, fixed-step simulation and sector geometry.
3. Implement player movement/collision and pickups; verify a complete route
   through each level before adding combat.
4. Load transparent billboard sprites and weapon screen-space animation.
5. Implement shared ammunition, weapon attacks, NPC state machines and damage.
6. Add music, spatial sound and stationary paint effects.
7. Implement keyed exits and the nine-level progression, statistics and ending.
8. Add native live radar and input hints using the new game's actual scene and
   input APIs. These are not supplied as working KEX features.

Use the target project's existing engine and JSON/image/audio libraries.
Do not create a second renderer or force a specific C++ framework unnecessarily.

## Level geometry and maps

`Game/levels.json` indexes nine `Levels/E1Mx.json` files and matching north-up PNG
maps. JSON geometry is decoded from the selected WAD, including its validated
spawn placement and node-builder vertex additions, not an approximated preview.

- Horizontal world axes: +X east, +Y north. Height is +Z. One metre is 32 units.
  Angles are degrees counterclockwise from east. For a Y-up engine, explicitly
  map `(x,y,z)` to the engine's horizontal/vertical axes and adjust winding.
- `vertices`: `[x,y]` integer coordinates.
- `sectors`: floor/ceiling heights and material IDs, light (0–255), special, tag.
- `sides`: sector index, upper/lower/middle material IDs, texture offsets.
- `lines`: endpoint indices, flags, special, tag, front/back sidedef indices.
  A `back` of -1 means no back side, not a valid vector index.
- `things`: position, facing angle, type ID, skill/behavior flags.
- `F_SKY1` means render the level's `sky`; `-` means no texture.
- Blocking flag 1 and two-sided flag 4 are bitmasks, not exclusive enum values.
  Thing flags 1/2/4 select skill groups; flag 8 is ambush behavior.

Reconstruct closed sector boundaries, holes and disjoint loops before
triangulating floors/ceilings. Generate upper/lower walls at neighboring sector
height differences, respecting front/back orientation and sidedef offsets.
Raised cover is actual geometry: it must block movement, sight and hitscans.
Do not render every linedef as a full-height solid wall.

Use player cylinder/radius clearance for movement. Exits use keyed door geometry
and normal-exit linedefs (special 52). Interpret the actual specials/tags in each
level; the exported `UMAPINFO.txt` retains campaign progression and the special
Islands-to-Zoo handoff. Do not permit a level transition merely because the
player reaches a preview marker.

PNG maps include red player-start and blue-card markers; they are static
reference images, not radar. `map_transform` supplies the exact world-to-image
formula so live markers can be placed correctly. To build the requested radar
in a C++ engine: center on the player's current world position, rotate geometry
and relative enemy positions by the inverse player heading, clip to the HUD
panel, keep player-forward upward, and update from live actor state. Hide
removed/dead actors according to the game's chosen radar rules. Never use the
campaign-route thumbnail as a level radar.

Campaign order: ROM, Queen's Park, Sankofa Square, Nathan Phillips Square,
Union Station, Scotiabank Arena, Rogers Centre, Toronto Islands, Toronto Zoo.
Geometry is deliberately compressed and landmark-inspired, not a building survey.

### Landmark scenery and static decorations

The first five maps include framed ROM panels and ten artifact displays;
28 Queen's Park tree decorations and a sandstone Legislature; Sankofa's raised
stage, speakers and fictional billboard buildings; a winter civic rink and
one cylindrical City Hall tower; and Union's northern Royal York facade with
southern railway platforms. North/south follows real Union geography.
The revision also updates arena/baseball scenes, the Zoo and Islands shoreline.

The polished scenery uses four original high-quality AI atlases in
`art_sources/polish`, with provenance and checksum-bound normalization metadata.
Run `py -B scripts\prepare_venue_art.py` before rebuilding if those sources change.
Its 38 transparent poses replace the procedural museum objects, foliage,
signposts, sports people and seven wildlife species. Existing paintball
opponent identities, weapon artwork and the supplied portrait are retained.
Materials include detailed masonry, cedar, civic ribs, framed art, ice, paths,
soil, grass and water; tile-edge blending precedes Doom-palette quantization.

Native sprite pixels are world units, not an arbitrary display resolution.
Standing sports people are about 64 units tall, relative to the 56-unit player
body and 41-unit eye height. Their neutral torsos intersect the eye-height
crosshair; animation poses share one scale and bottom-center ground anchor.
Do not stretch a crouching catcher to standing height. Animals retain species
scale: elephant 104, giraffe 176, deer/kangaroo about 64, tiger 48, bison 72
and penguin 24 units tall. Small wildlife naturally lies below a level gaze;
do not enlarge it to human height simply to hit the center of the screen.

`Game/decorations.json` is a separate actor registry, not part of `npcs.json`.
Resolve DoomEd IDs 15200-15240 to their `frames` resources in `sprites.json`.
These families are nonblocking, non-shootable, have no drops,
pickup effects or kill/item counts, and never enter combat AI. Anchor at
`(width/2,height)` on the sector floor; duration -1 means hold frame A forever.
Other durations use a 35 Hz native state clock and explicit next-state IDs.
Do not treat the terminal self-reference as a busy-loop animation.
Visual foliage does not block hitscans; solid sector trunks/cases supply cover.
Preserve skill masks on placements and do not spawn these actors as enemies.

Referee animation and peaceful zoo animals are cosmetic. The baseball scene
is NOT two independent looping actors: its invisible controller owns a 210-tic
cycle. Spawn finite-lived pitcher/catcher actors together; release the outbound
ball at tic 35 and the return at tic 140, each lasting 35 tics. Children expire
at the cycle boundary, without damage, collision, item/kill counts or AI.
Preserve the controller's remaining time, child states and ball position/velocity
on save/load. `decorations.json` records scene roles, anchor offsets and timing;
`DEHACKED.txt` supplies the exact spawn arguments and state graph.
Ball release travels from Z52 at the mound to Z34 at the catcher, then back;
preserve the exported vertical velocity instead of a head-height flat throw.
Rogers starts at (0,-640), facing north (90 degrees): catcher at Y-100, mound
at Y590. The directional pitcher/catcher sources supply eight native views.
Animated scenery also supplies per-frame `rotations`: select the appropriate
front/side/rear artwork from the viewer's bearing relative to the actor's fixed
world angle. Do not rotate the actor toward the player. Native sprite planes
still face the camera; these are directional images, not planar world meshes.
Static A0 foliage remains ordinary billboard art.
The hockey pair faces each other; the referee has long black-and-white vertical
shirt stripes and black pants. Arena mascot sprites use ABWR so they cannot
override the Zoo combat bear's BEAR artwork.

Both sports venues contain elevated seating with eight distinct animated crowd
groups. Preserve their world-facing angles and the seating floor anchor.
The arena has 164 group placements; Rogers has 172. Do not substitute three
repeated fans or reorder the same frames and call them different designs.

The exit control is a ground-mounted rectangular panel, with no post, a gold
outer outline and a recessed octagonal key socket. `Game/portal_gates.json`
describes sparse inactive falling dust on the fixed emitter and the glowing
beam after keyed USE. Replace the dust on activation rather than spawning
unbounded effects; preserve inactive and active state on save/load.

Use exported wall PNG dimensions and sidedef offsets exactly. Gallery panels
and fictional billboard facades contain intentional blank masonry margins,
so scaling a whole image to every wall would crop or repeat the signs wrongly.
Large wall textures are assembled in the WAD from short classic patches; the
portable PNG already contains the complete image. Floors remain 64x64 tiles.
The civic rink is ordinary traversable floor, not slippery ice. Platforms have
slightly lowered tracks and visual safety edges, not moving trains.
Stepped roofs/crescents are sector silhouettes, not meshes or genuine domes;
the existing Freedom Arch piers do not contain real overhead spans.

Original editable sources, dimensions and provenance are under
`art_sources/venues`. Re-export regenerates their PNGs and inventory from
`scripts/venue_scenery.py`; preserve its hand-maintained `provenance.json`.
Reference photographs are not included. Do not copy contemporary museum art
or real advertisements when extending these original designs.

## NPCs and animation

`Game/npcs.json` covers eighteen venue-specific rivals plus the shared raccoon.
It includes identity, spawn ID, physical dimensions, HP, movement parameter,
attack action/timing, sound references and animation groups. Custom NPCs also
have explicit generated state graphs with actions and next states.

- Combat rivals use camera-facing transparent A0 billboards. Directional
  scenery/patrol views are separate registries, not a replacement combat AI.
  There are no skeletons, rigging, 3D meshes or skeletal animations.
- `Game/sprites.json` maps WAD sprite IDs to individual RGBA PNGs and offsets.
  Place a world sprite's ground anchor using its left/top offsets; preserve its
  opaque body height and feet instead of scaling by transparent image bounds.
- Standard custom frames: A–D walk; E/F/G aim/fire/recover; H pain; I–N intact
  defeat; O/P idle. Raccoon is different: consult its explicit groups in JSON.
- Tics are 1/35 second. Execute entry actions at state changes, allow pain/death
  interrupts and honor terminal `next: null` states. Actor speed is a native
  movement parameter, not metres/second.
- `sound_resources` order is alert, pain, death, idle. Firing sounds are separate
  and follow attack semantics in `gameplay.json`.
- `states` retains the base actor graph. Override ranged entry with
  `far_attack_state` and merge `attack_states` by state ID. These effective
  states come from the selected WAD's DEHACKED, with explicit `action`, `frame`,
  `fullbright`, `tics`, `next`, `args`, `misc1` and `misc2` fields.
- Use line of sight, collision, pursuit and ranged aiming. The source engine's
  randomness/spread, pain chance, reactions and damage rules need equivalent
  native C++ behavior for faithful parity; the WAD override file is not a full
  engine definition.

All nineteen NPCs use size-based marker progression. Heights <=54 use slot 2
(one pellet), 55-87 use slot 3 (seven simultaneous pellets), and >=88 use slot 4
(two single-pellet shots four tics apart). Each pellet deals
`5 * random_integer(1,3)` damage with 5.625-degree horizontal spread.
Aim lasts ten tics; each shot lasts four; recovery is fourteen tics for pump
or eight otherwise, then resumes the original chase. `PlaySound` uses `misc1`
as its sound slot and `misc2=0` for positional audio. Automatic uses dedicated
slot 548 (`DSFRE048`), avoiding the stock linked chaingun sound. NPC ammunition
is unlimited; health, dimensions, movement and drops are unchanged. Receiver
art distinguishes tiers in living walk, aim/fire, pain and idle poses.

Legacy coyote, old large-raccoon and reference-sheet PNGs are kept for
provenance, not added to the active nineteen-NPC roster.

## Player weapons, effects and supplies

`Game/weapons.json` defines slots, sprite prefixes, shared pool, shot costs and
basic attacks. Weapon 1 is the harlequin overhead/right-shoulder mallet, requires
no ammo and replaces only fists. Slots 2/3/4 remain starter pistol, pump and
automatic. No projectile weapons are added.

- The mallet uses AI-generated source art in `art_sources/weapons`, with
  provenance in `mallet_source.json`. Four detailed first-person poses replace
  the old flat procedural drawing. Runtime `PUNG` frames remain 160x144 with
  per-pose offsets in `Game/sprites.json`, binary transparency and the Doom
  palette. Idle leaves the crosshair clear; the overhead strike moves inward.
  The generator compensates for 1:1.2 display pixel aspect before quantization.
- Share one paint pool: initial 50, capacity 400, backpack capacity 800.
- Starter: one paint per shot. Pump: seven pellets and seven paint; cannot fire
  with fewer than seven. Automatic: one paint per round, two rounds per cycle.
- Debit once per actual attack, not once for both state animation and effect.
- HUD weapon offsets are screen-space Doom patch offsets, not world anchors.
  Doom's 320x200 virtual screen has 1:1.2 display pixel aspect. Explicitly decide
  whether to preserve that appearance or use square pixels consistently.
- Port native weapon state timing, recoil, refire, spread and damage, applying
  `DEHACKED.txt` overrides; these are not encoded as a universal C++ animation
  player. Preserve the mallet's original melee behavior.
- Paint splash frames PBLT A/B/C/D last 5/85/10/5 tics (three seconds).
  They are stationary, camera-facing, nonblocking effects, not wall decals.

`Game/pickups.json` maps supply spawn IDs to behavior/art. Original portable
health/armour/backpack icons supplement supplies whose appearance in the WAD
comes from the commercial base game; these icons are explicitly marked as new,
not pixel-identical WAD extracts. All active level thing IDs must resolve to a
player start, NPC, supply or introduction trigger.
Blue access cards unlock exits. Pods/cases give 25/125 paint before skill
multipliers. Introduction thing IDs 15100–15108 display once-only venue/map tips,
not damage, ammo or item-count rewards.

## Audio, surfaces and UI

- `Game/materials.json` indexes custom RGBA wall, flat and sky images by material
  name. Wrap tileable materials; sky panoramas wrap horizontally. Keep palette
  pixels crisp rather than applying smoothing indiscriminately.
  All nine skies and the formerly procedural walls (city streets/bases, hotel
  facade, stage, stadium/arena seating, boards, ice, roof, track ballast,
  keyed doors) are high-definition AI artwork downsampled to native texel
  density with baked lighting and ambient occlusion; their reviewed source
  atlases are `assets/skies_squares.png`, `assets/skies_waterfront.png`,
  `assets/materials_city.png` and `assets/materials_arena.png`.
- `Game/audio.json` indexes unsigned 8-bit mono PCM WAV effects converted from
  original project DMX sounds, without DMX guard samples. Use the WAV header's
  sample rate. Ogg files are newly synthesized stereo loops; MIDI is a reference
  score. All nine compositions are original, including Rogers' organ waltz.
  No third-party compositions, recordings, external samples or soundfonts are
  included. The old borrowed ballpark refrain is no longer used.
- `Game/Music` uses the nine-map campaign IDs. Do not map the source `music`
  folder's old venue slots directly to current levels.
  `audio.json` records each track's genre, tempo, beats per bar and zero-based
  General MIDI programs by channel. Channel 9 is percussion. Rogers is 3/4;
  the other eight tracks are 4/4. Use the supplied Ogg files for the intended
  guitar, organ, brass, bass, choir-like pad and keyboard synthesis, rather than
  assuming a generic MIDI soundfont reproduces those timbres.
  `Music/provenance.json` documents composition/performance origins, exact file
  hashes and the absence of third-party music licensing/royalty dependencies.
  This does not certify exclusive copyright ownership of AI-assisted output.
  `Music/presentation.json` assigns the same original tracks to title,
  intermission and finale cues; do not substitute stock Doom music.
  Builds/exports reject mismatched provenance. Regenerate all current tracks with
  `py -B scripts\expansion_music.py` before rebuilding/exporting the campaign.
- `Game/presentation.json` indexes HUD background, all 42 supplied-character
  face expressions, medium number glyphs, victory, level-title and overworld
  art. Stock keys/backgrounds remain excluded; do not extract them from IWADs.
  Portrait provenance is `art_sources/player-face-provenance.json`.
- Candidate HUD removes Tab/WASD/mouse hints and the old campaign thumbnail.
  The approved KEX fallback automatically selects TRMAP1..9 after first movement.
  It is a static north-up plan with fixed spawn dot/north arrow, not live radar
  or heading. Native types 15300..15303 silently encode levels 1..9 in unused
  key-item bits (2,3,5,6), reset each level, and never count as items or affect
  blue checkpoint locks. All-keys cheats suppress the inset until the next map.
  In C++ select directly by current-level ID and ignore those native marker
  things; `Game/gameplay.json` exports the complete static_level_inset contract.
  Any optional live compass must use real heading, not an animation clock.
- A future reactive Tab prompt should reflect the actual full-map action and
  fill while that map is open. KEX's supported SBARDEF 1.0 does not provide
  the needed binding, key-state, automap-state or actor-query interface.
- Future introductory hints should show actual rebound movement/mouse/fire/use/
  weapon/map actions at each fresh level start, dismiss on first gameplay input
  (not menu/console events), and use live input state. Do not fake it with a timer.

## Script responsibilities

All Python files are in the sibling `scripts` folder; `Game/scripts.json`
inventories each file's APIs.

- `build_toronto_wad`: shared sprite/art/WAD helpers and preserved three-map
  reference path. `build_expansion`: candidate assembly, validation and guarded
  publication. Never run a reference rebuild over the preserved backup.
- `doom_geometry`, `venue_geometry`: binary map structures, node building and
  polygon compilation. `toronto_venues`: footprints, raised cover, routes,
  encounters and exits.
- `campaign_order`, `expansion_cast`, `toronto_enemies`: venue order, dimensions,
  identities and generated NPC state graphs.
- `npc_weapons`: campaign-only size tiers, native hitscan bursts, dedicated
  automatic sound and marker receivers; backup helpers retain their defaults.
- `toronto_materials`, `expansion_presentation`: original surfaces/skies and
  ending art. `campaign_feedback`: shared ammo, introductions, paint and HUD.
  `campaign_overworld`: campaign/intermission map art, not live radar.
- `paintball_audio`, `expansion_audio`, `toronto_music`, `expansion_music`:
  deterministic effects, voices, scores and encoding.
- `prepare_expansion_art`: source-alpha and sprite-sheet normalization.
  `build_mod_previews`, `build_expansion_previews`: presentation previews.
- `verify_expansion_runtime`: native starts/music; `verify_expansion_checkpoints`:
  actual keyed handoffs; `verify_campaign_fixture`: isolated routing fixture;
  `verify_campaign_feedback`: native ammo/splash tests; `verify_campaign_finale`:
  ending stability; `verify_campaign_overworld`: intermission/progress captures.
  `verify_npc_weapons`: native pistol/pump/automatic encounter smoke captures;
  unit tests verify exact pellet counts, sound slots and state graphs.
- `test_*`: regression suites for the corresponding content and geometry.
  `test_game_assets`: relocation and portable export integrity.
  `project_paths`: workspace/asset locations, independent of working directory.
  `export_game_assets`: this portable package's reproducible generator.

## Acceptance checks for a consuming C++ game

- Load all nine levels and resolve every material, sprite, sound and spawn ID.
- Verify world/map correspondence at start, card, cover and exit coordinates.
- Verify all nineteen NPC silhouettes, ground anchors and distinct state changes.
- Confirm shared ammo and dry pump behavior, backpack capacity and melee fallback.
- Confirm every keyed exit, Islands handoff and final victory.
- Verify stereo music loops and mono spatial sound without clipping.
- Clearly distinguish features implemented in the new engine from those merely
  requested or inherited from Doom. Do not claim full combat/parity/performance
  testing based only on asset loading.
