package dev.enginehost.plugin.tyrano;

/** Prints PcBuildShim's script, for test_shim.js. Compiled with plain javac (no Android classes). */
public final class PrintShim {
    public static void main(String[] args) { System.out.print(PcBuildShim.script()); }
}
