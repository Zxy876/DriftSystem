package com.driftmc;

import org.bukkit.Bukkit;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.backend.BackendClient;
import com.driftmc.commands.AdvanceCommand;
import com.driftmc.commands.HeartMenuCommand;
import com.driftmc.commands.LevelCommand;
import com.driftmc.commands.LevelsCommand;
import com.driftmc.commands.SayToAICommand;
import com.driftmc.commands.TreeCommand;
import com.driftmc.commands.custom.CmdSay;
import com.driftmc.commands.custom.CmdStoryNext;
import com.driftmc.commands.custom.CmdTeleport;
import com.driftmc.commands.custom.CmdTime;
import com.driftmc.dsl.DslExecutor;
import com.driftmc.dsl.DslRegistry;
import com.driftmc.dsl.DslRunCommand;
import com.driftmc.intent.IntentRouter;
import com.driftmc.intent2.IntentDispatcher2;
import com.driftmc.intent2.IntentRouter2;
import com.driftmc.listeners.PlayerChatListener;
import com.driftmc.listeners.PlayerMoveListener;
import com.driftmc.minimap.MiniMapCommand;
import com.driftmc.npc.NPCManager;
import com.driftmc.session.PlayerSessionManager;
import com.driftmc.world.WorldPatchExecutor;

public class DriftPlugin extends JavaPlugin {

    private BackendClient backend;
    private PlayerSessionManager sessionManager;
    private WorldPatchExecutor worldPatcher;
    private NPCManager npcManager;
    private DslExecutor dslExecutor;

    private IntentRouter intentRouter;
    private IntentRouter2 intentRouter2;
    private IntentDispatcher2 intentDispatcher2;

    private String backendUrl;

    @Override
    public void onEnable() {

        saveDefaultConfig();
        backendUrl = getConfig().getString("backend-url", "http://localhost:8000");

        getLogger().info("Backend URL = " + backendUrl);

        backend = new BackendClient(backendUrl);
        sessionManager = new PlayerSessionManager();
        worldPatcher = new WorldPatchExecutor(this);
        npcManager = new NPCManager(this, sessionManager);

        DslRegistry registry = DslRegistry.createDefault(worldPatcher, npcManager, backend);
        dslExecutor = new DslExecutor(registry);

        intentRouter = new IntentRouter(
                this, backend, dslExecutor, npcManager, worldPatcher, sessionManager
        );

        intentRouter2 = new IntentRouter2(this, backend);
        intentDispatcher2 = new IntentDispatcher2(this);

        npcManager.setRouter(intentRouter);

        // -------------------- 注册命令 --------------------
        if (getCommand("levels") != null)
            getCommand("levels").setExecutor(
                    new LevelsCommand(backend, intentRouter, worldPatcher, sessionManager));

        if (getCommand("level") != null)
            getCommand("level").setExecutor(
                    new LevelCommand(backend, intentRouter, worldPatcher, sessionManager));

        if (getCommand("advance") != null)
            getCommand("advance").setExecutor(
                    new AdvanceCommand(backend, intentRouter, worldPatcher, sessionManager));

        if (getCommand("tree") != null)
            getCommand("tree").setExecutor(
                    new TreeCommand(backend, intentRouter, worldPatcher, sessionManager));

        if (getCommand("saytoai") != null)
            getCommand("saytoai").setExecutor(
                    new SayToAICommand(backend, intentRouter, worldPatcher, sessionManager));

        if (getCommand("heartmenu") != null)
            getCommand("heartmenu").setExecutor(
                    new HeartMenuCommand(backend, intentRouter, worldPatcher, sessionManager));

        if (getCommand("drift") != null)
            getCommand("drift").setExecutor(new DslRunCommand(dslExecutor));

        if (getCommand("storynext") != null)
            getCommand("storynext").setExecutor(
                    new CmdStoryNext(backend, intentRouter, worldPatcher, sessionManager));

        if (getCommand("tp2") != null)
            getCommand("tp2").setExecutor(
                    new CmdTeleport(backend, intentRouter, worldPatcher, sessionManager));

        if (getCommand("time2") != null)
            getCommand("time2").setExecutor(
                    new CmdTime(backend, intentRouter, worldPatcher, sessionManager));

        if (getCommand("sayc") != null)
            getCommand("sayc").setExecutor(
                    new CmdSay(backend, intentRouter, worldPatcher, sessionManager));

        if (getCommand("minimap") != null)
            getCommand("minimap").setExecutor(new MiniMapCommand(this, backendUrl));

        // -------------------- 监听器 --------------------

        // 聊天 -> 意图系统
        Bukkit.getPluginManager().registerEvents(
                new PlayerChatListener(
                        this, backend, intentRouter, sessionManager, intentRouter2, intentDispatcher2
                ),
                this
        );

        // 移动监听器（触发剧情）
        Bukkit.getPluginManager().registerEvents(
                new PlayerMoveListener(backend, worldPatcher),
                this
        );

        getLogger().info("✔ DriftMC Loaded Successfully (Triggers + AI + DSL + MiniMap)");
    }

    @Override
    public void onDisable() {
        getLogger().info("✘ DriftMC Disabled");
    }
}