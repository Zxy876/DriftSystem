package com.driftmc;

import org.bukkit.Bukkit;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.PluginCommand;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.backend.BackendClient;
import com.driftmc.commands.AdvanceCommand;
import com.driftmc.commands.DriftCommand;
import com.driftmc.commands.HeartMenuCommand;
import com.driftmc.commands.LevelCommand;
import com.driftmc.commands.LevelsCommand;
import com.driftmc.commands.MiniMapCommand;
import com.driftmc.commands.NpcMasterCommand;
import com.driftmc.commands.SayToAICommand;
import com.driftmc.commands.StoryCreativeCommand;
import com.driftmc.commands.TalkCommand;
import com.driftmc.commands.custom.CmdSay;
import com.driftmc.commands.custom.CmdStoryNext;
import com.driftmc.commands.custom.CmdTeleport;
import com.driftmc.commands.custom.CmdTime;
import com.driftmc.dsl.DslExecutor;
import com.driftmc.dsl.DslRegistry;
import com.driftmc.intent.IntentRouter;
import com.driftmc.intent2.IntentDispatcher2;
import com.driftmc.intent2.IntentRouter2;
import com.driftmc.listeners.NearbyNPCListener;
import com.driftmc.listeners.PlayerChatListener;
import com.driftmc.listeners.PlayerJoinListener;
import com.driftmc.npc.NPCManager;
import com.driftmc.session.PlayerSessionManager;
import com.driftmc.story.StoryCreativeManager;
import com.driftmc.story.StoryManager;
import com.driftmc.tutorial.TutorialManager;
import com.driftmc.world.WorldPatchExecutor;

public class DriftPlugin extends JavaPlugin {

    private BackendClient backend;
    private WorldPatchExecutor worldPatcher;
    private StoryManager storyManager;
    private StoryCreativeManager storyCreativeManager;
    private TutorialManager tutorialManager;
    private PlayerSessionManager sessionManager;
    private NPCManager npcManager;
    private DslRegistry dslRegistry;
    private DslExecutor dslExecutor;
    private IntentRouter intentRouter;
    private IntentRouter2 intentRouter2;
    private IntentDispatcher2 intentDispatcher2;

    @Override
    public void onEnable() {
        saveDefaultConfig();

        // 从 config.yml 读取后端地址
        String url = getConfig().getString("backend_url");
        if (url == null || url.isBlank()) {
            url = "http://127.0.0.1:8000";
        }
        if (url.endsWith("/")) {
            url = url.substring(0, url.length() - 1);
        }

        getLogger().info("[DriftPlugin] 后端地址: " + url);

        // 初始化核心组件
        this.backend = new BackendClient(url);
        this.worldPatcher = new WorldPatchExecutor(this);
        this.storyManager = new StoryManager(this, backend);
        this.storyCreativeManager = new StoryCreativeManager(this);
        this.tutorialManager = new TutorialManager(this, backend);
        this.sessionManager = new PlayerSessionManager();
        this.npcManager = new NPCManager(this, sessionManager);
        this.dslRegistry = DslRegistry.createDefault(worldPatcher, npcManager, backend);
        this.dslExecutor = new DslExecutor(dslRegistry);
        this.intentRouter = new IntentRouter(this, backend, dslExecutor, npcManager, worldPatcher, sessionManager);

        // 意图系统 (新版多意图管线)
        this.intentRouter2 = new IntentRouter2(this, backend);
        this.intentDispatcher2 = new IntentDispatcher2(this, backend, worldPatcher);
        this.intentDispatcher2.setTutorialManager(tutorialManager);

        // 注册聊天监听器（核心：自然语言驱动）
        Bukkit.getPluginManager().registerEvents(
            new PlayerChatListener(this, intentRouter2, intentDispatcher2, tutorialManager),
            this);

        // 注册玩家加入/离开监听器（教学系统）
        Bukkit.getPluginManager().registerEvents(
            new PlayerJoinListener(this, tutorialManager),
            this);

        // 注册剧情创造管理器监听器
        Bukkit.getPluginManager().registerEvents(storyCreativeManager, this);

        // 注册 NPC 临近监听（触发老版 IntentRouter）
        Bukkit.getPluginManager().registerEvents(new NearbyNPCListener(npcManager, intentRouter), this);

        // 注册命令
        registerCommand("drift", new DriftCommand(backend, storyManager, worldPatcher, tutorialManager));
        registerCommand("storycreative", new StoryCreativeCommand(this, storyCreativeManager, storyManager));
        registerCommand("minimap", new MiniMapCommand(this, url));
        registerCommand("talk", new TalkCommand(intentRouter));
        registerCommand("saytoai", new SayToAICommand(backend, intentRouter, worldPatcher, sessionManager));
        registerCommand("advance", new AdvanceCommand(backend, intentRouter, worldPatcher, sessionManager));
        registerCommand("storynext", new CmdStoryNext(backend, intentRouter, worldPatcher, sessionManager));
        registerCommand("heartmenu", new HeartMenuCommand(backend, intentRouter, worldPatcher, sessionManager));
        registerCommand("level", new LevelCommand(backend, intentRouter, worldPatcher, sessionManager));
        registerCommand("levels", new LevelsCommand(backend, intentRouter, worldPatcher, sessionManager));
        registerCommand("npc", new NpcMasterCommand(npcManager));
        registerCommand("tp2", new CmdTeleport(backend, intentRouter, worldPatcher, sessionManager));
        registerCommand("time2", new CmdTime(backend, intentRouter, worldPatcher, sessionManager));
        registerCommand("sayc", new CmdSay(backend, intentRouter, worldPatcher, sessionManager));

        getLogger().info("======================================");
        getLogger().info("   DriftSystem / 心悦宇宙");
        getLogger().info("   完全自然语言驱动的AI冒险系统");
        getLogger().info("======================================");
        getLogger().info("✓ 后端连接: " + url);
        getLogger().info("✓ 自然语言解析: 已启用");
        getLogger().info("✓ 世界动态渲染: 已启用");
        getLogger().info("✓ 剧情引擎: 已就绪");
        getLogger().info("✓ DSL注入: 支持");
        getLogger().info("✓ 新手教学: 已启用");
        getLogger().info("======================================");
        getLogger().info("玩家可以直接在聊天中说话来推进剧情！");
        getLogger().info("新玩家将自动进入教学系统！");
        getLogger().info("======================================");
    }

    @Override
    public void onDisable() {
        // 清理创造模式会话
        if (storyCreativeManager != null) {
            storyCreativeManager.cleanup();
        }

        if (tutorialManager != null) {
            Bukkit.getOnlinePlayers().forEach(tutorialManager::cleanupPlayer);
        }

        getLogger().info("======================================");
        getLogger().info("   DriftSystem 已关闭");
        getLogger().info("======================================");
    }

    private void registerCommand(String name, CommandExecutor executor) {
        PluginCommand command = getCommand(name);
        if (command == null) {
            getLogger().severe("plugin.yml 未定义命令: " + name);
            return;
        }
        command.setExecutor(executor);
    }

    public BackendClient getBackend() {
        return backend;
    }

    public StoryManager getStoryManager() {
        return storyManager;
    }

    public WorldPatchExecutor getWorldPatcher() {
        return worldPatcher;
    }

    public TutorialManager getTutorialManager() {
        return tutorialManager;
    }
}