# Steamworks setup: Paint the Town, step by step

Everything technical is already prepared in this repository:

| Prepared artifact | Location |
|---|---|
| Game build (content root) | `dist\Paint_the_Town_Standalone\` |
| Build scripts for upload | `steam\app_build.vdf`, `steam\depot_build.vdf` |
| Store graphics (exact required sizes) | `steam\store_assets\` |
| Screenshots (1920x1080 native) | `steam\store_assets\screenshots\` |
| Store description text | `steam\store_copy.md` |

Follow the numbered steps in order. Steps marked **(you)** need your identity,
payment, or judgement and cannot be automated.

## Part A — Partner account (one time)

1. **(you)** Go to https://partner.steamgames.com/newpartner and sign in with
   the Steam account that should own the game.
2. **(you)** Enter legal name/address exactly as on your tax documents
   (individual is fine; "Richard Harris" as legal entity sole proprietor).
3. **(you)** Pay the one-time USD $100 Steam Direct fee (per app; recoupable
   after the app earns USD $1,000).
4. **(you)** Complete the tax interview (W-8BEN for a Canadian individual;
   you'll need your SIN as the foreign tax ID) and banking details.
5. Wait for Valve's identity verification email (typically 1–3 business days).

## Part B — Create the app

6. In https://partner.steamgames.com → "Apps & Packages" → "Create a new app",
   spend one app credit, type = Game, name = **Paint the Town**.
7. Note the **App ID** Valve assigns (e.g., 3456780). The default content
   **Depot ID** is App ID + 1.
8. Edit two files in this repo, replacing the placeholders:
   - `steam\app_build.vdf`: `YOUR_APPID` → your App ID, `YOUR_DEPOTID` → depot ID
   - `steam\depot_build.vdf`: `YOUR_DEPOTID` → depot ID
9. In Steamworks → your app → "Depots": confirm the depot exists with
   OS = Windows, architecture = 64-bit. Save and **Publish** the depot change
   (green "Publish" tab; publishing configuration is separate from the store).

## Part C — Launch options (how Steam starts the game)

10. Steamworks → app → "Installation" → "General Installation":
    - Launch option 1: Executable = `Paint the Town.bat`
      (type: Launch / OS: Windows). Description: "Play Paint the Town".
11. Save + publish the configuration set.

## Part D — Upload the build

12. **(you)** Install steamcmd: https://developer.valvesoftware.com/wiki/SteamCMD
    (unzip anywhere, e.g. `C:\steamcmd`).
13. Rebuild the package fresh so it matches the published WAD:
    ```powershell
    cd C:\Users\Richard\Dropbox\Workspace\Code\DOOM-WAD
    py -B scripts\build_standalone.py
    ```
14. **(you)** Upload (replace the account name; Steam Guard prompt follows):
    ```powershell
    C:\steamcmd\steamcmd.exe +login YOUR_PARTNER_ACCOUNT `
      +run_app_build "C:\Users\Richard\Dropbox\Workspace\Code\DOOM-WAD\steam\app_build.vdf" +quit
    ```
15. Steamworks → app → "SteamPipe" → "Builds": set the uploaded build live on
    the **default** branch.
16. Test install: in your Steam client the app now appears in your library
    (as the owner). Install and launch it; confirm the title screen and E1M1.

## Part E — Store page

17. Steamworks → app → "Edit Store Page":
    - Upload every image from `steam\store_assets\` into its matching slot
      (file names state the slot and exact pixel size).
    - Upload at least 5 screenshots from `steam\store_assets\screenshots\`.
    - Paste short/long descriptions from `steam\store_copy.md`.
    - Genre: Action / Indie. Features: Single-player, Partial Controller
      (through the port) — leave unchecked anything untested.
18. "Content survey" (mature content): describe as *"Cartoon paintball
    combat against fictional animal rivals; paint splats, no blood, no gore,
    PG-13 themes."* No nudity/drugs/gambling.
19. Legal line (bottom of store page): use the one in `steam\store_copy.md`
    (Freedoom credit, GPL Woof! credit, not affiliated with id/Bethesda/Valve).
20. Pricing: pick the price (or free). Release date: "When ready" is fine.

## Part F — Review and release

21. When the store page checklist is all green, click **"Submit for review"**
    on the store page. Separately, the build/launch configuration must be
    published (Parts B–D).
22. Valve review usually takes 1–5 business days and includes them running
    the build. Common feedback to be ready for:
    - *Third-party IP*: answer that NO id Software/Bethesda data is shipped;
      the game is self-contained via Freedoom (BSD) and only *optionally*
      reads a DOOM.WAD the customer already owns locally. Licenses ship in
      `licenses\`.
    - *Launch via .bat*: if Valve objects to a batch launcher, change the
      launch option to `port\woof.exe` with arguments
      `-iwad ..\iwad\freedoom1.wad -file ..\Paint_the_Town.wad -save ..\saves`
      (configure in Installation → launch options; no rebuild needed).
23. After approval you choose the release moment ("Release now" button).
    Store page and build both must be approved before release.

## Honest risk notes

- Valve review outcomes are not guaranteed. The Freedoom-default build is the
  standard legally-clean pattern for Doom-engine games, but reviewers have
  discretion, and Bethesda's IP posture on Doom-adjacent storefront titles is
  outside our control. If rejected on IP grounds, the same package remains
  fully usable as a free standalone download + "Add a Non-Steam Game" entry.
- AI-assisted art/music: Valve requires an AI disclosure in the content
  survey. Describe it as: *"Pre-generated AI-assisted artwork and music,
  human-reviewed and edited; no live generation at runtime."*
- Never upload DOOM.WAD or any commercial IWAD in the depot. The build tests
  in this repo fail if one is present.
