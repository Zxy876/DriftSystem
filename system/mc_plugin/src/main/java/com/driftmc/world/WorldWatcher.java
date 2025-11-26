package com.driftmc.world;

import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerMoveEvent;
import org.bukkit.event.player.PlayerPickupItemEvent;

import com.driftmc.backend.BackendClient;

public class WorldWatcher implements Listener {

    private final BackendClient backend;

    public WorldWatcher(BackendClient backend) {
        this.backend = backend;
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent event) {
        sendEvent(event.getPlayer(), "join", "{}");
    }

    @EventHandler
    public void onPickup(PlayerPickupItemEvent event) {
        String item = event.getItem().getItemStack().getType().toString();
        sendEvent(event.getPlayer(), "pickup", "{ \"item\": \"" + item + "\" }");
    }

    @EventHandler
    public void onDeath(PlayerDeathEvent event) {
        sendEvent(event.getEntity(), "death",
                "{ \"reason\": \"" + event.getDeathMessage() + "\" }");
    }

    @EventHandler
    public void onMove(PlayerMoveEvent event) {
        if (event.getTo().distance(event.getFrom()) < 0.1) return;

        Location loc = event.getTo();
        String json = String.format(
                "{ \"x\": %.2f, \"y\": %.2f, \"z\": %.2f, \"world\": \"%s\" }",
                loc.getX(), loc.getY(), loc.getZ(), loc.getWorld().getName()
        );
        sendEvent(event.getPlayer(), "move", json);
    }

    private void sendEvent(Player p, String type, String json) {

        String payload = "{ \"player\": \"" + p.getName() + "\", " +
                "\"event\": \"" + type + "\", \"data\": " + json + " }";

        Bukkit.getScheduler().runTaskAsynchronously(
                Bukkit.getPluginManager().getPlugin("DriftSystem"),
                () -> {
                    try {
                        backend.postJson("/world/event", payload);
                    } catch (Exception e) {
                        // 世界事件失败不阻塞游戏
                        System.out.println("[WorldWatcher] Failed to send: " + e.getMessage());
                    }
                }
        );
    }
}