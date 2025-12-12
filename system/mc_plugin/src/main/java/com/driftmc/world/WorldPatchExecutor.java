package com.driftmc.world;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.SoundCategory;
import org.bukkit.World;
import org.bukkit.attribute.Attribute;
import org.bukkit.entity.Entity;
import org.bukkit.entity.EntityType;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.scheduler.BukkitTask;

import com.driftmc.scene.QuestEventCanonicalizer;
import com.driftmc.scene.RuleEventBridge;

/**
 * WorldPatchExecutor
 *
 * 心悦宇宙 · 完整稳定版执行器（含 SafeTeleport v3）
 *
 * 统一执行来自后端的 world_patch / mc_patch：
 *
 * 支持 key：
 * tell / weather / time / teleport / build / spawn
 * effect / particle / sound / title / actionbar
 */
public class WorldPatchExecutor {

    private final JavaPlugin plugin;
    private AdvancedWorldBuilder advancedBuilder;
    private RuleEventBridge ruleEventBridge;
    private final Map<UUID, CopyOnWriteArrayList<LocationTrigger>> triggerRegistry = new ConcurrentHashMap<>();
    private BukkitTask triggerPoller;

    public WorldPatchExecutor(JavaPlugin plugin) {
        this.plugin = plugin;
        this.advancedBuilder = new AdvancedWorldBuilder(plugin, this);
    }

    public JavaPlugin getPlugin() {
        return this.plugin;
    }

    public void setRuleEventBridge(RuleEventBridge bridge) {
        this.ruleEventBridge = bridge;
    }

    public RuleEventBridge getRuleEventBridge() {
        return this.ruleEventBridge;
    }

    /**
     * Hook for subclasses to inject featured NPC behavior during scene patches.
     * Default implementation is a no-op.
     */
    public void ensureFeaturedNpc(Player player, Map<String, Object> metadata, Map<String, Object> operations) {
        // intentionally empty
    }

    public void shutdown() {
        if (triggerPoller != null) {
            triggerPoller.cancel();
            triggerPoller = null;
        }
        triggerRegistry.clear();
    }

    // =============================== 核心入口 ===============================
    public void execute(Player player, Map<String, Object> patch) {
        if (player == null || patch == null || patch.isEmpty()) {
            return;
        }

        final Map<String, Object> patchFinal = patch;

        // —— 异步切回主线程（纸片人保护）——
        if (!Bukkit.isPrimaryThread()) {
            Bukkit.getScheduler().runTask(plugin, () -> execute(player, patchFinal));
            return;
        }

        plugin.getLogger().info("[WorldPatchExecutor] execute patch = " + patch);

        Map<String, Object> primary = patch;
        processOperationMap(player, primary);

        Object mcObj = patch.get("mc");

        if (mcObj instanceof Map) {
            Map<String, Object> mcMap = asStringObjectMap(mcObj);
            processOperationMap(player, mcMap);
        } else if (mcObj instanceof List) {
            List<?> mcList = (List<?>) mcObj;
            for (Object entry : mcList) {
                if (entry instanceof Map) {
                    Map<String, Object> entryMap = asStringObjectMap(entry);
                    processOperationMap(player, entryMap);
                }
            }
        }
    }

    @SuppressWarnings("unchecked")
    private void processOperationMap(Player player, Map<String, Object> operations) {
        if (operations == null || operations.isEmpty()) {
            return;
        }

        // tell
        handleTell(player, operations.get("tell"));

        // weather
        if (operations.containsKey("weather")) {
            handleWeather(player, string(operations.get("weather"), "clear"));
        }

        if (operations.containsKey("weather_transition")) {
            Object transitionObj = operations.get("weather_transition");
            if (transitionObj instanceof Map<?, ?> map) {
                handleWeatherTransition(player, (Map<String, Object>) map);
            } else {
                handleWeather(player, string(transitionObj, "clear"));
            }
        }

        // time
        if (operations.containsKey("time")) {
            handleTime(player, string(operations.get("time"), "day"));
        }

        if (operations.containsKey("lighting_shift")) {
            handleLightingShift(player, operations.get("lighting_shift"));
        }

        if (operations.containsKey("music")) {
            handleMusic(player, operations.get("music"));
        }

        Map<String, Object> teleportConfig = null;
        Location teleportTarget = null;
        if (operations.containsKey("teleport")) {
            Object tpObj = operations.get("teleport");
            if (tpObj instanceof Map<?, ?> tpRaw) {
                teleportConfig = (Map<String, Object>) tpRaw;
                teleportTarget = calculateSafeTeleportTarget(player, teleportConfig);
            }
        }

        Location anchorLocation = teleportTarget != null
                ? teleportTarget.clone()
                : player.getLocation().clone();

        if (operations.containsKey("trigger_zones")) {
            handleTriggerZones(player, operations.get("trigger_zones"), anchorLocation);
        }

        if (operations.containsKey("_scene_cleanup") && player != null) {
            clearPlayerTriggers(player.getUniqueId());
        }

        // build
        if (operations.containsKey("build")) {
            Object buildObj = operations.get("build");
            if (buildObj instanceof Map<?, ?> bRaw) {
                handleBuild(player, (Map<String, Object>) bRaw, anchorLocation);
            } else if (buildObj instanceof List<?> buildList) {
                for (Object entry : (List<?>) buildList) {
                    if (entry instanceof Map<?, ?> entryMap) {
                        handleBuild(player, (Map<String, Object>) entryMap, anchorLocation);
                    }
                }
            }
        }

        // build_multi（批量构建）
        if (operations.containsKey("build_multi")) {
            Object buildMultiObj = operations.get("build_multi");
            if (buildMultiObj instanceof List<?> buildList) {
                advancedBuilder.handleBuildMulti(player, buildList, anchorLocation);
            }
        }

        // spawn
        if (operations.containsKey("spawn")) {
            Object spawnObj = operations.get("spawn");
            if (spawnObj instanceof Map<?, ?> sRaw) {
                handleSpawn(player, (Map<String, Object>) sRaw, anchorLocation);
            } else if (spawnObj instanceof List<?> spawnList) {
                for (Object entry : (List<?>) spawnList) {
                    if (entry instanceof Map<?, ?> entryMap) {
                        handleSpawn(player, (Map<String, Object>) entryMap, anchorLocation);
                    }
                }
            }
        }

        // spawn_multi（批量生成实体）
        if (operations.containsKey("spawn_multi")) {
            Object spawnMultiObj = operations.get("spawn_multi");
            if (spawnMultiObj instanceof List<?> spawnList) {
                advancedBuilder.handleSpawnMulti(player, spawnList, anchorLocation);
            }
        }

        if (teleportConfig != null && teleportTarget != null) {
            performTeleport(player, teleportConfig, teleportTarget);
        }

        // effect
        if (operations.containsKey("effect")) {
            Object effObj = operations.get("effect");
            if (effObj instanceof Map<?, ?> effRaw) {
                handleEffect(player, (Map<String, Object>) effRaw);
            }
        }

        // particle
        if (operations.containsKey("particle")) {
            Object pObj = operations.get("particle");
            if (pObj instanceof Map<?, ?> pRaw) {
                handleParticle(player, (Map<String, Object>) pRaw);
            }
        }

        // sound
        if (operations.containsKey("sound")) {
            Object sObj = operations.get("sound");
            if (sObj instanceof Map<?, ?> sRaw) {
                handleSound(player, (Map<String, Object>) sRaw);
            }
        }

        // title
        if (operations.containsKey("title")) {
            Object tObj = operations.get("title");
            if (tObj instanceof Map<?, ?> tRaw) {
                handleTitle(player, (Map<String, Object>) tRaw);
            }
        }

        // actionbar
        if (operations.containsKey("actionbar")) {
            Object abObj = operations.get("actionbar");
            if (abObj instanceof String abStr) {
                handleActionBar(player, abStr);
            }
        }
    }

    // =============================== tell ===============================
    private void handleTell(Player player, Object tellObj) {
        if (tellObj == null)
            return;

        if (tellObj instanceof String tell) {
            player.sendMessage(ChatColor.AQUA + "【心悦宇宙】 " + ChatColor.WHITE + tell);
        } else if (tellObj instanceof List<?> list) {
            for (Object line : list) {
                if (line == null)
                    continue;
                player.sendMessage(ChatColor.AQUA + "【心悦宇宙】 " + ChatColor.WHITE + line.toString());
            }
        }
    }

    // =============================== weather ===============================
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

    private void handleWeatherTransition(Player player, Map<String, Object> payload) {
        if (payload == null || payload.isEmpty()) {
            return;
        }
        String fromState = string(payload.get("from"), "");
        String toState = string(payload.get("to"), string(payload.get("state"), ""));
        String message = string(payload.get("message"), "");
        if (!toState.isBlank()) {
            handleWeather(player, toState);
        }
        if (!message.isBlank()) {
            player.sendMessage(ChatColor.BLUE + "✧ " + message);
        } else if (!fromState.isBlank() || !toState.isBlank()) {
            player.sendMessage(ChatColor.BLUE + "✧ 天气转场：" + humanize(fromState) + " → " + humanize(toState));
        }
    }

    // =============================== time ===============================
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

    private void handleLightingShift(Player player, Object payload) {
        if (payload == null) {
            return;
        }

        String shiftName = "";
        String suggestedTime = "";

        if (payload instanceof String shift) {
            shiftName = shift;
        } else if (payload instanceof Map<?, ?> map) {
            shiftName = string(map.get("label"), string(map.get("id"), string(map.get("name"), "")));
            suggestedTime = string(map.get("time"), "");
        }

        if (!shiftName.isBlank()) {
            player.sendMessage(ChatColor.GOLD + "✧ 光线变化：" + humanize(shiftName));
        }

        String normalized = shiftName.toLowerCase(Locale.ROOT);
        if (!suggestedTime.isBlank()) {
            handleTime(player, suggestedTime);
        } else if (!normalized.isBlank()) {
            if (normalized.contains("sunrise") || normalized.contains("dawn")) {
                handleTime(player, "sunrise");
            } else if (normalized.contains("dusk") || normalized.contains("sunset")) {
                handleTime(player, "sunset");
            } else if (normalized.contains("night") || normalized.contains("neon")) {
                handleTime(player, "night");
            }
        }
    }

    private void handleMusic(Player player, Object payload) {
        if (payload == null) {
            return;
        }

        String record = null;
        double volume = 0.8;
        double pitch = 1.0;

        if (payload instanceof String direct) {
            record = direct;
        } else if (payload instanceof Map<?, ?> map) {
            record = string(map.get("record"), string(map.get("id"), ""));
            volume = number(map.get("volume"), 0.8).doubleValue();
            pitch = number(map.get("pitch"), 1.0).doubleValue();
        }

        if (record == null || record.isBlank()) {
            return;
        }

        Sound sound = resolveRecord(record);
        if (sound == null) {
            return;
        }

        float vol = (float) volume;
        float pit = (float) pitch;
        player.playSound(player.getLocation(), sound, SoundCategory.RECORDS, Math.max(0.0f, vol), Math.max(0.1f, pit));
        player.sendMessage(ChatColor.LIGHT_PURPLE + "♪ 音轨切换：" + humanize(record));
    }

    // =============================== teleport ★ SafeTeleport v3
    // ===============================
    private Location calculateSafeTeleportTarget(Player player, Map<String, Object> tpMap) {
        World world = player.getWorld();
        Location base = player.getLocation();

        String mode = string(tpMap.get("mode"), "relative");
        double x = number(tpMap.get("x"), 0).doubleValue();
        double y = number(tpMap.get("y"), base.getY()).doubleValue();
        double z = number(tpMap.get("z"), 0).doubleValue();

        Location rawTarget;
        if ("absolute".equalsIgnoreCase(mode)) {
            rawTarget = new Location(world, x, y, z, base.getYaw(), base.getPitch());
        } else {
            rawTarget = base.clone().add(x, y, z);
        }

        var chunk = world.getChunkAt(rawTarget);
        if (!chunk.isLoaded()) {
            chunk.load(true);
            plugin.getLogger().info("[SafeTeleport] Chunk forced load at " +
                    chunk.getX() + "," + chunk.getZ());
        }

        int highestBlockY = world.getHighestBlockYAt(rawTarget.getBlockX(), rawTarget.getBlockZ());
        double safeY = rawTarget.getY();

        if (safeY <= 1) {
            safeY = highestBlockY + 1.2;
        } else if (safeY - highestBlockY > 6) {
            safeY = highestBlockY + 1.2;
        }

        Material blockAt = world.getBlockAt(rawTarget).getType();
        if (blockAt.isSolid()) {
            safeY = Math.max(safeY, highestBlockY + 1.2);
            plugin.getLogger().warning("[SafeTeleport] inside solid block → Y fixed to " + safeY);
        }

        return new Location(
                world,
                rawTarget.getX(),
                safeY,
                rawTarget.getZ(),
                base.getYaw(),
                base.getPitch());
    }

    @SuppressWarnings("unchecked")
    private void performTeleport(Player player, Map<String, Object> tpMap, Location safeTarget) {
        World world = player.getWorld();

        Bukkit.getScheduler().runTask(plugin, () -> {
            player.teleport(safeTarget);
            plugin.getLogger().info(String.format("[SafeTeleport] Player teleported to %.2f,%.2f,%.2f",
                    safeTarget.getX(), safeTarget.getY(), safeTarget.getZ()));

            player.sendMessage(ChatColor.GREEN + "✧ 你被世界轻轻挪到了一个安全的位置。");

            if (tpMap.containsKey("safe_platform")) {
                Object spObj = tpMap.get("safe_platform");
                if (spObj instanceof Map<?, ?> spRaw) {
                    Map<String, Object> sp = (Map<String, Object>) spRaw;
                    String matName = string(sp.get("material"), "GLASS");
                    int radius = number(sp.get("radius"), 2).intValue();
                    Material mat = Material.matchMaterial(matName.toUpperCase());
                    if (mat == null) {
                        mat = Material.GLASS;
                    }
                    buildPlatform(world, safeTarget.clone().add(0, -1, 0), radius, mat);
                }
            }
        });
    }

    // =============================== build ===============================

    @SuppressWarnings("unchecked")
    private void handleBuild(Player player, Map<String, Object> buildMap, Location anchor) {
        World world = player.getWorld();
        Location base = anchor != null ? anchor.clone() : player.getLocation().clone();

        String shape = string(buildMap.get("shape"), "platform");
        String materialName = string(buildMap.get("material"), "OAK_PLANKS");
        Material material = Material.matchMaterial(materialName.toUpperCase());
        if (material == null)
            material = Material.OAK_PLANKS;

        int size = number(buildMap.get("size"), 3).intValue();
        if (size < 1)
            size = 1;

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

        for (int x = 0; x < w; x++) {
            for (int z = 0; z < w; z++) {
                world.getBlockAt(ox + x, oy, oz + z).setType(mat);
            }
        }

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
                    if (d2 > r2)
                        continue;
                    if (hollow && d2 < inner)
                        continue;
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

    // ♥ 小心悦专属心形平台
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

    // =============================== spawn ===============================
    @SuppressWarnings("unchecked")
    private void handleSpawn(Player player, Map<String, Object> spawnMap, Location anchor) {
        World world = player.getWorld();
        Location base = anchor != null ? anchor.clone() : player.getLocation().clone();

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

    // =============================== effect ===============================
    private void handleEffect(Player player, Map<String, Object> effMap) {
        String typeName = string(effMap.get("type"), "SPEED");
        int seconds = number(effMap.get("seconds"), 5).intValue();
        int amplifier = number(effMap.get("amplifier"), 1).intValue();

        PotionEffectType pet = PotionEffectType.getByName(typeName.toUpperCase());
        if (pet == null)
            pet = PotionEffectType.SPEED;

        player.addPotionEffect(new PotionEffect(pet, seconds * 20, amplifier));
        player.sendMessage(ChatColor.DARK_PURPLE + "✧ 你的状态被「" + typeName + "」轻轻改变。");
    }

    // =============================== particle ===============================
    private void handleParticle(Player player, Map<String, Object> pMap) {
        World world = player.getWorld();
        Location base = player.getLocation().add(0, 1, 0);

        String typeName = string(pMap.get("type"), "HEART");
        int count = number(pMap.get("count"), 40).intValue();
        double radius = number(pMap.get("radius"), 1.5).doubleValue();

        Particle particle = Particle.HEART;
        try {
            particle = Particle.valueOf(typeName.toUpperCase());
        } catch (IllegalArgumentException ignored) {
        }

        for (int i = 0; i < count; i++) {
            double angle = 2 * Math.PI * i / count;
            double dx = Math.cos(angle) * radius;
            double dz = Math.sin(angle) * radius;
            world.spawnParticle(particle, base.getX() + dx, base.getY(), base.getZ() + dz, 1, 0, 0, 0, 0);
        }

        player.sendMessage(ChatColor.LIGHT_PURPLE + "✧ 粒子在你周围旋转，像飘移的思绪。");
    }

    // =============================== sound ===============================
    private void handleSound(Player player, Map<String, Object> sMap) {
        Location loc = player.getLocation();

        String typeName = string(sMap.get("type"), "BLOCK_NOTE_BLOCK_BELL");
        float volume = number(sMap.get("volume"), 1.0).floatValue();
        float pitch = number(sMap.get("pitch"), 1.0).floatValue();

        Sound sound = Sound.BLOCK_NOTE_BLOCK_BELL;
        try {
            sound = Sound.valueOf(typeName.toUpperCase());
        } catch (IllegalArgumentException ignored) {
        }

        player.getWorld().playSound(loc, sound, volume, pitch);
    }

    // =============================== title / actionbar
    // ===============================
    private void handleTitle(Player player, Map<String, Object> tMap) {
        String main = string(tMap.get("main"), "");
        String sub = string(tMap.get("sub"), "");
        int fadeIn = number(tMap.get("fade_in"), 10).intValue();
        int stay = number(tMap.get("stay"), 60).intValue();
        int fadeOut = number(tMap.get("fade_out"), 10).intValue();

        player.sendTitle(
                ChatColor.LIGHT_PURPLE + main,
                ChatColor.WHITE + sub,
                fadeIn, stay, fadeOut);
    }

    private void handleActionBar(Player player, String text) {
        player.sendActionBar(ChatColor.AQUA + text);
    }

    // =============================== triggers ===============================
    private void handleTriggerZones(Player player, Object spec, Location anchor) {
        if (player == null || spec == null) {
            return;
        }

        List<Map<String, Object>> entries = new ArrayList<>();
        if (spec instanceof Map<?, ?> map) {
            entries.add(asStringObjectMap(map));
        } else if (spec instanceof List<?> list) {
            for (Object entry : list) {
                if (entry instanceof Map<?, ?> entryMap) {
                    entries.add(asStringObjectMap(entryMap));
                }
            }
        }

        if (entries.isEmpty()) {
            return;
        }

        clearPlayerTriggers(player.getUniqueId());

        Location reference = anchor != null ? anchor.clone() : player.getLocation().clone();
        CopyOnWriteArrayList<LocationTrigger> triggers = new CopyOnWriteArrayList<>();

        for (Map<String, Object> entry : entries) {
            String questEvent = string(entry.get("quest_event"), "").toLowerCase(Locale.ROOT);
            questEvent = QuestEventCanonicalizer.canonicalize(questEvent);
            if (questEvent.isBlank()) {
                continue;
            }
            double radius = number(entry.get("radius"), 3.0D).doubleValue();
            boolean repeat = Boolean.TRUE.equals(entry.get("repeat"));
            boolean once = !repeat;
            Location center = resolveTriggerCenter(reference, entry, player);
            String triggerId = string(entry.get("id"), questEvent);
            triggers.add(new LocationTrigger(triggerId, center, radius, questEvent, once));
        }

        if (triggers.isEmpty()) {
            return;
        }

        triggerRegistry.put(player.getUniqueId(), triggers);
        ensureTriggerTask();
    }

    private void ensureTriggerTask() {
        if (triggerPoller != null) {
            return;
        }
        triggerPoller = Bukkit.getScheduler().runTaskTimer(plugin, this::pollTriggerZones, 40L, 20L);
    }

    private void pollTriggerZones() {
        if (triggerRegistry.isEmpty()) {
            return;
        }

        List<UUID> removals = new ArrayList<>();

        for (Map.Entry<UUID, CopyOnWriteArrayList<LocationTrigger>> entry : triggerRegistry.entrySet()) {
            UUID playerId = entry.getKey();
            Player player = Bukkit.getPlayer(playerId);
            if (player == null || !player.isOnline()) {
                removals.add(playerId);
                continue;
            }

            CopyOnWriteArrayList<LocationTrigger> triggers = entry.getValue();
            if (triggers == null || triggers.isEmpty()) {
                removals.add(playerId);
                continue;
            }

            Location playerLoc = player.getLocation();
            if (playerLoc.getWorld() == null) {
                continue;
            }

            for (LocationTrigger trigger : triggers) {
                if (trigger.once && trigger.triggered) {
                    continue;
                }
                if (trigger.center.getWorld() == null || !playerLoc.getWorld().equals(trigger.center.getWorld())) {
                    continue;
                }
                if (playerLoc.distanceSquared(trigger.center) <= trigger.radiusSq) {
                    trigger.triggered = true;
                    if (ruleEventBridge != null) {
                        Map<String, Object> payload = new LinkedHashMap<>();
                        payload.put("trigger_id", trigger.id);
                        payload.put("radius", trigger.radius);
                        payload.put("source", "trigger_zone");
                        ruleEventBridge.emitQuestEvent(player, trigger.questEvent, trigger.center, payload);
                    }
                }
            }

            triggers.removeIf(LocationTrigger::shouldRemove);
            if (triggers.isEmpty()) {
                removals.add(playerId);
            }
        }

        for (UUID playerId : removals) {
            triggerRegistry.remove(playerId);
        }

        if (triggerRegistry.isEmpty() && triggerPoller != null) {
            triggerPoller.cancel();
            triggerPoller = null;
        }
    }

    private void clearPlayerTriggers(UUID playerId) {
        triggerRegistry.remove(playerId);
        if (triggerRegistry.isEmpty() && triggerPoller != null) {
            triggerPoller.cancel();
            triggerPoller = null;
        }
    }

    private Location resolveTriggerCenter(Location anchor, Map<String, Object> spec, Player fallback) {
        Location base;
        if (anchor != null) {
            base = anchor.clone();
        } else if (fallback != null) {
            base = fallback.getLocation().clone();
        } else if (!Bukkit.getWorlds().isEmpty()) {
            base = Bukkit.getWorlds().get(0).getSpawnLocation().clone();
        } else {
            return new Location(null, 0, 0, 0);
        }

        String worldName = string(spec.get("world"), "");
        if (!worldName.isBlank()) {
            var world = Bukkit.getWorld(worldName);
            if (world != null) {
                base.setWorld(world);
            }
        }

        double x = base.getX();
        double y = base.getY();
        double z = base.getZ();

        if (spec.get("x") != null) {
            x = number(spec.get("x"), x).doubleValue();
        }
        if (spec.get("y") != null) {
            y = number(spec.get("y"), y).doubleValue();
        }
        if (spec.get("z") != null) {
            z = number(spec.get("z"), z).doubleValue();
        }

        Map<String, Object> offset = asStringObjectMap(spec.get("offset"));
        if (!offset.isEmpty()) {
            x += number(offset.get("dx"), 0).doubleValue();
            y += number(offset.get("dy"), 0).doubleValue();
            z += number(offset.get("dz"), 0).doubleValue();
        }

        if (spec.get("dx") != null || spec.get("dy") != null || spec.get("dz") != null) {
            x += number(spec.get("dx"), 0).doubleValue();
            y += number(spec.get("dy"), 0).doubleValue();
            z += number(spec.get("dz"), 0).doubleValue();
        }

        return new Location(base.getWorld(), x, y, z);
    }

    // =============================== 工具 ===============================
    private String string(Object o, String def) {
        return o == null ? def : o.toString();
    }

    private Number number(Object o, Number def) {
        if (o instanceof Number n)
            return n;
        if (o == null)
            return def;
        try {
            return Double.parseDouble(o.toString());
        } catch (Exception e) {
            return def;
        }
    }

    private Map<String, Object> asStringObjectMap(Object value) {
        if (!(value instanceof Map<?, ?> raw)) {
            return Collections.emptyMap();
        }

        Map<String, Object> converted = new LinkedHashMap<>();
        for (Map.Entry<?, ?> entry : raw.entrySet()) {
            Object key = entry.getKey();
            if (key instanceof String keyStr) {
                converted.put(keyStr, entry.getValue());
            }
        }
        return converted;
    }

    private Sound resolveRecord(String recordName) {
        if (recordName == null) {
            return null;
        }
        String token = recordName.trim();
        if (token.isEmpty()) {
            return null;
        }
        token = token.replace("minecraft:", "");
        token = token.replace("record_", "");
        token = token.replace('-', '_');
        String enumName = token.toUpperCase(Locale.ROOT);
        if (!enumName.startsWith("MUSIC_DISC_")) {
            enumName = "MUSIC_DISC_" + enumName;
        }
        try {
            return Sound.valueOf(enumName);
        } catch (IllegalArgumentException ex) {
            plugin.getLogger().fine("[WorldPatchExecutor] Unknown record: " + recordName);
            return null;
        }
    }

    private String humanize(String token) {
        if (token == null || token.isBlank()) {
            return "平缓";
        }
        String cleaned = token.replace("minecraft:", "").replace('_', ' ').trim();
        if (cleaned.isEmpty()) {
            return token;
        }
        return cleaned.substring(0, 1).toUpperCase(Locale.ROOT) + cleaned.substring(1);
    }

    private static final class LocationTrigger {
        final String id;
        final Location center;
        final double radius;
        final double radiusSq;
        final String questEvent;
        final boolean once;
        boolean triggered;

        LocationTrigger(String id, Location center, double radius, String questEvent, boolean once) {
            this.id = id;
            this.center = center;
            this.radius = radius;
            this.radiusSq = radius * radius;
            this.questEvent = questEvent;
            this.once = once;
            this.triggered = false;
        }

        boolean shouldRemove() {
            return once && triggered;
        }
    }
}
