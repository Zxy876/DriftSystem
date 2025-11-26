# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.tree_api import router as tree_router
from app.api.dsl_api import router as dsl_router
from app.api.hint_api import router as hint_router
from app.api.world_api import router as world_router
from app.api.story_api import router as story_router

from app.core.story.story_loader import list_levels, load_level
from app.core.story.story_engine import story_engine

from app.routers import ai_router

app = FastAPI(title="DriftSystem · Heart Levels + Story Engine")

# --------- CORS ---------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------- Routers ---------
app.include_router(tree_router,   tags=["Tree"])
app.include_router(dsl_router,    tags=["DSL"])
app.include_router(hint_router,   tags=["Hint"])
app.include_router(world_router,  tags=["World"])
app.include_router(story_router,  tags=["Story"])

# ---- NEW: AI Intent Router ----
app.include_router(ai_router.router)

print(">>> DriftSystem loaded: TREE + DSL + HINT + WORLD + STORY + AI")
print(">>> StoryEngine started at:", story_engine.start_node_id)

# --------- Simple Heart Levels endpoints ---------
@app.get("/levels")
def api_list_levels():
    return {"status":"ok", "levels": list_levels()}

@app.get("/levels/{level_id}")
def api_get_level(level_id: str):
    try:
        lv = load_level(level_id)
        return {"status":"ok", "level": lv.__dict__}
    except FileNotFoundError:
        return {"status":"error", "msg": f"Level {level_id} not found"}

@app.get("/")
def home():
    return {
        "status": "running",
        "message": "DriftSystem backend alive",
        "routes": [
            "/levels",
            "/levels/{id}",
            "/story/levels",
            "/story/level/{id}",
            "/story/load/{player_id}/{id}",
            "/story/advance/{player_id}",
            "/tree/*",
            "/dsl/*",
            "/hint/*",
            "/world/*",
            "/story/*",
            "/ai/*",
        ],
        "story_state": story_engine.get_public_state(),
    }