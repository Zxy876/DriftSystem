package com.driftmc.listeners;

import org.bukkit.ChatColor;
import org.bukkit.Location;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerMoveEvent;

import com.driftmc.intent.IntentRouter;
import com.driftmc.npc.NPCManager;
import com.driftmc.scene.RuleEventBridge;

@SuppressWarnings("deprecation")
public class NearbyNPCListener implements Listener {

    private final NPCManager npcManager;
    private final IntentRouter router;
    private final RuleEventBridge ruleEvents;

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

                p.sendMessage(ChatColor.LIGHT_PURPLE + "你靠近了 " + name + "。");
                if (ruleEvents != null) {
                    ruleEvents.emitNearNpc(p, name, entity.getLocation());
                }

                // 触发自然语言 AI
                router.handlePlayerSpeak(p, "我靠近了 " + name);
            }
        }
    }
}