package com.driftmc.cityphone;

import java.io.IOException;
import java.util.Arrays;
import java.util.UUID;
import java.util.function.Consumer;

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

  public CityPhoneManager(DriftPlugin plugin, BackendClient backend) {
    this.plugin = plugin;
    this.backend = backend;
    this.phoneKey = new NamespacedKey(plugin, "cityphone_device");
  }

  public void givePhone(Player player) {
    player.getInventory().addItem(createPhoneItem());
    player.sendMessage(Component.text("[CityPhone] 已放入背包。", NamedTextColor.AQUA));
  }

  public ItemStack createPhoneItem() {
    ItemStack stack = new ItemStack(Material.COMPASS);
    ItemMeta meta = stack.getItemMeta();
    if (meta != null) {
      meta.displayName(Component.text("CityPhone", NamedTextColor.AQUA));
      meta.lore(Arrays.asList(
          Component.text("档案馆配发的随身终端", NamedTextColor.GRAY),
          Component.text("右键同步剧情记录", NamedTextColor.DARK_GRAY)));
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
    requestState(player.getUniqueId(), player.getName(), snapshot -> {
      Player target = Bukkit.getPlayer(player.getUniqueId());
      if (target != null) {
        CityPhoneUi.open(target, snapshot);
      }
    });
  }

  public void submitNarrative(Player player, String narrative) {
    if (narrative == null || narrative.isBlank()) {
      player.sendMessage(Component.text("请填写要记录的叙述。", NamedTextColor.RED));
      return;
    }
    JsonObject payload = new JsonObject();
    payload.addProperty("player_id", player.getName());
    payload.addProperty("scenario_id", DEFAULT_SCENARIO);
    payload.addProperty("action", "submit_narrative");
    JsonObject body = new JsonObject();
    body.addProperty("narrative", narrative.trim());
    payload.add("payload", body);

    dispatchAction(player.getUniqueId(), payload, "已同步你的新记录。");
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

    dispatchAction(player.getUniqueId(), payload, "已同步当前位置。");
  }

  public void applyTemplate(Player player, String templateKey) {
    if (templateKey == null || templateKey.isBlank()) {
      player.sendMessage(Component.text("[CityPhone] 未识别的模板。", NamedTextColor.RED));
      return;
    }
    JsonObject payload = new JsonObject();
    payload.addProperty("player_id", player.getName());
    payload.addProperty("scenario_id", DEFAULT_SCENARIO);
    payload.addProperty("action", "apply_template");
    JsonObject body = new JsonObject();
    body.addProperty("template", templateKey);
    payload.add("payload", body);

    dispatchAction(player.getUniqueId(), payload, "已应用模板。");
  }

  private void requestState(UUID playerId, String playerName, Consumer<CityPhoneSnapshot> callback) {
    String path = "/ideal-city/cityphone/state/" + playerName + "?scenario_id=" + DEFAULT_SCENARIO;
    backend.getAsync(path, new Callback() {
      @Override
      public void onFailure(Call call, IOException e) {
        sendMessage(playerId, Component.text("[CityPhone] 后端连接失败。", NamedTextColor.RED));
      }

      @Override
      public void onResponse(Call call, Response response) throws IOException {
        try (response) {
          if (!response.isSuccessful()) {
            sendMessage(playerId, Component.text("[CityPhone] 状态获取失败 (" + response.code() + ")", NamedTextColor.RED));
            return;
          }
          ResponseBody body = response.body();
          if (body == null) {
            sendMessage(playerId, Component.text("[CityPhone] 后端返回为空。", NamedTextColor.RED));
            return;
          }
          JsonObject root = GSON.fromJson(body.string(), JsonObject.class);
          if (root == null || !root.has("status")) {
            sendMessage(playerId, Component.text("[CityPhone] 无法解析后端响应。", NamedTextColor.RED));
            return;
          }
          String status = root.get("status").getAsString();
          if (!"ok".equalsIgnoreCase(status)) {
            String error = root.has("error") ? root.get("error").getAsString() : "未知错误";
            sendMessage(playerId, Component.text("[CityPhone] " + error, NamedTextColor.RED));
            return;
          }
          JsonObject state = root.getAsJsonObject("state");
          if (state == null) {
            sendMessage(playerId, Component.text("[CityPhone] 未能获取当前状态。", NamedTextColor.RED));
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
        sendMessage(playerId, Component.text("[CityPhone] 提交失败。", NamedTextColor.RED));
      }

      @Override
      public void onResponse(Call call, Response response) throws IOException {
        try (response) {
          if (!response.isSuccessful()) {
            sendMessage(playerId, Component.text("[CityPhone] 提交失败 (" + response.code() + ")", NamedTextColor.RED));
            return;
          }
          ResponseBody body = response.body();
          if (body == null) {
            sendMessage(playerId, Component.text("[CityPhone] 后端返回为空。", NamedTextColor.RED));
            return;
          }
          JsonObject root = GSON.fromJson(body.string(), JsonObject.class);
          if (root == null) {
            sendMessage(playerId, Component.text("[CityPhone] 无法解析响应。", NamedTextColor.RED));
            return;
          }
          String status = root.has("status") ? root.get("status").getAsString() : "error";
          JsonObject state = root.getAsJsonObject("state");
          if (!"ok".equalsIgnoreCase(status)) {
            String error = root.has("error") ? root.get("error").getAsString() : "未知错误";
            sendMessage(playerId, Component.text("[CityPhone] " + error, NamedTextColor.RED));
            if (state != null) {
              CityPhoneSnapshot snapshot = CityPhoneSnapshot.fromJson(state);
              runSync(playerId, player -> CityPhoneUi.open(player, snapshot));
            }
            return;
          }
          String message = root.has("message") && !root.get("message").isJsonNull()
              ? root.get("message").getAsString()
              : fallbackMessage;
          if (message != null && !message.isEmpty()) {
            sendMessage(playerId, Component.text("[CityPhone] " + message, NamedTextColor.AQUA));
          }
          if (state != null) {
            CityPhoneSnapshot snapshot = CityPhoneSnapshot.fromJson(state);
            runSync(playerId, player -> CityPhoneUi.open(player, snapshot));
          }
        }
      }
    });
  }

  private void sendMessage(UUID playerId, Component message) {
    runSync(playerId, player -> player.sendMessage(message));
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
