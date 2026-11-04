import io
import json
import os
import struct
import tempfile
import unittest
import zipfile

import tyrano_survey as ts

CONFIG = """;System.title = My Story
;scWidth = 1280
;scHeight = 720
;configSave = file // saves to files
"""
FIRST_KS = """*start
[cm]
[bg storage="room.jpg" time=500]
@playbgm storage=bgm1.ogg
Hello[p]
; a comment [notatag]
[iscript]
var fs = require('fs'); window.open("https://example.com");
tf.x = 1;
[endscript]
[jump target=*start]
"""
GAME = {
    "index.html": "<script src='tyrano/libs.js'></script>",
    "tyrano/tyrano.js": "/* TyranoScript Ver5.21 */ var tyrano = {};",
    "data/system/Config.tjs": CONFIG,
    "data/scenario/first.ks": FIRST_KS,
    "data/others/plugin/theme_kopanda/init.ks": "[macro name=x][endmacro]",
    "data/others/plugin/theme_kopanda/main.js": "window.studio_api.fs.writeFile('a','b');",
}


def write_folder(root, files):
    for p, body in files.items():
        full = os.path.join(root, p)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(body)


def zip_bytes(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for p, body in files.items():
            z.writestr(p, body)
    return buf.getvalue()


def asar_bytes(files):
    tree, blob, off = {"files": {}}, b"", 0
    for p, body in files.items():
        node = tree
        parts = p.split("/")
        for d in parts[:-1]:
            node = node["files"].setdefault(d, {"files": {}})
        data = body.encode()
        node["files"][parts[-1]] = {"size": len(data), "offset": str(off)}
        blob += data
        off += len(data)
    header = json.dumps(tree).encode()
    pad = (4 - len(header) % 4) % 4
    pickle = struct.pack("<II", len(header) + 4 + pad, len(header)) + header + b"\0" * pad
    return struct.pack("<II", 4, len(pickle)) + pickle + blob


class Survey(unittest.TestCase):
    def check(self, g):
        self.assertEqual(g["title"], "My Story")
        self.assertEqual(g["configSave"], "file")
        self.assertEqual(g["screen"], ["1280", "720"])
        self.assertEqual(g["version"][0], "5.21")
        self.assertEqual(g["plugins"], ["theme_kopanda"])
        self.assertEqual(g["tags"]["bg"], 1)
        self.assertEqual(g["tags"]["playbgm"], 1)
        self.assertNotIn("notatag", g["tags"])
        self.assertEqual(g["iscriptBlocks"], 1)
        self.assertGreaterEqual(g["risks"]["studio_api.fs"], 1)
        self.assertEqual(g["risks"]["node_fs"], 1)
        self.assertEqual(g["risks"]["window.open"], 1)
        self.assertIn("[iscript]", g["riskFiles"]["require"])

    def test_every_way_a_game_is_stored(self):
        with tempfile.TemporaryDirectory() as top:
            write_folder(os.path.join(top, "folder-game"), GAME)
            os.makedirs(os.path.join(top, "nw-game"))
            with open(os.path.join(top, "nw-game", "package.nw"), "wb") as f:
                f.write(zip_bytes(GAME))
            os.makedirs(os.path.join(top, "exe-game"))
            with open(os.path.join(top, "exe-game", "Game.exe"), "wb") as f:
                f.write(b"MZ" + b"\0" * 4096 + zip_bytes(GAME))
            os.makedirs(os.path.join(top, "electron-game", "resources"))
            with open(os.path.join(top, "electron-game", "resources", "app.asar"), "wb") as f:
                f.write(asar_bytes(GAME))
            os.makedirs(os.path.join(top, "not-a-game"))
            with open(os.path.join(top, "not-a-game", "Other.exe"), "wb") as f:
                f.write(b"MZ" + b"\0" * 100)
            out = os.path.join(top, "r.json")
            self.assertEqual(ts.main([top, "--out", out]), 0)
            with open(out, encoding="utf-8") as f:
                report = json.load(f)
            kinds = sorted(g["kind"] for g in report["games"])
            self.assertEqual(kinds, ["asar", "exe", "folder", "package.nw"])
            for g in report["games"]:
                with self.subTest(kind=g["kind"]):
                    self.check(g)
            s = report["summary"]
            self.assertEqual(s["configSave"], {"file": 4})
            self.assertEqual(s["gamesWithRisk"]["studio_api.fs"], 4)

    def test_nothing_in_a_game_is_written(self):
        with tempfile.TemporaryDirectory() as top, tempfile.TemporaryDirectory() as outdir:
            g = os.path.join(top, "g")
            write_folder(g, GAME)
            before = {os.path.join(dp, f): os.path.getmtime(os.path.join(dp, f))
                      for dp, _, fs in os.walk(g) for f in fs}
            ts.main([top, "--out", os.path.join(outdir, "r.json")])
            after = {os.path.join(dp, f): os.path.getmtime(os.path.join(dp, f))
                     for dp, _, fs in os.walk(g) for f in fs}
            self.assertEqual(before, after)

    def test_config_reads_like_tyranos_own_compile_config(self):
        with tempfile.TemporaryDirectory() as d:
            write_folder(d, {"tyrano/a.js": "", "data/system/Config.tjs": ';configSave = "webstorage" // x\nnot;a=b\n'})
            cfg = ts.tyrano_config(ts.FolderSource(d))
        self.assertEqual(cfg, {"configSave": "webstorage"})


if __name__ == "__main__":
    unittest.main()
