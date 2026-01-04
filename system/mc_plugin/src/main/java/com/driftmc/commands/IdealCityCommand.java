package com.driftmc.commands;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Level;

import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.backend.BackendClient;
import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.Response;

/**
 * Natural language submission command for Ideal City DeviceSpecs.
 * This command only forwards player intent to the backend and never issues
 * world patches or bypasses adjudication; presentation feedback is textual.
 */
public class IdealCityCommand implements CommandExecutor {

    private static final Gson GSON = new Gson();

    private final JavaPlugin plugin;
    private final BackendClient backend;
    private final Map<UUID, ProposalDraft> drafts = new ConcurrentHashMap<>();

    public IdealCityCommand(JavaPlugin plugin, BackendClient backend) {
        this.plugin = plugin;
        this.backend = backend;
    }

    public boolean submitNarrative(Player player, String narrative) {
        if (player == null) {
            return false;
        }

        String trimmed = narrative != null ? narrative.trim() : "";
        if (trimmed.isEmpty()) {
            return false;
        }

        player.sendMessage("§7[IdealCity] 提交规格中，请稍候…");

        Map<String, Object> payload = new HashMap<>();
        payload.put("player_id", player.getUniqueId().toString());
        payload.put("narrative", trimmed);

        submitPayload(player, payload);
        return true;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player player)) {
            sender.sendMessage("Only players can submit Ideal City proposals.");
            return true;
        }

        if (args.length == 0) {
            sendWizardHelp(player);
            return true;
        }

        if (handleWizardCommand(player, args)) {
            return true;
        }

        String narrative = String.join(" ", args).trim();
        if (!submitNarrative(player, narrative)) {
            sender.sendMessage("Please describe your proposal in natural language.");
            return true;
        }

        return true;
    }

    private boolean handleWizardCommand(Player player, String[] args) {
        String action = args[0].toLowerCase();
        UUID playerId = player.getUniqueId();
        ProposalDraft draft = drafts.get(playerId);

        switch (action) {
            case "start":
                String startingNarrative = joinArgs(args, 1);
                draft = new ProposalDraft();
                draft.setNarrative(startingNarrative);
                drafts.put(playerId, draft);
                player.sendMessage("§a[IdealCity] 已创建新的建造草稿。");
                player.sendMessage("§7使用 /idealcity narrative <描述> 来更新意图描述。");
                player.sendMessage("§7使用 /idealcity constraint|step|success <内容> 来逐条追加，完成后 /idealcity submit 提交。");
                return true;
            case "cancel":
            case "clear":
                if (drafts.remove(playerId) != null) {
                    player.sendMessage("§a[IdealCity] 草稿已清除。");
                } else {
                    player.sendMessage("§7[IdealCity] 当前没有草稿。");
                }
                return true;
            case "show":
            case "status":
                if (draft == null) {
                    player.sendMessage("§7[IdealCity] 尚未创建草稿，使用 /idealcity start 开始。");
                } else {
                    player.sendMessage("§b[IdealCity] 草稿预览：");
                    player.sendMessage("§7- 叙述: " + (draft.getNarrative().isBlank() ? "(未设置)" : draft.getNarrative()));
                    player.sendMessage("§7- 约束: " + draft.getConstraints().size() + " 条");
                    previewList(player, draft.getConstraints());
                    player.sendMessage("§7- 步骤: " + draft.getSteps().size() + " 条");
                    previewList(player, draft.getSteps());
                    player.sendMessage("§7- 成功标准: " + draft.getSuccessCriteria().size() + " 条");
                    previewList(player, draft.getSuccessCriteria());
                    if (!draft.getResources().isEmpty()) {
                        player.sendMessage("§7- 资源: " + draft.getResources().size() + " 条");
                        previewList(player, draft.getResources());
                    }
                }
                return true;
            case "narrative":
            case "intent":
                ensureDraft(player, playerId, draft);
                draft = drafts.get(playerId);
                String narrativeText = joinArgs(args, 1);
                if (narrativeText.isBlank()) {
                    player.sendMessage("§c[IdealCity] 请输入叙述内容。");
                    return true;
                }
                draft.setNarrative(narrativeText);
                player.sendMessage("§a[IdealCity] 已更新叙述。");
                return true;
            case "constraint":
            case "constraints":
                ensureDraft(player, playerId, draft);
                draft = drafts.get(playerId);
                addEntry(player, draft.getConstraints(), args, "约束");
                autoSubmitIfReady(player, playerId, draft, AutoTrigger.CONSTRAINT);
                return true;
            case "step":
            case "steps":
                ensureDraft(player, playerId, draft);
                draft = drafts.get(playerId);
                addEntry(player, draft.getSteps(), args, "步骤");
                autoSubmitIfReady(player, playerId, draft, AutoTrigger.STEP);
                return true;
            case "success":
            case "successes":
                ensureDraft(player, playerId, draft);
                draft = drafts.get(playerId);
                addEntry(player, draft.getSuccessCriteria(), args, "成功标准");
                autoSubmitIfReady(player, playerId, draft, AutoTrigger.SUCCESS);
                return true;
            case "resource":
            case "resources":
                ensureDraft(player, playerId, draft);
                draft = drafts.get(playerId);
                addEntry(player, draft.getResources(), args, "资源记录");
                autoSubmitIfReady(player, playerId, draft, AutoTrigger.RESOURCE);
                return true;
            case "submit":
                if (draft == null) {
                    player.sendMessage("§c[IdealCity] 当前没有草稿，先使用 /idealcity start。");
                    return true;
                }
                if (submitDraft(player, playerId, draft, SubmissionMode.MANUAL)) {
                    drafts.remove(playerId);
                }
                return true;
            case "help":
                sendWizardHelp(player);
                return true;
            default:
                return false;
        }
    }

    private void ensureDraft(Player player, UUID playerId, ProposalDraft draft) {
        if (draft == null) {
            ProposalDraft created = new ProposalDraft();
            drafts.put(playerId, created);
            player.sendMessage("§7[IdealCity] 已新建草稿，可继续添加内容。");
        }
    }

    private void addEntry(Player player, List<String> target, String[] args, String label) {
        String value = joinArgs(args, 1);
        if (value.isBlank()) {
            player.sendMessage("§c[IdealCity] 请输入" + label + "内容。");
            return;
        }
        target.add(value);
        player.sendMessage("§a[IdealCity] 已添加" + label + "（当前共 " + target.size() + " 条）。");
    }

    private void previewList(Player player, List<String> values) {
        for (int i = 0; i < Math.min(values.size(), 3); i++) {
            player.sendMessage("§7 • " + values.get(i));
        }
        if (values.size() > 3) {
            player.sendMessage("§7 • ... (更多条目已记录)");
        }
    }

    private void autoSubmitIfReady(Player player, UUID playerId, ProposalDraft draft, AutoTrigger trigger) {
        if (draft == null) {
            return;
        }
        if (draft.isSubmitted()) {
            return;
        }
        if (!draft.isReadyForSubmission()) {
            return;
        }
        if (trigger == AutoTrigger.CONSTRAINT && draft.getSuccessCriteria().isEmpty()) {
            return;
        }
        if (trigger == AutoTrigger.STEP && draft.getSuccessCriteria().isEmpty()) {
            return;
        }

        player.sendMessage("§6[IdealCity] 草稿要素齐备，已自动提交裁决。");
        if (submitDraft(player, playerId, draft, SubmissionMode.AUTOMATIC)) {
            drafts.remove(playerId);
        }
    }

    private boolean submitDraft(Player player, UUID playerId, ProposalDraft draft, SubmissionMode mode) {
        if (draft == null) {
            player.sendMessage("§c[IdealCity] 当前没有草稿。使用 /idealcity start 开始。");
            return false;
        }

        if (draft.getNarrative().isBlank()) {
            player.sendMessage("§c[IdealCity] 草稿缺少叙述，请先使用 /idealcity narrative <描述> 设置。");
            return false;
        }

        if (draft.getSteps().size() < 2) {
            player.sendMessage("§e[IdealCity] 提醒：步骤少于 2 条，可能被裁决为 PARTIAL 或 REJECT。");
        }

        Map<String, Object> payload = new HashMap<>();
        payload.put("player_id", playerId.toString());
        payload.put("narrative", draft.getNarrative());
        if (!draft.getConstraints().isEmpty()) {
            payload.put("world_constraints", new ArrayList<>(draft.getConstraints()));
        }
        if (!draft.getSteps().isEmpty()) {
            payload.put("logic_outline", new ArrayList<>(draft.getSteps()));
        }
        if (!draft.getSuccessCriteria().isEmpty()) {
            payload.put("success_criteria", new ArrayList<>(draft.getSuccessCriteria()));
        }
        if (!draft.getResources().isEmpty()) {
            payload.put("resource_ledger", new ArrayList<>(draft.getResources()));
        }

        if (mode == SubmissionMode.MANUAL) {
            player.sendMessage("§7[IdealCity] 草稿已提交，等待裁决…");
        }

        draft.markSubmitted();
        submitPayload(player, payload);
        return true;
    }

    private void submitPayload(Player player, Map<String, Object> payload) {
        String json = GSON.toJson(payload);

        backend.postJsonAsync("/ideal-city/device-specs", json, new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                plugin.getLogger().log(Level.WARNING, "[IdealCityCommand] backend error", e);
                Bukkit.getScheduler().runTask(plugin, () ->
                        player.sendMessage("§c[IdealCity] 后端暂时不可用，请稍后再试。"));
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                try (response) {
                    String body = response.body() != null ? response.body().string() : "{}";
                    if (!response.isSuccessful()) {
                        plugin.getLogger().log(Level.WARNING,
                                "[IdealCityCommand] backend replied HTTP {0} payload {1}",
                                new Object[] { response.code(), body });
                        Bukkit.getScheduler().runTask(plugin, () ->
                                player.sendMessage("§c[IdealCity] 提交失败，请联系管理员。"));
                        return;
                    }

                    JsonObject root = JsonParser.parseString(body).getAsJsonObject();
                    JsonObject specJson = root.has("spec") && root.get("spec").isJsonObject()
                            ? root.getAsJsonObject("spec") : null;
                    JsonObject noticeJson = root.has("notice") && root.get("notice").isJsonObject()
                            ? root.getAsJsonObject("notice") : null;
                    JsonObject planJson = root.has("build_plan") && root.get("build_plan").isJsonObject()
                            ? root.getAsJsonObject("build_plan") : null;
                    JsonObject narrationJson = root.has("narration") && root.get("narration").isJsonObject()
                            ? root.getAsJsonObject("narration") : null;

                    Bukkit.getScheduler().runTask(plugin, () -> {
                        JsonObject noticeToUse = noticeJson;
                        JsonObject planToUse = planJson;
                        JsonObject narrationToUse = narrationJson;

                        player.sendMessage("§a[IdealCity] 方案已记录。");
                        if (specJson != null && specJson.has("intent_summary")) {
                            player.sendMessage("§7目标摘要: " + specJson.get("intent_summary").getAsString());
                        }
                        if (noticeToUse != null) {
                            if (noticeToUse.has("headline")) {
                                player.sendMessage("§e" + noticeToUse.get("headline").getAsString());
                            }
                            if (noticeToUse.has("body") && noticeToUse.get("body").isJsonArray()) {
                                noticeToUse.getAsJsonArray("body").forEach(element ->
                                        player.sendMessage("§7 - " + element.getAsString()));
                            }
                            if (noticeToUse.has("guidance") && noticeToUse.get("guidance").isJsonArray()) {
                                player.sendMessage("§6后续指导：");
                                for (JsonElement element : noticeToUse.getAsJsonArray("guidance")) {
                                    player.sendMessage("§7 • " + element.getAsString());
                                }
                            }
                            if (planToUse == null && noticeToUse.has("build_plan")
                                    && noticeToUse.get("build_plan").isJsonObject()) {
                                planToUse = noticeToUse.getAsJsonObject("build_plan");
                            }
                            if (narrationToUse == null && noticeToUse.has("broadcast")
                                    && noticeToUse.get("broadcast").isJsonObject()) {
                                narrationToUse = noticeToUse.getAsJsonObject("broadcast");
                            }
                        } else {
                            player.sendMessage("§7裁决结果即将送达，请稍后刷新。");
                        }

                        if (planToUse != null) {
                            if (planToUse.has("summary")) {
                                player.sendMessage("§b建造计划: " + planToUse.get("summary").getAsString());
                            }
                            if (planToUse.has("steps") && planToUse.get("steps").isJsonArray()) {
                                JsonArray steps = planToUse.getAsJsonArray("steps");
                                for (int i = 0; i < Math.min(steps.size(), 3); i++) {
                                    player.sendMessage("§3 - " + formatPlanStep(steps.get(i)));
                                }
                                if (steps.size() > 3) {
                                    player.sendMessage("§3 - ... (更多步骤已记录)");
                                }
                            }
                            if (planToUse.has("mod_hooks") && planToUse.get("mod_hooks").isJsonArray()) {
                                JsonArray mods = planToUse.getAsJsonArray("mod_hooks");
                                if (mods.size() > 0) {
                                    StringBuilder builder = new StringBuilder();
                                    for (int i = 0; i < mods.size(); i++) {
                                        if (i > 0) {
                                            builder.append(", ");
                                        }
                                        builder.append(mods.get(i).getAsString());
                                    }
                                    player.sendMessage("§d关联模组: " + builder);
                                }
                            }
                        }

                        if (narrationToUse != null) {
                            if (narrationToUse.has("title")) {
                                player.sendMessage("§5广播: " + narrationToUse.get("title").getAsString());
                            }
                            if (narrationToUse.has("spoken") && narrationToUse.get("spoken").isJsonArray()) {
                                for (JsonElement element : narrationToUse.getAsJsonArray("spoken")) {
                                    player.sendMessage("§5 " + element.getAsString());
                                }
                            }
                            if (narrationToUse.has("call_to_action")) {
                                player.sendMessage("§d号召: " + narrationToUse.get("call_to_action").getAsString());
                            }
                        }
                    });
                } catch (Exception ex) {
                    plugin.getLogger().log(Level.WARNING, "[IdealCityCommand] parse failure", ex);
                    Bukkit.getScheduler().runTask(plugin, () ->
                            player.sendMessage("§c[IdealCity] 返回结果读取失败。"));
                }
            }
        });
    }

    private String formatPlanStep(JsonElement element) {
        if (element == null || element.isJsonNull()) {
            return "(未提供步骤详情)";
        }
        if (element.isJsonPrimitive()) {
            return element.getAsString();
        }
        if (element.isJsonObject()) {
            JsonObject obj = element.getAsJsonObject();
            String title = getOptionalString(obj, "title");
            String description = getOptionalString(obj, "description");
            String stepId = getOptionalString(obj, "step_id");
            StringBuilder builder = new StringBuilder();
            if (title != null && !title.isBlank()) {
                builder.append(title);
            } else if (stepId != null && !stepId.isBlank()) {
                builder.append(stepId);
            }
            if (description != null && !description.isBlank()) {
                if (builder.length() > 0) {
                    builder.append("：");
                }
                builder.append(description);
            }
            if (builder.length() > 0) {
                return builder.toString();
            }
        }
        return element.toString();
    }

    private String getOptionalString(JsonObject obj, String key) {
        if (obj.has(key) && obj.get(key).isJsonPrimitive()) {
            return obj.get(key).getAsString();
        }
        return null;
    }

    private void sendWizardHelp(Player player) {
        player.sendMessage("§7[IdealCity] 使用方式: /idealcity <叙述>");
        player.sendMessage("§7或：/idealcity start [叙述] — 开始草稿");
        player.sendMessage("§7/idealcity narrative <叙述>、constraint <文本>、step <文本>、success <文本>、resource <文本>");
        player.sendMessage("§7/idealcity show 查看草稿，/idealcity submit 提交，/idealcity cancel 取消草稿。");
    }

    private static String joinArgs(String[] args, int startIndex) {
        if (startIndex >= args.length) {
            return "";
        }
        return String.join(" ", Arrays.copyOfRange(args, startIndex, args.length)).trim();
    }

    private enum SubmissionMode {
        MANUAL,
        AUTOMATIC
    }

    private enum AutoTrigger {
        CONSTRAINT,
        STEP,
        SUCCESS,
        RESOURCE
    }

    private static final class ProposalDraft {
        private String narrative = "";
        private final List<String> constraints = new ArrayList<>();
        private final List<String> steps = new ArrayList<>();
        private final List<String> successCriteria = new ArrayList<>();
        private final List<String> resources = new ArrayList<>();
        private boolean submitted;

        String getNarrative() {
            return narrative == null ? "" : narrative.trim();
        }

        void setNarrative(String value) {
            this.narrative = value == null ? "" : value.trim();
        }

        List<String> getConstraints() {
            return constraints;
        }

        List<String> getSteps() {
            return steps;
        }

        List<String> getSuccessCriteria() {
            return successCriteria;
        }

        List<String> getResources() {
            return resources;
        }

        boolean isReadyForSubmission() {
            return !getNarrative().isBlank()
                    && !constraints.isEmpty()
                    && !steps.isEmpty()
                    && !successCriteria.isEmpty();
        }

        void markSubmitted() {
            this.submitted = true;
        }

        boolean isSubmitted() {
            return submitted;
        }
    }
}
