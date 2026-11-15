# Paint the Town asset integration

- Read [IMPLEMENTATION.md](IMPLEMENTATION.md) before implementing a C++ game.
  Load [Game/manifest.json](Game/manifest.json) to identify the exported version.
- Use `Game` PNG, WAV, Ogg and JSON files as the runtime content boundary. Do
  not load commercial Doom IWADs or embed installed game resources.
- Source atlases are not ready-to-use animation grids: sizes, gutters, frame
  ordering, alpha cleanup and attack substitutions vary. Prefer the exported
  transparent frames and their metadata.
- Preserve the nineteen NPC identities, nine-level order and player weapon
  slots. `Game/npcs.json` and `Game/weapons.json` describe current behavior.
  NPCs use height-based starter/pump/automatic tiers: <=54 / 55-87 / >=88 units.
  Apply `far_attack_state` and `attack_states` over the legacy base states;
  preserve pellet counts, burst cadence and sounds, not just weapon artwork.
- Default-control hints are removed. The approved KEX fallback is an automatically
  selected static current-level inset after first movement, not radar or compass.
  For C++ select TRMAP1..9 directly by level ID; ignore native marker things
  15300..15303. These are internal level-local key bits, not progression pickups.
  Follow `Game/gameplay.json` static_level_inset metadata. An optional live
  compass must derive from actual heading, never an animation clock.
- Build real world-space collision and gameplay state. A campaign image is not
  a live level map, and an animated decoration is not input feedback.
- Resolve `Game/decorations.json` separately from NPCs/pickups. Its static and
  animated scenery is nonblocking and non-shootable; intentional collision
  belongs to sector geometry. Preserve framed-panel offsets and full billboard
  texture dimensions. Union's hotel is north; its railway platforms are south.
- Wall and sky resources are high-definition AI art at native texel density:
  nine sky panoramas come from reviewed strips of `skies_toronto.png`,
  `skies_squares.png` and `skies_waterfront.png` (1024x128, seam-blended),
  and formerly procedural walls come from the 4x2 atlases `materials_city.png`
  and `materials_arena.png` (cropped inside divider lines, edge-blended).
  Keep baked lighting/ambient-occlusion texture detail; do not regenerate flat
  noise substitutes. One texel per map unit is the native sampling limit.
- Animated scenery's `rotations` selects front/side/rear artwork relative to its
  fixed world facing and the viewer. Do not turn the character toward the player
  or use its front view for every angle. Static foliage remains billboard art.
  Arena mascot artwork uses `ABWR`; reserve `BEAR` for the Zoo combat NPC.
  The faceoff referee wears long black-and-white vertical stripes and black pants.
  The wandering girls (GRLG in Queen's Park, GRLP in Sankofa Square) use their
  supplied side-view walk art as rotation-0 billboards; the purple-haired girl's
  shirt shows an original bold X-eyed smiley badge, never band lettering.
- Route tips are one-shot message pickups: the spawn message reminds controls
  (W A S D / Mouse), a Tab-map tip sits mid-route, the objective and venue name
  repeat intermittently, and spacebar advice accompanies the Portal Key.
- A live view-direction compass is NOT expressible in native KEX SBARDEF (no
  player-angle condition exists); the inset stays static north-up there. Ported
  engines must derive the inset arrow from the actual player angle with eight
  facings (up=north, down=south, left=west, right=east plus diagonals).
- Native KEX cannot inject runtime statistics into the static campaign-complete
  picture. Ported engines should track the player's longest kill streak between
  deaths and display it on the campaign-complete screen, which credits
  "Built by Richard Harris".
- Preserve `Game/portal_gates.json`: a gold-edged ground-mounted socket panel,
  sparse inactive falling dust, and activation-only beam. Dust is the fixed
  emitter's animation, not an accumulating particle spawn or an inventory item.
- Keep baseball on one 210-tic controller clock, with outbound/return releases
  at tics 35/140 and finite-lived children. Serialize the entire scene timing,
  not two independent actor loops. Zoo animals never enter rival combat AI.
- Preserve the polished sprites' native world scale and bottom-center anchors:
  standing people about 64 units, player eye height 41, crouched people shorter,
  large wildlife taller and penguins genuinely small. Do not normalize every
  species/pose to identical visible height. Original AI atlases and reviewed
  preparation metadata live in `art_sources/polish`.
- Use a 35 Hz fixed gameplay step for compatible timings. Convert Doom XY/Z and
  sprite offsets explicitly to the target engine's coordinate conventions.
- Use `Game/audio.json` and `Game/Music/provenance.json` for the current venue
  soundtrack. Source scores in `music/paint_the_town` retain historical source
  IDs; exported music uses current campaign IDs. All nine compositions are
  original: Rogers is a 3/4 organ waltz, the others are 4/4 instrumentals.
  There are no borrowed melodies, samples or external soundfonts. Preserve
  file-hash provenance and `Game/Music/presentation.json` cue assignments.
  No third-party music license or royalty is required; do not claim certified
  exclusive copyright ownership of AI-assisted output.
  Preserve the Ogg loop, meter and zero-based
  MIDI program metadata. Do not substitute commercial recordings or copied riffs.
- The package contains billboards and sector geometry, not rigged models or
  surveyed buildings. Do not invent missing meshes or claim exact parity with
  Doom's native engine behavior.
- Rebuild exports from the workspace root with
  `py -B scripts\export_game_assets.py`. Do not hand-edit generated files in
  `Game`; change their source data/generator, regenerate and run its tests.
- Preserve WADs, native release proofs and the three-map backup. Exporting assets
  does not authorize publishing a WAD or changing gameplay balance.
