package dev.enginehost.plugin.tyrano;

/**
 * What a Tyrano game's PC build gives its scripts, for a game that saves to files
 * ({@code configSave = file}), answered inside the WebView and confined to the save folder.
 *
 * A PC build runs Tyrano in NW.js or Electron, where {@code require('fs')} and
 * {@code window.studio_api.fs} reach the disk and {@code process.execPath} says where the game
 * is. Here every file such a script writes or reads lives in a virtual tree stored in the game's
 * save-folder store (plugin-web's LocalStorageBridge, window.EnginehostStorage), under keys that
 * begin with {@link #PREFIX}. No real file is opened, so nothing outside the save folder can be
 * read or written, whatever path a script names. Paths are kept as written, with \ made /.
 *
 * Provided: fs (readFileSync, writeFileSync, appendFileSync, existsSync, mkdirSync, unlinkSync,
 * readdirSync, statSync, and the callback forms readFile, writeFile, exists, unlink, mkdir),
 * path (join, dirname, basename, extname, resolve, sep), process (execPath, platform, argv, env,
 * cwd, exit), nw.gui / nw.Window.get() and Electron's remote window as no-op stubs, and
 * window.studio_api.fs as the same fs. Refused, with an Error: any other module,
 * child_process above all (docs/behaviour/risks.md). Every first use of a name is logged to the
 * console (EnginehostTyrano), which plugin-web forwards to logcat, so a rig run shows what a game
 * actually calls.
 */
final class PcBuildShim {
    static final String PREFIX = "enginehost-tyrano-file:";

    private PcBuildShim() {}

    static String script() {
        return SCRIPT.replace("@PREFIX@", PREFIX);
    }

    private static final String SCRIPT = """
        (function(){
        if (window.__enginehostTyrano) return; window.__enginehostTyrano = true;
        var bridge = window.EnginehostStorage; if (!bridge) return;
        var P = '@PREFIX@', seen = {};
        function note(name){ if (!seen[name]) { seen[name] = 1; console.log('EnginehostTyrano: ' + name); } }
        function norm(p){ p = String(p).replace(/\\\\/g, '/'); while (p.indexOf('//') >= 0) p = p.replace('//', '/'); return p.replace(/\\/$/, ''); }
        function key(p){ return P + 'f:' + norm(p); }
        function dkey(p){ return P + 'd:' + norm(p); }
        function enoent(op, p){ var e = new Error("ENOENT: no such file or directory, " + op + " '" + p + "'"); e.code = 'ENOENT'; return e; }
        function text(v, enc){ if (v == null) return ''; if (typeof v === 'string') return v; try { return new TextDecoder().decode(v); } catch (e) { return String(v); } }
        function bytes(s){ try { return new TextEncoder().encode(s); } catch (e) { return s; } }
        function markDirs(p){ var parts = norm(p).split('/'); for (var i = 1; i < parts.length; i++) bridge.setItem(dkey(parts.slice(0, i).join('/')), '1'); }
        var fs = {
          readFileSync: function(p, o){ note('fs.readFileSync'); var v = bridge.getItem(key(p)); if (v == null) throw enoent('open', p);
            var enc = typeof o === 'string' ? o : (o && o.encoding); return enc ? v : bytes(v); },
          writeFileSync: function(p, d){ note('fs.writeFileSync'); markDirs(p); bridge.setItem(key(p), text(d)); },
          appendFileSync: function(p, d){ note('fs.appendFileSync'); var v = bridge.getItem(key(p)) || ''; markDirs(p); bridge.setItem(key(p), v + text(d)); },
          existsSync: function(p){ note('fs.existsSync'); return bridge.getItem(key(p)) != null || bridge.getItem(dkey(p)) != null; },
          mkdirSync: function(p){ note('fs.mkdirSync'); markDirs(norm(p) + '/x'); bridge.setItem(dkey(p), '1'); },
          unlinkSync: function(p){ note('fs.unlinkSync'); if (bridge.getItem(key(p)) == null) throw enoent('unlink', p); bridge.removeItem(key(p)); },
          readdirSync: function(p){ note('fs.readdirSync'); var base = norm(p) + '/', out = {}, all = JSON.parse(bridge.load() || '{}');
            Object.keys(all).forEach(function(k){ if (k.indexOf(P) !== 0) return; var path = k.slice(P.length + 2);
              if (path.indexOf(base) === 0) out[path.slice(base.length).split('/')[0]] = 1; });
            return Object.keys(out); },
          statSync: function(p){ note('fs.statSync'); var f = bridge.getItem(key(p)), d = bridge.getItem(dkey(p));
            if (f == null && d == null) throw enoent('stat', p);
            return { size: f == null ? 0 : f.length, isFile: function(){ return f != null; }, isDirectory: function(){ return f == null; }, mtime: new Date() }; }
        };
        function cb(fn){ return function(){ var a = [].slice.call(arguments), done = typeof a[a.length - 1] === 'function' ? a.pop() : null;
          var r, err = null; try { r = fn.apply(fs, a); } catch (e) { err = e; } if (done) setTimeout(function(){ done(err, r); }, 0); }; }
        fs.readFile = cb(fs.readFileSync); fs.writeFile = cb(fs.writeFileSync); fs.unlink = cb(fs.unlinkSync); fs.mkdir = cb(fs.mkdirSync);
        fs.exists = function(p, done){ var r = fs.existsSync(p); if (done) setTimeout(function(){ done(r); }, 0); };
        var path = {
          sep: '/',
          join: function(){ note('path.join'); return norm([].slice.call(arguments).join('/')); },
          resolve: function(){ note('path.resolve'); return norm([].slice.call(arguments).join('/')); },
          dirname: function(p){ p = norm(p); var i = p.lastIndexOf('/'); return i > 0 ? p.slice(0, i) : '.'; },
          basename: function(p, ext){ p = norm(p); var b = p.slice(p.lastIndexOf('/') + 1); return ext && b.slice(-ext.length) === ext ? b.slice(0, -ext.length) : b; },
          extname: function(p){ var b = path.basename(p), i = b.lastIndexOf('.'); return i > 0 ? b.slice(i) : ''; }
        };
        // Any member of a stub is a no-op that returns the stub, so window calls (maximize,
        // fullscreen, on('close')) neither fail nor do anything.
        function stub(name){ var s = new Proxy(function(){}, { get: function(t, k){ if (k === 'then') return undefined; note(name + '.' + String(k)); return s; },
          apply: function(){ return s; } }); return s; }
        var nwgui = { Window: { get: function(){ note('nw.Window.get'); return stub('nw.window'); } }, App: stub('nw.App'), Shell: { openExternal: function(u){ note('nw.Shell.openExternal'); window.open(u); } } };
        var proc = { execPath: '/enginehost/game/Game.exe', platform: 'win32', argv: [], env: {}, versions: {}, cwd: function(){ return '/enginehost/game'; },
          exit: function(){ note('process.exit'); }, on: function(){ return proc; } };
        var modules = { fs: fs, 'node:fs': fs, path: path, 'node:path': path, 'nw.gui': nwgui };
        window.require = function(name){ note('require(' + name + ')');
          if (Object.prototype.hasOwnProperty.call(modules, name)) return modules[name];
          throw new Error("Enginehost's Tyrano core does not provide the module '" + name + "'"); };
        if (typeof window.process === 'undefined') window.process = proc;
        if (typeof window.nw === 'undefined') window.nw = nwgui;
        window.studio_api = window.studio_api || { fs: fs, path: path };
        })();
        """;
}
