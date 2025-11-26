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
import com.driftmc.listeners.PlayerChatListener;
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

    @Override
    public void onEnable() {
        saveDefaultConfig();

        String backendUrl = getConfig().getString("backend-url", "http://localhost:8000");
        getLogger().info("Backend URL = " + backendUrl);

        backend = new BackendClient(backendUrl);
        sessionManager = new PlayerSessionManager();
        worldPatcher = new WorldPatchExecutor(this);

        // NPC 管理
        npcManager = new NPCManager(this, sessionManager);

        // DSL
        DslRegistry registry = DslRegistry.createDefault(worldPatcher, npcManager, backend);
        dslExecutor = new DslExecutor(registry);

        // Intent Router（AI 总线）
        intentRouter = new IntentRouter(
                this,
                backend,
                dslExecutor,
                npcManager,
                worldPatcher,
                sessionManager
        );

        // 解决循环依赖
        npcManager.setRouter(intentRouter);

        // --- 注册命令（全部统一构造器） ---
        if (getCommand("levels") != null) {
            getCommand("levels").setExecutor(
                    new LevelsCommand(backend, intentRouter, worldPatcher, sessionManager)
            );
        }

        if (getCommand("level") != null) {
            getCommand("level").setExecutor(
                    new LevelCommand(backend, intentRouter, worldPatcher, sessionManager)
            );
        }

        if (getCommand("advance") != null) {
            getCommand("advance").setExecutor(
                    new AdvanceCommand(backend, intentRouter, worldPatcher, sessionManager)
            );
        }

        if (getCommand("tree") != null) {
            getCommand("tree").setExecutor(
                    new TreeCommand(backend, intentRouter, worldPatcher, sessionManager)
            );
        }

        if (getCommand("saytoai") != null) {
            getCommand("saytoai").setExecutor(
                    new SayToAICommand(backend, intentRouter, worldPatcher, sessionManager)
            );
        }

        if (getCommand("heartmenu") != null) {
            getCommand("heartmenu").setExecutor(
                    new HeartMenuCommand(backend, intentRouter, worldPatcher, sessionManager)
            );
        }

        if (getCommand("drift") != null) {
            getCommand("drift").setExecutor(new DslRunCommand(dslExecutor));
        }

        if (getCommand("storynext") != null) {
            getCommand("storynext").setExecutor(
                    new CmdStoryNext(backend, intentRouter, worldPatcher, sessionManager)
            );
        }

        if (getCommand("tp2") != null) {
            getCommand("tp2").setExecutor(
                    new CmdTeleport(backend, intentRouter, worldPatcher, sessionManager)
            );
        }

        if (getCommand("time2") != null) {
            getCommand("time2").setExecutor(
                    new CmdTime(backend, intentRouter, worldPatcher, sessionManager)
            );
        }

        if (getCommand("sayc") != null) {
            getCommand("sayc").setExecutor(
                    new CmdSay(backend, intentRouter, worldPatcher, sessionManager)
            );
        }

        // --- 事件监听：自然语言聊天 ---
        Bukkit.getPluginManager().registerEvents(
                new PlayerChatListener(backend, intentRouter, sessionManager),
                this
        );

        getLogger().info("✔ DriftMC Loaded Successfully (心悦宇宙 · AI + DSL + NPC + WorldPatch)");
    }

    @Override
    public void onDisable() {
        getLogger().info("✘ DriftMC Disabled");
    }
}