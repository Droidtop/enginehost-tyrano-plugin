#!/usr/bin/env python3
"""Survey a folder of TyranoScript games, read in place, for the Tyrano core's broad pass.

Usage:
    python3 -I tyrano_survey.py GAMES_DIR [--out report.json] [--max-depth N]

A game is found wherever its files are: an unpacked folder holding tyrano/ and data/, a
package.nw (zip), a Windows NW.js build whose .exe carries the zip appended, or an Electron
build's resources/app.asar. Archives are read, never unpacked; nothing is written except the
report and nothing is copied.

For each game the report gives:
- where its files are (folder, package.nw, exe, asar) and the TyranoScript version the engine
  files name;
- data/system/Config.tjs: the title, the screen size and configSave (webstorage,
  webstorage_compress or file; "file" needs the PC build's studio_api.fs);
- how often each tag is used in the scenario (.ks) files, the plugins under
  data/others/plugin/, and how many [iscript] blocks carry inline JavaScript;
- in the game's own JavaScript (data/, [iscript] blocks and index.html, not the stock engine),
  how often it reaches for things the core must refuse or confine: studio_api, require(),
  Node/NW.js/Electron objects, child processes, shell open, window.open and network calls.
  These feed the risk list (Droidtop/tracker#868).
"""
import argparse
import collections
import io
import json
import os
import re
import struct
import sys
import zipfile

READ_LIMIT = 32 << 20  # no single file is read past this

RISKS = {
    "studio_api": re.compile(r"\bstudio_api\b"),
    "studio_api.fs": re.compile(r"\bstudio_api\s*\.\s*fs\b"),
    "require": re.compile(r"\brequire\s*\(\s*['\"]"),
    "node_fs": re.compile(r"\brequire\s*\(\s*['\"](?:node:)?fs['\"]"),
    "child_process": re.compile(r"\bchild_process\b"),
    "nw": re.compile(r"\bnw\s*\.\s*(?:Shell|Window|App|Menu|Tray|Clipboard)\b"),
    "electron": re.compile(r"\belectron\b"),
    "shell_open": re.compile(r"\b(?:openExternal|openItem|openPath|Shell\s*\.\s*openExternal)\b"),
    "process": re.compile(r"\bprocess\s*\.\s*(?:env|exit|argv|execPath|platform)\b"),
    "window.open": re.compile(r"\bwindow\s*\.\s*open\s*\("),
    "network": re.compile(r"\b(?:XMLHttpRequest|fetch\s*\(|WebSocket|navigator\s*\.\s*sendBeacon)|https?://"),
}
TAG_RE = re.compile(r"\[([A-Za-z_][A-Za-z0-9_]*)")
AT_TAG_RE = re.compile(r"^\s*@([A-Za-z_][A-Za-z0-9_]*)")
VERSION_RES = [
    re.compile(r"""TyranoScript\s*(?:Ver(?:sion)?\.?\s*)?v?(\d+(?:\.\d+)*[a-z]?)""", re.I),
    re.compile(r"""\bversion\s*[:=]\s*['"]?(\d{3,})['"]?"""),
]


# ---------------------------------------------------------------- where a game's files are

class Source:
    """Case-insensitive read-only view of one game's files."""

    def __init__(self, kind, label):
        self.kind, self.label = kind, label
        self._names = {}  # lower-case path -> real key

    def _index(self, names):
        for n in names:
            n = n.replace("\\", "/").lstrip("/")
            if n and not n.endswith("/"):
                self._names.setdefault(n.lower(), n)

    def paths(self):
        return list(self._names.values())

    def has(self, path):
        return path.lower() in self._names

    def read(self, path):
        return self._read(self._names[path.lower()])


class FolderSource(Source):
    def __init__(self, root):
        super().__init__("folder", root)
        self.root = root
        names = []
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d.lower() not in ("save", "savedata", ".git")]
            for f in fns:
                names.append(os.path.relpath(os.path.join(dp, f), root).replace(os.sep, "/"))
        self._index(names)

    def _read(self, key):
        with open(os.path.join(self.root, key), "rb") as f:
            return f.read(READ_LIMIT)


class ZipSource(Source):
    """A zip, whole (package.nw) or appended to an NW.js .exe; zipfile finds the directory from the end."""

    def __init__(self, path, kind):
        super().__init__(kind, path)
        self.zip = zipfile.ZipFile(path)
        self._index(self.zip.namelist())

    def _read(self, key):
        with self.zip.open(key) as f:
            return f.read(READ_LIMIT)


class AsarSource(Source):
    """Electron's asar: u32 4, u32 header pickle size, then a pickled JSON header and the files."""

    def __init__(self, path):
        super().__init__("asar", path)
        self.path = path
        with open(path, "rb") as f:
            head = f.read(16)
            if len(head) < 16:
                raise ValueError("not an asar")
            header_size = struct.unpack_from("<I", head, 4)[0]
            json_size = struct.unpack_from("<I", head, 12)[0]
            if json_size > 64 << 20:
                raise ValueError("asar header too large")
            header = json.loads(f.read(json_size).decode("utf-8"))
        self.base = 8 + header_size
        self.files = {}

        def walk(node, prefix):
            for name, entry in node.get("files", {}).items():
                p = prefix + name
                if "files" in entry:
                    walk(entry, p + "/")
                elif not entry.get("unpacked"):
                    self.files[p] = (int(entry.get("offset", 0)), int(entry.get("size", 0)))

        walk(header, "")
        self._index(self.files)

    def _read(self, key):
        off, size = self.files[key]
        with open(self.path, "rb") as f:
            f.seek(self.base + off)
            return f.read(min(size, READ_LIMIT))


def is_tyrano(src):
    paths = [p.lower() for p in src.paths()]
    return any(p.startswith("tyrano/") for p in paths) and any(p.startswith("data/") for p in paths)


def sources_in(folder):
    """Every Tyrano game whose files sit in this folder, however they are stored."""
    found = []
    try:
        entries = os.listdir(folder)
    except OSError:
        return found
    lower = {e.lower(): e for e in entries}
    if "tyrano" in lower and "data" in lower:
        found.append(FolderSource(folder))
        return found
    candidates = []
    if "package.nw" in lower:
        candidates.append(("package.nw", os.path.join(folder, lower["package.nw"])))
    for e in entries:
        if e.lower().endswith(".exe"):
            candidates.append(("exe", os.path.join(folder, e)))
    res = lower.get("resources")
    if res and os.path.isdir(os.path.join(folder, res)):
        for e in os.listdir(os.path.join(folder, res)):
            if e.lower() == "app.asar":
                candidates.append(("asar", os.path.join(folder, res, e)))
    for kind, path in candidates:
        try:
            src = AsarSource(path) if kind == "asar" else ZipSource(path, kind)
        except (zipfile.BadZipFile, ValueError, OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if is_tyrano(src):
            found.append(src)
    return found


# ---------------------------------------------------------------- reading one game

def text(data):
    for enc in ("utf-8-sig", "shift_jis", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def tyrano_config(src):
    """Config.tjs as Tyrano's own compileConfig reads it: ';key = value' lines."""
    path = "data/system/Config.tjs"
    if not src.has(path):
        return {}
    out = {}
    for line in text(src.read(path)).splitlines():
        line = line.strip()
        if not line.startswith(";"):
            continue
        parts = line.split("//")[0].strip().replace(";", "").replace('"', "").split("=")
        if len(parts) >= 2:
            out[parts[0].strip()] = parts[1].strip()
    return out


def engine_version(src):
    found = collections.Counter()
    for p in src.paths():
        lp = p.lower()
        if lp.startswith("tyrano/") and lp.endswith(".js") and lp.count("/") <= 2:
            head = text(src.read(p)[:65536])
            for rx in VERSION_RES:
                for m in rx.finditer(head):
                    found[m.group(1)] += 1
    return [v for v, _ in found.most_common(3)]


def scan_scenario(body, tags, iscript_js):
    """Count tags in a .ks file; collect the JavaScript of its [iscript] blocks."""
    in_script = False
    script = []
    for line in body.splitlines():
        s = line.strip()
        low = s.lower()
        if in_script:
            if low.startswith("[endscript") or low.startswith("@endscript"):
                in_script = False
                iscript_js.append("\n".join(script))
                script = []
                tags["endscript"] += 1
            else:
                script.append(line)
            continue
        if not s or s.startswith(";") or s.startswith("*"):
            continue
        m = AT_TAG_RE.match(line)
        if m:
            tags[m.group(1).lower()] += 1
            if m.group(1).lower() == "iscript":
                in_script = True
            continue
        for m in TAG_RE.finditer(line):
            name = m.group(1).lower()
            tags[name] += 1
            if name == "iscript":
                in_script = True
    if script:
        iscript_js.append("\n".join(script))


def survey_source(src):
    cfg = tyrano_config(src)
    game = {
        "path": src.label, "kind": src.kind, "version": engine_version(src),
        "title": cfg.get("System.title"), "configSave": cfg.get("configSave"),
        "screen": [cfg.get("scWidth") or cfg.get("ScreenWidth"), cfg.get("scHeight") or cfg.get("ScreenHeight")],
        "files": len(src.paths()), "tags": {}, "plugins": [], "iscriptBlocks": 0, "risks": {}, "riskFiles": {},
        "errors": [],
    }
    tags = collections.Counter()
    iscript = []
    plugins = set()
    risks = collections.Counter()
    risk_files = collections.defaultdict(set)
    for p in sorted(src.paths()):
        lp = p.lower()
        try:
            if lp.startswith("data/others/plugin/"):
                rest = p.split("/")[3:]
                if len(rest) > 1:
                    plugins.add(rest[0])
            if lp.endswith(".ks"):
                scan_scenario(text(src.read(p)), tags, iscript)
            # The game's own code: anything under data/ and the page itself. The stock engine under
            # tyrano/ is the same in every game and is read once, for the core, not per game.
            if (lp.startswith("data/") and lp.endswith(".js")) or lp in ("index.html", "main.js", "package.json"):
                body = text(src.read(p))
                for name, rx in RISKS.items():
                    n = len(rx.findall(body))
                    if n:
                        risks[name] += n
                        risk_files[name].add(p)
        except (OSError, KeyError, zipfile.BadZipFile, RuntimeError) as e:
            game["errors"].append(f"{p}: {e}")
    for block in iscript:
        for name, rx in RISKS.items():
            n = len(rx.findall(block))
            if n:
                risks[name] += n
                risk_files[name].add("[iscript]")
    game["tags"] = dict(tags.most_common())
    game["plugins"] = sorted(plugins)
    game["iscriptBlocks"] = len(iscript)
    game["risks"] = dict(risks)
    game["riskFiles"] = {k: sorted(v)[:20] for k, v in risk_files.items()}
    return game


def find_games(top, max_depth):
    games = []
    top_depth = top.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, _ in os.walk(top):
        if dirpath.count(os.sep) - top_depth >= max_depth:
            dirnames[:] = []
        srcs = sources_in(dirpath)
        if srcs:
            games.extend(srcs)
            dirnames[:] = []  # a game's own folders are not more games
    return games


def summarise(games):
    tags_total, tags_games = collections.Counter(), collections.Counter()
    risk_games = collections.Counter()
    plugins = collections.Counter()
    for g in games:
        for t, n in g["tags"].items():
            tags_total[t] += n
            tags_games[t] += 1
        for r in g["risks"]:
            risk_games[r] += 1
        for p in g["plugins"]:
            plugins[p] += 1
    return {
        "games": len(games),
        "kinds": dict(collections.Counter(g["kind"] for g in games)),
        "versions": dict(collections.Counter((g["version"] or ["unknown"])[0] for g in games).most_common()),
        "configSave": dict(collections.Counter(g["configSave"] or "unset" for g in games)),
        "tagsByUse": [{"tag": t, "uses": n, "games": tags_games[t]} for t, n in tags_total.most_common()],
        "plugins": dict(plugins.most_common()),
        "gamesWithRisk": dict(risk_games.most_common()),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("games_dir")
    ap.add_argument("--out", default="tyrano-survey.json")
    ap.add_argument("--max-depth", type=int, default=4)
    a = ap.parse_args(argv)
    games = []
    for src in find_games(a.games_dir, a.max_depth):
        try:
            games.append(survey_source(src))
        except Exception as e:  # one unreadable game must not end the survey
            games.append({"path": src.label, "kind": src.kind, "errors": [repr(e)], "tags": {}, "risks": {},
                          "plugins": [], "version": [], "configSave": None})
        print(f"{len(games):4d} {src.kind:10} {src.label}", file=sys.stderr)
    report = {"summary": summarise(games), "games": games}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1, ensure_ascii=False)
    s = report["summary"]
    print(f"{s['games']} games; saves {s['configSave']}; {len(s['tagsByUse'])} tags seen; report in {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
