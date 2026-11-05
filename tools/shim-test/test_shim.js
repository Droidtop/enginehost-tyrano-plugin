// Runs PcBuildShim's script (from PrintShim) against a mock of plugin-web's EnginehostStorage and
// checks what a Tyrano PC build's save code relies on. Usage: node test_shim.js <script file>
'use strict';
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const store = {};
const bridge = {
  load: () => JSON.stringify(store),
  getItem: (k) => (Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: (k) => { delete store[k]; },
};
const logs = [];
const opened = [];
const window = { EnginehostStorage: bridge, open: (u) => opened.push(u) };
const ctx = vm.createContext({
  window, console: { log: (m) => logs.push(m) }, setTimeout, TextEncoder, TextDecoder, Proxy, JSON, Object, Error, Date, String,
});
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), ctx);

const nodeFs = window.require('fs');
const path = window.require('path');
assert.strictEqual(window.studio_api.fs, nodeFs);

// Tyrano's file saves: a .sav beside the exe, written escaped, read back as text.
const dir = path.dirname(window.process.execPath);
const sav = path.join(dir, 'savedata', 'tyrano_data.sav');
assert.strictEqual(nodeFs.existsSync(sav), false);
assert.throws(() => nodeFs.readFileSync(sav, 'utf-8'), (e) => e.code === 'ENOENT');
nodeFs.writeFileSync(sav, escape('{"slot":1}'));
assert.strictEqual(nodeFs.existsSync(sav), true);
assert.strictEqual(unescape(nodeFs.readFileSync(sav, 'utf-8')), '{"slot":1}');
assert.strictEqual(nodeFs.existsSync(path.join(dir, 'savedata')), true, 'a written file makes its folder exist');
assert.deepStrictEqual(nodeFs.readdirSync(path.join(dir, 'savedata')), ['tyrano_data.sav']);
assert.ok(nodeFs.statSync(sav).isFile());
// Windows separators name the same file.
assert.strictEqual(unescape(nodeFs.readFileSync(sav.replace(/\//g, '\\'), 'utf-8')), '{"slot":1}');

// Every file lives in the save-folder store, under the core's prefix; nothing else is touched.
for (const k of Object.keys(store)) assert.ok(k.startsWith('enginehost-tyrano-file:'), k);
// A path outside the game is just another key in the store, never a real file.
nodeFs.writeFileSync('C:\\Windows\\system.ini', 'x');
assert.ok(Object.keys(store).some((k) => k.endsWith('C:/Windows/system.ini')));

nodeFs.unlinkSync(sav);
assert.strictEqual(nodeFs.existsSync(sav), false);

// Refused: anything but fs, path and nw.gui.
assert.throws(() => window.require('child_process'), /does not provide the module 'child_process'/);
assert.throws(() => window.require('electron'), /does not provide/);

// Window calls are harmless no-ops; shell open goes through window.open, which plugin-web offers.
const win = window.require('nw.gui').Window.get();
win.maximize(); win.on('close', () => {}).enterFullscreen();
window.nw.Shell.openExternal('https://example.com');
assert.deepStrictEqual(opened, ['https://example.com']);

// What the game used is logged once per name.
assert.ok(logs.includes('EnginehostTyrano: fs.writeFileSync'));
assert.strictEqual(logs.filter((l) => l === 'EnginehostTyrano: fs.writeFileSync').length, 1);

// Callback forms.
nodeFs.writeFile('a.txt', 'hi', (err) => {
  assert.strictEqual(err, null);
  nodeFs.readFile('a.txt', 'utf8', (err2, v) => {
    assert.strictEqual(err2, null);
    assert.strictEqual(v, 'hi');
    console.log('shim ok:', logs.length, 'names logged');
  });
});
