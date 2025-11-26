#!/bin/bash
set -e

PLUGIN_DIR="mc_plugin"

echo "=== Creating clean MC plugin structure: $PLUGIN_DIR ==="

rm -rf $PLUGIN_DIR
mkdir -p $PLUGIN_DIR/src/main/java/com/heartstory
mkdir -p $PLUGIN_DIR/src/main/java/com/heartstory/commands
mkdir -p $PLUGIN_DIR/src/main/java/com/heartstory/http
mkdir -p $PLUGIN_DIR/src/main/resources

# ------------------------
# pom.xml
# ------------------------
cat > $PLUGIN_DIR/pom.xml << 'EOF'
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         https://maven.apache.org/xsd/maven-4.0.0.xsd">

    <modelVersion>4.0.0</modelVersion>

    <groupId>com.heartstory</groupId>
    <artifactId>heart-story-plugin</artifactId>
    <version>1.0-SNAPSHOT</version>
    <packaging>jar</packaging>

    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
    </properties>

    <repositories>
        <repository>
            <id>spigot-repo</id>
            <url>https://hub.spigotmc.org/nexus/content/repositories/snapshots/</url>
        </repository>
    </repositories>

    <dependencies>
        <dependency>
            <groupId>org.spigotmc</groupId>
            <artifactId>spigot-api</artifactId>
            <version>1.20.1-R0.1-SNAPSHOT</version>
            <scope>provided</scope>
        </dependency>

        <dependency>
            <groupId>com.squareup.okhttp3</groupId>
            <artifactId>okhttp</artifactId>
            <version>4.10.0</version>
        </dependency>
    </dependencies>

</project>
EOF

# ------------------------
# plugin.yml
# ------------------------
cat > $PLUGIN_DIR/src/main/resources/plugin.yml << 'EOF'
name: HeartStory
main: com.heartstory.HeartStoryPlugin
version: 1.0
api-version: 1.20
description: Heart Story Engine bridge

commands:
  loadlevel:
    description: Load story level
    usage: /loadlevel <level>
  sayai:
    description: Send text to AI
    usage: /sayai <text>
EOF

# ------------------------
# BackendClient.java
# ------------------------
cat > $PLUGIN_DIR/src/main/java/com/heartstory/http/BackendClient.java << 'EOF'
package com.heartstory.http;

import okhttp3.*;

public class BackendClient {

    private final OkHttpClient http = new OkHttpClient();
    private final String baseUrl = "http://127.0.0.1:8000";

    public String loadLevel(String player, String levelId) throws Exception {
        Request request = new Request.Builder()
                .url(baseUrl + "/story/load/" + player + "/" + levelId)
                .post(RequestBody.create("", MediaType.parse("application/json")))
                .build();

        return http.newCall(request).execute().body().string();
    }

    public String sayToAI(String player, String text) throws Exception {
        String json = "{\"world_state\":{},\"action\":{\"say\":\"" + text + "\"}}";

        Request request = new Request.Builder()
                .url(baseUrl + "/story/advance/" + player)
                .post(RequestBody.create(json, MediaType.parse("application/json")))
                .build();

        return http.newCall(request).execute().body().string();
    }
}
EOF

# ------------------------
# LoadLevelCommand.java
# ------------------------
cat > $PLUGIN_DIR/src/main/java/com/heartstory/commands/LoadLevelCommand.java << 'EOF'
package com.heartstory.commands;

import com.heartstory.http.BackendClient;
import org.bukkit.command.*;
import org.bukkit.entity.Player;

public class LoadLevelCommand implements CommandExecutor {

    private final BackendClient backend = new BackendClient();

    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String label, String[] args) {

        if (!(sender instanceof Player player)) {
            sender.sendMessage("玩家才能使用！");
            return true;
        }

        if (args.length < 1) {
            player.sendMessage("用法: /loadlevel <level_id>");
            return true;
        }

        String levelId = args[0];

        player.sendMessage("§e正在加载关卡：" + levelId);

        try {
            String resp = backend.loadLevel(player.getName(), levelId);
            player.sendMessage("§a后端响应: §f" + resp);
        } catch (Exception e) {
            player.sendMessage("§c连接后端失败：" + e.getMessage());
        }

        return true;
    }
}
EOF

# ------------------------
# SayAICommand.java
# ------------------------
cat > $PLUGIN_DIR/src/main/java/com/heartstory/commands/SayAICommand.java << 'EOF'
package com.heartstory.commands;

import com.heartstory.http.BackendClient;
import org.bukkit.command.*;
import org.bukkit.entity.Player;

public class SayAICommand implements CommandExecutor {

    private final BackendClient backend = new BackendClient();

    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String lbl, String[] args) {

        if (!(sender instanceof Player player)) {
            sender.sendMessage("玩家才能使用！");
            return true;
        }

        if (args.length < 1) {
            player.sendMessage("用法: /sayai <文本>");
            return true;
        }

        String text = String.join(" ", args);

        try {
            String resp = backend.sayToAI(player.getName(), text);
            player.sendMessage("§aAI回应: §f" + resp);
        } catch (Exception e) {
            player.sendMessage("§c后端连接失败：" + e.getMessage());
        }

        return true;
    }
}
EOF

# ------------------------
# HeartStoryPlugin.java
# ------------------------
cat > $PLUGIN_DIR/src/main/java/com/heartstory/HeartStoryPlugin.java << 'EOF'
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
EOF

echo "=== 插件已生成 ==="
echo "现在运行："
echo "cd mc_plugin && mvn clean package"
