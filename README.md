# Enginehost TyranoScript core

TyranoScript's own Enginehost core (Droidtop/tracker#868). The owner, 2026-11-04: "Tyrano should
get its own core too, in case that wasn't clear." Every engine keeps its own core (Enginehost
`docs/SPEC.md`, "Every engine keeps its own core"); until this core is published, Tyrano games keep
running on the HTML core. It is built under Enginehost's policy for cores written from scratch
(`docs/SPEC.md`, "Cores we write from scratch"): survey real games, list the risks, one broad pass,
then compare against each game's PC build on a rig.

Branches follow Enginehost `docs/plugin-lines.md`: the engine branch carries this tree, `plugin-core`
the Enginehost wrapper, and the composed `plugin/<line>` builds the bundle.

## What is here now

- `tools/survey/tyrano_survey.py` scans a folder of games in place: unpacked folders, `package.nw`,
  an NW.js `.exe` with its zip appended, and Electron `resources/app.asar`. It reports:
  - the TyranoScript version, the title, the screen size and `configSave`;
  - each tag's use, the plugins, and the `[iscript]` blocks;
  - every reach in the game's own JavaScript for `studio_api`, Node, NW.js or Electron, child
    processes, shell open, `window.open` and the network.

  It writes only its report. Tests: `python3 -m unittest discover -s tools/survey`.
- `docs/behaviour/`: what the core is written from, and the risk list.

## Licence

GPL-3.0 (`LICENSE`), as Enginehost's HTML core.
