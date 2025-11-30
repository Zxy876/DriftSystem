package com.driftmc.intent2;

import java.util.HashMap;
import java.util.Map;
import java.util.function.Consumer;

import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.backend.BackendClient;
import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

public class IntentRouter2 {

    private static final Gson GSON = new Gson();

    private final JavaPlugin plugin;
    private final BackendClient backend;

    public IntentRouter2(JavaPlugin plugin, BackendClient backend) {
        this.plugin = plugin;
        this.backend = backend;
    }

    public void askIntent(String playerId, String text, Consumer<IntentResponse2> callback) {
        try {
            Map<String, Object> bodyMap = new HashMap<>();
            bodyMap.put("player_id", playerId);
            bodyMap.put("text", text);

            String body = GSON.toJson(bodyMap);

            String resp = backend.postJson("/ai/intent", body);
            JsonObject root = JsonParser.parseString(resp).getAsJsonObject();

            IntentResponse2 parsed = IntentResponse2.fromJson(root);
            callback.accept(parsed);

        } catch (Exception e) {
            plugin.getLogger().warning("[IntentRouter2] error: " + e.getMessage());

            callback.accept(new IntentResponse2(
                    IntentType2.UNKNOWN,
                    null,
                    null,
                    text
            ));
        }
    }
}