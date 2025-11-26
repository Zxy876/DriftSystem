package com.heartstory.http;

import okhttp3.*;

public class BackendClient {

    private final OkHttpClient http = new OkHttpClient();
    private final String baseUrl = "http://127.0.0.1:8000";

    public String loadLevel(String player, String levelId) throws Exception {
        Request request = new Request.Builder()
                .url(baseUrl + "/story/load/" + player + "/" + levelId)
                .post(RequestBody.create("", MediaType.parse("application/json")))
                .build();

        return http.newCall(request).execute().body().string();
    }

    public String sayToAI(String player, String text) throws Exception {
        String json = "{\"world_state\":{},\"action\":{\"say\":\"" + text + "\"}}";

        Request request = new Request.Builder()
                .url(baseUrl + "/story/advance/" + player)
                .post(RequestBody.create(json, MediaType.parse("application/json")))
                .build();

        return http.newCall(request).execute().body().string();
    }
}
