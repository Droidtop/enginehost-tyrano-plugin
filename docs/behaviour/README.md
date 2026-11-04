# Behaviour descriptions

What the core is written from: what a TyranoScript game expects of its runtime, in our own words.
TyranoScript itself is open source and ships inside every game (`tyrano/`), so unlike Wolf there is
no closed runtime to read. The game's own engine copy runs unchanged in the core's WebView. What the
core provides, and must describe here, is what the PC build gives that engine and a WebView does not:
- the NW.js or Electron objects behind `window.studio_api` (files, window, shell);
- `configSave: file` saves;
- the window and fullscreen calls;
- quitting.

Each claim is marked [V] (checked), [S] (secondary source) or [M] (memory, to check). The survey
(`tools/survey/`) says which of these the owner's games use and how often.

Pages: `risks.md`, the risk list and the core's answer to each.
