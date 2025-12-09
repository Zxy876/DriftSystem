package com.driftmc.scene;

import java.util.Map;
import java.util.Objects;
import java.util.logging.Level;

import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.cinematic.CinematicController;
import com.driftmc.npc.NPCManager;
import com.driftmc.world.WorldPatchExecutor;



/**
 * Coordinates scene application and cleanup for a player.
 */
public final class SceneLoader implements SceneLifecycleBridge {

    private final JavaPlugin plugin;
    private final SceneCleanupService cleanup;
    private final NPCManager npcManager;
    private CinematicController cinematicController;

    public SceneLoader(JavaPlugin plugin, WorldPatchExecutor world, NPCManager npcManager) {
        this.plugin = Objects.requireNonNull(plugin, "plugin");
        this.cleanup = new SceneCleanupService(plugin, Objects.requireNonNull(world, "world"));
        this.npcManager = Objects.requireNonNull(npcManager, "npcManager");
    }

    @Override
    public void handleScenePatch(Player player, Map<String, Object> metadata, Map<String, Object> operations) {
        if (player == null || operations == null || operations.isEmpty()) {
            return;
        }
        cleanup.beginSession(player, metadata, operations);
        npcManager.onScenePatch(player, metadata, operations);
        triggerCinematic(player, metadata, operations);
        plugin.getLogger().log(Level.FINE, "[SceneLoader] Scene applied for player {0}", player.getName());
    }

    @Override
    public void handleSceneCleanup(Player player, Map<String, Object> metadata) {
        if (player == null) {
            return;
        }
        cleanup.cleanup(player, metadata);
        npcManager.onSceneCleanup(player, metadata);
    }

    public void shutdown() {
        cleanup.cleanupAll();
    }

    public void setCinematicController(CinematicController cinematicController) {
        this.cinematicController = cinematicController;
    }

    public void handleCinematic(Player player, Map<String, Object> definition) {
        if (player == null || cinematicController == null || definition == null || definition.isEmpty()) {
            return;
        }
        Map<String, Object> copy = ScenePatchUtils.deepCopyMap(definition);
        cinematicController.playSequence(player, copy);
    }

    private void triggerCinematic(Player player, Map<String, Object> metadata, Map<String, Object> operations) {
        if (player == null || cinematicController == null) {
            return;
        }
        Map<String, Object> candidate = null;
        if (metadata != null) {
            Object metaCinematic = metadata.get("cinematic");
            if (metaCinematic instanceof Map<?, ?> map) {
                candidate = ScenePatchUtils.deepCopyMap(map);
            }
        }
        if (candidate == null && operations != null) {
            Object opCinematic = operations.get("_cinematic");
            if (opCinematic instanceof Map<?, ?> map) {
                candidate = ScenePatchUtils.deepCopyMap(map);
            }
        }
        if (candidate != null && !candidate.isEmpty()) {
            cinematicController.playSequence(player, candidate);
        }
    }
}
