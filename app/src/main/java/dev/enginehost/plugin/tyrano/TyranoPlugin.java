package dev.enginehost.plugin.tyrano;

import android.view.KeyEvent;
import android.webkit.WebView;
import dev.enginehost.api.EngineControllerEvent;
import dev.enginehost.api.EnginePlugin;
import dev.enginehost.api.EnginePluginSession;
import dev.enginehost.web.GameServer;
import dev.enginehost.web.GameWebView;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * TyranoScript games, on a core of their own (Droidtop/tracker#868; the owner: "Tyrano should get
 * its own core too").
 *
 * A Tyrano game ships its own engine (tyrano/) and runs it in a browser, so the browser, the
 * private https origin, the save-folder localStorage and the link sheet are Enginehost's plugin-web
 * ({@link GameWebView}), as for the HTML core. What this core adds is what a game's PC build has
 * and a WebView does not: a game whose Config.tjs says {@code configSave = file} saves through
 * Node's fs in its NW.js or Electron build. For those games {@link PcBuildShim} answers fs, path,
 * process and studio_api from a store kept in the game's save folder, and nothing else: no real
 * file outside it, no processes, no native modules (docs/behaviour/risks.md).
 */
public final class TyranoPlugin implements EnginePlugin {
    private static final String TAG = "enginehost-tyrano";

    private GameWebView game;

    @Override
    public void onCreate(EnginePluginSession session) throws Exception {
        if (!"tyranoscript".equals(session.engine())) {
            throw new IOException("This runtime runs TyranoScript games, not " + session.engine());
        }
        Map<String, String> config = readConfig(new File(session.gamePath()));
        boolean fileSaves = "file".equals(config.get("configSave"));
        session.host().log(android.util.Log.INFO, TAG,
            "Tyrano game: configSave=" + config.getOrDefault("configSave", "(unset)")
                + (fileSaves ? "; its file saves go to the save folder" : ""), null);
        String pageScript = fileSaves ? PcBuildShim.script() : "";
        game = GameWebView.open(session, TAG, new GameServer.Site() {
            @Override public String[] entryPages() { return new String[] {"index.html", "index.htm"}; }
            @Override public String pageScript() { return pageScript; }
        });
        WebView view = game.view();
        view.setFocusableInTouchMode(true);
        view.requestFocus();
    }

    /**
     * data/system/Config.tjs as Tyrano's own compileConfig reads it: every line starting with ';'
     * is {@code ;key = value}, comments after //, quotes dropped. Missing or unreadable: empty.
     */
    static Map<String, String> readConfig(File gameRoot) {
        Map<String, String> out = new LinkedHashMap<>();
        File file = findIgnoringCase(gameRoot, "data", "system", "Config.tjs");
        if (file == null) return out;
        String text;
        try {
            text = new String(GameServer.readAll(file), StandardCharsets.UTF_8);
        } catch (IOException error) {
            return out;
        }
        for (String raw : text.split("\r?\n")) {
            String line = raw.trim();
            if (!line.startsWith(";")) continue;
            int comment = line.indexOf("//");
            if (comment >= 0) line = line.substring(0, comment);
            String[] parts = line.trim().replace(";", "").replace("\"", "").split("=");
            if (parts.length >= 2) out.put(parts[0].trim(), parts[1].trim());
        }
        return out;
    }

    /** A path below root whose names match ignoring case, as Windows games are written; null if absent. */
    static File findIgnoringCase(File root, String... names) {
        File current = root;
        for (String name : names) {
            File exact = new File(current, name);
            if (exact.exists()) { current = exact; continue; }
            String[] children = current.list();
            File match = null;
            if (children != null) {
                for (String child : children) {
                    if (child.equalsIgnoreCase(name)) { match = new File(current, child); break; }
                }
            }
            if (match == null) return null;
            current = match;
        }
        return current.isFile() ? current : null;
    }

    @Override public boolean onControllerEvent(EngineControllerEvent event) {
        // Tyrano's own keyboard: Enter and Space advance and confirm, Escape opens the menu, the
        // arrows move between choices and buttons where the game uses keyboard focus.
        int key;
        switch (event.action()) {
            case "up": key = KeyEvent.KEYCODE_DPAD_UP; break;
            case "down": key = KeyEvent.KEYCODE_DPAD_DOWN; break;
            case "left": case "page_previous": key = KeyEvent.KEYCODE_DPAD_LEFT; break;
            case "right": case "page_next": key = KeyEvent.KEYCODE_DPAD_RIGHT; break;
            case "confirm": key = KeyEvent.KEYCODE_ENTER; break;
            case "cancel": case "menu": key = KeyEvent.KEYCODE_ESCAPE; break;
            default: return false;
        }
        WebView view = game == null ? null : game.view();
        if (view == null) return false;
        int action = event.pressed() ? KeyEvent.ACTION_DOWN : KeyEvent.ACTION_UP;
        return view.dispatchKeyEvent(new KeyEvent(event.eventTime(), event.eventTime(), action, key, 0));
    }

    @Override public void onResume() { if (game != null) game.onResume(); }

    @Override public void onPause() { if (game != null) game.onPause(); }

    @Override public void onDestroy() { if (game != null) game.onDestroy(); }
}
