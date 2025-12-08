package com.driftmc.scene;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Level;

import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.world.WorldPatchExecutor;

/**
 * Tracks active scene sessions per player and applies inverse patches when needed.
 */
final class SceneCleanupService {

    private final JavaPlugin plugin;
    private final WorldPatchExecutor world;
    private final Map<UUID, SceneSession> sessions = new ConcurrentHashMap<>();

    SceneCleanupService(JavaPlugin plugin, WorldPatchExecutor world) {
        this.plugin = plugin;
        this.world = world;
    }

    void beginSession(Player player, Map<String, Object> metadata, Map<String, Object> operations) {
        if (player == null || operations == null || operations.isEmpty()) {
            return;
        }
        UUID playerId = player.getUniqueId();
        SceneSession previous = sessions.remove(playerId);
        if (previous != null) {
            applyCleanup(player, previous, "previous_session");
        }

        SceneSession session = SceneSession.create(player, metadata, operations);
        if (session.buildCleanupPatch().isEmpty()) {
            plugin.getLogger().log(Level.FINE, "[SceneCleanup] Skip tracking; nothing to clean for player {0}", player.getName());
            return;
        }
        sessions.put(playerId, session);
        plugin.getLogger().log(Level.INFO, "[SceneCleanup] Tracked scene for player {0}", player.getName());
    }

    void cleanup(Player player, Map<String, Object> metadata) {
        if (player == null) {
            return;
        }
        UUID playerId = player.getUniqueId();
        boolean sceneExpected = metadata == null || Boolean.TRUE.equals(metadata.get("scene"));
        if (!sceneExpected && !sessions.containsKey(playerId)) {
            return;
        }
        SceneSession session = sessions.remove(playerId);
        if (session == null) {
            plugin.getLogger().log(Level.FINE, "[SceneCleanup] No tracked scene for player {0}", player.getName());
            return;
        }
        applyCleanup(player, session, "requested_cleanup");
    }

    void cleanupAll() {
        for (Map.Entry<UUID, SceneSession> entry : sessions.entrySet()) {
            UUID playerId = entry.getKey();
            Player player = Bukkit.getPlayer(playerId);
            if (player == null) {
                continue;
            }
            applyCleanup(player, entry.getValue(), "shutdown_cleanup");
        }
        sessions.clear();
    }

    private void applyCleanup(Player player, SceneSession session, String reason) {
        Map<String, Object> cleanup = session.buildCleanupPatch();
        if (cleanup.isEmpty()) {
            return;
        }
        plugin.getLogger().log(Level.INFO,
            "[SceneCleanup] Applying cleanup for player {0} due to {1}",
            new Object[]{player.getName(), reason});
        world.execute(player, cleanup);
        session.reset();
    }
}
