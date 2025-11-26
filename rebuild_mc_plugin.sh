#!/usr/bin/env bash
set -e

echo "=== Rebuild Drift MC Plugin (fresh minimal) ==="

ROOT_DIR="$(pwd)"
PLUGIN_DIR="$ROOT_DIR/system/mc_plugin"
SERVER_DIR="$ROOT_DIR/server"
PKG_DIR="$PLUGIN_DIR/src/main/java/com/driftmc"

echo "[0] ensure plugin dir exists: $PLUGIN_DIR"
mkdir -p "$PLUGIN_DIR"

echo "[1] wipe old src/target (fresh start)"
rm -rf "$PLUGIN_DIR/src" "$PLUGIN_DIR/target"

echo "[2] create maven folders"
mkdir -p "$PKG_DIR/backend" "$PKG_DIR/commands" "$PKG_DIR/listeners" "$PKG_DIR/actions"
mkdir -p "$PLUGIN_DIR/src/main/resources"

echo "[3] write pom.xml"
cat > "$PLUGIN_DIR/pom.xml" <<'EOF'
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         https://maven.apache.org/xsd/maven-4.0.0.xsd">

  <modelVersion>4.0.0</modelVersion>
  <groupId>com.driftmc</groupId>
  <artifactId>drift-mc-plugin</artifactId>
  <version>1.0-SNAPSHOT</version>
  <name>drift-mc-plugin</name>
  <packaging>jar</packaging>

  <properties>
    <java.version>17</java.version>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
  </properties>

  <repositories>
    <repository>
      <id>papermc-repo</id>
      <url>https://repo.papermc.io/repository/maven-public/</url>
    </repository>
  </repositories>

  <dependencies>
    <!-- Paper API (Spigot compatible) -->
    <dependency>
      <groupId>io.papermc.paper</groupId>
      <artifactId>paper-api</artifactId>
      <version>1.20.1-R0.1-SNAPSHOT</version>
      <scope>provided</scope>
    </dependency>

    <!-- JSON support -->
    <dependency>
      <groupId>org.json</groupId>
      <artifactId>json</artifactId>
      <version>20240303</version>
    </dependency>
  </dependencies>

  <build>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-compiler-plugin</artifactId>
        <version>3.11.0</version>
        <configuration>
          <source>${java.version}</source>
          <target>${java.version}</target>
        </configuration>
      </plugin>
    </plugins>
  </build>
</project>
EOF

echo "[4] write plugin.yml"
cat > "$PLUGIN_DIR/src/main/resources/plugin.yml" <<'EOF'
name: DriftMCPlugin
version: 1.0
main: com.driftmc.DriftPlugin
api-version: 1.20

commands:
  level:
    description: Load a drift level
    usage: /level <level_id>
  heart:
    description: Open heart menu (placeholder)
    usage: /heart
  saytoai:
    description: Send a message to AI backend (placeholder)
    usage: /saytoai <text>
EOF

echo "[5] write config.yml (optional placeholder)"
cat > "$PLUGIN_DIR/src/main/resources/config.yml" <<'EOF'
backend:
  url: "http://127.0.0.1:8000"
  timeout_ms: 3000
EOF

echo "[6] write DriftPlugin.java (MAIN CLASS)"
cat > "$PKG_DIR/DriftPlugin.java" <<'EOF'
package com.driftmc;

import com.driftmc.backend.BackendClient;
import com.driftmc.commands.HeartMenuCommand;
import com.driftmc.commands.LevelCommand;
import com.driftmc.commands.SayToAICommand;
import com.driftmc.listeners.PlayerChatListener;
import org.bukkit.plugin.java.JavaPlugin;

public class DriftPlugin extends JavaPlugin {

    private static DriftPlugin instance;
    private BackendClient backendClient;

    public static DriftPlugin getInstance() {
        return instance;
    }

    public BackendClient getBackendClient() {
        return backendClient;
    }

    @Override
    public void onEnable() {
        instance = this;
        saveDefaultConfig();

        backendClient = new BackendClient(this);

        // register commands
        getCommand("level").setExecutor(new LevelCommand(this));
        getCommand("heart").setExecutor(new HeartMenuCommand(this));
        getCommand("saytoai").setExecutor(new SayToAICommand(this));

        // register listeners
        getServer().getPluginManager().registerEvents(new PlayerChatListener(this), this);

        getLogger().info("DriftMCPlugin enabled.");
    }

    @Override
    public void onDisable() {
        getLogger().info("DriftMCPlugin disabled.");
    }
}
EOF

echo "[7] write BackendClient.java (placeholder, no real http yet)"
cat > "$PKG_DIR/backend/BackendClient.java" <<'EOF'
package com.driftmc.backend;

import com.driftmc.DriftPlugin;
import org.bukkit.Bukkit;

public class BackendClient {

    private final DriftPlugin plugin;
    private final String baseUrl;
    private final int timeoutMs;

    public BackendClient(DriftPlugin plugin) {
        this.plugin = plugin;
        this.baseUrl = plugin.getConfig().getString("backend.url", "http://127.0.0.1:8000");
        this.timeoutMs = plugin.getConfig().getInt("backend.timeout_ms", 3000);
    }

    // placeholder async call
    public void sendToAI(String playerName, String text) {
        Bukkit.getScheduler().runTaskAsynchronously(plugin, () -> {
            plugin.getLogger().info("[BackendClient placeholder] " + playerName + ": " + text);
            // TODO: real HTTP to python backend
        });
    }
}
EOF

echo "[8] write LevelCommand.java"
cat > "$PKG_DIR/commands/LevelCommand.java" <<'EOF'
package com.driftmc.commands;

import com.driftmc.DriftPlugin;
import org.bukkit.ChatColor;
import org.bukkit.command.*;
import org.bukkit.entity.Player;

public class LevelCommand implements CommandExecutor {

    private final DriftPlugin plugin;

    public LevelCommand(DriftPlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String label, String[] args) {
        if (!(sender instanceof Player p)) {
            sender.sendMessage("Only players can use this command.");
            return true;
        }
        if (args.length < 1) {
            p.sendMessage(ChatColor.RED + "Usage: /level <level_id>");
            return true;
        }
        String levelId = args[0];
        p.sendMessage(ChatColor.AQUA + "[Drift] Loading level: " + levelId);

        // TODO: hook to real world/pack loader later
        plugin.getLogger().info(p.getName() + " requested level " + levelId);
        return true;
    }
}
EOF

echo "[9] write HeartMenuCommand.java"
cat > "$PKG_DIR/commands/HeartMenuCommand.java" <<'EOF'
package com.driftmc.commands;

import com.driftmc.DriftPlugin;
import org.bukkit.ChatColor;
import org.bukkit.command.*;
import org.bukkit.entity.Player;

public class HeartMenuCommand implements CommandExecutor {

    private final DriftPlugin plugin;

    public HeartMenuCommand(DriftPlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String label, String[] args) {
        if (!(sender instanceof Player p)) {
            sender.sendMessage("Only players can use this command.");
            return true;
        }
        p.sendMessage(ChatColor.LIGHT_PURPLE + "[Heart] Menu placeholder. (later we bind to 心悦文集 UI)");
        return true;
    }
}
EOF

echo "[10] write SayToAICommand.java"
cat > "$PKG_DIR/commands/SayToAICommand.java" <<'EOF'
package com.driftmc.commands;

import com.driftmc.DriftPlugin;
import org.bukkit.ChatColor;
import org.bukkit.command.*;
import org.bukkit.entity.Player;

public class SayToAICommand implements CommandExecutor {

    private final DriftPlugin plugin;

    public SayToAICommand(DriftPlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command cmd, String label, String[] args) {
        if (!(sender instanceof Player p)) {
            sender.sendMessage("Only players can use this command.");
            return true;
        }
        if (args.length < 1) {
            p.sendMessage(ChatColor.RED + "Usage: /saytoai <text>");
            return true;
        }
        String text = String.join(" ", args);
        p.sendMessage(ChatColor.GREEN + "[AI] Sent: " + text);
        plugin.getBackendClient().sendToAI(p.getName(), text);
        return true;
    }
}
EOF

echo "[11] write PlayerChatListener.java"
cat > "$PKG_DIR/listeners/PlayerChatListener.java" <<'EOF'
package com.driftmc.listeners;

import com.driftmc.DriftPlugin;
import org.bukkit.event.*;
import org.bukkit.event.player.AsyncPlayerChatEvent;

public class PlayerChatListener implements Listener {

    private final DriftPlugin plugin;

    public PlayerChatListener(DriftPlugin plugin) {
        this.plugin = plugin;
    }

    @EventHandler
    public void onChat(AsyncPlayerChatEvent e) {
        // placeholder: later you can route normal chat into AI too
        plugin.getLogger().info("[Chat] " + e.getPlayer().getName() + ": " + e.getMessage());
    }
}
EOF

echo "[12] dummy WorldPatchExecutor.java (placeholder)"
cat > "$PKG_DIR/actions/WorldPatchExecutor.java" <<'EOF'
package com.driftmc.actions;

public class WorldPatchExecutor {
    // TODO: later use this to patch/load 心悦文集关卡
}
EOF

echo "[13] mvn clean package"
cd "$PLUGIN_DIR"
mvn -q clean package

JAR_PATH="$PLUGIN_DIR/target/drift-mc-plugin-1.0-SNAPSHOT.jar"
echo "✔ Build ok: $JAR_PATH"

if [ -d "$SERVER_DIR/plugins" ]; then
  echo "[14] inject jar to server/plugins"
  cp "$JAR_PATH" "$SERVER_DIR/plugins/"
  echo "✔ injected to $SERVER_DIR/plugins/"
else
  echo "⚠ server/plugins not found, skip inject."
fi

echo "=== DONE ==="
echo "Next:"
echo "1) cd $SERVER_DIR"
echo "2) ./start.sh"
echo "3) in game: /level level_1  /heart  /saytoai hello"
