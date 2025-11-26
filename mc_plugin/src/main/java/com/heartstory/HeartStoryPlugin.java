package com.heartstory;

import com.heartstory.commands.LoadLevelCommand;
import com.heartstory.commands.SayAICommand;

import org.bukkit.plugin.java.JavaPlugin;

public class HeartStoryPlugin extends JavaPlugin {

    @Override
    public void onEnable() {
        getCommand("loadlevel").setExecutor(new LoadLevelCommand());
        getCommand("sayai").setExecutor(new SayAICommand());

        getLogger().info("HeartStory 插件已启动！");
    }

    @Override
    public void onDisable() {
        getLogger().info("HeartStory 插件已卸载！");
    }
}
