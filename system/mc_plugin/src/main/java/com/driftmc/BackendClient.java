package com.driftmc;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import org.bukkit.entity.Player;
import org.json.JSONObject;

public class BackendClient {

    private final String backendUrl;

    public BackendClient(String backendUrl) {
        this.backendUrl = backendUrl;
    }

    public void sendSay(Player player, String text, BackendResponse callback) {

        try {
            URL url = new URL(backendUrl + "/world/apply");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();

            conn.setRequestMethod("POST");
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json");

            // ------- 构造 JSON -------
            JSONObject body = new JSONObject();
            JSONObject action = new JSONObject();

            action.put("say", text);
            body.put("player_id", player.getName());
            body.put("action", action);

            // ------- 发送 -------
            try (OutputStream os = conn.getOutputStream()) {
                os.write(body.toString().getBytes(StandardCharsets.UTF_8));
            }

            // ------- 读取响应 -------
            int code = conn.getResponseCode();

            InputStream in = (code >= 200 && code < 300)
                    ? conn.getInputStream()
                    : conn.getErrorStream();

            if (in == null) {
                callback.onError(new Exception("后端无响应 inputStream=null"));
                return;
            }

            String result = new String(in.readAllBytes(), StandardCharsets.UTF_8).trim();

            // ------- 检查是不是有效 JSON -------
            if (!result.startsWith("{")) {
                callback.onError(new Exception("后端返回非 JSON：" + result));
                return;
            }

            JSONObject json = new JSONObject(result);
            callback.onSuccess(json);

        } catch (Exception e) {
            e.printStackTrace();
            callback.onError(e);
        }
    }

    public interface BackendResponse {
        void onSuccess(JSONObject response);
        void onError(Exception error);
    }
}