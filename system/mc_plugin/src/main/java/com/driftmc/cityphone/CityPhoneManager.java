package com.driftmc.cityphone;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.function.Consumer;
import java.util.concurrent.ConcurrentHashMap;

import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.scheduler.BukkitScheduler;
import org.bukkit.util.Vector;

import com.driftmc.DriftPlugin;
import com.driftmc.backend.BackendClient;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Response;
import okhttp3.ResponseBody;

public final class CityPhoneManager {

  private static final String DEFAULT_SCENARIO = "default";
  private static final Gson GSON = new GsonBuilder().create();

  private final DriftPlugin plugin;
  private final BackendClient backend;
  private final NamespacedKey phoneKey;
  private final Map<UUID, CityPhoneSnapshot> snapshotCache = new ConcurrentHashMap<>();

  public CityPhoneManager(DriftPlugin plugin, BackendClient backend) {
    this.plugin = plugin;
    this.backend = backend;
    this.phoneKey = new NamespacedKey(plugin, "cityphone_device");
  }

  public void givePhone(Player player) {
    player.getInventory().addItem(createPhoneItem());
    player.sendMessage(CityPhoneLocalization.prefixed("message.phone_received", NamedTextColor.AQUA));
  }

  public ItemStack createPhoneItem() {
    ItemStack stack = new ItemStack(Material.COMPASS);
    ItemMeta meta = stack.getItemMeta();
    if (meta != null) {
      meta.displayName(CityPhoneLocalization.component("device.display_name", NamedTextColor.AQUA));
      List<String> lore = CityPhoneLocalization.list("device.lore");
      List<Component> loreComponents = new ArrayList<>();
      if (!lore.isEmpty()) {
        loreComponents.add(Component.text(lore.get(0), NamedTextColor.GRAY));
      }
      if (lore.size() > 1) {
        loreComponents.add(Component.text(lore.get(1), NamedTextColor.DARK_GRAY));
      }
      meta.lore(loreComponents);
      PersistentDataContainer container = meta.getPersistentDataContainer();
      container.set(phoneKey, PersistentDataType.STRING, "1");
      stack.setItemMeta(meta);
    }
    return stack;
  }

  public boolean isCityPhone(ItemStack stack) {
    if (stack == null || stack.getType() == Material.AIR) {
      return false;
    }
    ItemMeta meta = stack.getItemMeta();
    if (meta == null) {
      return false;
    }
    PersistentDataContainer container = meta.getPersistentDataContainer();
    return container.has(phoneKey, PersistentDataType.STRING);
  }

  public void openPhone(Player player) {
    UUID playerId = player.getUniqueId();
    String playerName = player.getName();
    requestState(playerId, playerName, snapshot -> {
      Player target = Bukkit.getPlayer(playerId);
      if (target != null) {
        CityPhoneSnapshot previous = snapshotCache.put(playerId, snapshot);
        maybeAnnounceModeChange(target, previous, snapshot);
        CityPhoneUi.open(target, snapshot);
      } else {
        snapshotCache.put(playerId, snapshot);
      }
    });
  }

  public void openHistory(Player player) {
    UUID playerId = player.getUniqueId();
    CityPhoneSnapshot snapshot = snapshotCache.get(playerId);
    if (snapshot == null) {
      player.sendMessage(CityPhoneLocalization.prefixed("message.syncing", NamedTextColor.YELLOW));
      openPhone(player);
      return;
    }
    CityPhoneUi.openHistory(player, snapshot);
  }

  public void openNarrative(Player player) {
    UUID playerId = player.getUniqueId();
    CityPhoneSnapshot snapshot = snapshotCache.get(playerId);
    if (snapshot == null) {
      player.sendMessage(CityPhoneLocalization.prefixed("message.syncing", NamedTextColor.YELLOW));
      openPhone(player);
      return;
    }
    CityPhoneNarrativePanel.open(player, snapshot);
  }

  public void reopenFromCache(Player player) {
    UUID playerId = player.getUniqueId();
    CityPhoneSnapshot snapshot = snapshotCache.get(playerId);
    if (snapshot == null) {
      openPhone(player);
      return;
    }
    CityPhoneUi.open(player, snapshot);
  }

  public void submitNarrative(Player player, String narrative) {
    if (narrative == null || narrative.isBlank()) {
      player.sendMessage(CityPhoneLocalization.prefixed("message.narrative_missing", NamedTextColor.RED));
      return;
    }
    JsonObject payload = new JsonObject();
    payload.addProperty("player_id", player.getName());
    payload.addProperty("scenario_id", DEFAULT_SCENARIO);
    payload.addProperty("action", "submit_narrative");
    JsonObject body = new JsonObject();
    body.addProperty("narrative", narrative.trim());
    payload.add("payload", body);

    dispatchAction(player.getUniqueId(), payload, CityPhoneLocalization.text("message.narrative_synced"));
  }

  public void submitPose(Player player) {
    JsonObject payload = new JsonObject();
    payload.addProperty("player_id", player.getName());
    payload.addProperty("scenario_id", DEFAULT_SCENARIO);
    payload.addProperty("action", "push_pose");

    JsonObject pose = new JsonObject();
    pose.addProperty("world", player.getWorld().getName());
    pose.addProperty("x", player.getLocation().getX());
    pose.addProperty("y", player.getLocation().getY());
    pose.addProperty("z", player.getLocation().getZ());
    pose.addProperty("yaw", player.getLocation().getYaw());
    pose.addProperty("pitch", player.getLocation().getPitch());

    JsonObject body = new JsonObject();
    body.add("pose", pose);
    Vector block = player.getLocation().toVector();
    String locationHint = String.format(
        "%s @ (%.1f, %.1f, %.1f)",
        player.getWorld().getName(),
        block.getX(),
        block.getY(),
        block.getZ());
    body.addProperty("location_hint", locationHint);
    payload.add("payload", body);

    dispatchAction(player.getUniqueId(), payload, CityPhoneLocalization.text("message.pose_synced"));
  }

  private void requestState(UUID playerId, String playerName, Consumer<CityPhoneSnapshot> callback) {
    String path = "/ideal-city/cityphone/state/" + playerName + "?scenario_id=" + DEFAULT_SCENARIO;
    backend.getAsync(path, new Callback() {
      @Override
      public void onFailure(Call call, IOException e) {
        sendMessage(playerId, CityPhoneLocalization.prefixed("message.backend_failed", NamedTextColor.RED));
      }

      @Override
      public void onResponse(Call call, Response response) throws IOException {
        try (response) {
          if (!response.isSuccessful()) {
            sendMessage(playerId, CityPhoneLocalization.prefixedFormatted("message.state_failed", NamedTextColor.RED, response.code()));
            return;
          }
          ResponseBody body = response.body();
          if (body == null) {
            sendMessage(playerId, CityPhoneLocalization.prefixed("message.state_empty", NamedTextColor.RED));
            return;
          }
          JsonObject root = GSON.fromJson(body.string(), JsonObject.class);
          if (root == null || !root.has("status")) {
            sendMessage(playerId, CityPhoneLocalization.prefixed("message.state_parse_failed", NamedTextColor.RED));
            return;
          }
          String status = root.get("status").getAsString();
          if (!"ok".equalsIgnoreCase(status)) {
            String error = root.has("error") ? root.get("error").getAsString() : CityPhoneLocalization.text("message.error_unknown");
            sendMessage(playerId, CityPhoneLocalization.prefixedRaw(error, NamedTextColor.RED));
            return;
          }
          JsonObject state = root.getAsJsonObject("state");
          if (state == null) {
            sendMessage(playerId, CityPhoneLocalization.prefixed("message.state_missing", NamedTextColor.RED));
            return;
          }
          CityPhoneSnapshot snapshot = CityPhoneSnapshot.fromJson(state);
          runSync(playerId, player -> callback.accept(snapshot));
        }
      }
    });
  }

  private void dispatchAction(UUID playerId, JsonObject request, String fallbackMessage) {
    backend.postJsonAsync("/ideal-city/cityphone/action", GSON.toJson(request), new Callback() {
      @Override
      public void onFailure(Call call, IOException e) {
        sendMessage(playerId, CityPhoneLocalization.prefixed("message.action_failed_generic", NamedTextColor.RED));
      }

      @Override
      public void onResponse(Call call, Response response) throws IOException {
        try (response) {
          if (!response.isSuccessful()) {
            sendMessage(playerId, CityPhoneLocalization.prefixedFormatted("message.action_failed", NamedTextColor.RED, response.code()));
            return;
          }
          ResponseBody body = response.body();
          if (body == null) {
            sendMessage(playerId, CityPhoneLocalization.prefixed("message.action_empty", NamedTextColor.RED));
            return;
          }
          JsonObject root = GSON.fromJson(body.string(), JsonObject.class);
          if (root == null) {
            sendMessage(playerId, CityPhoneLocalization.prefixed("message.action_parse_failed", NamedTextColor.RED));
            return;
          }
          String status = root.has("status") ? root.get("status").getAsString() : "error";
          JsonObject state = root.getAsJsonObject("state");
          List<String> interpretation = new ArrayList<>(parseStringList(root.get("city_interpretation")));
          List<String> unknowns = new ArrayList<>(parseStringList(root.get("unknowns")));
          List<String> delays = new ArrayList<>(parseStringList(root.get("interpretation_delays")));
          if (!"ok".equalsIgnoreCase(status)) {
            String error = root.has("error") ? root.get("error").getAsString() : CityPhoneLocalization.text("message.error_unknown");
            sendMessage(playerId, CityPhoneLocalization.prefixedRaw(error, NamedTextColor.RED));
            if (state != null) {
              CityPhoneSnapshot snapshot = CityPhoneSnapshot.fromJson(state);
              runSync(playerId, player -> {
                CityPhoneSnapshot previous = snapshotCache.put(playerId, snapshot);
                maybeAnnounceModeChange(player, previous, snapshot);
                deliverInsights(player, interpretation, unknowns, delays);
                CityPhoneUi.open(player, snapshot);
              });
            }
            return;
          }
          String message = root.has("message") && !root.get("message").isJsonNull()
              ? root.get("message").getAsString()
              : fallbackMessage;
          if (message != null && !message.isEmpty()) {
            sendMessage(playerId, CityPhoneLocalization.prefixedRaw(message, NamedTextColor.AQUA));
          }
          if (state != null) {
            CityPhoneSnapshot snapshot = CityPhoneSnapshot.fromJson(state);
            runSync(playerId, player -> {
              CityPhoneSnapshot previous = snapshotCache.put(playerId, snapshot);
              maybeAnnounceModeChange(player, previous, snapshot);
              deliverInsights(player, interpretation, unknowns, delays);
              CityPhoneUi.open(player, snapshot);
            });
          }
        }
      }
    });
  }

  private void sendMessage(UUID playerId, Component message) {
    runSync(playerId, player -> player.sendMessage(message));
  }

  private List<String> parseStringList(JsonElement element) {
    if (element == null || element.isJsonNull() || !element.isJsonArray()) {
      return Collections.emptyList();
    }
    List<String> values = new ArrayList<>();
    element.getAsJsonArray().forEach(entry -> {
      if (!entry.isJsonNull()) {
        String text = entry.getAsString().trim();
        if (!text.isEmpty()) {
          values.add(text);
        }
      }
    });
    return values;
  }

  private void deliverInsights(Player player, List<String> interpretation, List<String> unknowns, List<String> delays) {
    if (!interpretation.isEmpty()) {
      player.sendMessage(CityPhoneLocalization.component("message.interpretation_header", NamedTextColor.AQUA));
      interpretation.forEach(line -> player.sendMessage(Component.text("• " + line, NamedTextColor.WHITE)));
    }

    if (!unknowns.isEmpty()) {
      player.sendMessage(CityPhoneLocalization.component("message.unknowns_header", NamedTextColor.GOLD));
      unknowns.forEach(line -> player.sendMessage(Component.text("• " + line, NamedTextColor.YELLOW)));
    }

    if (!delays.isEmpty()) {
      List<String> filtered = new ArrayList<>();
      for (String entry : delays) {
        if (entry == null || entry.isBlank()) {
          continue;
        }
        if (unknowns.contains(entry)) {
          continue;
        }
        if (filtered.contains(entry)) {
          continue;
        }
        filtered.add(entry);
      }
      if (!filtered.isEmpty()) {
        player.sendMessage(CityPhoneLocalization.component("message.delay_header", NamedTextColor.YELLOW));
        filtered.forEach(line -> player.sendMessage(Component.text("• " + line, NamedTextColor.GOLD)));
      }
    }
  }

  private void maybeAnnounceModeChange(Player player, CityPhoneSnapshot previous, CityPhoneSnapshot current) {
    String currentMode = extractMode(current);
    if (currentMode == null || currentMode.isEmpty()) {
      return;
    }
    String previousMode = extractMode(previous);
    if (previousMode != null && previousMode.equalsIgnoreCase(currentMode)) {
      return;
    }
    String label = resolveModeLabel(current, currentMode);
    Component announcement = buildModeSwitchMessage(currentMode, label);
    player.sendMessage(announcement);
  }

  private String extractMode(CityPhoneSnapshot snapshot) {
    if (snapshot == null) {
      return null;
    }
    if (snapshot.exhibitMode != null && snapshot.exhibitMode.mode != null && !snapshot.exhibitMode.mode.isBlank()) {
      return snapshot.exhibitMode.mode.toLowerCase(Locale.ROOT);
    }
    if (snapshot.narrative != null && snapshot.narrative.mode != null && !snapshot.narrative.mode.isBlank()) {
      return snapshot.narrative.mode.toLowerCase(Locale.ROOT);
    }
    return null;
  }

  private String resolveModeLabel(CityPhoneSnapshot snapshot, String mode) {
    if (snapshot != null && snapshot.exhibitMode != null && snapshot.exhibitMode.label != null && !snapshot.exhibitMode.label.isBlank()) {
      return snapshot.exhibitMode.label;
    }
    if (snapshot != null && snapshot.narrative != null && snapshot.narrative.mode != null && !snapshot.narrative.mode.isBlank()) {
      return snapshot.narrative.mode;
    }
    if (mode != null && !mode.isEmpty()) {
      String key = "mode.label." + mode;
      String localized = CityPhoneLocalization.text(key);
      if (localized != null && !localized.equals(key)) {
        return localized;
      }
      return mode;
    }
    return CityPhoneLocalization.text("mode.label.archive");
  }

  private Component buildModeSwitchMessage(String mode, String label) {
    String key = "message.mode_switch." + mode;
    String message = CityPhoneLocalization.text(key);
    if (message != null && !message.equals(key)) {
      return CityPhoneLocalization.prefixedRaw(message, NamedTextColor.AQUA);
    }
    if (label == null || label.isEmpty()) {
      label = mode;
    }
    return CityPhoneLocalization.prefixedFormatted("message.mode_switch_generic", NamedTextColor.AQUA, label);
  }

  private void runSync(UUID playerId, Consumer<Player> consumer) {
    BukkitScheduler scheduler = Bukkit.getScheduler();
    scheduler.runTask(plugin, () -> {
      Player target = Bukkit.getPlayer(playerId);
      if (target != null) {
        consumer.accept(target);
      }
    });
  }
}
