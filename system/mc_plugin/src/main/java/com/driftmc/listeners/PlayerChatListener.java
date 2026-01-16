package com.driftmc.listeners;

import java.util.List;
import java.util.Locale;
import java.util.logging.Level;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.exit.ExitIntentDetector;
import com.driftmc.hud.dialogue.ChoicePanel;
import com.driftmc.intent2.IntentDispatcher2;
import com.driftmc.intent2.IntentResponse2;
import com.driftmc.intent2.IntentRouter2;
import com.driftmc.intent2.IntentType2;
import com.driftmc.scene.RuleEventBridge;
import com.driftmc.tutorial.TutorialManager;

import io.papermc.paper.event.player.AsyncChatEvent;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;

public class PlayerChatListener implements Listener {

    private final JavaPlugin plugin;
    private final IntentRouter2 router;
    private final IntentDispatcher2 dispatcher;
    private final TutorialManager tutorialManager;
    private final RuleEventBridge ruleEvents;
    private final ExitIntentDetector exitDetector;
    private final ChoicePanel choicePanel;

    private static final String FRONT_KEYWORD = "在我面前";
    private static final Pattern BLOCK_ID_PATTERN = Pattern.compile("minecraft:[a-z0-9_./\\-]+", Pattern.CASE_INSENSITIVE);
    private static final Pattern COORD_MARKER_PATTERN = Pattern.compile("(坐标|坐標|coordinate[s]?)\\s*[:：]?\\s*-?\\d+(?:\\.\\d+)?\\s+-?\\d+(?:\\.\\d+)?\\s+-?\\d+(?:\\.\\d+)?", Pattern.CASE_INSENSITIVE);
    private static final Pattern COORD_TRIPLE_PATTERN = Pattern.compile("-?\\d+(?:\\.\\d+)?\\s+-?\\d+(?:\\.\\d+)?\\s+-?\\d+(?:\\.\\d+)?");

    public PlayerChatListener(JavaPlugin plugin, IntentRouter2 router, IntentDispatcher2 dispatcher,
            TutorialManager tutorialManager, RuleEventBridge ruleEvents, ExitIntentDetector exitDetector,
            ChoicePanel choicePanel) {
        this.plugin = plugin;
        this.router = router;
        this.dispatcher = dispatcher;
        this.tutorialManager = tutorialManager;
        this.ruleEvents = ruleEvents;
        this.exitDetector = exitDetector;
        this.choicePanel = choicePanel;
    }

    @EventHandler
    public void onAsyncChat(AsyncChatEvent e) {
        Player p = e.getPlayer();

        String msg = PlainTextComponentSerializer.plainText().serialize(e.message());
        e.setCancelled(true);

        if (choicePanel != null && choicePanel.consumeSelection(p, msg)) {
            return;
        }

        p.sendMessage("§7你：" + msg);
        plugin.getLogger().log(Level.INFO, "[聊天] 玩家 {0} 说: {1}", new Object[]{p.getName(), msg});

        if (ruleEvents != null) {
            ruleEvents.emitChat(p, msg);
        }

        // 保存原始消息
        final String originalMsg = msg;
        final String processedMsg = augmentWithFrontCoordinate(p, originalMsg);

        // 首先检查教学进度（如果玩家在教学中）
        tutorialManager.checkProgress(p, originalMsg);

        if (exitDetector != null && exitDetector.handle(p, originalMsg)) {
            return;
        }

        // 多意图版本
        router.askIntent(p.getName(), processedMsg, (List<IntentResponse2> intents) -> {
            plugin.getLogger().log(Level.INFO, "[聊天] 收到 {0} 个意图", intents.size());

            final boolean forceCreateBlock = shouldForceCreateBlock(processedMsg);
            final IntentResponse2 firstIntent = intents.isEmpty() ? null : intents.get(0);

            Bukkit.getScheduler().runTask(plugin, () -> {
                if (forceCreateBlock) {
                    plugin.getLogger().log(Level.INFO,
                            "[聊天] creation_hard_route triggered, rawText={0}", processedMsg);

                    IntentResponse2 forcedIntent = new IntentResponse2(
                            IntentType2.CREATE_BLOCK,
                            firstIntent != null ? firstIntent.levelId : null,
                            firstIntent != null ? firstIntent.minimap : null,
                            processedMsg,
                            null);

                    dispatcher.dispatch(p, forcedIntent);
                    return;
                }

                // 依次分发所有意图，并传递原始消息
                for (IntentResponse2 intent : intents) {
                    plugin.getLogger().log(Level.INFO,
                            "[聊天] 分发意图: {0}, rawText={1}",
                            new Object[]{intent.type, intent.rawText});

                    IntentType2 targetType = intent.type;

                    IntentResponse2 fixedIntent = new IntentResponse2(
                            targetType,
                            intent.levelId,
                            intent.minimap,
                            processedMsg,
                            targetType == IntentType2.CREATE_BLOCK ? null : intent.worldPatch);

                    if (!processedMsg.equals(intent.rawText)) {
                        plugin.getLogger().log(Level.INFO,
                                "[聊天] 修正后的rawText: {0}", processedMsg);
                    }

                    dispatcher.dispatch(p, fixedIntent);
                }
            });
        });
    }

    private String augmentWithFrontCoordinate(Player player, String message) {
        if (message == null || message.isEmpty()) {
            return "";
        }
        String trimmed = message.trim();
        if (!trimmed.contains(FRONT_KEYWORD)) {
            return message;
        }

        String lower = trimmed.toLowerCase(Locale.ROOT);
        String blockId = null;
        if (!lower.contains("minecraft:")) {
            if (lower.contains("紫水晶") || lower.contains("amethyst")) {
                blockId = "minecraft:amethyst_block";
            }
        }

        var location = player.getLocation();
        var direction = location.getDirection();
        direction.setY(0);
        if (direction.lengthSquared() == 0) {
            direction.setX(-Math.sin(Math.toRadians(location.getYaw())));
            direction.setZ(Math.cos(Math.toRadians(location.getYaw())));
        }
        direction.normalize();

        var frontLocation = location.clone().add(direction);
        int targetX = frontLocation.getBlockX();
        int targetY = location.getBlockY();
        int targetZ = frontLocation.getBlockZ();

        plugin.getLogger().info(String.format(Locale.ROOT,
                "[IntentRouter] resolved_front_position = (%d, %d, %d)", targetX, targetY, targetZ));

    StringBuilder builder = new StringBuilder(message);
    if (blockId != null) {
        builder.append(" 方块 ").append(blockId);
        plugin.getLogger().info(String.format(Locale.ROOT,
            "[IntentRouter] resolved_block_id = %s", blockId));
    }
    builder.append(String.format(Locale.ROOT, " 坐标 %d %d %d", targetX, targetY, targetZ));
    return builder.toString();
    }

    private boolean shouldForceCreateBlock(String message) {
        if (message == null || message.isBlank()) {
            return false;
        }
        String lower = message.toLowerCase(Locale.ROOT);
        if (!BLOCK_ID_PATTERN.matcher(lower).find()) {
            return false;
        }
        if (COORD_MARKER_PATTERN.matcher(lower).find()) {
            return true;
        }
        Matcher triple = COORD_TRIPLE_PATTERN.matcher(message);
        return triple.find();
    }
}