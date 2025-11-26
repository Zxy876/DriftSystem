package com.driftmc.backend;

import com.driftmc.intent.IntentResponse;
import com.google.gson.Gson;
import okhttp3.*;

import java.io.IOException;

public class BackendClient {

    private final String baseUrl;
    private final OkHttpClient client;
    private final Gson gson;

    public BackendClient(String baseUrl) {
        if (baseUrl.endsWith("/")) {
            baseUrl = baseUrl.substring(0, baseUrl.length() - 1);
        }
        this.baseUrl = baseUrl;
        this.client = new OkHttpClient();
        this.gson = new Gson();
    }

    private String buildUrl(String path) {
        if (!path.startsWith("/")) path = "/" + path;
        return baseUrl + path;
    }

    public String get(String path) throws IOException {
        Request request = new Request.Builder()
                .url(buildUrl(path))
                .get()
                .build();
        try (Response resp = client.newCall(request).execute()) {
            if (!resp.isSuccessful()) {
                throw new IOException("GET " + path + " failed: " + resp.code());
            }
            ResponseBody body = resp.body();
            return body != null ? body.string() : "";
        }
    }

    public String postJson(String path, String json) throws IOException {
        RequestBody body = RequestBody.create(
                json,
                MediaType.parse("application/json; charset=utf-8")
        );
        Request request = new Request.Builder()
                .url(buildUrl(path))
                .post(body)
                .build();
        try (Response resp = client.newCall(request).execute()) {
            if (!resp.isSuccessful()) {
                throw new IOException("POST " + path + " failed: " + resp.code());
            }
            ResponseBody rb = resp.body();
            return rb != null ? rb.string() : "";
        }
    }

    /**
     * 专门给 /ai/route 用的封装
     */
    public IntentResponse sendIntent(String playerName, String message) throws IOException {
        String payload = gson.toJson(new AiPayload(playerName, message));
        String respJson = postJson("/ai/route", payload);
        return gson.fromJson(respJson, IntentResponse.class);
    }

    // ==== 内部 DTO ====
    private static class AiPayload {
        public final String player;
        public final String message;

        AiPayload(String player, String message) {
            this.player = player;
            this.message = message;
        }
    }
}
