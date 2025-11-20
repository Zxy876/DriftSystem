from fastapi import FastAPI

# --- 引入 API 路由 ---
from app.api.tree_api import router as tree_router
from app.api.dsl_api import router as dsl_router
from app.api.hint_api import router as hint_router
from app.api.world_api import router as world_router   # ⭐ 新增世界路由

# --- 启动信息 ---
print(">>> DriftSystem Routers Loaded: TREE + DSL + HINT + WORLD")

# --- 创建 FastAPI 实例 ---
app = FastAPI(title="DriftSystem 0-1")

# --- 注册所有路由 ---
app.include_router(tree_router, prefix="/tree", tags=["Tree"])
app.include_router(dsl_router, prefix="/dsl", tags=["DSL"])
app.include_router(hint_router, prefix="/hint", tags=["Hint"])
app.include_router(world_router, prefix="/world", tags=["World"])    # ⭐ 新增

# --- 主页测试 ---
@app.get("/")
def home():
    return {
        "status": "running",
        "message": "DriftSystem backend is alive.",
        "routes": ["/tree", "/dsl", "/hint", "/world"]
    }