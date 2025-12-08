package com.driftmc.scene;

import java.util.Map;
import java.util.Objects;
import java.util.logging.Level;

import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.world.WorldPatchExecutor;

/**
 * Coordinates scene application and cleanup for a player.
 */
public final class SceneLoader implements SceneLifecycleBridge {

    private final JavaPlugin plugin;
    private final SceneCleanupService cleanup;

    public SceneLoader(JavaPlugin plugin, WorldPatchExecutor world) {
        this.plugin = Objects.requireNonNull(plugin, "plugin");
        this.cleanup = new SceneCleanupService(plugin, Objects.requireNonNull(world, "world"));
    }

    @Override
    public void handleScenePatch(Player player, Map<String, Object> metadata, Map<String, Object> operations) {
        if (player == null || operations == null || operations.isEmpty()) {
            return;
        }
        cleanup.beginSession(player, metadata, operations);
        plugin.getLogger().log(Level.FINE, "[SceneLoader] Scene applied for player {0}", player.getName());
    }

    @Override
    public void handleSceneCleanup(Player player, Map<String, Object> metadata) {
        if (player == null) {
            return;
        }
        cleanup.cleanup(player, metadata);
    }

    public void shutdown() {
        cleanup.cleanupAll();
    }
}
