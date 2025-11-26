package com.driftmc.npc;

import java.util.ArrayList;
import java.util.List;

import org.bukkit.ChatColor;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.Player;
import org.bukkit.entity.Rabbit;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.intent.IntentRouter;
import com.driftmc.session.PlayerSessionManager;

public class NPCManager {

    private final JavaPlugin plugin;
    private final PlayerSessionManager sessionManager;
    private IntentRouter router;

    private final List<Entity> spawnedNPCs = new ArrayList<>();

    public NPCManager(JavaPlugin plugin, PlayerSessionManager sess) {
        this.plugin = plugin;
        this.sessionManager = sess;
    }

    public void setRouter(IntentRouter router) {
        this.router = router;
    }

    /**
     * 获取所有已生成的 NPC
     */
    public List<Entity> getSpawnedNPCs() {
        return spawnedNPCs;
    }

    /**
     * 召唤一只带名字的小兔子 NPC
     */
    public void spawnRabbit(Player player, String name) {
        Location loc = player.getLocation();
        World w = loc.getWorld();
        if (w == null) return;

        Rabbit rabbit = (Rabbit) w.spawnEntity(loc.add(1, 0, 1), EntityType.RABBIT);

        rabbit.setCustomName(ChatColor.LIGHT_PURPLE + name);
        rabbit.setCustomNameVisible(true);

        spawnedNPCs.add(rabbit);

        player.sendMessage(ChatColor.AQUA + "NPC " + name + " 已出现。");
    }
}