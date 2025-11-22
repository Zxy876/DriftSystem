# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.tree_api import router as tree_router
from app.api.dsl_api import router as dsl_router
from app.api.hint_api import router as hint_router
from app.api.world_api import router as world_router

# 引入 StoryEngine
from app.core.story.manager import story_engine

print(">>> DriftSystem Routers Loaded: TREE + DSL + HINT + WORLD + STORY")
print(">>> StoryEngine initialized. Starting node:", story_engine.current_node_id)

app = FastAPI(title="DriftSystem 0-1 With Story Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tree_router, prefix="/tree", tags=["Tree"])
app.include_router(dsl_router, prefix="/dsl", tags=["DSL"])
app.include_router(hint_router, prefix="/hint", tags=["Hint"])
app.include_router(world_router, prefix="/world", tags=["World"])

@app.get("/")
def home():
    return {
        "status": "running",
        "message": "Drift backend alive",
        "story_state": story_engine.current_node_id,
        "routes": ["/tree", "/dsl", "/hint", "/world", "/story"]
    }
