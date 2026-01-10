package com.driftmc.atmosphere;

import java.io.IOException;
import java.text.DecimalFormat;
import java.util.List;
import java.util.UUID;

import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.Particle;
import org.bukkit.Sound;
import org.bukkit.WeatherType;
import org.bukkit.entity.Player;
import org.bukkit.scheduler.BukkitScheduler;

import com.driftmc.DriftPlugin;
import com.driftmc.backend.BackendClient;
import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.annotations.SerializedName;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Response;
import okhttp3.ResponseBody;

/**
 * Pulls social feedback atmosphere recommendations from the backend and
 * translates them into in-game ambience for the joining player.
 */
public final class SocialAtmosphereManager {

    private static final DecimalFormat PERCENT_FORMAT = new DecimalFormat("0");

    private final DriftPlugin plugin;
    private final BackendClient backend;
    private final Gson gson;

    public SocialAtmosphereManager(DriftPlugin plugin, BackendClient backend) {
        this.plugin = plugin;
        this.backend = backend;
        this.gson = new Gson();
    }

    public void scheduleFor(Player player) {
        if (player == null) {
            return;
        }
        UUID playerId = player.getUniqueId();
        Bukkit.getScheduler().runTaskLater(plugin, () -> requestAndApply(playerId), 60L);
    }

    private void requestAndApply(UUID playerId) {
        backend.getAsync("/ideal-city/social-feedback/atmosphere", new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                notifyFailure(playerId, ChatColor.RED + "[CityPhone] 未能同步城市气氛。");
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                try (response) {
                    ResponseBody body = response.body();
                    if (!response.isSuccessful() || body == null) {
                        notifyFailure(playerId, ChatColor.RED + "[CityPhone] 城市气氛接口暂不可用。");
                        return;
                    }
                    JsonObject root = JsonParser.parseString(body.string()).getAsJsonObject();
                    String status = root.has("status") ? root.get("status").getAsString() : "error";
                    if (!"ok".equalsIgnoreCase(status)) {
                        notifyFailure(playerId, ChatColor.RED + "[CityPhone] 城市气氛未准备就绪。");
                        return;
                    }
                    if (!root.has("atmosphere") || root.get("atmosphere").isJsonNull()) {
                        notifyFailure(playerId, ChatColor.RED + "[CityPhone] 缺少城市气氛数据。");
                        return;
                    }
                    AtmospherePayload payload = gson.fromJson(root.get("atmosphere"), AtmospherePayload.class);
                    if (payload == null || payload.effect == null || payload.snapshot == null) {
                        notifyFailure(playerId, ChatColor.RED + "[CityPhone] 城市气氛解析失败。");
                        return;
                    }
                    handleResponse(playerId, payload);
                } catch (Exception ex) {
                    notifyFailure(playerId, ChatColor.RED + "[CityPhone] 城市气氛解析异常。");
                    plugin.getLogger().warning("[Atmosphere] Failed to parse atmosphere payload: " + ex.getMessage());
                }
            }
        });
    }

    private void notifyFailure(UUID playerId, String message) {
        BukkitScheduler scheduler = Bukkit.getScheduler();
        scheduler.runTask(plugin, () -> {
            Player target = Bukkit.getPlayer(playerId);
            if (target != null && target.isOnline()) {
                target.sendMessage(message);
            }
        });
    }

    private void handleResponse(UUID playerId, AtmospherePayload payload) {
        BukkitScheduler scheduler = Bukkit.getScheduler();
        scheduler.runTask(plugin, () -> {
            Player player = Bukkit.getPlayer(playerId);
            if (player == null || !player.isOnline()) {
                return;
            }
            applyEffect(player, payload);
        });
    }

    private void applyEffect(Player player, AtmospherePayload payload) {
        SocialEffect effect = payload.effect;
        SocialSnapshot snapshot = payload.snapshot;

        applyWeather(player, effect.weather);
        playSound(player, effect.sound);
        spawnParticles(player, effect);

        double trustPercent = Math.max(0.0, Math.min(100.0, snapshot.trustIndex * 100.0));
        double stressPercent = Math.max(0.0, Math.min(100.0, snapshot.stressIndex * 100.0));

        String subtitle = ChatColor.GRAY + "信任 " + PERCENT_FORMAT.format(trustPercent) + "% · 压力 "
                + PERCENT_FORMAT.format(stressPercent) + "%";
        String title = ChatColor.LIGHT_PURPLE + (effect.headline != null ? effect.headline : "城市舆论更新");
        player.sendTitle(title, subtitle, 10, 80, 20);

        player.sendMessage(ChatColor.AQUA + "—— 城市社情 ——");
        if (effect.detailLines != null && !effect.detailLines.isEmpty()) {
            for (String line : effect.detailLines) {
                player.sendMessage(ChatColor.WHITE + " • " + ChatColor.GRAY + line);
            }
        } else if (snapshot.entries != null && !snapshot.entries.isEmpty()) {
            SocialEntry entry = snapshot.entries.get(0);
            player.sendMessage(ChatColor.WHITE + " • " + ChatColor.GRAY + entry.title);
        }
    }

    private void applyWeather(Player player, String weatherKey) {
        if (weatherKey == null || weatherKey.isBlank()) {
            player.resetPlayerWeather();
            return;
        }
        String lowered = weatherKey.toLowerCase();
        if ("rain".equals(lowered)) {
            player.setPlayerWeather(WeatherType.DOWNFALL);
            scheduleWeatherReset(player.getUniqueId(), 200L);
        } else if ("thunder".equals(lowered)) {
            player.setPlayerWeather(WeatherType.DOWNFALL);
            player.playSound(player.getLocation(), Sound.ENTITY_LIGHTNING_BOLT_THUNDER, 0.6f, 1.0f);
            scheduleWeatherReset(player.getUniqueId(), 200L);
        } else {
            player.resetPlayerWeather();
        }
    }

    private void scheduleWeatherReset(UUID playerId, long delayTicks) {
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            Player target = Bukkit.getPlayer(playerId);
            if (target != null && target.isOnline()) {
                target.resetPlayerWeather();
            }
        }, delayTicks);
    }

    private void playSound(Player player, String soundKey) {
        if (soundKey == null || soundKey.isBlank()) {
            return;
        }
        try {
            Sound sound = Sound.valueOf(soundKey);
            player.playSound(player.getLocation(), sound, 0.8f, 1.0f);
        } catch (IllegalArgumentException ignored) {
            plugin.getLogger().warning("[Atmosphere] Unknown sound key: " + soundKey);
        }
    }

    private void spawnParticles(Player player, SocialEffect effect) {
        if (effect.particle == null || effect.particle.isBlank()) {
            return;
        }
        try {
            Particle particle = Particle.valueOf(effect.particle);
            int count = Math.max(1, effect.particleCount);
            double radius = Math.max(0.5d, effect.particleRadius);
            player.getWorld().spawnParticle(
                    particle,
                    player.getLocation().add(0, 1.0d, 0),
                    count,
                    radius,
                    radius / 2.0d,
                    radius,
                    0.01d);
        } catch (IllegalArgumentException ignored) {
            plugin.getLogger().warning("[Atmosphere] Unknown particle key: " + effect.particle);
        }
    }

    private static final class AtmospherePayload {
        @SerializedName("snapshot")
        private SocialSnapshot snapshot;
        @SerializedName("effect")
        private SocialEffect effect;
    }

    private static final class SocialSnapshot {
        @SerializedName("trust_index")
        private double trustIndex;
        @SerializedName("stress_index")
        private double stressIndex;
        @SerializedName("entries")
        private List<SocialEntry> entries;
    }

    private static final class SocialEntry {
        @SerializedName("entry_id")
        private String entryId;
        @SerializedName("category")
        private String category;
        @SerializedName("title")
        private String title;
        @SerializedName("body")
        private String body;
    }

    private static final class SocialEffect {
        @SerializedName("mood")
        private String mood;
        @SerializedName("intensity")
        private String intensity;
        @SerializedName("particle")
        private String particle;
        @SerializedName("particle_count")
        private int particleCount;
        @SerializedName("particle_radius")
        private double particleRadius;
        @SerializedName("sound")
        private String sound;
        @SerializedName("weather")
        private String weather;
        @SerializedName("headline")
        private String headline;
        @SerializedName("detail_lines")
        private List<String> detailLines;
        @SerializedName("dominant_category")
        private String dominantCategory;
    }
}
