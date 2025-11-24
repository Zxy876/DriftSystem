package com.driftmc;

import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.Bukkit;

import com.driftmc.listeners.PlayerChatListener;
import com.driftmc.actions.WorldPatchExecutor;

public class DriftMCPlugin extends JavaPlugin {

    private BackendClient backend;
    private WorldPatchExecutor executor;

    @Override
    public void onEnable() {

        // ================================================
        //  后端 URL（本机 FastAPI 服务器）
        //  -----------------------------------------------
        //  ⚠ 你的后端是跑在你电脑的 http://127.0.0.1:8000
        //  插件会访问:
        //      http://127.0.0.1:8000/world/apply
        //
        //  同学连接你的 Minecraft 服务器（局域网或热点）
        //  → 后端仍然走你的电脑，不需要任何公网映射
        // ================================================

        String backendUrl = "http://127.0.0.1:8000";

        this.backend = new BackendClient(backendUrl);
        this.executor = new WorldPatchExecutor(this);

        // 注册聊天监听器（AI 主逻辑）
        Bukkit.getPluginManager().registerEvents(
                new PlayerChatListener(this, backend, executor),
                this
        );

        getLogger().info("DriftMC Plugin 已启动！");
    }

    public BackendClient getBackend() {
        return backend;
    }

    public WorldPatchExecutor getExecutor() {
        return executor;
    }
}