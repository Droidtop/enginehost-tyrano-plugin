# Enginehost TyranoScript core: the wrapper (plugin-core)

TyranoScript's own Enginehost core, `dev.enginehost.tyrano.v1` (Droidtop/tracker#868). The owner,
2026-11-04: "Tyrano should get its own core too, in case that wasn't clear."

A Tyrano game carries its own engine (`tyrano/`) and runs it in a browser. This core runs that
engine unchanged in Enginehost's shared web host (`plugin-web`: a confined WebView, the game served
from a private https origin, `localStorage` kept in the game's save folder, links offered by
Enginehost). What it adds is what the game's PC build has and a WebView lacks:

- **File saves.** A game whose `data/system/Config.tjs` says `configSave = file` saves through the
  NW.js/Electron build's Node `fs`. `PcBuildShim` answers `require('fs')`, `path`, `process` and
  `window.studio_api` from a store in the save folder. No real file is opened, so a script cannot
  reach outside the save folder whatever path it names.
- **Refusals.** `child_process` and every other module throw. Window calls (maximise, fullscreen)
  are no-ops. A shell open goes through Enginehost's link sheet.
- **A record.** Each name a game uses is logged once (`EnginehostTyrano: …` in logcat), so a rig run
  shows what the owner's games call.

The line is `plugin/1`, built from plugin-core alone (`enginehost/lines/1`, no upstream: every game
brings its own engine). The survey tool lives on the engine branch (`tools/survey/`).

Tests: `tools/shim-test/` runs the shim in Node against a mock of the save store; CI runs it before
building.

## Not yet

- Lockdown. It is declared only after this core's own learning run on the rig shows no refused
  path (Enginehost docs/engine-bundle-format.md, `lockdown`).
- Quitting from Tyrano's `[close]`. It is logged and ignored; the host menu ends the game.
- Enginehost still detects Tyrano games as `html` until this core is published on Unstable
  (Enginehost docs/SPEC.md, "Every engine keeps its own core").
