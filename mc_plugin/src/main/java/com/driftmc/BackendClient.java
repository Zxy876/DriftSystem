package com.driftmc;

import okhttp3.*;

public class BackendClient {

    private static OkHttpClient client;
    private static final String BASE_URL = "http://127.0.0.1:8000";

    public static void init() {
        client = new OkHttpClient();
    }

    public static String post(String path) {
        try {
            Request request = new Request.Builder()
                    .url(BASE_URL + path)
                    .post(RequestBody.create("", null))
                    .build();

            Response resp = client.newCall(request).execute();
            return resp.body().string();

        } catch (Exception e) {
            return "ERROR: " + e.getMessage();
        }
    }
}
