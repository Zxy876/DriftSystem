package com.driftmc.listeners;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

import org.bukkit.ChatColor;
import org.bukkit.Location;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.event.player.PlayerMoveEvent;
import org.bukkit.inventory.EquipmentSlot;

import com.driftmc.intent.IntentRouter;
import com.driftmc.npc.NPCManager;
import com.driftmc.scene.RuleEventBridge;

@SuppressWarnings("deprecation")
public class NearbyNPCListener implements Listener {

    private final NPCManager npcManager;
    private final IntentRouter router;
    private final RuleEventBridge ruleEvents;
    private final Map<String, Long> proximityCooldown = new ConcurrentHashMap<>();
    private final Map<UUID, Long> interactCooldown = new ConcurrentHashMap<>();

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

        Entity target = event.getRightClicked();
        if (!npcManager.isNpc(target)) {
            return;
        }

        event.setCancelled(true);

        Player player = event.getPlayer();
        if (!tryConsumeInteract(player.getUniqueId())) {
            return;
        }

        String name = target.getCustomName();
        if (name == null) {
            name = "未知NPC";
        }

        player.sendMessage(ChatColor.LIGHT_PURPLE + "你与 " + name + " 开始对话...");

        if (ruleEvents != null) {
            ruleEvents.emitInteractEntity(player, target, "right_click");
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
}