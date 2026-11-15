# Paint the Town: from-scratch Copilot build guide

## Purpose, starting point and limits

Use this guide to create a new nine-map **Paint the Town** DOOM PWAD in an
empty workspace with a legally installed DOOM + DOOM II KEX runtime. No existing
project scripts, PNGs, music, README, WAD, backup or conversation history are
required. The stages below instruct Copilot to create those inputs before using
them. Tool installation, original image generation and native playtesting may
require user participation.

This recreates the **design and feature contract**, not the original WAD's exact
bytes. New art, music, layout decisions and tool versions can differ. Exact
reproduction requires the original source bundle, original supplied artwork,
recorded dependencies and matching tools. Do not promise the original portrait,
header, musical scores, geometry or release checksum from prompts alone.

This ordinary Markdown document is not automatically loaded as a VS Code
instruction file. Supply the whole document as context, then submit the numbered
stage prompts in order. Each prompt assumes this document remains available.
If a session loses context, reread it and the new project's generated README.
Execute one stage at a time; do not invoke a later command before its tool exists.

The existing mod informed this guide. Its latest documented release passed
native startup/music checks but did not complete all interactive acceptance.
Do not import that release's unverified claims as success in the new project.
The current workspace [README](README.txt) is optional historical reference,
not a prerequisite for a person starting elsewhere.

## Operating rules for every stage

- Work only in the chosen project directory. Do not modify installed executables,
  Steam files, commercial IWADs, unrelated files or reference source trees.
- Keep the target KEX with its ID24/MBF21/DEHEXTRA support and SBARDEF 1.0.0.
  Other ports are not substitutes for native KEX compatibility evidence.
- Make original PG-13 paintball art/audio. Real visitors, workers, performers,
  fans and peaceful exhibits are not combat targets. Fictional rivals are.
- Treat commercial games, music and venue photographs as broad research/mood
  references only. Do not copy characters, team marks, logos, map tiles, lyrics,
  recordings, samples, melodies or recognizable riffs.
- Preserve sources, generation parameters, reviewed artwork and provenance.
  Change source generators, not just compiled WADs or exported JSON/images.
- Surface failures explicitly. Do not insert silent missing-asset defaults,
  fake runtime evidence, weaken acceptance thresholds or bypass release gates.
- Give brief milestone updates. Ask for material design choices and approvals;
  resolve ordinary implementation details consistently with this specification.
- Native input may operate only on an owned foreground game. Never interrupt a
  user game, force repeated focus stealing or disable focus-loss safeguards.
- Use Windows PowerShell and backslashes in shell paths. Commands run from the
  new workspace root; environment variables must be set in the same shell.
- Record each stage's inputs, generated outputs, decisions, test results and
  remaining limitations in the new project's README/provenance. Preserve the
  last known working candidate before risky changes.

## Stage sequence and dependency map

| Stage | Prerequisites | Concrete outcome |
|---|---|---|
| 0 | This guide and licensed KEX | Workspace, dependencies, tool/path configuration |
| 1 | 0 | WAD reader/writer, node integration, one native playable test room |
| 2 | 1 | Nine-stop campaign contract and tested geometry primitives |
| 3 | 2 | Three-map playable greybox slice and first project baseline |
| 4 | 3 | Original source assets and reproducible resource conversion |
| 5 | 4 | Nineteen rivals, four player slots and shared paintball gameplay |
| 6 | 5 | Nine fully connected venue maps, supplies and collision |
| 7 | 6 | Readable HUD, selected markers and automatic level inset |
| 8 | 7 | Venue animation, directional baseball and integrated walkers |
| 9 | 8 | Keyed portals, title, campaign map and stable story/victory ending |
| 10 | 9 | Nine original tracks, sound provenance and finished presentation |
| 11 | 10 | Portable export, previews and complete native acceptance ledger |
| 12 | 11 | Authorized published WAD, reproducible source bundle and handoff |

Intermediate WADs are development artifacts. Publication happens only in stage
12. Do not recreate historical Toronto Realms names/order just to follow the
old development chronology; use the final Paint the Town contract throughout.
For a standalone Steam release, bundle a verified ID24-compliant GPL source
port (Woof!; GZDoom rejects the 2024 DeHackEd spec) plus Freedoom Phase 1 so
no commercial IWAD ships; prefer a locally owned DOOM.WAD at launch time, and
keep store build scripts, assets and the Steamworks walkthrough under steam\.

## 0. Establish the empty workspace and toolchain

**Inputs:** this guide, an empty project directory, legally installed KEX/IWAD.
No original project backup or assets are assumed.

**Prompt**

```text
Create a new Paint the Town PWAD project in this empty workspace. Follow this
guide's operating rules. Locate the licensed KEX executable and DOOM IWAD
without modifying either. Identify Python, FFmpeg and a trustworthy ZDBSP node
builder. Ask for approval before downloads/installations or paid asset tools.
Create the project layout, dependency manifest, path configuration, a stage
ledger in README.txt and tool provenance. Do not build the final game yet.
```

**Create**

- `scripts`, `assets\art_sources`, `assets\music\paint_the_town`, `tools`,
  `runtime_validation`, `mod_preview` and `releases`.
- `requirements.txt`: Pillow, NumPy, Shapely >=2,<3. Record tested versions after
  installation; do not claim these ranges guarantee byte-identical outputs.
- `scripts\project_paths.py`: paths relative to the project root, active
  `Paint_the_Town_candidate.wad` and `Paint_the_Town.wad`; read an explicit
  `DOOM_IWAD` override and configurable KEX/node-builder locations.
- Obtain ZDBSP from its official project or a trustworthy recorded distribution.
  Record origin, version, SHA-256 and applicable license in
  `tools\nodebuilder.json`; retain its license. Do not bundle it as game content.
- Use FFmpeg with Vorbis support for soundtrack generation/tests. Record its
  version. Use available fonts or document a legally usable font dependency.
- `README.txt`: project purpose, stage ledger, paths, tools and known limits.
  Do not link to files you have not created as if they already exist.

After creating the dependency manifest and approving restoration:

```powershell
py -B -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency restoration failed' }
```

**Gate:** imports succeed; IWAD is readable; node builder/FFmpeg are available;
licensed runtime launches normally. A missing input blocks the dependent stage.

## 1. Implement the WAD foundation and a native test room

**Prompt**

```text
Implement scripts\doom_geometry.py and its tests from scratch. Use documented
classic Doom WAD/map formats and a staged ZDBSP build. Create one square test
room with a start, ordinary door and exit, using local IWAD resources only for
this private bootstrap test. Build a disposable PWAD and launch it in KEX.
Verify movement, door use and exit. Record actual results, not presumed support.
```

**Implementation contract**

- WAD header: `PWAD`, little-endian signed 32-bit lump count and directory offset.
  Directory entries: offset, size and zero-padded ASCII name of at most 8 bytes.
  Check bounds, malformed counts, truncated records and invalid references.
  Preserve ordered duplicate lumps; do not reduce the whole WAD to a dictionary.
- A classic map begins with its `E1Mx` marker followed by `THINGS`, `LINEDEFS`,
  `SIDEDEFS`, `VERTEXES`, `SEGS`, `SSECTORS`, `NODES`, `SECTORS`, `REJECT`,
  `BLOCKMAP`. Serialize documented little-endian records, not guessed byte layouts.
- Model vertices, sectors, sidedefs, linedefs and things with explicit types.
  Check indices, winding, sector heights, texture names, flags and tags.
- XY is horizontal; +X east, +Y north, Z up; angles counterclockwise from east.
  Gameplay runs at 35 tics/second. Use Doom units consistently.
- Construct a bounded square around the origin, floor 0, ceiling 128, one player
  start with headroom, a small adjoining room reached through a working door,
  and an exit trigger. Confirm orientation/collision in-game before generalizing.
- Run ZDBSP in a temporary directory. Check return code, diagnostics, output
  existence and valid classic node/map resources. Never invent dummy BSP data.
- Write a temporary candidate, validate it, then replace the intended candidate
  atomically. Do not leave a failed partial write at a known-good path.
- Create `scripts\verify_expansion_runtime.py` with configurable runtime paths,
  owned-process cleanup and native initialization/error-log checks.
  Accept an explicit map list: verify the test room first, the three-map slice
  next and all nine maps after expansion. Do not require nonexistent maps early.

Use official format/spec references during implementation. Their exact URLs,
versions and relevant findings belong in the new README/tool ledger.

**Gate:** WAD round-trip and malformed-input tests pass; native test room is
walkable, its door opens and exit works; no native texture/sprite/map errors.
Do not infer these from a map diagram alone.

## 2. Freeze the final campaign contract and geometry model

**Prompt**

```text
Create scripts\campaign_order.py and scripts\venue_geometry.py. Define the nine
final campaign slots below and an original compact layout brief for each.
Research official venue maps/pages for recognizable features without embedding
their imagery. Implement polygon regions, raised cover, passages, holes,
sector boundaries and radius-aware route/spawn checks. Test these primitives
before building venues. Record numerical layout choices so later builds agree.
```

| Slot | Venue | Two exclusive fictional rivals, plus raccoon gunner |
|---|---|---|
| E1M1 | Royal Ontario Museum | Dinosaur skeleton, medieval armour |
| E1M2 | Queen's Park | Black squirrel, armoured stag |
| E1M3 | Sankofa Square | Beaver engineer, urban red fox |
| E1M4 | Nathan Phillips Square | Armoured Canada goose, chipmunk |
| E1M5 | Union Station | Transit drone, armoured pigeon |
| E1M6 | Scotiabank Arena | Snowy owl, wolverine |
| E1M7 | Rogers Centre | Blue jay, groundhog catcher |
| E1M8 | Toronto Islands | Swan, river otter |
| E1M9 | Toronto Zoo | Polar bear, arctic wolf |

**Create**

- Stable venue identities separate from slot numbers; in a fresh project use
  final slots directly. If later reordered, remap sky/music/actor metadata.
- Region descriptions with floor/ceiling/material/light, solid cover boundaries,
  starts, exits, routes, encounter roles and secrets.
- Two routes per venue, nominal 100-unit-clear corridors where feasible; check
  actual traversability after shrinking by the player radius and at closed doors.
- No unsupported stacked-sector architecture. Recognizable compressed designs,
  not surveyed building reproductions. Raised geometry supplies real cover.
- An allocation registry for custom Thing IDs, DeHackEd Thing indices, states,
  sprites, sounds, keys and tags. These namespaces differ; never conflate them.
- Research ledger with official source URLs, approximations and original layout
  drawings. If a source is unavailable, state the limitation.

**Gate:** tested polygons and holes; valid shared boundaries; non-overlapping
skill-compatible starts; radius/headroom clearance; key reachable before exit
opens. Layout data is saved, not left as undocumented Copilot decisions.

## 3. Build the first playable slice and establish a new baseline

**Prompt**

```text
Create scripts\toronto_venues.py and scripts\build_expansion.py using the tested
foundation. First build ROM, Queen's Park and Sankofa as final slots E1M1-E1M3.
Use explicit development materials/rivals while original assets are pending.
Add two routes, cover, one secret, supplies and one blue-key checkpoint per map.
Verify all skills and actual native transitions. Establish a project-local
baseline only after passing those checks; no original Toronto Realms file exists.
```

**Create**

- A candidate-only build CLI. Do not implement publication as a raw file copy.
  Import only modules already created. Support the current stage's three maps
  without importing future scenery, music or HUD modules; wire those modules
  deliberately as their stages complete. Switch final validation to nine maps
  in stage 6, not while the slice still has only three.
- Data-driven population with player start, pickups and screened fictional
  encounters. In the temporary slice use ordinary Doom mechanics privately;
  do not advertise final custom art/gameplay before stages 4-5.
- Exactly one blue-key progression pickup per map, outside its locked checkpoint.
  Use supported native door/exit specials and an explicit temporary end picture
  or documented supported ending for the third map.
- Geometry/resource tests, all skill masks, node validation, key/exit routes
  and a native checkpoint fixture that removes combat only for routing evidence.
- Once verified, save an immutable project-created baseline under `releases`
  and record its computed hash in `releases\baseline.json`.

**Fresh-project baseline rule:** no historical WAD name or hardcoded hash is
required. Before the first verified baseline, candidate development is allowed
and publication is disabled. Afterwards protect the recorded baseline.
If porting original source code later, adapt its historical backup dependency
deliberately to this fresh-project policy; do not fake the original hash.

**Gate:** slice boots, supplies/secret/key/door/exit work on every skill; routes
connect across all three maps; baseline bytes/hash are preserved.

## 4. Create original source assets and the conversion pipeline

**Prompt**

```text
Create an original Paint the Town art direction and asset inventory. Generate
or draw all required source art, retaining prompt/parameters, hashes and reviewed
results. No original portrait/header/atlases are supplied. Ask whether to provide
a portrait reference or approve a new original face. Create source-preparation,
palette conversion, transparent sprite-patch and material/sky encoders with tests.
First prove one rival, one marker and one material in native KEX, then expand.
```

**Create**

- `scripts\prepare_expansion_art.py`, `scripts\prepare_venue_art.py`,
  `scripts\venue_art.py`, `scripts\toronto_materials.py` and supporting resource
  conversion helpers. Names are new deliverables, not pre-existing imports.
- Source inventory for all nineteen rivals, player marker/mallet art, paint
  impacts, props, sports actors, fans, musicians, walkers, fourteen Zoo species,
  portal/key/ground panel, face/HUD glyphs, nine skies, title and victory artwork.
- Nine high-definition AI sky panoramas sourced from reviewed atlas sheets of
  stacked strips: record each sheet's actual divider rows, crop an 8:1 window
  anchored at each strip's skyline base, grade palette-hostile blue toward
  neutral grey and resize onto the native 1024x128 sky sampling grid with a
  wrap blend at the yaw seam.
- High-definition 4x2 site texture atlases (city and stadium/arena) with baked
  lighting and ambient occlusion for every visible wall family — asphalt,
  cobbles, concrete bases, hotel facade, stage back, kiosk, platform edge,
  panel frame, stadium wall, arena seats, rink boards/ice/roof, track ballast,
  stage floor and keyed doors. Crop cells inside the divider lines, downsample
  to native texel density and edge-blend for seamless tiling. Do not ship flat
  procedural noise walls; one texel per map unit is the engine's sampling limit.
- For each asset: stable ID, original file, dimensions, frame order, crop/alpha
  cleanup, anchors, rotations, native size, resource names and provenance hash.
  Create the asset before any preparation script requires it.
- Original human proportions and crisp pixel-art silhouettes; standing humans
  about 64 units, eye height about 41, crouched humans shorter. Different species
  retain different scales. Bottom-centre feet stay grounded across frames.
- Classic patch headers/column posts and offset/height constraints, binary
  transparency, Doom palette conversion and no global palette replacement merely
  to alter one label. Test transparency, anchors and decoded frame dimensions.
- TEXTURE/PNAMES/flat resources with valid patch references; no copied venue
  photographs, billboard ads or stock art repackaged as original content.
  Use sprite/flat namespace markers where required and audit every referenced
  texture, patch, sprite, sound and music name against packaged resources or
  explicitly inherited licensed-runtime dependencies.
- Eight directions where world-facing anatomy matters; four walk phases per
  direction for pedestrians/bear. State durations must reflect foot plants.
- Compose presentation at 4:3, then encode 320x200 Doom patches with aspect
  correction. New header/portrait art is a substitute, not the original image.

User-requested image generation is authorized by submitting this stage prompt,
but availability/cost still needs confirmation. If no image tool is available,
agree on original hand/procedural pixel art or supplied original artwork.
Do not silently substitute placeholders as finished assets.

**Gate:** source inventory complete for stage 5; preparation reruns reproducibly;
native front/rear/side and near/far views show clean alpha and correct scale.
New generation is not deterministic merely because a prompt was recorded;
preserve the chosen source bytes for repeatable future builds.

## 5. Implement paintball gameplay, nineteen rivals and four player slots

**Prompt**

```text
Create the combat/content modules and DeHackEd generators with non-overlapping
allocations. Implement the four player slots, one shared paintball ammo pool,
nineteen fictional rivals with proportional dimensions and height-based marker
tiers, original sound/effects and non-gory tag-outs. Use documented native
ID24/MBF21 actions. Test isolated ammo/weapon fixtures and native rival behavior
before merging into maps. Preserve working movement and progression.
```

**Create:** `scripts\expansion_cast.py`, `scripts\npc_weapons.py`,
`scripts\campaign_feedback.py`, sound generation helpers and combat tests.

| Slot | Weapon | Ammo contract |
|---|---|---|
| 1 | Heavy harlequin/circus mallet | No ammo; native melee timing/damage; overhead right-shoulder swing |
| 2 | Starter marker | 1 per shot |
| 3 | Pump marker | 7 per seven-pellet burst; cannot fire at 6 |
| 4 | Automatic marker | 1 per round, 2 per full native cycle |

- Initial paint 50; ordinary capacity 400, backpack 800. Pods give 25 and cases
  125 before native skill multipliers. Marker pickups/rival drops refill the
  shared pool. No shell-only supplies and no duplicated ConsumeAmmo debit.
- Give rivals walk, idle, aim/fire/recover, pain and non-graphic defeat poses.
  Small heights <=54 use starter tier; 55-87 pump; >=88 automatic.
  Use one shared tier table: starter one pellet/one round, pump seven
  pellets/one round, automatic one pellet/six rounds. Aim 10 tics, fire
  4 tics per round, recovery 8/42/8 tics respectively. Expected pellet
  damage is 10; attack-chain expected DPM is about 955/2625/3000.
  These are programmed ceilings, not actual AI hit rates. Preserve native
  sight, pain, reaction-time and chase behavior. Compare id's p_enemy.c.
  Allocate sixteen states per actor, including sound states; test the
  entire graph, allocation boundaries and matching portable metadata.
- Suggested design dimensions, height/radius in Doom units:
  raccoon 56/20; drone 56/22; dinosaur 128/34; armour 88/30; combat bear 104/34;
  wolf 48/24; pigeon 40/16; beaver 64/24; fox 54/20; goose 50/20;
  chipmunk 30/12; blue jay 38/14; groundhog 66/26; owl 48/18; wolverine 76/28;
  squirrel 34/12; stag 108/34; swan 54/22; otter 52/20.
- Set health/speed/attack timing explicitly in data, document and balance them.
  Original exact health/timing tables are not supplied by this guide. Dinosaur
  and combat bear use 180 HP as the target; don't leave other stats accidental.
- Stationary paint splash lifetime 105 tics at 35 Hz; nonblocking/nondamaging,
  shrinking before removal. Camera-facing sprites, not true attached decals.
- Original pneumatic marker effects and species-matched non-gory reactions.
  No stock Doom audio relabeled as project-owned.

**Gate:** zero ammo, pump at 6/7, consumption 1/7/2, 400/800 clamping, pickup
refills, multiplayer-independent single-player assumptions and native save/load
are tested. Rival tier fixtures visibly fire the expected pellets/cadence.
Paint stays stationary for its tested lifetime. No unknown native code pointers.

## 6. Expand to nine finished venue layouts

**Prompt**

```text
Expand the existing slice into all nine final slots using the following venue
briefs. Produce saved numerical geometry, starts, routes and encounter data.
Reuse tested generation primitives; introduce no parallel map pipeline.
Keep rivals screened at spawn and provide early pump, automatic, paint,
health, armour, one key and one secret on each map. Add native layout checks.
```

| Venue | Required layout/features |
|---|---|
| ROM | Galleries with original framed wall art and grounded historic artifact props |
| Queen's Park | Trees and mansion/legislature-like stone building near the start |
| Sankofa | Stage, speakers, surrounding buildings and original billboards |
| Nathan Phillips | Skating-rink treatment and City Hall interpretation with exactly one rear cylindrical tower |
| Union | Concourse/platform paths and Royal York facade treatment; use hotel north/platforms south for this design |
| Arena | Ice, centre line/circle, blocking boards, connected entrance tunnels/rinkside route, raised spectator seating behind boards |
| Rogers | Original field markings, fixed pitcher/catcher/home axis, spawn behind catcher, two side-entry dugouts |
| Islands | Compressed shoreline, visible water/skyline, traversable bridges and waterfront |
| Zoo | Compact seven-region path/habitat overview, no floating rocks, grounded exhibits |

The original conversation had conflicting Union directions. This guide chooses
hotel north/platforms south explicitly; do not reverse it from historical text.
Layouts are new numerical designs inspired by these briefs, not exact original
coordinates. Store every dimension, start, route and placement for repeatability.

Zoo region/species pairs, all peaceful and unique across exhibits:

| Region | Pair |
|---|---|
| Indo-Malaya | Orangutan, tapir |
| Africa | Elephant, giraffe |
| Americas | Bison, jaguar |
| Australasia | Kangaroo, penguin |
| Eurasia | Tiger, snow leopard |
| Canadian Domain | Deer, moose |
| Tundra Trek | Polar bear, arctic wolf |

Combat bear/wolf are fictional rivals, not duplicates of peaceful exhibit AI.
Geometry must supply real barriers/cover. Dugout masked mesh alone is not
bulletproof: use approved solid protective lower walls, transparent mesh above
and sheltered side entrances. Verify where a standing player's shots are blocked.

**Gate:** all nine native starts; routes/key/secret reachable per skill; no
overlapping actors or insufficient headroom; foes cannot see initial start.
Supply budget covers encounters with a documented margin. Both dugouts can be
entered/exited; board walls do not strand players, supplies, key or exit.

## 7. Build the HUD and automatic current-level inset

**Prompt**

```text
Implement an original readable ID24 SBARDEF status bar with shared paint/capacity,
health, armour, selected marker feedback and the newly approved face artwork.
Create scripts\level_inset.py. Automatically choose a static north-up plan of
the actual map after first movement. Keep native Tab automap; do not claim radar
or dynamic compass support. Add numerical, visual and save/load checks.
```

**Create**

- Friendly palette-coloured medium consistent PAINTBALLS/HEALTH/MARKERS/ARMOUR
  labels/numbers, dark side fill and no obsolete TAB/WASD/mouse drawings over the
  lower-right inset. Check widths at 800/800 and native HUD display modes.
  Draw all four labels with the same unscaled compact 3x5 binary-alpha bitmap
  lettering, and automap/status glyphs with explicit pixel patterns; resampled
  font strokes thinner than one texel are discarded by alpha thresholding and
  render blurry or broken natively.
- Highlight selected slots 2/3/4 using selected-weapon conditions, not ownership
  conditions; when melee is selected don't highlight all owned markers.
- Nine static map images with north indicator and fixed spawn dot. They are
  current-level geometry, not the between-level campaign image or live position.
- Probe native supported level selection. One compatible approach uses four
  invisible level-local marker bits encoding 1..9, collected after movement.
  Separate these internal markers from the progression blue key, reset per map
  and test any inventory/cheat interaction. Document bit/key allocations.
- A first-movement once-only message reminding the controls (W A S D + mouse)
  plus one-shot route tips: a Tab-map reminder reachable about a minute into
  play (never at spawn), the objective "Find the Portal Key & Exit!" and the
  venue name repeating intermittently along both routes, and spacebar advice
  placed with the Portal Key. All are message pickups with no ammo, health,
  bonus, sound or item reward. Use native message duration behavior.
  A live view-direction HUD compass is not expressible in SBARDEF (no
  player-angle condition); keep the inset static north-up natively and specify
  the eight-way live arrow only in the ported-engine metadata.

**Gate:** nine correct selections, unchanged progression key behavior, native
save/load and HUD-free mode; selected-marker switches and readable display.
Native Tab retains the real level automap/live arrow. No live-compass promise.

## 8. Integrate venue life, directional baseball and solid walkers

**Prompt**

```text
Create scripts\venue_scenery.py, scripts\sports_scenery.py and
scripts\venue_walkers.py. First probe supported native animation/movement in
disposable fixtures. Integrate the scene contracts below with allocation tests.
Implement actual directional walking/displacement, not sliding animated
billboards. Test in-map collision, grounding, animation and save/load.
```

**Scene contracts**

- Arena: exactly one referee on the red line between opposed blue/red players
  on opposite sides. Players face each other; stick blades converge on the centre
  circle; subtle ready/puck-drop animation. No gold centre blocker.
- Animated fans in rising seat rows behind blocking boards. Seat heights ground
  fan feet and provide headroom; no visitors standing inside solid walls.
- Blue-jersey polar bear walks by the boards, solid/noncombat, about height 72,
  radius 28. Do not call a shuttle a full perimeter circuit unless implemented.
- Two Union pedestrians, about height 64/radius 16, walk real concourse routes
  with turns, foot plants and weight shifts. Initialize world-fixed routes
  independently of player position; do not assume SpawnObject copies pointers
  as intended without inspecting native saves. A missing/stationary walker is
  a failed test, not a fallback. Require exactly two Union walkers, not any one.
  Associate native records with unique bounded world routes across snapshots;
  every actor must move independently and continue moving after reload.
  Never count distance between different pedestrians, or a stationary actor's
  displacement from its spawn, as evidence of motion. Invalidate stale success
  reports before rerunning acceptance, including when a later run fails.
- Both walker types are non-shootable, non-counting and non-rewarding; must not
  trap players or permanently block doors/routes. Test obstruction and resume.
- Two animated Sankofa musicians, guitarist/drummer, placed on stage.
- Fixed-world animated hotdog/ice-cream carts on Queen Street at Nathan Phillips.
  Preserve billboard-facing limitations honestly; idle frames must not translate
  their anchors. Add Union's two asphalt lanes/cobbled median with level crossing,
  and north/south Yonge plus southwest Eaton/H&M frontage at Sankofa.
- Twelve individually sourced original classical/historical paintings in ROM,
  each displayed once, never a mirrored/repeated substitute. Ensure texture
  wrapping cannot repeat a painting down a long wall. Put minerals on pedestals.
- Peaceful Zoo animals and sports characters remain noncombat; geometry supplies
  intended collision where appropriate. Walking characters specifically are solid.
- Rogers pitcher faces toward catcher/home/spawn; catcher rear faces spawn.
  Preserve fixed world-facing angles and eight rotations when the viewer moves.
  One synchronized 210-tic throw/catch/return cycle; release outbound at tic 35
  and return at 140. Finite-lived children; no damage/ammo changes.

**Technical direction:** use documented MBF21/ID24 state actions. Use the
native-proven fixed-anchor bootstrap, not the superseded player-target/projectile
chain. A map controller uses `SpawnObject` to create a zero-size fixed anchor;
after one tic the anchor adds COUNTKILL, waits one tic and spawns the solid walker.
The walker waits one tic, runs `FindTracer` once (one-block range), then enters
the gait. Eight tics after spawning the walker, the anchor clears COUNTKILL
and adds NOBLOCKMAP. KEX probes required that temporary COUNTKILL for acquisition;
do not assume public source-port behavior matches KEX. Add the flag only AFTER
anchor creation so spawning does not add a kill to the level total.
Use `JumpIfTracerCloser`/`SeekTracer` for bounded outbound/return paths and
180-degree turnarounds; never reacquire the player. Walkers start SOLID,
nonshootable/noncounting, grounded and are never projectiles.
Probe range units, spawn/tracer relationships, grounding and action support.
Do not use an unsupported `Stop` action or infinite zero-duration state loop.
Follow both conditional branches in graph tests: an untaken return-distance
test must advance to a positive-tic motion state, never itself.
Record actor/state definitions and validated native behavior explicitly.

**Create tests/verifiers:** allocation uniqueness, four gait phases x eight
directions, controller counts per map, fan placement, world angles and timings;
`scripts\verify_venue_walkers.py`, `scripts\verify_union_stability.py` and
`scripts\verify_revision_scenes.py`. Require three movement snapshots to avoid
sampling a periodic patrol twice at the same position; check every actor.
Reload proof must include a fresh native setup-log entry and post-reload motion.
The stability runner must test player obstruction/resume, the actual keyed
Nathan-to-Union exit/intermission and an extended direct-candidate movement/fire
run with saved native simulation clocks. Preserve actual geometry/combat in
repositioned-start fixtures and disclose those fixture differences.

**Gate:** actual Union/Arena in-map travel, both pedestrians present, turning,
obstruction/resume, noncombat flags and native reload; multiple baseball cycles
and front/rear/both-side views before/after reload. Visual correctness is reviewed.

## 9. Create keyed portals and cohesive campaign presentation

**Prompt**

```text
Create scripts\expansion_presentation.py and scripts\campaign_overworld.py.
Build original Paint the Town title/header, story and Campaign Complete art.
Reskin the native blue key as a metallic octagonal Portal Key; implement one
panel and a tall glowing portal reveal without removing the real keyed gate.
Probe KEX title/door/finale behavior and implement stable campaign routing.
```

**Create**

- Original compact metal octagon/hexagon key, not a harpoon; reduce the former
  64x96 body by about 35% and retain a pulsing yellow ground halo.
  Retain blue-key inventory internally and one progression pickup per map.
- One activation panel, not repeated EXIT tiles. After keyed activation reveal
  a ground-to-sky beam; no visible rising barrier. Match the panel to the metal
  key outline and retain readable EXIT text. Prove a supported KEX mechanism
  before replacing the native gate; test keyless denial, activation and reload.
  Implement `scripts\portal_gates.py`: tag the ceiling-zero ring, use a remote
  Boom transfer-height control sector (special 242) to render it unobtrusively,
  and blue open-stay lines (32) to retain real collision/key gating.
  A fixed, zero-size, nonshootable AMBUSH/NOGRAVITY/NOBLOCKMAP emitter uses timed
  Look/Turn polling behind the closed ring. Native KEX A_Turn uses binary angles:
  Unknown 1 = 1073741824 turns a quarter circle; 90 barely changes the angle.
  Keep both polling states positive-tic to avoid a simulation freeze.
  Only after sight opens does a finite SpawnObject chain
  create seven 224-unit NOGRAVITY/NOBLOCKMAP fullbright beam segments.
  Animate four tileable phases. Use an opaque core/patterned edges: the project's
  native-translucency probe produced ghosted shapes outdoors and was rejected.
  While inactive, the emitter's own eight sparse animated phases show faint
  fairy dust falling where the exit will open; keyed activation replaces the
  dust with the beam chain, and reload preserves the active/inactive state.
  Place one ground-mounted, gold-outlined EXIT panel with a recessed octagonal
  key socket resting directly on the ground by the approach (no post or stick),
  and eight exit lines
  within a 40-unit octagonal footprint, so exit occurs inside the column.
  Test interior/exterior rendering, keyless USE/shooting/collision denial, actual
  key pickup/USE, fixed segment heights and safe native-logged reload on all maps.
  Cover south and silent north approaches: prior gunfire supplies a sound target
  and can hide A_Look's normal forward-only scan. Put fixture keys on reachable
  paths. Use measured ordinary strafing to align with the narrow exit footprint,
  not teleportation or assumed symmetric keypress displacement. Require a fresh
  D_inter.ogg log entry to prove walking actually started intermission.
  Preserve the emitter and panel at their real positions in checkpoint/finale
  fixtures as well as dedicated portal fixtures.
  The official ID24 interlevel specification defines background layers beneath
  engine-rendered statistics/text, not a font override. Do not invent JSON font
  fields or hide the statistics to claim matching transition typography.
  Reference: https://github.com/doom-cross-port-collab/id24/blob/main/version_0_99_2_md/Interlevel_lumps.md
  In a new project reserve unique Thing/state/sprite/map IDs before generating.
- Use a sharper high-contrast derived portrait sheet, preserving the approved
  character and all 42 native face reactions; preserve original references.
  Mallet shaft must stay straight through socket/grip in all four poses.
  Use cream/green HUD-style native transition labels/digits and story glyphs.
  Inspect actual native intermissions: embedded WIF/WINUM/STCFN replacements
  and DeHackEd resource-name remapping did not change KEX's stock-red UI in
  project probes. Do not count resource-byte tests as typography acceptance or
  modify the installed engine to conceal this unresolved integration issue.
- New original Toronto landmark/paintball header, with PAINT THE TOWN branding.
  No original header is required; preserve the newly selected source and derived
  versions. No unwanted "Promotional Art" wording in game/preview outputs.
- Native TITLEPIC/DEMOLOOP presentation targeting two seconds. Test without warp;
  disclose the closest reliable native behavior if exact duration is unsupported.
- Original Toronto pixel-art campaign map: dimmed results, bright next-stop view,
  distinct cleared/current-next/future symbols, Zoo inset. Not navigational scale.
- Explicit Islands->Zoo interlude when native slot-8 entering behavior skips the
  ordinary screen. Verify transitions 1->2, 4->5, 8->9.
- Original light-fantasy story: nine sleeping landmark gates, paint/colour
  awakening their portals, city restored after the Zoo gate. Write and preserve
  the exact approved script; no copied fictional universe or commercial lyrics.
- Readable blue/teal story backdrop, original CAMPAIGN COMPLETE / THANKS FOR
  PLAYING composition and stable final end picture.
- Explicit UMAPINFO final intertext/backdrop/music/endpic; no self-looping
  next/nextsecret or untested `endgame=true`-only finale. The original project
  encountered a native crash with an implicit ending; reproduce/test new behavior.

**Gate:** all actual key/portal transitions; observed no-warp title; native
intermission progress; final keyed exit, story and victory visible; remain stable
for at least 15 seconds after victory. Save/load does not undo gate state.

## 10. Compose original venue music and finish resource provenance

**Prompt**

```text
Create scripts\expansion_music.py and audio tests. Compose nine original
instrumental tracks following the table, with reproducible scores and
mathematically synthesized performances. Do not copy commercial songs,
recordings, riffs or soundfonts. Preserve approved source scores, Ogg/MIDI pairs,
instrument/meter metadata and hashes. Replace title/intermission/finale music
with original cue assignments in all native music modes.
```

| Slot | Track title / original musical brief | BPM / meter |
|---|---|---|
| E1M1 | Gates of Memory / warm choral hip-hop | 78 / 4/4 |
| E1M2 | Legislature Voltage / gentle funk groove | 88 / 4/4 |
| E1M3 | Square Bounce / relaxed bounce | 86 / 4/4 |
| E1M4 | Winter Borough Lights / soft city anthem | 76 / 4/4 |
| E1M5 | Platform Cipher / warm jazzy boom-bap | 80 / 4/4 |
| E1M6 | Boardside Thunder / restrained stomp groove | 92 / 4/4 |
| E1M7 | Seventh-Inning Portal / soft original organ waltz | 96 / 3/4 |
| E1M8 | Island Afterburn / laid-back Southern groove | 94 / 4/4 |
| E1M9 | Wildlife Midway / mellow playful hip-hop | 84 / 4/4 |

Define melody/harmony/rhythm notes, durations, loop length, oscillator envelopes,
instrument mapping and mixing constants in saved source data. Mood/BPM alone
cannot reproduce the original score; select new original compositions and freeze
their source. Avoid external soundfonts or uncleared samples.
Keep leads in a lower register (MIDI pitch <=67), using warm sine-led voices,
gentle attacks and softened percussion rather than piercing synth/metal hits.
Retain the former three-map historical soundtrack unchanged. Test decoded
stereo peak <0.8, RMS >0.06, endpoint seam <0.12 and energy above 2 kHz <0.1%.

Embed matching Ogg performances in D_/O_/H_ native music modes and explicitly
assign INTRO/INTROA/INTER/VICTOR/BUNNY cues. Validate length, loop seams, headroom,
stereo content and DC offset against documented numeric limits.

**Gate:** nine distinct decoded mixes and original score provenance; native map
and presentation cues play without errors. No borrowed music labeled owned;
describe authorship/licensing factually, not certified exclusive AI copyright.

## 11. Implement export, previews and full native acceptance

**Prompt**

```text
Create scripts\export_game_assets.py, scripts\build_expansion_previews.py and
all missing verification helpers. Export original runtime content, not an engine.
Create a checksum-bound acceptance ledger for the final candidate and collect
actual native evidence for every feature. Run focused tests, full regressions
and sequential owned KEX checks. Document fixtures and failures honestly.
```

**Export outputs**

- `assets\Game`: transparent sprites, original materials/skies, original WAV,
  Ogg/MIDI, JSON map geometry/spawns, maps, weapons/NPCs/pickups/scenery/walkers,
  gameplay/timing, music cues and source inventories.
- `manifest.json`: source WAD SHA-256, output hashes, schema version, published
  hash if present, `source_is_published`. False is expected before publication.
  Derive `release_status` from source/release byte identity too, not merely the
  existence of an older release. List incomplete beam and native-font integration
  honestly even when their draft art resources already exist.
- `assets\IMPLEMENTATION.md` and `assets\AGENTS.md`: coordinate/scale/animation
  contracts, inherited native rules and limitations for a separate C++ game.
  Do not implement that game or redistribute IWAD/executable/reference art.
- Native gameplay captures versus original illustrations/map diagrams labeled
  accurately. Inspect dimensions, branding and source selection, not file count.

**Implement these CLI helpers before running them**

| Script / option | Evidence |
|---|---|
| `verify_expansion_runtime.py` | Nine native starts/music and error diagnostics |
| `verify_expansion_checkpoints.py --live` | Actual keyed routing in disclosed combat-free fixtures |
| `verify_level_inset.py` | Nine inset selections and reload |
| `verify_campaign_feedback.py` | Ammo/paint thresholds, clamping, backpack and lifetime |
| `verify_campaign_finale.py` | Actual final exit, story/victory and stability |
| `verify_campaign_overworld.py` | Required results/entering/progress views |
| `verify_npc_weapons.py` | Three live tier encounter smoke fixtures; exact pellet/burst graphs are unit-tested, not measured damage/minute |
| `verify_mallet_art.py` | Four native pose captures and actual melee smoke; held-pose fixtures do not prove full-motion realism, which remains explicitly unaccepted |
| `verify_revision_scenes.py` | Scene views/baseball cycles/selected marker evidence |
| `verify_venue_walkers.py` | Exact per-route counts/travel, grounding, noncombat flags, logged native reload and continued motion |
| `verify_union_stability.py` | Obstruction/resume, actual Nathan-to-Union entry, extended direct-candidate movement/fire with advancing native clocks |
| `verify_portal_gates.py` | Nine actual-geometry south/silent-north approaches, keyless denial, real pickup activation, exact beam pieces, logged reload and actual intermission; captures still require visual review |

Use configurable local save/log paths. Existing-user-game detection, owned PID
cleanup, focus-loss stopping, binding/settings restoration and blank capture
rejection are mandatory. No competing native verifiers at the same time.
Manual play/capture is acceptable when recorded rigorously; do not present a
failed automation run as proof. Startup/captures alone do not prove movement,
bullet protection, save/load or complete traversal.

**Acceptance reports to implement**

Every report binds to the exact candidate SHA-256 and runtime version, with test
setup/fixture differences, measured observations, evidence paths/hashes and
pass/fail/unverified status. Any byte change requires refreshing affected
checksum-bound release evidence; never transplant old hashes into new proofs.

Core reports: `runtime-results.json`, `checkpoint-live-results.json`,
`static-inset-results.json`, `feedback-results.json`, `finale-results.json`,
`overworld-results.json`, plus `paint-town-acceptance.json` under
`runtime_validation`. Implement versioned schemas and validators together.

Full feature report uses these exact keys:

| Key | Gate |
|---|---|
| `startup_presentation` | Correct branding and measured no-warp native presentation |
| `solid_walkers_and_save_load` | Both pedestrians/bear travel, turn, obstruct/resume, stay grounded/solid/noncombat and reload |
| `arena_life` | Blocking boards, ascending animated fans, exact puck-drop composition |
| `stage_band` | Two correctly placed animated noncombat musicians |
| `directional_baseball_and_save_load` | Fixed world axis, eight views, multiple synchronized cycles and reload |
| `dugout_access_and_shot_protection` | Both entries/exits and protection against actual rival shots |
| `fourteen_unique_zoo_species` | Seven correct pairs, fourteen unique peaceful grounded species |
| `selected_marker_feedback` | Selected versus owned marker switches, including melee |
| `keyed_portal_reveals` | Keyless denial, pickup, one panel, tall reveal and persistence |
| `ending_story_and_victory` | Real final exit, story/backdrop, completion and stability |

For design-compatible quantitative checks, test exact ammo debits/thresholds,
grounding relative to the actor's floor, controller counts, actor displacement
on each planned route, four phases/eight directions, 210-tic baseball timing,
105-tic paint lifetime and >=15-second victory stability. Select documented
visual-match tolerances from actual capture calibration; original pixel-error
constants are not available in an empty workspace. Never loosen them after a
failed result merely to pass. Review saves after reload, not only before saving.

**Gate:** all structural/resource tests pass; native claims have evidence;
representative combat traversal/skills and worst-case performance are reviewed.
Record unmeasured coverage. If full acceptance is blocked, retain that status
and seek explicit limited-release authorization at stage 12.

## 12. Implement guarded publication and hand off the finished project

**Prompt**

```text
Implement two guarded publishers in scripts\build_expansion.py. Prefer full
native feature acceptance. Allow a narrower KEX startup-verified release only
with explicit user authorization, never automatically after full acceptance
fails. Protect the project-created baseline, validate the candidate and reports,
replace the release safely and record the true validation scope. Re-export,
run every regression and verify release/source/evidence identity before handoff.
```

**Publication policies**

- After a reported freeze, neither publisher may bypass stability acceptance:
  require checksum-bound Union evidence for both pedestrians, repeated turns,
  obstruction/resume, Nathan->Union entry, reload and extended play. Require
  at least 180 seconds and six strictly advancing native simulation-tic samples
  spanning at least 6,300 tics (180 seconds at 35 Hz),
  not merely a live process or changing render frames. Never fabricate that report.
- `--publish`: require the recorded fresh-project baseline unchanged, all nine
  native starts/music, keyed routing, inset/reload, ammo/paint, overworld/finale
  and all ten feature gates for the final candidate. Inspect evidence as well
  as booleans; missing/failed/unverified checks refuse publication.
- `--publish-kex-verified`: explicit authorization is a workflow prerequisite.
  Require exactly nine distinct current-checksum startup/music successes,
  clean matching native logs and complete structural/resource validation.
  Record `kex-publication.json` with `full_feature_acceptance=false`, evidence
  hashes and every outstanding interactive limitation. No fake full report.
- Both refuse protected baseline/candidate destinations; preserve prior releases
  under recorded hashes. Validate staged output before replacing active
  `Paint_the_Town.wad`; verify exact candidate/release byte identity.
- Release metadata/report updates must be failure-safe; never silently leave a
  successful-looking report for an unpublished or mismatched WAD.
- No hardcoded historical Toronto Realms backup or checksum dependency in this
  new project's publisher. Preserve the original project files only if the user
  later supplies them explicitly as additional protected inputs.

### Commands: only after the stages created these entry points

Preparation is required after source-art changes, not every unchanged build:

```powershell
py -B scripts\prepare_expansion_art.py
if ($LASTEXITCODE -ne 0) { throw 'Combat art preparation failed' }
py -B scripts\prepare_venue_art.py
if ($LASTEXITCODE -ne 0) { throw 'Venue art preparation failed' }
```

Rerender music only when deliberately changing the saved compositions:

```powershell
py -B scripts\expansion_music.py
if ($LASTEXITCODE -ne 0) { throw 'Music generation failed' }
```

Candidate build, export and regressions:

```powershell
py -B scripts\build_expansion.py
if ($LASTEXITCODE -ne 0) { throw 'Candidate build failed' }
py -B scripts\export_game_assets.py
if ($LASTEXITCODE -ne 0) { throw 'Export failed' }
$env:PYTHONPATH = Join-Path (Get-Location) 'scripts'
py -B -m unittest discover -s scripts -p 'test_*.py'
if ($LASTEXITCODE -ne 0) { throw 'Regression failure; inspect before proceeding' }
```

Design tests correctly for a fresh project: candidate tests work before any
release exists; publication tests create isolated temporary fixtures; a release
equality check is a post-publication assertion, not a mandatory absent file in
every early-stage test. Never delete real regression tests to obtain green output.

Run all required native helpers sequentially and check every exit code/report.
In particular, generate the common stability proof for the final candidate:

```powershell
py -B scripts\verify_venue_walkers.py
if ($LASTEXITCODE -ne 0) { throw 'Integrated patrol/reload verification failed' }
py -B scripts\verify_union_stability.py
if ($LASTEXITCODE -ne 0) { throw 'Union stability verification failed' }
py -B scripts\verify_portal_gates.py
if ($LASTEXITCODE -ne 0) { throw 'Portal verification failed' }
```

Then select **one authorized publication policy**:

```powershell
py -B scripts\build_expansion.py --publish
if ($LASTEXITCODE -ne 0) { throw 'Full-acceptance publication refused' }
```

Or, only after explicit authorization of narrower coverage:

```powershell
py -B scripts\verify_expansion_runtime.py
if ($LASTEXITCODE -ne 0) { throw 'Native startup verification failed' }
py -B scripts\build_expansion.py --publish-kex-verified
if ($LASTEXITCODE -ne 0) { throw 'Limited publication refused' }
```

Post-publication:

```powershell
py -B scripts\export_game_assets.py
if ($LASTEXITCODE -ne 0) { throw 'Published export refresh failed' }
py -B -m unittest discover -s scripts -p 'test_*.py'
if ($LASTEXITCODE -ne 0) { throw 'Post-publication tests failed' }
$candidateHash = (Get-FileHash 'Paint_the_Town_candidate.wad' -Algorithm SHA256).Hash
$releaseHash = (Get-FileHash 'Paint_the_Town.wad' -Algorithm SHA256).Hash
if ($candidateHash -ne $releaseHash) { throw 'Release differs from candidate' }
$manifest = Get-Content 'assets\Game\manifest.json' -Raw | ConvertFrom-Json
if ($manifest.source_sha256 -ne $releaseHash -or -not $manifest.source_is_published) {
    throw 'Export publication identity mismatch'
}
```

Also verify `releases\baseline.json` against its actual recorded baseline bytes
and report/evidence hashes against the release. Implement baseline schema/access
in stage 3 rather than assuming an original project's filenames.

### Player and maintainer handoff

- Update the new README with exact map order, controls, loadout, provenance,
  launch/build commands, release policy, test results and remaining limitations.
- Use `scripts\build_expansion_previews.py` for published previews and an
  implemented `--candidate` option for development previews. Labels/status must
  derive from actual source/evidence, not a stale hardcoded blocker.
- Deliver the standalone WAD for playing and a separate reproducible source
  bundle: all scripts/tests, original selected asset bytes, scores, parameters,
  dependency/tool records and licenses. Do not include commercial game files.
- Clean only owned temporary artifacts/processes and restore native settings.
  Keep baseline, sources and useful evidence.
- Start a **new campaign**; old saves from changed layouts/actors are unsupported
  unless specifically tested. No-warp launch preserves title presentation.

Launch example, after discovering the installation location:

```powershell
& 'C:\Program Files (x86)\Steam\steamapps\common\Ultimate Doom\rerelease\doom.exe' -file "$PWD\Paint_the_Town.wad"
```

For this Steam installation, place `steam_appid.txt` containing the public
application ID `2280` in the launch working directory. Test the exact no-warp
command without injected Steam environment variables: verify New Game reaches
the first map and can move/save. Do not mistake a Steam relaunch or an initial
process exit for verified gameplay, and do not modify installed engine files.

Use `-warp 1 6` only for Arena diagnostics, not as proof of campaign progression
or startup timing.

**Final gate:** actual persistent published WAD exists, matches the tested
candidate, has truthful checksum-bound scope, all regressions pass, baseline
unchanged and export reports published identity. Report blocked interactive
acceptance explicitly; never call startup-only evidence full gameplay acceptance.

## Session restart and incremental completion prompt

Submit this with the next unfinished stage if continuing in another session:

```text
Read this from-scratch guide and the generated project README/stage ledger.
Identify the highest completed gate from actual files and evidence, not a claimed
status. Continue only the next unfinished stage, creating its prerequisites
before invoking commands. Preserve the baseline, sources and unrelated work.
Summarize completed outputs, tests/native observations, decisions and blockers
at the end of the stage. Do not regenerate approved art/music unnecessarily,
restore obsolete requirements, fake proofs or publish before authorization.
```

## What this guide does not supply

This is an incremental engineering/design specification, not embedded source
code or a deterministic image/music seed that reproduces the old binary.
Copilot must implement the described modules, research native formats, create
new original assets, choose/save numerical layouts and balance data, calibrate
tests and obtain real runtime evidence. Unsupported mechanics remain blockers
until solved or explicitly revised. Exact-original recreation needs the original
source bundle; a design-compatible new Paint the Town needs only this guide,
the stated tools, original asset creation capability and licensed native testing.
