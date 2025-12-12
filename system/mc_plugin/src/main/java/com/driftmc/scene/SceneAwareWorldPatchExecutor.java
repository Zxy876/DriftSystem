package com.driftmc.scene;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.metadata.FixedMetadataValue;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.cinematic.CinematicController;
import com.driftmc.npc.NPCManager;
import com.driftmc.world.WorldPatchExecutor;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;

/**
 * Wrapper over {@link WorldPatchExecutor} that inspects scene metadata before executing patches.
 */
public final class SceneAwareWorldPatchExecutor extends WorldPatchExecutor {

    private final SceneLoader sceneLoader;
    private final NPCManager npcManager;
    private Map<String, Object> currentRawOperations;

    public SceneAwareWorldPatchExecutor(JavaPlugin plugin, NPCManager npcManager) {
        super(plugin);
        this.npcManager = npcManager;
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

    @Override
    public void shutdown() {
        super.shutdown();
        sceneLoader.shutdown();
    }

    @Override
    public void ensureFeaturedNpc(Player player, Map<String, Object> metadata, Map<String, Object> operationsView) {
        if (currentRawOperations == null || metadata == null || operationsView == null || operationsView.isEmpty()) {
            return;
        }
        maybeInjectFeaturedNpc(metadata, operationsView, currentRawOperations);
    }

    private void maybeInjectFeaturedNpc(Map<String, Object> metadata,
                                        Map<String, Object> operationsView,
                                        Map<String, Object> rawOperations) {
        String featuredNpc = cleanString(metadata.get("featured_npc"));
        if (featuredNpc.isEmpty()) {
            return;
        }

        List<Map<String, Object>> skinDefinitions = extractNpcSkinDefinitions(metadata);
        if (skinDefinitions.isEmpty()) {
            skinDefinitions = extractNpcSkinDefinitions(operationsView);
        }
        if (skinDefinitions.isEmpty()) {
            return;
        }

        Map<String, Object> skinDefinition = findSkinDefinition(skinDefinitions, featuredNpc);
        if (skinDefinition == null) {
            return;
        }

        if (hasExistingSpawn(rawOperations, featuredNpc)) {
            ensureNpcTriggerEvents(metadata, operationsView, rawOperations);
            return;
        }

        Map<String, Object> spawnDirective = buildSpawnDirective(metadata, skinDefinition, featuredNpc);
        appendSpawn(rawOperations, spawnDirective);
        appendSpawn(operationsView, new LinkedHashMap<>(spawnDirective));
        ensureNpcTriggerEvents(metadata, operationsView, rawOperations);
    }

    private List<Map<String, Object>> extractNpcSkinDefinitions(Map<String, Object> source) {
        if (source == null || source.isEmpty()) {
            return Collections.emptyList();
        }
        Object raw = source.get("npc_skins");
        if (!(raw instanceof List<?> list) || list.isEmpty()) {
            return Collections.emptyList();
        }
        List<Map<String, Object>> result = new ArrayList<>();
        for (Object entry : list) {
            if (entry instanceof Map<?, ?> map) {
                result.add(filterStringKeys(map));
            }
        }
        return result;
    }

    private Map<String, Object> findSkinDefinition(List<Map<String, Object>> skins, String npcName) {
        if (skins == null) {
            return null;
        }
        String target = normalize(npcName);
        for (Map<String, Object> skin : skins) {
            String id = cleanString(skin.get("id"));
            if (!id.isEmpty() && normalize(id).equals(target)) {
                return skin;
            }
            String name = cleanString(skin.get("name"));
            if (!name.isEmpty() && normalize(name).equals(target)) {
                return skin;
            }
        }
        return null;
    }

    private Map<String, Object> buildSpawnDirective(Map<String, Object> metadata,
                                                    Map<String, Object> skinDefinition,
                                                    String npcName) {
        Map<String, Object> spawn = new LinkedHashMap<>();
        String type = cleanString(skinDefinition.get("type"));
        if (type.isEmpty()) {
            type = "player_like";
        }
        spawn.put("type", type);
        spawn.put("name", npcName);
        String npcId = cleanString(skinDefinition.get("id"));
        if (!npcId.isEmpty()) {
            spawn.put("id", npcId);
        }
        spawn.put("_auto_featured", Boolean.TRUE);

        Map<String, Object> offset = resolveOffset(metadata, skinDefinition);
        spawn.put("offset", offset);
        return spawn;
    }

    private Map<String, Object> resolveOffset(Map<String, Object> metadata, Map<String, Object> skinDefinition) {
        Map<String, Object> offset = new LinkedHashMap<>();

        Map<String, Object> providedOffset = castToMap(skinDefinition.get("offset"));
        if (providedOffset != null && !providedOffset.isEmpty()) {
            offset.put("dx", asDoubleOrDefault(providedOffset.get("dx"), 1.5));
            offset.put("dy", asDoubleOrDefault(providedOffset.get("dy"), 0.0));
            offset.put("dz", asDoubleOrDefault(providedOffset.get("dz"), 0.5));
            return offset;
        }

        Double dx = null;
        Double dy = null;
        Double dz = null;

        Map<String, Object> teleport = castToMap(metadata.get("teleport"));
        Double x = asNullableDouble(skinDefinition.get("x"));
        Double y = asNullableDouble(skinDefinition.get("y"));
        Double z = asNullableDouble(skinDefinition.get("z"));
        if (teleport != null && x != null && y != null && z != null) {
            Double tx = asNullableDouble(teleport.get("x"));
            Double ty = asNullableDouble(teleport.get("y"));
            Double tz = asNullableDouble(teleport.get("z"));
            if (tx != null && ty != null && tz != null) {
                dx = x - tx;
                dy = y - ty;
                dz = z - tz;
            }
        }

        if (dx == null || dy == null || dz == null) {
            if (dx == null) {
                dx = asNullableDouble(skinDefinition.get("dx"));
            }
            if (dy == null) {
                dy = asNullableDouble(skinDefinition.get("dy"));
            }
            if (dz == null) {
                dz = asNullableDouble(skinDefinition.get("dz"));
            }
        }

        if (dx == null) {
            dx = x;
        }
        if (dy == null) {
            dy = y;
        }
        if (dz == null) {
            dz = z;
        }

        if (dx == null) {
            dx = 1.5;
        }
        if (dy == null) {
            dy = 0.0;
        }
        if (dz == null) {
            dz = 0.5;
        }

        offset.put("dx", dx);
        offset.put("dy", dy);
        offset.put("dz", dz);
        return offset;
    }

    private boolean hasExistingSpawn(Map<String, Object> operations, String npcName) {
        if (operations == null || npcName == null) {
            return false;
        }
        String target = normalize(npcName);
        return containsNpcWithName(operations.get("spawn"), target)
                || containsNpcWithName(operations.get("spawn_multi"), target);
    }

    private boolean containsNpcWithName(Object candidate, String normalizedTarget) {
        if (candidate == null) {
            return false;
        }
        if (candidate instanceof Map<?, ?> map) {
            Map<String, Object> cast = filterStringKeys(map);
            if (Boolean.TRUE.equals(cast.get("_auto_featured"))) {
                return true;
            }
            String name = cleanString(cast.get("name"));
            if (!name.isEmpty() && normalize(name).equals(normalizedTarget)) {
                return true;
            }
            String id = cleanString(cast.get("id"));
            if (!id.isEmpty() && normalize(id).equals(normalizedTarget)) {
                return true;
            }
            return false;
        }
        if (candidate instanceof List<?> list) {
            for (Object element : list) {
                if (containsNpcWithName(element, normalizedTarget)) {
                    return true;
                }
            }
        }
        return false;
    }

    private void appendSpawn(Map<String, Object> target, Map<String, Object> spawnDirective) {
        if (target == null) {
            return;
        }
        if (appendToSlot(target, "spawn_multi", spawnDirective)) {
            return;
        }
        if (appendToSlot(target, "spawn", spawnDirective)) {
            return;
        }
        target.put("spawn", spawnDirective);
    }

    private boolean appendToSlot(Map<String, Object> target, String key, Map<String, Object> spawnDirective) {
        Object existing = target.get(key);
        if (existing == null) {
            return false;
        }
        List<Object> list;
        if (existing instanceof List<?> existingList) {
            list = new ArrayList<>(existingList);
        } else if (existing instanceof Map<?, ?> existingMap) {
            list = new ArrayList<>();
            list.add(existingMap);
        } else {
            list = new ArrayList<>();
            list.add(existing);
        }
        list.add(spawnDirective);
        target.put(key, list);
        return true;
    }

    private void ensureNpcTriggerEvents(Map<String, Object> metadata,
                                        Map<String, Object> operationsView,
                                        Map<String, Object> rawOperations) {
        if (rawOperations.containsKey("npc_trigger_events")) {
            return;
        }
        List<Map<String, Object>> triggers = extractTriggerDefinitions(metadata);
        if (triggers.isEmpty()) {
            return;
        }
        rawOperations.put("npc_trigger_events", copyTriggerList(triggers));
        operationsView.put("npc_trigger_events", triggers);
    }

    private List<Map<String, Object>> extractTriggerDefinitions(Map<String, Object> source) {
        if (source == null || source.isEmpty()) {
            return Collections.emptyList();
        }
        Object raw = source.get("npc_triggers");
        if (!(raw instanceof List<?> list) || list.isEmpty()) {
            return Collections.emptyList();
        }
        List<Map<String, Object>> result = new ArrayList<>();
        for (Object entry : list) {
            if (entry instanceof Map<?, ?> map) {
                result.add(filterStringKeys(map));
            }
        }
        return result;
    }

    private List<Map<String, Object>> copyTriggerList(List<Map<String, Object>> source) {
        List<Map<String, Object>> copy = new ArrayList<>(source.size());
        for (Map<String, Object> entry : source) {
            copy.add(new LinkedHashMap<>(entry));
        }
        return copy;
    }

    private Map<String, Object> castToMap(Object value) {
        if (!(value instanceof Map<?, ?> map)) {
            return null;
        }
        return filterStringKeys(map);
    }

    private Double asNullableDouble(Object value) {
        if (value instanceof Number number) {
            return number.doubleValue();
        }
        if (value instanceof String str) {
            try {
                String trimmed = str.trim();
                if (!trimmed.isEmpty()) {
                    return Double.parseDouble(trimmed);
                }
            } catch (NumberFormatException ignored) {
                // ignore malformed numeric strings
            }
        }
        return null;
    }

    private double asDoubleOrDefault(Object value, double fallback) {
        Double converted = asNullableDouble(value);
        return converted != null ? converted : fallback;
    }

    private String cleanString(Object value) {
        return value == null ? "" : value.toString().trim();
    }

    private String normalize(String value) {
        return cleanString(value).toLowerCase(Locale.ROOT);
    }

    @SuppressWarnings("unchecked")
    private void inspectObject(Player player, Object candidate) {
        if (!(candidate instanceof Map<?, ?> rawCandidate)) {
            return;
        }

        Map<String, Object> operations = filterStringKeys(rawCandidate);
        if (operations.isEmpty()) {
            return;
        }

        Map<String, Object> rawOperations = (Map<String, Object>) rawCandidate;

        boolean sceneHandled = false;

        Object cleanup = operations.get("_scene_cleanup");
        if (cleanup instanceof Map<?, ?> cleanupMap) {
            sceneLoader.handleSceneCleanup(player, filterStringKeys(cleanupMap));
        }

        Object scene = operations.get("_scene");
        if (scene instanceof Map<?, ?> sceneMap) {
            Map<String, Object> sceneMetadata = filterStringKeys(sceneMap);
            Map<String, Object> previousRawOps = currentRawOperations;
            currentRawOperations = rawOperations;
            try {
                sceneLoader.handleScenePatch(player, sceneMetadata, operations);
            } finally {
                currentRawOperations = previousRawOps;
            }
            sceneHandled = true;
        }

        Object cinematic = operations.get("_cinematic");
        if (cinematic instanceof Map<?, ?> cinematicMap) {
            if (!sceneHandled) {
                sceneLoader.handleCinematic(player, filterStringKeys(cinematicMap));
            }
        }

        Object emotion = operations.get("npc_emotion");
        if (emotion instanceof Map<?, ?> emotionMap) {
            npcManager.applyEmotionPatch(player, filterStringKeys(emotionMap));
        } else if (emotion instanceof List<?> emotionList) {
            for (Object entry : emotionList) {
                if (entry instanceof Map<?, ?> entryMap) {
                    npcManager.applyEmotionPatch(player, filterStringKeys(entryMap));
                }
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

    @Override
    protected void afterSpawn(Player player, Map<String, Object> spawnSpec, Entity entity) {
        super.afterSpawn(player, spawnSpec, entity);
        if (spawnSpec == null || entity == null) {
            return;
        }
        if (!Boolean.TRUE.equals(spawnSpec.get("_auto_featured"))) {
            return;
        }
        if (!(entity instanceof LivingEntity living)) {
            return;
        }

        String npcName = cleanString(spawnSpec.get("name"));
        if (npcName.isEmpty()) {
            Component customName = living.customName();
            if (customName != null) {
                npcName = cleanString(PlainTextComponentSerializer.plainText().serialize(customName));
            }
        }

        String npcId = cleanString(spawnSpec.get("id"));
        if (!npcId.isEmpty()) {
            living.addScoreboardTag("npc_id:" + npcId);
            living.setMetadata("npc_id", new FixedMetadataValue(getPlugin(), npcId));
            if (npcName.isEmpty()) {
                npcName = npcId;
            }
        }

        npcManager.registerAutoFeaturedNpc(living, npcName);
    }
}
