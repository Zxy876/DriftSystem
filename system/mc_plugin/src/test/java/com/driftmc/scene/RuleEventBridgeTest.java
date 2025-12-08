package com.driftmc.scene;

import static org.junit.jupiter.api.Assertions.*;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import com.driftmc.backend.BackendClient;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import be.seeseemelk.mockbukkit.MockBukkit;
import be.seeseemelk.mockbukkit.ServerMock;
import be.seeseemelk.mockbukkit.entity.PlayerMock;
import be.seeseemelk.mockbukkit.plugin.MockPlugin;
import okhttp3.Callback;

class RuleEventBridgeTest {

    private static ServerMock server;

    private MockPlugin plugin;
    private RecordingBackend backend;
    private SceneAwareWorldPatchExecutor worldPatcher;
    private RuleEventBridge bridge;

    @BeforeAll
    static void initServer() {
        server = MockBukkit.mock();
    }

    @AfterAll
    static void shutdownServer() {
        MockBukkit.unmock();
    }

    @BeforeEach
    void setUp() {
        plugin = MockBukkit.createMockPlugin();
        backend = new RecordingBackend();
        worldPatcher = new SceneAwareWorldPatchExecutor(plugin);
        bridge = new RuleEventBridge(plugin, backend, worldPatcher);
    }

    @AfterEach
    void tearDown() {
        backend.clear();
        worldPatcher.shutdown();
    }

    @Test
    void duplicateTriggerSuppression() {
        PlayerMock player = server.addPlayer("DuplicateTester");
        bridge.setCooldownMillis(10_000L);

        bridge.emit(player, "chat", Map.of("text", "hello"));
        bridge.emit(player, "chat", Map.of("text", "hello"));

        assertEquals(1, backend.requestCount(), "Cooldown should suppress duplicate payloads");
    }

    @Test
    void offlinePlayerResponseIsDiscarded() throws Exception {
        UUID ghostId = UUID.randomUUID();

        JsonObject worldPatch = new JsonObject();
        worldPatch.addProperty("tell", "should_not_apply");

        invokeApplyRuleEventResult(
                bridge,
                ghostId,
                "GhostPlayer",
                worldPatch,
                new JsonArray(),
                new JsonArray(),
                new JsonArray(),
                new JsonArray(),
                false,
                new JsonObject());

        assertTrue(getPlayerStates(bridge).isEmpty(),
                "Player state map should remain empty for offline players");
    }

    @Test
    void integrationAppliesWorldPatchAndNodes() throws Exception {
        PlayerMock player = server.addPlayer("QuestRunner");

        JsonObject worldPatch = new JsonObject();
        worldPatch.addProperty("tell", "奖励已发放");

        JsonArray nodes = new JsonArray();
        JsonObject node = new JsonObject();
        node.addProperty("type", "task_complete");
        node.addProperty("title", "完成：collect_sunflower");
        node.addProperty("text", "你闻到了花香。");
        nodes.add(node);

        JsonArray completed = new JsonArray();
        completed.add("collect_sunflower");

        JsonObject summary = new JsonObject();
        summary.addProperty("type", "task_summary");
        summary.addProperty("title", "任务总结");
        summary.addProperty("text", "继续冒险吧！");

        invokeApplyRuleEventResult(
                bridge,
                player.getUniqueId(),
                player.getName(),
                worldPatch,
                nodes,
                new JsonArray(),
                completed,
                new JsonArray(),
                true,
                summary);

        List<String> messages = drainMessages(player);
        assertTrue(messages.stream().anyMatch(msg -> msg.contains("【心悦宇宙】") && msg.contains("奖励已发放")),
                "World patch tell message should reach the player");
        assertTrue(messages.stream().anyMatch(msg -> msg.contains("【完成】")),
                "Completion headline should be announced");
        assertTrue(messages.stream().anyMatch(msg -> msg.contains("✔ 任务完成")),
                "Completed task toast should reach the player");
        assertTrue(messages.stream().anyMatch(msg -> msg.contains("当前关卡任务全部完成")),
                "Exit readiness message should notify the player");
    }

    private static void invokeApplyRuleEventResult(
            RuleEventBridge bridge,
            UUID playerId,
            String playerName,
            JsonObject worldPatch,
            JsonArray nodes,
            JsonArray commands,
            JsonArray completed,
            JsonArray milestones,
            boolean exitReady,
            JsonObject summary) throws Exception {

        Method method = RuleEventBridge.class.getDeclaredMethod(
                "applyRuleEventResult",
                UUID.class,
                String.class,
                JsonObject.class,
                JsonArray.class,
                JsonArray.class,
                JsonArray.class,
                JsonArray.class,
                boolean.class,
                JsonObject.class);
        method.setAccessible(true);
        method.invoke(
                bridge,
                playerId,
                playerName,
                worldPatch,
                nodes,
                commands,
                completed,
                milestones,
                exitReady,
                summary);
    }

    private static List<String> drainMessages(PlayerMock player) {
        List<String> messages = new ArrayList<>();
        String message;
        while ((message = player.nextMessage()) != null) {
            messages.add(message);
        }
        return messages;
    }

    @SuppressWarnings("unchecked")
    private static Map<UUID, ?> getPlayerStates(RuleEventBridge bridge) throws Exception {
        Field field = RuleEventBridge.class.getDeclaredField("playerStates");
        field.setAccessible(true);
        return (Map<UUID, ?>) field.get(bridge);
    }

    private static final class RecordingBackend extends BackendClient {

        private int requests;

        RecordingBackend() {
            super("http://localhost");
        }

        @Override
        public void postJsonAsync(String path, String json, Callback callback) {
            requests++;
        }

        int requestCount() {
            return requests;
        }

        void clear() {
            requests = 0;
        }
    }
}
