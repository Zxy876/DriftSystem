package com.driftmc;

import org.bukkit.Bukkit;
import org.bukkit.plugin.java.JavaPlugin;

import com.driftmc.backend.BackendClient;
import com.driftmc.intent2.IntentDispatcher2;
import com.driftmc.intent2.IntentRouter2;
import com.driftmc.listeners.PlayerChatListener;
import com.driftmc.world.WorldPatchExecutor;

public class DriftPlugin extends JavaPlugin {

    private BackendClient backend;
    private WorldPatchExecutor worldPatcher;

    private IntentRouter2 intentRouter2;
    private IntentDispatcher2 intentDispatcher2;

    @Override
    public void onEnable() {
        saveDefaultConfig();

        // 从 plugin.yml 或 config.yml 读取后端地址
        String url = getConfig().getString("backend_url", "http://127.0.0.1:8000");
        if (url.endsWith("/")) url = url.substring(0, url.length() - 1);

        getLogger().info("[DriftPlugin] 后端地址: " + url);

        // 初始化 BackendClient(String baseUrl)
        this.backend = new BackendClient(url);

        // 世界 patch 执行器
        this.worldPatcher = new WorldPatchExecutor(this);

        // 意图系统
        this.intentRouter2 = new IntentRouter2(this, backend);
        this.intentDispatcher2 = new IntentDispatcher2(this, backend, worldPatcher);

        // 注册聊天监听器
        Bukkit.getPluginManager().registerEvents(
                new PlayerChatListener(this, intentRouter2, intentDispatcher2),
                this
        );

        getLogger().info("======== DriftMC / DriftSystem 插件已启动 ========");
    }

    @Override
    public void onDisable() {
        getLogger().info("[DriftPlugin] 已关闭。");
    }
}