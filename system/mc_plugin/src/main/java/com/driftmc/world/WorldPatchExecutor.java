package com.driftmc.world;

import java.util.List;
import java.util.Map;

import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.World;
import org.bukkit.attribute.Attribute;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;

/**
 * WorldPatchExecutor
 *
 * 心悦宇宙 · 王者版执行器
 * 统一执行来自后端的 world_patch / mc_patch：
 *
 * 支持 key：
 *  tell / weather / time / teleport / build / spawn
 *  effect / particle / sound / title / actionbar
 */
public class WorldPatchExecutor {

    private final JavaPlugin plugin;

    public WorldPatchExecutor(JavaPlugin plugin) {
        this.plugin = plugin;
    }

    /**
     * 只发一条心悦宇宙风格文本。
     */
    public void execute(Player player, String text) {
        if (player == null || text == null || text.isEmpty()) {
            return;
        }
        player.sendMessage(ChatColor.LIGHT_PURPLE + "【心悦宇宙】 " + ChatColor.WHITE + text);
    }

    /**
     * 核心入口：执行 world_patch / mc_patch
     *
     * 兼容两种结构：
     * 1) { "tell": "...", "build": {...}, ... }
     * 2) { "variables": {...}, "mc": { "tell": "...", ... } }
     */
    @SuppressWarnings("unchecked")
public void execute(Player player, Map<String, Object> patch) {
    if (player == null || patch == null || patch.isEmpty()) {
        return;
    }

    // ========== ① 创建一个不会被修改的最终变量 ==========
    final Map<String, Object> patchFinal = patch;

    // ========== ② 异步切回主线程 ==========
    if (!Bukkit.isPrimaryThread()) {
        Bukkit.getScheduler().runTask(plugin, () -> execute(player, patchFinal));
        return;
    }

    plugin.getLogger().info("[WorldPatchExecutor] execute patch = " + patch);

    // ========== ③ 胶水变量（可修改，不属于 lambda）==========
    Map<String, Object> newPatch = patch;

    // 如果有 mc 子字段： { "variables": ..., "mc": {...} }
    if (newPatch.containsKey("mc")) {
        Object mcObj = newPatch.get("mc");
        if (mcObj instanceof Map<?, ?> mcMap) {
            newPatch = (Map<String, Object>) mcMap;
        }
    }

    // ========== ④ 以下全部用 newPatch，不再用 patch ==========
    // 1. tell
    handleTell(player, newPatch.get("tell"));

    // 2. weather
    if (newPatch.containsKey("weather")) {
        handleWeather(player, string(newPatch.get("weather"), "clear"));
    }

    // 3. time
    if (newPatch.containsKey("time")) {
        handleTime(player, string(newPatch.get("time"), "day"));
    }

    // 4. teleport
    if (newPatch.containsKey("teleport")) {
        Object tpObj = newPatch.get("teleport");
        if (tpObj instanceof Map<?, ?> tpRaw) {
            handleTeleport(player, (Map<String, Object>) tpRaw);
        }
    }

    // 5. build
    if (newPatch.containsKey("build")) {
        Object buildObj = newPatch.get("build");
        if (buildObj instanceof Map<?, ?> bRaw) {
            handleBuild(player, (Map<String, Object>) bRaw);
        }
    }

    // 6. spawn
    if (newPatch.containsKey("spawn")) {
        Object spawnObj = newPatch.get("spawn");
        if (spawnObj instanceof Map<?, ?> sRaw) {
            handleSpawn(player, (Map<String, Object>) sRaw);
        }
    }

    // 7. effect
    if (newPatch.containsKey("effect")) {
        Object effObj = newPatch.get("effect");
        if (effObj instanceof Map<?, ?> effRaw) {
            handleEffect(player, (Map<String, Object>) effRaw);
        }
    }

    // 8. particle
    if (newPatch.containsKey("particle")) {
        Object pObj = newPatch.get("particle");
        if (pObj instanceof Map<?, ?> pRaw) {
            handleParticle(player, (Map<String, Object>) pRaw);
        }
    }

    // 9. sound
    if (newPatch.containsKey("sound")) {
        Object sObj = newPatch.get("sound");
        if (sObj instanceof Map<?, ?> sRaw) {
            handleSound(player, (Map<String, Object>) sRaw);
        }
    }

    // 10. title
    if (newPatch.containsKey("title")) {
        Object tObj = newPatch.get("title");
        if (tObj instanceof Map<?, ?> tRaw) {
            handleTitle(player, (Map<String, Object>) tRaw);
        }
    }

    // 11. actionbar
    if (newPatch.containsKey("actionbar")) {
        Object abObj = newPatch.get("actionbar");
        if (abObj instanceof String abStr) {
            handleActionBar(player, abStr);
        }
    }
}

    // ========================= tell =========================

    private void handleTell(Player player, Object tellObj) {
        if (tellObj == null) return;

        if (tellObj instanceof String tell) {
            player.sendMessage(ChatColor.AQUA + "【心悦宇宙】 " + ChatColor.WHITE + tell);
        } else if (tellObj instanceof List<?> list) {
            for (Object line : list) {
                if (line == null) continue;
                player.sendMessage(ChatColor.AQUA + "【心悦宇宙】 " + ChatColor.WHITE + line.toString());
            }
        }
    }

    // ========================= weather =========================

    private void handleWeather(Player player, String weather) {
        World world = player.getWorld();
        weather = weather.toLowerCase();

        switch (weather) {
            case "clear" -> {
                world.setStorm(false);
                world.setThundering(false);
                world.setWeatherDuration(20 * 60 * 5);
                player.sendMessage(ChatColor.YELLOW + "✧ 天空放晴，心绪也变得清透。");
            }
            case "rain" -> {
                world.setStorm(true);
                world.setThundering(false);
                player.sendMessage(ChatColor.BLUE + "✧ 细雨落下，像是心里的某种投影。");
            }
            case "storm", "thunder" -> {
                world.setStorm(true);
                world.setThundering(true);
                player.sendMessage(ChatColor.DARK_BLUE + "✧ 雷声滚滚，世界在为你的故事鼓点。");
            }
            case "dream_sky" -> {
                world.setStorm(false);
                world.setThundering(false);
                player.sendMessage(ChatColor.LIGHT_PURPLE + "✧ 天空像被染成柔软的梦色。");
            }
            case "dark_sky" -> {
                world.setStorm(true);
                world.setThundering(false);
                player.sendMessage(ChatColor.DARK_PURPLE + "✧ 乌云压顶，像是剧情即将转折。");
            }
            default -> {
                world.setStorm(false);
                world.setThundering(false);
            }
        }
    }

    // ========================= time =========================

    private void handleTime(Player player, String time) {
        World world = player.getWorld();
        time = time.toLowerCase();

        long ticks;
        switch (time) {
            case "day" -> ticks = 1000L;
            case "sunrise" -> ticks = 23000L;
            case "sunset" -> ticks = 12000L;
            case "midnight" -> ticks = 18000L;
            case "night" -> ticks = 14000L;
            default -> ticks = world.getTime();
        }

        world.setTime(ticks);
        player.sendMessage(ChatColor.GOLD + "✧ 时间被轻轻拨动，场景也随之改变。");
    }

    // ========================= teleport =========================

    @SuppressWarnings("unchecked")
    private void handleTeleport(Player player, Map<String, Object> tpMap) {
        World world = player.getWorld();
        Location base = player.getLocation();

        String mode = string(tpMap.get("mode"), "relative");
        double x = number(tpMap.get("x"), 0).doubleValue();
        double y = number(tpMap.get("y"), 0).doubleValue();
        double z = number(tpMap.get("z"), 0).doubleValue();

        Location target;
        if ("absolute".equalsIgnoreCase(mode)) {
            target = new Location(world, x, y, z, base.getYaw(), base.getPitch());
        } else {
            target = base.clone().add(x, y, z);
        }

        player.teleport(target);
        player.sendMessage(ChatColor.GREEN + "✧ 你被世界轻轻挪到了一个新的坐标。");

        // 可选：safe_platform
        if (tpMap.containsKey("safe_platform")) {
            Object spObj = tpMap.get("safe_platform");
            if (spObj instanceof Map<?, ?> spRaw) {
                Map<String, Object> sp = (Map<String, Object>) spRaw;
                String matName = string(sp.get("material"), "GLASS");
                int radius = number(sp.get("radius"), 2).intValue();
                Material mat = Material.matchMaterial(matName.toUpperCase());
                if (mat == null) mat = Material.GLASS;
                buildPlatform(world, target.clone().add(0, -1, 0), radius, mat);
            }
        }
    }

    // ========================= build =========================

    @SuppressWarnings("unchecked")
    private void handleBuild(Player player, Map<String, Object> buildMap) {
        World world = player.getWorld();
        Location base = player.getLocation();

        String shape = string(buildMap.get("shape"), "platform");
        String materialName = string(buildMap.get("material"), "OAK_PLANKS");
        Material material = Material.matchMaterial(materialName.toUpperCase());
        if (material == null) {
            material = Material.OAK_PLANKS;
        }

        int size = number(buildMap.get("size"), 3).intValue();
        if (size < 1) size = 1;

        Map<String, Object> offsetMap = null;
        if (buildMap.get("offset") instanceof Map<?, ?> off) {
            offsetMap = (Map<String, Object>) off;
        } else if (buildMap.get("safe_offset") instanceof Map<?, ?> off2) {
            offsetMap = (Map<String, Object>) off2;
        }

        Location origin = base.clone();
        if (offsetMap != null) {
            double dx = number(offsetMap.get("dx"), 0).doubleValue();
            double dy = number(offsetMap.get("dy"), 0).doubleValue();
            double dz = number(offsetMap.get("dz"), 0).doubleValue();
            origin.add(dx, dy, dz);
        }

        shape = shape.toLowerCase();
        switch (shape) {
            case "platform" -> buildPlatform(world, origin, size, material);
            case "house" -> buildSimpleHouse(world, origin, size, material);
            case "wall" -> buildWall(world, origin, size, material);
            case "line" -> buildLine(world, origin, size, material);
            case "sphere" -> buildSphere(world, origin, size, material, false);
            case "hollow_sphere" -> buildSphere(world, origin, size, material, true);
            case "cylinder" -> buildCylinder(world, origin, size, material);
            case "floating_platform" -> buildPlatform(world, origin.add(0, size, 0), size, material);
            case "heart_pad" -> buildHeartPad(world, origin, size, material);
            default -> buildPlatform(world, origin, size, material);
        }

        player.sendMessage(ChatColor.YELLOW + "✧ 世界根据你的心念，构筑了「" + shape + "」。");
    }

    private void buildPlatform(World world, Location origin, int radius, Material mat) {
        int ox = origin.getBlockX();
        int oy = origin.getBlockY();
        int oz = origin.getBlockZ();

        for (int x = -radius; x <= radius; x++) {
            for (int z = -radius; z <= radius; z++) {
                world.getBlockAt(ox + x, oy, oz + z).setType(mat);
            }
        }
    }

    private void buildWall(World world, Location origin, int size, Material mat) {
        int ox = origin.getBlockX();
        int oy = origin.getBlockY();
        int oz = origin.getBlockZ();

        int h = Math.max(3, size);
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < size; x++) {
                world.getBlockAt(ox + x, oy + y, oz).setType(mat);
            }
        }
    }

    private void buildLine(World world, Location origin, int length, Material mat) {
        int ox = origin.getBlockX();
        int oy = origin.getBlockY();
        int oz = origin.getBlockZ();
        for (int i = 0; i < length; i++) {
            world.getBlockAt(ox + i, oy, oz).setType(mat);
        }
    }

    private void buildSimpleHouse(World world, Location origin, int size, Material mat) {
        int ox = origin.getBlockX();
        int oy = origin.getBlockY();
        int oz = origin.getBlockZ();

        int w = size;
        int h = Math.max(3, size);

        // 地板
        for (int x = 0; x < w; x++) {
            for (int z = 0; z < w; z++) {
                world.getBlockAt(ox + x, oy, oz + z).setType(mat);
            }
        }

        // 墙
        for (int y = 1; y <= h; y++) {
            for (int x = 0; x < w; x++) {
                world.getBlockAt(ox + x, oy + y, oz).setType(mat);
                world.getBlockAt(ox + x, oy + y, oz + w - 1).setType(mat);
            }
            for (int z = 0; z < w; z++) {
                world.getBlockAt(ox, oy + y, oz + z).setType(mat);
                world.getBlockAt(ox + w - 1, oy + y, oz + z).setType(mat);
            }
        }

        // 顶
        for (int x = 0; x < w; x++) {
            for (int z = 0; z < w; z++) {
                world.getBlockAt(ox + x, oy + h + 1, oz + z).setType(mat);
            }
        }
    }

    private void buildSphere(World world, Location origin, int radius, Material mat, boolean hollow) {
        int ox = origin.getBlockX();
        int oy = origin.getBlockY();
        int oz = origin.getBlockZ();

        int r2 = radius * radius;
        int inner = (radius - 1) * (radius - 1);

        for (int x = -radius; x <= radius; x++) {
            for (int y = -radius; y <= radius; y++) {
                for (int z = -radius; z <= radius; z++) {
                    int d2 = x * x + y * y + z * z;
                    if (d2 > r2) continue;
                    if (hollow && d2 < inner) continue;
                    world.getBlockAt(ox + x, oy + y, oz + z).setType(mat);
                }
            }
        }
    }

    private void buildCylinder(World world, Location origin, int radius, Material mat) {
        int ox = origin.getBlockX();
        int oy = origin.getBlockY();
        int oz = origin.getBlockZ();

        int h = Math.max(3, radius);

        for (int y = 0; y < h; y++) {
            for (int x = -radius; x <= radius; x++) {
                for (int z = -radius; z <= radius; z++) {
                    if (x * x + z * z <= radius * radius) {
                        world.getBlockAt(ox + x, oy + y, oz + z).setType(mat);
                    }
                }
            }
        }
    }

    /**
     * 小心悦专属：地上画一个 ♥
     */
    private void buildHeartPad(World world, Location origin, int size, Material mat) {
        int ox = origin.getBlockX();
        int oy = origin.getBlockY();
        int oz = origin.getBlockZ();

        double r = size;

        for (int x = -size; x <= size; x++) {
            for (int z = -size; z <= size; z++) {
                double nx = x / r;
                double nz = z / r;
                double f = Math.pow(nx * nx + nz * nz - 1, 3) - nx * nx * nz * nz * nz;
                if (f <= 0) {
                    world.getBlockAt(ox + x, oy, oz + z).setType(mat);
                }
            }
        }
    }

    // ========================= spawn =========================

    @SuppressWarnings("unchecked")
    private void handleSpawn(Player player, Map<String, Object> spawnMap) {
        World world = player.getWorld();
        Location base = player.getLocation();

        String typeName = string(spawnMap.get("type"), "ARMOR_STAND");
        String name = string(spawnMap.get("name"), "");

        Map<String, Object> offsetMap = null;
        if (spawnMap.get("offset") instanceof Map<?, ?> off) {
            offsetMap = (Map<String, Object>) off;
        }

        Location loc = base.clone();
        if (offsetMap != null) {
            double dx = number(offsetMap.get("dx"), 0).doubleValue();
            double dy = number(offsetMap.get("dy"), 0).doubleValue();
            double dz = number(offsetMap.get("dz"), 0).doubleValue();
            loc.add(dx, dy, dz);
        }

        EntityType type = EntityType.fromName(typeName.toUpperCase());
        if (type == null) {
            type = EntityType.ARMOR_STAND;
        }

        Entity entity = world.spawnEntity(loc, type);
        if (entity instanceof LivingEntity living) {
            if (!name.isEmpty()) {
                living.setCustomName(name);
                living.setCustomNameVisible(true);
            }
            var attr = living.getAttribute(Attribute.GENERIC_MAX_HEALTH);
            if (attr != null) {
                attr.setBaseValue(40.0);
                living.setHealth(40.0);
            }
        }

        player.sendMessage(ChatColor.LIGHT_PURPLE + "✧ 世界召唤了一个存在：" +
                (name.isEmpty() ? type.name() : name));
    }

    // ========================= effect =========================

    private void handleEffect(Player player, Map<String, Object> effMap) {
        String typeName = string(effMap.get("type"), "SPEED");
        int seconds = number(effMap.get("seconds"), 5).intValue();
        int amplifier = number(effMap.get("amplifier"), 1).intValue();

        PotionEffectType pet = PotionEffectType.getByName(typeName.toUpperCase());
        if (pet == null) {
            pet = PotionEffectType.SPEED;
        }

        player.addPotionEffect(new PotionEffect(pet, seconds * 20, amplifier));
        player.sendMessage(ChatColor.DARK_PURPLE + "✧ 你的状态被「" + typeName + "」轻轻改变。");
    }

    // ========================= particle =========================

    private void handleParticle(Player player, Map<String, Object> pMap) {
        World world = player.getWorld();
        Location base = player.getLocation().add(0, 1, 0);

        String typeName = string(pMap.get("type"), "HEART");
        int count = number(pMap.get("count"), 40).intValue();
        double radius = number(pMap.get("radius"), 1.5).doubleValue();

        Particle particle = Particle.HEART;
        try {
            particle = Particle.valueOf(typeName.toUpperCase());
        } catch (IllegalArgumentException ignored) {}

        for (int i = 0; i < count; i++) {
            double angle = 2 * Math.PI * i / count;
            double dx = Math.cos(angle) * radius;
            double dz = Math.sin(angle) * radius;
            world.spawnParticle(particle, base.getX() + dx, base.getY(), base.getZ() + dz, 1, 0, 0, 0, 0);
        }

        player.sendMessage(ChatColor.LIGHT_PURPLE + "✧ 粒子在你周围旋转，像飘移的思绪。");
    }

    // ========================= sound =========================

    private void handleSound(Player player, Map<String, Object> sMap) {
        Location loc = player.getLocation();

        String typeName = string(sMap.get("type"), "BLOCK_NOTE_BLOCK_BELL");
        float volume = number(sMap.get("volume"), 1.0).floatValue();
        float pitch = number(sMap.get("pitch"), 1.0).floatValue();

        Sound sound = Sound.BLOCK_NOTE_BLOCK_BELL;
        try {
            sound = Sound.valueOf(typeName.toUpperCase());
        } catch (IllegalArgumentException ignored) {}

        player.getWorld().playSound(loc, sound, volume, pitch);
    }

    // ========================= title / actionbar =========================

    private void handleTitle(Player player, Map<String, Object> tMap) {
        String main = string(tMap.get("main"), "");
        String sub = string(tMap.get("sub"), "");
        int fadeIn = number(tMap.get("fade_in"), 10).intValue();
        int stay = number(tMap.get("stay"), 60).intValue();
        int fadeOut = number(tMap.get("fade_out"), 10).intValue();

        player.sendTitle(
                ChatColor.LIGHT_PURPLE + main,
                ChatColor.WHITE + sub,
                fadeIn, stay, fadeOut
        );
    }

    private void handleActionBar(Player player, String text) {
        player.sendActionBar(ChatColor.AQUA + text);
    }

    // ========================= 工具 =========================

    private String string(Object o, String def) {
        return o == null ? def : o.toString();
    }

    private Number number(Object o, Number def) {
        if (o instanceof Number n) return n;
        if (o == null) return def;
        try {
            return Double.parseDouble(o.toString());
        } catch (Exception e) {
            return def;
        }
    }
}