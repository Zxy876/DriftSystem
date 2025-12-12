package com.driftmc.listeners;

import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Level;

import org.bukkit.ChatColor;
import org.bukkit.Location;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerInteractAtEntityEvent;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.player.PlayerMoveEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.metadata.MetadataValue;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.DriftPlugin;
import com.driftmc.intent.IntentRouter;
import com.driftmc.npc.NPCManager;
import com.driftmc.scene.QuestEventCanonicalizer;
import com.driftmc.scene.RuleEventBridge;
import com.driftmc.story.LevelIds;
import com.driftmc.story.StoryManager;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;

@SuppressWarnings("deprecation")
public class NearbyNPCListener implements Listener {

    private static final long NPC_INTERACT_COOLDOWN_MS = 2_000L;
    private static final long TUTORIAL_CHECKPOINT_COOLDOWN_MS = 3_000L;
    private static final String NPC_ID_META = "npc_id";
    private static final String NPC_ID_PREFIX = "npc_id:";
    private static final String TUTORIAL_WORLD_NAME = "KunmingLakeTutorial";
    private static final String TUTORIAL_GUIDE_NAME = "心悦向导";
    private static final String TUTORIAL_GUIDE_ID = "tutorial_guide";
    private static final String TUTORIAL_MEET_GUIDE_EVENT = "tutorial_meet_guide";
    private static final String TUTORIAL_REACH_CHECKPOINT_EVENT = "tutorial_reach_checkpoint";
    private static final double TUTORIAL_SAFE_Y_THRESHOLD = 118.0D;

    private final JavaPlugin plugin;
    private final NPCManager npcManager;
    private final IntentRouter router;
    private final RuleEventBridge ruleEvents;
    private final StoryManager storyManager;
    private final Map<String, Long> proximityCooldown = new ConcurrentHashMap<>();
    private final Map<UUID, Long> interactCooldown = new ConcurrentHashMap<>();
    private final Map<String, Long> npcQuestCooldown = new ConcurrentHashMap<>();
    private final Map<UUID, Long> tutorialCheckpointCooldown = new ConcurrentHashMap<>();

    public NearbyNPCListener(JavaPlugin plugin, NPCManager npcManager, IntentRouter router, RuleEventBridge ruleEvents) {
        this.plugin = plugin;
        this.npcManager = npcManager;
        this.router = router;
        this.ruleEvents = ruleEvents;
        this.storyManager = plugin instanceof DriftPlugin drift ? drift.getStoryManager() : null;
    }

    @EventHandler
    public void onMove(PlayerMoveEvent event) {

        Player p = event.getPlayer();

        for (Entity entity : npcManager.getSpawnedNPCs()) {

            if (entity == null) continue;
            if (!entity.isValid()) continue;

            Location loc = entity.getLocation();
            if (loc.getWorld() != p.getWorld()) continue;

            // 距离判断
            if (loc.distance(p.getLocation()) < 3) {

                String name = entity.getCustomName();
                if (name == null) name = "未知NPC";

                boolean notify = shouldNotifyProximity(p.getUniqueId(), entity.getUniqueId());
                if (notify) {
                    p.sendMessage(ChatColor.LIGHT_PURPLE + "你靠近了 " + name + "。");
                    if (ruleEvents != null) {
                        ruleEvents.emitNearNpc(p, name, entity.getLocation());
                    }
                    router.handlePlayerSpeak(p, "我靠近了 " + name);
                }
            }
        }

        maybeTriggerTutorialCheckpoint(p);
    }

    @EventHandler(ignoreCancelled = true)
    public void onInteract(PlayerInteractEntityEvent event) {
        if (event.getHand() != EquipmentSlot.HAND) {
            return;
        }
        plugin.getLogger().log(Level.INFO,
                "[NearbyNPCListener] PlayerInteractEntityEvent: {0} -> {1}",
                new Object[]{event.getPlayer().getName(), event.getRightClicked().getType()});
        if (handleNpcInteraction(event.getPlayer(), event.getRightClicked())) {
            event.setCancelled(true);
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onInteractAt(PlayerInteractAtEntityEvent event) {
        if (event.getHand() != EquipmentSlot.HAND) {
            return;
        }
        plugin.getLogger().log(Level.INFO,
                "[NearbyNPCListener] PlayerInteractAtEntityEvent: {0} -> {1}",
                new Object[]{event.getPlayer().getName(), event.getRightClicked().getType()});
        if (handleNpcInteraction(event.getPlayer(), event.getRightClicked())) {
            event.setCancelled(true);
        }
    }

    private boolean shouldNotifyProximity(UUID playerId, UUID entityId) {
        long now = System.currentTimeMillis();
        String key = playerId + ":" + entityId;
        Long last = proximityCooldown.get(key);
        if (last != null && now - last < 3_000L) {
            return false;
        }
        proximityCooldown.put(key, now);
        return true;
    }

    private void maybeTriggerTutorialCheckpoint(Player player) {
        if (player == null || ruleEvents == null) {
            return;
        }

        Location location = player.getLocation();
        if (!isFlagshipTutorialLevel(player)) {
            return;
        }

        if (!isInTutorialWorld(location)) {
            return;
        }

        if (!isInsideTutorialCheckpoint(location)) {
            return;
        }

        if (!consumeTutorialCheckpoint(player.getUniqueId())) {
            return;
        }

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("source", "trigger_zone");
        payload.put("zone", "tutorial_checkpoint");
        String levelId = resolveCurrentLevel(player);
        if (!levelId.isBlank()) {
            payload.put("level_id", levelId);
        }
        appendLocation(payload, location);
        ruleEvents.emit(player, TUTORIAL_REACH_CHECKPOINT_EVENT, payload);
        plugin.getLogger().log(Level.INFO,
                "[NearbyNPCListener] emit tutorial_reach_checkpoint for {0}",
                new Object[]{player.getName()});
    }

    private boolean isInTutorialWorld(Location location) {
        if (location == null || location.getWorld() == null) {
            return false;
        }
        String worldName = location.getWorld().getName();
        if (worldName.isBlank()) {
            return false;
        }
        if (worldName.equalsIgnoreCase(TUTORIAL_WORLD_NAME)) {
            return true;
        }
        return worldName.toLowerCase(Locale.ROOT).contains("tutorial");
    }

    private boolean isInsideTutorialCheckpoint(Location location) {
        if (location == null) {
            return false;
        }
        return location.getY() < TUTORIAL_SAFE_Y_THRESHOLD;
    }

    private boolean consumeTutorialCheckpoint(UUID playerId) {
        long now = System.currentTimeMillis();
        Long last = tutorialCheckpointCooldown.get(playerId);
        if (last != null && now - last < TUTORIAL_CHECKPOINT_COOLDOWN_MS) {
            return false;
        }
        tutorialCheckpointCooldown.put(playerId, now);
        return true;
    }

    private boolean tryConsumeInteract(UUID playerId) {
        long now = System.currentTimeMillis();
        Long last = interactCooldown.get(playerId);
        if (last != null && now - last < 750L) {
            return false;
        }
        interactCooldown.put(playerId, now);
        return true;
    }

    private boolean handleNpcInteraction(Player player, Entity target) {
        if (player == null || target == null) {
            return false;
        }
        if (!npcManager.isNpc(target)) {
            return false;
        }

        if (!tryConsumeInteract(player.getUniqueId())) {
            return true;
        }

        String displayName = target.getCustomName();
        if (displayName == null || displayName.isBlank()) {
            displayName = "未知NPC";
        }

        plugin.getLogger().log(Level.INFO,
                "[NearbyNPCListener] Handling interaction: player={0}, entity={1}, type={2}",
                new Object[]{player.getName(), displayName, target.getType()});

        player.sendMessage(ChatColor.LIGHT_PURPLE + "你与【" + displayName + "】交谈。");
        player.sendActionBar(Component.text("你与【" + displayName + "】交谈", NamedTextColor.LIGHT_PURPLE));

        String npcId = extractNpcId(target);
        String levelId = resolveCurrentLevel(player);
        boolean flagshipTutorial = LevelIds.isFlagshipTutorial(levelId);
        boolean tutorialGuide = isTutorialGuide(target, displayName, npcId);

        if (ruleEvents != null) {
            ruleEvents.emitInteractEntity(player, target, "right_click");

            if (tutorialGuide && flagshipTutorial) {
                Map<String, Object> payload = new LinkedHashMap<>();
                payload.put("source", "npc_interact");
                payload.put("npc", TUTORIAL_GUIDE_NAME);
                if (!levelId.isBlank()) {
                    payload.put("level_id", levelId);
                }
                appendLocation(payload, target.getLocation());
                plugin.getLogger().log(Level.INFO,
                        "[NearbyNPCListener] FORCE emit tutorial_meet_guide for {0}",
                        new Object[]{player.getName()});
                ruleEvents.emit(player, TUTORIAL_MEET_GUIDE_EVENT, payload);
                player.sendMessage(ChatColor.GOLD + "触发事件: " + TUTORIAL_MEET_GUIDE_EVENT);
            } else {
                String questEvent = npcManager.lookupQuestEvent(target);
                if (questEvent.isBlank() && !npcId.isBlank()) {
                    questEvent = npcManager.lookupQuestEvent(npcId);
                }
                if (questEvent.isBlank()) {
                    questEvent = npcManager.lookupQuestEvent(displayName);
                }

                String canonicalQuestEvent = QuestEventCanonicalizer.canonicalize(questEvent);
                String eventType = !canonicalQuestEvent.isEmpty() ? canonicalQuestEvent : questEvent;

                if (!eventType.isBlank() && consumeNpcQuest(player.getUniqueId(), eventType)) {
                    Map<String, Object> payload = new LinkedHashMap<>();
                    payload.put("source", "npc_interact");
                    String canonicalNpcName = npcId.isBlank() ? displayName : npcId;
                    payload.put("npc", canonicalNpcName);
                    if (!levelId.isBlank()) {
                        payload.put("level_id", levelId);
                    }
                    appendLocation(payload, target.getLocation());
                    ruleEvents.emit(player, eventType, payload);
                    player.sendMessage(ChatColor.GOLD + "触发事件: " + eventType);
                    plugin.getLogger().log(Level.INFO,
                            "[NearbyNPCListener] Emitted event {0} for player {1} (npc={2})",
                            new Object[]{eventType, player.getName(), canonicalNpcName});
                } else {
                    plugin.getLogger().log(Level.INFO,
                            "[NearbyNPCListener] Interaction throttled or unresolved: player={0}, npc={1}, event={2}",
                            new Object[]{player.getName(), npcId.isBlank() ? displayName : npcId, eventType});
                }
            }
        }

        if (router != null) {
            router.handlePlayerSpeak(player, "我与 " + displayName + " 互动");
        }

        return true;
    }

    // player_like NPCs now spawn as HumanEntity with metadata instead of ArmorStand, so
    // we must pull the canonical npc_id to ensure quest events fire regardless of display name.
    private String extractNpcId(Entity entity) {
        if (entity.hasMetadata(NPC_ID_META)) {
            for (MetadataValue value : entity.getMetadata(NPC_ID_META)) {
                String raw = value.asString();
                String trimmed = raw.trim();
                if (!trimmed.isEmpty()) {
                    return trimmed;
                }
            }
        }

        Set<String> tags = entity.getScoreboardTags();
        for (String tag : tags) {
            if (tag == null) {
                continue;
            }
            if (tag.startsWith(NPC_ID_PREFIX)) {
                String trimmed = tag.substring(NPC_ID_PREFIX.length()).trim();
                if (!trimmed.isEmpty()) {
                    return trimmed;
                }
            }
        }

        return "";
    }

    private boolean consumeNpcQuest(UUID playerId, String questEvent) {
        long now = System.currentTimeMillis();
        String key = playerId + ":" + questEvent;
        Long last = npcQuestCooldown.get(key);
        if (last != null && now - last < NPC_INTERACT_COOLDOWN_MS) {
            return false;
        }
        npcQuestCooldown.put(key, now);
        return true;
    }

    private boolean isTutorialGuide(Entity entity, String displayName, String npcId) {
        if (entity == null) {
            return false;
        }
        if (npcId != null && !npcId.isBlank() && npcId.equalsIgnoreCase(TUTORIAL_GUIDE_ID)) {
            return true;
        }
        String stripped = displayName != null ? ChatColor.stripColor(displayName) : null;
        if (stripped != null && stripped.contains(TUTORIAL_GUIDE_NAME)) {
            return true;
        }
        Set<String> tags = entity.getScoreboardTags();
        for (String tag : tags) {
            if (tag == null) {
                continue;
            }
            String lowerTag = tag.toLowerCase(Locale.ROOT);
            if (lowerTag.contains(TUTORIAL_GUIDE_ID)) {
                return true;
            }
            if (lowerTag.contains(TUTORIAL_GUIDE_NAME)) {
                return true;
            }
        }
        return false;
    }

    private String resolveCurrentLevel(Player player) {
        if (player == null || storyManager == null) {
            return "";
        }
        return LevelIds.canonicalizeOrDefault(storyManager.getCurrentLevel(player));
    }

    private boolean isFlagshipTutorialLevel(Player player) {
        String levelId = resolveCurrentLevel(player);
        return LevelIds.isFlagshipTutorial(levelId);
    }

    private void appendLocation(Map<String, Object> payload, Location location) {
        if (payload == null || location == null) {
            return;
        }
        Map<String, Object> loc = new LinkedHashMap<>();
        if (location.getWorld() != null) {
            loc.put("world", location.getWorld().getName());
        }
        loc.put("x", location.getX());
        loc.put("y", location.getY());
        loc.put("z", location.getZ());
        payload.put("location", loc);
    }
}