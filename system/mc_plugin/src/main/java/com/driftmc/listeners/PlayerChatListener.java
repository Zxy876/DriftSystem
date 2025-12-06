package com.driftmc.listeners;

import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.intent2.IntentDispatcher2;
import com.driftmc.intent2.IntentResponse2;
import com.driftmc.intent2.IntentRouter2;
import com.driftmc.tutorial.TutorialManager;

import io.papermc.paper.event.player.AsyncChatEvent;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;

import java.util.List;

public class PlayerChatListener implements Listener {

    private final JavaPlugin plugin;
    private final IntentRouter2 router;
    private final IntentDispatcher2 dispatcher;
    private final TutorialManager tutorialManager;

    public PlayerChatListener(JavaPlugin plugin, IntentRouter2 router, IntentDispatcher2 dispatcher,
            TutorialManager tutorialManager) {
        this.plugin = plugin;
        this.router = router;
        this.dispatcher = dispatcher;
        this.tutorialManager = tutorialManager;
    }

    @EventHandler
    public void onAsyncChat(AsyncChatEvent e) {
        Player p = e.getPlayer();

        String msg = PlainTextComponentSerializer.plainText().serialize(e.message());
        e.setCancelled(true);

        p.sendMessage("§7你：" + msg);
        plugin.getLogger().info("[聊天] 玩家 " + p.getName() + " 说: " + msg);

        // 保存原始消息
        final String originalMsg = msg;

        // 首先检查教学进度（如果玩家在教学中）
        tutorialManager.checkProgress(p, originalMsg);

        // 多意图版本
        router.askIntent(p.getName(), msg, (List<IntentResponse2> intents) -> {
            plugin.getLogger().info("[聊天] 收到 " + intents.size() + " 个意图");
            Bukkit.getScheduler().runTask(plugin, () -> {
                // 依次分发所有意图，并传递原始消息
                for (IntentResponse2 intent : intents) {
                    plugin.getLogger().info("[聊天] 分发意图: " + intent.type + ", rawText=" + intent.rawText);

                    // 如果intent没有rawText，使用原始消息
                    IntentResponse2 fixedIntent = intent;
                    if (intent.rawText == null || intent.rawText.isEmpty()) {
                        fixedIntent = new IntentResponse2(
                                intent.type,
                                intent.levelId,
                                intent.minimap,
                                originalMsg, // 使用原始消息
                                intent.worldPatch);
                        plugin.getLogger().info("[聊天] 修正后的rawText: " + originalMsg);
                    }

                    dispatcher.dispatch(p, fixedIntent);
                }
            });
        });
    }
}