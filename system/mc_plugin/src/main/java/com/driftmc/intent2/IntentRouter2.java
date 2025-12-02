package com.driftmc.intent2;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import java.util.function.Consumer;

import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.backend.BackendClient;
import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Response;

public class IntentRouter2 {

    private static final Gson GSON = new Gson();
    private final JavaPlugin plugin;
    private final BackendClient backend;

    public IntentRouter2(JavaPlugin plugin, BackendClient backend) {
        this.plugin = plugin;
        this.backend = backend;
    }

    public void askIntent(String playerId, String text, Consumer<IntentResponse2> callback) {
        Map<String, Object> body = new HashMap<>();
        body.put("player_id", playerId);
        body.put("text", text);

        String jsonBody = GSON.toJson(body);

        backend.postJsonAsync("/ai/intent", jsonBody, new Callback() {

            @Override
            public void onFailure(Call call, IOException e) {
                plugin.getLogger().warning("[IntentRouter2] 请求失败: " + e.getMessage());
                callback.accept(new IntentResponse2(
                        IntentType2.UNKNOWN, null, null, text
                ));
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                try (response) {
                    String resp = response.body() != null ? response.body().string() : "{}";
                    JsonObject root = JsonParser.parseString(resp).getAsJsonObject();
                    IntentResponse2 parsed = IntentResponse2.fromJson(root);
                    callback.accept(parsed);

                } catch (Exception ex) {
                    plugin.getLogger().warning("[IntentRouter2] 解析错误: " + ex.getMessage());
                    callback.accept(new IntentResponse2(
                            IntentType2.UNKNOWN, null, null, text
                    ));
                }
            }
        });
    }
}