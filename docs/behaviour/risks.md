# Risks

Everything a Tyrano game can reach through its PC build that could be abused, and the core's
answer (Enginehost `docs/SPEC.md`, "Cores we write from scratch", step 2). The survey's `risks`
counts say which games actually use each. Status: candidates, none confirmed on the owner's games.

| Behaviour | How a game reaches it | Core's answer |
|---|---|---|
| Reading and writing files by path | `studio_api.fs`, `require('fs')` | Only inside the save folder (for `configSave: file`) and read-only inside the game folder; anything else fails as "not found" |
| Starting programs | `require('child_process')` | Not provided |
| Opening a URL or a file in the system shell | `nw.Shell`, Electron `shell.openExternal`, `window.open` | Offered through Enginehost's link sheet (the person chooses), as the HTML core does |
| Network | `XMLHttpRequest`, `fetch`, `WebSocket` | None by default; a per-game Fibrewall permission, off |
| Native modules and other Node APIs | `require(...)` of anything else | Not provided; the call fails |
| Inline JavaScript in scenarios | `[iscript]` blocks, plugins' `.js` | Runs in the WebView like the game's engine; it gets only what the rows above allow |
