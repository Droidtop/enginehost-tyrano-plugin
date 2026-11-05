plugins { id("com.android.library") }

// Enginehost's web game host (GameWebView, GameServer, LocalStorageBridge), compiled into this core:
// checked out with the plugin API into build/enginehost by the plugin-api action the workflow pins
// (as the HTML and RPG Maker MV/MZ cores do).
val enginehostWeb = rootProject.file("build/enginehost/plugin-web/src/main/java")
check(enginehostWeb.isDirectory) {
    "Enginehost's plugin-web is not checked out: clone Droidtop/enginehost into build/enginehost at the " +
        "commit .github/workflows/android.yml pins its plugin-api action to"
}

android {
    namespace = "dev.enginehost.plugin.tyrano"
    compileSdk = 36
    defaultConfig {
        minSdk = 26
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    sourceSets.getByName("main").java.srcDir(enginehostWeb)
}

dependencies {
    compileOnly(project(":api"))
}
