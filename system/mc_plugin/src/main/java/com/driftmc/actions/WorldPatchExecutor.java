package com.driftmc.actions;

import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.json.JSONObject;

public class WorldPatchExecutor {

    private final JavaPlugin plugin;

    public WorldPatchExecutor(JavaPlugin plugin) {
        this.plugin = plugin;
    }

    @SuppressWarnings("deprecation")
    public void apply(Player player, JSONObject patch) {

        if (!patch.has("mc")) return;
        JSONObject mc = patch.getJSONObject("mc");
        World world = player.getWorld();

        // 1) tell
        if (mc.has("tell")) {
            player.sendMessage("§a[AI] §f" + mc.getString("tell"));
        }

        // 2) time
        if (mc.has("time")) {
            String t = mc.getString("time");
            switch (t.toLowerCase()) {
                case "day" -> world.setTime(1000);
                case "noon" -> world.setTime(6000);
                case "night" -> world.setTime(13000);
                case "midnight" -> world.setTime(18000);
            }
        }

        // 3) weather
        if (mc.has("weather")) {
            String w = mc.getString("weather");
            switch (w.toLowerCase()) {
                case "clear" -> { world.setStorm(false); world.setThundering(false); }
                case "rain" -> world.setStorm(true);
                case "thunder" -> { world.setStorm(true); world.setThundering(true); }
            }
        }

        // 4) effect
        if (mc.has("effect")) {
            JSONObject ef = mc.getJSONObject("effect");
            PotionEffectType t = PotionEffectType.getByName(ef.optString("type", "GLOW"));
            int sec = ef.optInt("seconds", 5);
            int amp = ef.optInt("amplifier", 0);
            if (t != null) player.addPotionEffect(new PotionEffect(t, sec * 20, amp));
        }

        // 5) teleport
        if (mc.has("teleport")) {
            JSONObject tp = mc.getJSONObject("teleport");
            String mode = tp.optString("mode", "relative");

            double x = tp.optDouble("x", 0);
            double y = tp.optDouble("y", 0);
            double z = tp.optDouble("z", 0);

            Location target = mode.equals("absolute")
                    ? new Location(world, x, y, z)
                    : player.getLocation().add(x, y, z);

            target = findSafeLocation(target);
            player.teleport(target);
        }

        // ---------------------------
        // 6) BUILD 造物功能
        // ---------------------------
        if (mc.has("build")) {
            JSONObject b = mc.getJSONObject("build");
            String shape = b.optString("shape", "platform");
            String materialId = b.optString("material", "oak_planks");
            int size = b.optInt("size", 5);

            JSONObject off = b.optJSONObject("safe_offset");
            double dx = off != null ? off.optDouble("dx", 2) : 2;
            double dy = off != null ? off.optDouble("dy", 0) : 0;
            double dz = off != null ? off.optDouble("dz", 2) : 2;

            Material mat = Material.matchMaterial(materialId.toUpperCase());
            if (mat == null) mat = Material.OAK_PLANKS;

            Location base = player.getLocation().clone().add(dx, dy, dz);

            switch (shape.toLowerCase()) {
                case "pillar" -> buildPillar(base, mat, size);
                case "platform" -> buildPlatform(base, mat, size);
                case "house" -> buildHouse(base, mat, size);
                case "bridge" -> buildBridge(base, mat, size);
            }
        }

        // ---------------------------
        // 7) NPC / 动物生成
        // ---------------------------
        if (mc.has("spawn")) {
            JSONObject s = mc.getJSONObject("spawn");

            String type = s.optString("type", "rabbit"); 
            String name = s.optString("name", "");

            JSONObject off = s.optJSONObject("offset");
            double dx = off != null ? off.optDouble("dx", 1) : 1;
            double dy = off != null ? off.optDouble("dy", 0) : 0;
            double dz = off != null ? off.optDouble("dz", 1) : 1;

            Location loc = player.getLocation().clone().add(dx, dy, dz);

            EntityType et = EntityType.fromName(type.toUpperCase());
            if (et == null) et = EntityType.RABBIT;

            Entity e = world.spawnEntity(loc, et);

            if (!name.isEmpty()) {
                e.setCustomName("§d" + name);
                e.setCustomNameVisible(true);
            }

            // 让实体面向玩家（更像 NPC）
            lookAt(e, player.getLocation());
        }
    }

    // safe pos
    private Location findSafeLocation(Location loc) {
        World w = loc.getWorld();
        if (w == null) return loc;

        int x = loc.getBlockX();
        int z = loc.getBlockZ();
        int y = w.getHighestBlockYAt(x, z) + 1;
        return new Location(w, x + 0.5, y, z + 0.5);
    }

    // look at player
    private void lookAt(Entity e, Location target) {
        Location loc = e.getLocation();
        loc.setDirection(target.subtract(loc).toVector());
        e.teleport(loc);
    }

    // build functions
    private void buildPillar(Location base, Material mat, int h) {
        World w = base.getWorld();
        for (int i = 0; i < h; i++)
            w.getBlockAt(base.getBlockX(), base.getBlockY() + i, base.getBlockZ()).setType(mat);
    }

    private void buildPlatform(Location base, Material mat, int size) {
        World w = base.getWorld();
        int r = size / 2;
        for (int x = -r; x <= r; x++)
            for (int z = -r; z <= r; z++)
                w.getBlockAt(base.getBlockX() + x, base.getBlockY(), base.getBlockZ() + z).setType(mat);
    }

    private void buildBridge(Location base, Material mat, int len) {
        World w = base.getWorld();
        for (int i = 0; i < len; i++)
            w.getBlockAt(base.getBlockX() + i, base.getBlockY(), base.getBlockZ()).setType(mat);
    }

    private void buildHouse(Location base, Material mat, int size) {
        World w = base.getWorld();
        int r = size / 2;

        for (int x = -r; x <= r; x++)
            for (int z = -r; z <= r; z++)
                w.getBlockAt(base.getBlockX() + x, base.getBlockY(), base.getBlockZ() + z).setType(mat);

        for (int h = 1; h <= 3; h++) {
            for (int x = -r; x <= r; x++) {
                w.getBlockAt(base.getBlockX() + x, base.getBlockY() + h, base.getBlockZ() - r).setType(mat);
                w.getBlockAt(base.getBlockX() + x, base.getBlockY() + h, base.getBlockZ() + r).setType(mat);
            }
            for (int z = -r; z <= r; z++) {
                w.getBlockAt(base.getBlockX() - r, base.getBlockY() + h, base.getBlockZ() + z).setType(mat);
                w.getBlockAt(base.getBlockX() + r, base.getBlockY() + h, base.getBlockZ() + z).setType(mat);
            }
        }

        for (int x = -r; x <= r; x++)
            for (int z = -r; z <= r; z++)
                w.getBlockAt(base.getBlockX() + x, base.getBlockY() + 4, base.getBlockZ() + z).setType(mat);

        w.getBlockAt(base.getBlockX(), base.getBlockY() + 1, base.getBlockZ() - r).setType(Material.AIR);
        w.getBlockAt(base.getBlockX(), base.getBlockY() + 2, base.getBlockZ() - r).setType(Material.AIR);
    }
}