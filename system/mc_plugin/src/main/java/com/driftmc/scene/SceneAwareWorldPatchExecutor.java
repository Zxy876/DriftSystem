package com.driftmc.scene;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.cinematic.CinematicController;
import com.driftmc.npc.NPCManager;
import com.driftmc.world.WorldPatchExecutor;

/**
 * Wrapper over {@link WorldPatchExecutor} that inspects scene metadata before executing patches.
 */
public final class SceneAwareWorldPatchExecutor extends WorldPatchExecutor {

    private final SceneLoader sceneLoader;

    public SceneAwareWorldPatchExecutor(JavaPlugin plugin, NPCManager npcManager) {
        super(plugin);
        this.sceneLoader = new SceneLoader(plugin, this, npcManager);
    }

    @Override
    public void execute(Player player, Map<String, Object> patch) {
        if (player != null && patch != null && !patch.isEmpty()) {
            inspectObject(player, patch);
            Object mcObj = patch.get("mc");
            if (mcObj instanceof Map) {
                inspectObject(player, (Map<?, ?>) mcObj);
            } else if (mcObj instanceof List) {
                List<?> list = (List<?>) mcObj;
                for (Object entry : list) {
                    if (entry instanceof Map) {
                        inspectObject(player, (Map<?, ?>) entry);
                    }
                }
            }
        }
        super.execute(player, patch);
    }

    public void shutdown() {
        sceneLoader.shutdown();
    }

    private void inspectObject(Player player, Object candidate) {
        if (!(candidate instanceof Map<?, ?>)) {
            return;
        }
        Map<String, Object> operations = filterStringKeys((Map<?, ?>) candidate);
        if (operations.isEmpty()) {
            return;
        }

        boolean sceneHandled = false;

        Object cleanup = operations.get("_scene_cleanup");
        if (cleanup instanceof Map<?, ?> cleanupMap) {
            sceneLoader.handleSceneCleanup(player, filterStringKeys(cleanupMap));
        }

        Object scene = operations.get("_scene");
        if (scene instanceof Map<?, ?> sceneMap) {
            sceneLoader.handleScenePatch(player, filterStringKeys(sceneMap), operations);
            sceneHandled = true;
        }

        Object cinematic = operations.get("_cinematic");
        if (cinematic instanceof Map<?, ?> cinematicMap) {
            if (!sceneHandled) {
                sceneLoader.handleCinematic(player, filterStringKeys(cinematicMap));
            }
        }
    }

    private Map<String, Object> filterStringKeys(Map<?, ?> source) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (Map.Entry<?, ?> entry : source.entrySet()) {
            Object key = entry.getKey();
            if (key instanceof String keyStr) {
                result.put(keyStr, entry.getValue());
            }
        }
        return result;
    }

    public void attachCinematicController(CinematicController controller) {
        this.sceneLoader.setCinematicController(controller);
    }
}
