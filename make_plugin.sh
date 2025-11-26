#!/bin/bash
set -e

PLUGIN_ROOT=mc_plugin
JAVA_ROOT=$PLUGIN_ROOT/src/main/java/com/driftmc
RES_ROOT=$PLUGIN_ROOT/src/main/resources

echo "=== 创建目录结构 ==="
rm -rf $PLUGIN_ROOT
mkdir -p $JAVA_ROOT/commands
mkdir -p $JAVA_ROOT/api
mkdir -p $RES_ROOT

echo "=== 写入 plugin.yml ==="
cat > $RES_ROOT/plugin.yml <<EOF
name: DriftMC
main: com.driftmc.DriftPlugin
version: 1.0
api-version: 1.20
commands:
  levels:
    description: List all levels
  loadlevel:
    description: Load a level
  advance:
    description: Advance story
EOF

echo "=== 写入 BackendClient.java ==="
cat > $JAVA_ROOT/api/BackendClient.java <<EOF
package com.driftmc.api;

import java.io.IOException;
import java.net.URI;
import java.net.http.*;
import org.bukkit.Bukkit;

public class BackendClient {
    private static final String BASE = "http://127.0.0.1:8000";

    private static final HttpClient client = HttpClient.newBuilder().build();

    public static String httpGet(String path) {
        try {
            HttpRequest req = HttpRequest.newBuilder()
                .uri(URI.create(BASE + path))
                .GET()
                .build();
            return client.send(req, HttpResponse.BodyHandlers.ofString()).body();
        } catch (Exception e) {
            Bukkit.getLogger().warning("GET failed: " + e.getMessage());
            return null;
        }
    }

    public static String httpPost(String path) {
        try {
            HttpRequest req = HttpRequest.newBuilder()
                .uri(URI.create(BASE + path))
                .POST(HttpRequest.BodyPublishers.noBody())
                .build();
            return client.send(req, HttpResponse.BodyHandlers.ofString()).body();
        } catch (Exception e) {
            Bukkit.getLogger().warning("POST failed: " + e.getMessage());
            return null;
        }
    }
}
EOF

echo "=== 写入 DriftPlugin.java ==="
cat > $JAVA_ROOT/DriftPlugin.java <<EOF
package com.driftmc;

import org.bukkit.plugin.java.JavaPlugin;
import com.driftmc.commands.*;

public class DriftPlugin extends JavaPlugin {

    @Override
    public void onEnable() {
        getLogger().info("DriftMC 插件已启动!");

        getCommand("levels").setExecutor(new LevelCommand());
        getCommand("loadlevel").setExecutor(new LoadLevelCommand());
        getCommand("advance").setExecutor(new AdvanceCommand());
    }
}
EOF

echo "=== 写入 LevelCommand.java ==="
cat > $JAVA_ROOT/commands/LevelCommand.java <<EOF
package com.driftmc.commands;

import com.driftmc.api.BackendClient;
import org.bukkit.command.*;

public class LevelCommand implements CommandExecutor {
    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String label, String[] args) {
        String result = BackendClient.httpGet("/levels");
        sender.sendMessage("关卡列表: " + result);
        return true;
    }
}
EOF

echo "=== 写入 LoadLevelCommand.java ==="
cat > $JAVA_ROOT/commands/LoadLevelCommand.java <<EOF
package com.driftmc.commands;

import com.driftmc.api.BackendClient;
import org.bukkit.command.*;

public class LoadLevelCommand implements CommandExecutor {
    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String label, String[] args) {

        if (args.length != 2) {
            sender.sendMessage("/loadlevel <player> <level_id>");
            return true;
        }

        String player = args[0];
        String level = args[1];

        String result = BackendClient.httpPost("/story/load/" + player + "/" + level);
        sender.sendMessage("加载关卡结果: " + result);

        return true;
    }
}
EOF

echo "=== 写入 AdvanceCommand.java ==="
cat > $JAVA_ROOT/commands/AdvanceCommand.java <<EOF
package com.driftmc.commands;

import com.driftmc.api.BackendClient;
import org.bukkit.command.*;

public class AdvanceCommand implements CommandExecutor {
    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String label, String[] args) {

        if (args.length != 1) {
            sender.sendMessage("/advance <player>");
            return true;
        }

        String player = args[0];
        String result = BackendClient.httpPost("/story/advance/" + player);

        sender.sendMessage("推进故事: " + result);
        return true;
    }
}
EOF

echo "=== 插件全部生成完成 ==="
echo "下一步："
echo "cd mc_plugin && mvn clean package"
