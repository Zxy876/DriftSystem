
#!/bin/bash

BASE="http://127.0.0.1:8000/world/apply"
PID="zxy"

echo "=== 1. 第一步移动（x=1） ==="
curl -s -X POST $BASE \
-H "Content-Type: application/json" \
-d "{\"player_id\":\"$PID\",\"action\":{\"move\":{\"x\":1,\"y\":60,\"z\":1,\"speed\":0.4,\"moving\":true}}}"
echo -e "\n"
sleep 4

echo "=== 2. 第二步移动（x=2） ==="
curl -s -X POST $BASE \
-H "Content-Type: application/json" \
-d "{\"player_id\":\"$PID\",\"action\":{\"move\":{\"x\":2,\"y\":60,\"z\":1,\"speed\":0.3,\"moving\":true}}}"
echo -e "\n"
sleep 4

echo "=== 3. 第三步移动（x=3） ==="
curl -s -X POST $BASE \
-H "Content-Type: application/json" \
-d "{\"player_id\":\"$PID\",\"action\":{\"move\":{\"x\":3,\"y\":60,\"z\":1,\"speed\":0.3,\"moving\":true}}}"
echo -e "\n"
sleep 4

echo "=== 4. 停下观察（moving=false） ==="
curl -s -X POST $BASE \
-H "Content-Type: application/json" \
-d "{\"player_id\":\"$PID\",\"action\":{\"move\":{\"x\":3,\"y\":60,\"z\":1,\"speed\":0.0,\"moving\":false}}}"
echo -e "\n"
sleep 4

echo "=== 5. 查看故事上下文 ==="
curl -s "http://127.0.0.1:8000/story/state?player_id=$PID"
echo -e "\n"

echo "=== 测试结束 ==="
