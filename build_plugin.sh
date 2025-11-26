#!/bin/bash
set -e

PLUGIN_DIR="mc_plugin"
SRC_DIR="$PLUGIN_DIR/src/main/java/com/driftmc"

echo "=== 创建全新 mc_plugin 项目结构 ==="
rm -rf $PLUGIN_DIR
mkdir -p $SRC_DIR
mkdir -p $PLUGIN_DIR/src/main/resources

echo "=== 写入 pom.xml ==="
cat > $PLUGIN_DIR/pom.xml << 'EOF'
<project xmlns="http://maven.apache.org/POM/4.0.0"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
                      http://maven.apache.org/xsd/maven-4.0.0.xsd">

  <modelVersion>4.0.0</modelVersion>
  <groupId>com.driftmc</groupId>
  <artifactId>drift-mc-plugin</artifactId>
  <version>1.0-SNAPSHOT</version>
  <packaging>jar</packaging>

  <dependencies>
    <dependency>
      <groupId>io.papermc.paper</groupId>
      <artifactId>paper-api</artifactId>
      <version>1.20.1-R0.1-SNAPSHOT</version>
      <scope>provided</scope>
    </dependency>

    <!-- HTTP 客户端 -->
    <dependency>
      <groupId>com.squareup.okhttp3</groupId>
      <artifactId>okhttp</artifactId>
      <version>4.12.0</version>
    </dependency>
  </dependencies>

</project>
EOF


echo "=== 写入 plugin.yml ==="
cat > $PLUGIN_DIR/src/main/resources/plugin.yml << 'EOF'
name: DriftMC
main: com.driftmc.DriftPlugin
version: 1.0
api-version: 1.20
commands:
  level:
    description: 加载一个关卡
  next:
    description: 推进剧情
EOF


echo "=== 写入 Java 插件入口 DriftPlugin.java ==="
cat > $SRC_DIR/DriftPlugin.java << 'EOF'
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
EOF


echo "=== 写入 BackendClient ==="
cat > $SRC_DIR/BackendClient.java << 'EOF'
package com.driftmc;

import okhttp3.*;

public class BackendClient {

    private static OkHttpClient client;
    private static final String BASE_URL = "http://127.0.0.1:8000";

    public static void init() {
        client = new OkHttpClient();
    }

    public static String post(String path) {
        try {
            Request request = new Request.Builder()
                    .url(BASE_URL + path)
                    .post(RequestBody.create("", null))
                    .build();

            Response resp = client.newCall(request).execute();
            return resp.body().string();

        } catch (Exception e) {
            return "ERROR: " + e.getMessage();
        }
    }
}
EOF


echo "=== 写入 LevelCommand ==="
cat > $SRC_DIR/LevelCommand.java << 'EOF'
package com.driftmc;

import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

public class LevelCommand implements CommandExecutor {
    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String lbl, String[] args) {

        if (!(sender instanceof Player)) {
            sender.sendMessage("玩家才能执行");
            return true;
        }

        if (args.length != 1) {
            sender.sendMessage("用法: /level level_1");
            return true;
        }

        Player p = (Player) sender;
        String level = args[0];

        String res = BackendClient.post("/story/load/" + p.getName() + "/" + level);
        p.sendMessage("§a加载关卡: " + level);
        p.sendMessage("§7后端响应: " + res);
        return true;
    }
}
EOF


echo "=== 写入 NextCommand ==="
cat > $SRC_DIR/NextCommand.java << 'EOF'
package com.driftmc;

import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

public class NextCommand implements CommandExecutor {

    @Override
    public boolean onCommand(CommandSender cs, Command cmd, String lbl, String[] args) {

        if (!(cs instanceof Player)) {
            cs.sendMessage("玩家才能执行");
            return true;
        }

        Player p = (Player) cs;
        String res = BackendClient.post("/story/advance/" + p.getName());
        p.sendMessage("§b剧情推进！");
        p.sendMessage("§7后端响应: " + res);
        return true;
    }
}
EOF


echo "=== 编译插件 ==="
cd mc_plugin
mvn -q clean package

echo "=== 完成！插件输出：mc_plugin/target/drift-mc-plugin-1.0-SNAPSHOT.jar ==="
EOF
