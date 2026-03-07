package com.driftmc;

import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.Bukkit;

public class DriftPlugin extends JavaPlugin {

    private static DriftPlugin instance;
    public static DriftPlugin inst() { return instance; }

    @Override
    public void onEnable() {
        instance = this;

        Bukkit.getLogger().info("[DriftMC] 插件已启动");

        // 注册命令
        getCommand("level").setExecutor(new LevelCommand());
        getCommand("next").setExecutor(new NextCommand());

        // 注册 HTTP 客户端
        BackendClient.init();
    }

    @Override
    public void onDisable() {
        Bukkit.getLogger().info("[DriftMC] 插件已关闭");
    }
}
