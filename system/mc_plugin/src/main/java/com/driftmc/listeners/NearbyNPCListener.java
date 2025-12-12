package com.driftmc.listeners;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

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

import com.driftmc.intent.IntentRouter;
import com.driftmc.npc.NPCManager;
import com.driftmc.scene.RuleEventBridge;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;

@SuppressWarnings("deprecation")
public class NearbyNPCListener implements Listener {

    private static final long NPC_INTERACT_COOLDOWN_MS = 2_000L;
    private static final String NPC_ID_META = "npc_id";
    private static final String NPC_ID_PREFIX = "npc_id:";

    private final NPCManager npcManager;
    private final IntentRouter router;
    private final RuleEventBridge ruleEvents;
    private final Map<String, Long> proximityCooldown = new ConcurrentHashMap<>();
    private final Map<UUID, Long> interactCooldown = new ConcurrentHashMap<>();
    private final Map<String, Long> npcQuestCooldown = new ConcurrentHashMap<>();

    public NearbyNPCListener(NPCManager npcManager, IntentRouter router, RuleEventBridge ruleEvents) {
        this.npcManager = npcManager;
        this.router = router;
        this.ruleEvents = ruleEvents;
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
    }

    @EventHandler(ignoreCancelled = true)
    public void onInteract(PlayerInteractEntityEvent event) {
        if (event.getHand() != EquipmentSlot.HAND) {
            return;
        }
        if (handleNpcInteraction(event.getPlayer(), event.getRightClicked())) {
            event.setCancelled(true);
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onInteractAt(PlayerInteractAtEntityEvent event) {
        if (event.getHand() != EquipmentSlot.HAND) {
            return;
        }
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

        player.sendMessage(ChatColor.LIGHT_PURPLE + "你与【" + displayName + "】交谈。");
        player.sendActionBar(Component.text("你与【" + displayName + "】交谈", NamedTextColor.LIGHT_PURPLE));

        String npcId = extractNpcId(target);

        if (ruleEvents != null) {
            ruleEvents.emitInteractEntity(player, target, "right_click");

            String questEvent = npcManager.lookupQuestEvent(target);
            if (questEvent.isBlank() && !npcId.isBlank()) {
                questEvent = npcManager.lookupQuestEvent(npcId);
            }
            if (questEvent.isBlank()) {
                questEvent = npcManager.lookupQuestEvent(displayName);
            }

            if (!questEvent.isBlank() && consumeNpcQuest(player.getUniqueId(), questEvent)) {
                Map<String, Object> payload = new LinkedHashMap<>();
                payload.put("source", "npc_interact");
                payload.put("npc", npcId.isBlank() ? displayName : npcId);
                ruleEvents.emitQuestEvent(player, questEvent, target.getLocation(), payload);
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
                if (value == null) {
                    continue;
                }
                String raw = value.asString();
                if (raw == null) {
                    continue;
                }
                String trimmed = raw.trim();
                if (!trimmed.isEmpty()) {
                    return trimmed;
                }
            }
        }

        Set<String> tags = entity.getScoreboardTags();
        if (tags != null) {
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
}