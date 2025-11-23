# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.tree_api import router as tree_router
from app.api.dsl_api import router as dsl_router
from app.api.hint_api import router as hint_router
from app.api.world_api import router as world_router
from app.api.story_api import router as story_router

from app.core.story.story_engine import story_engine

app = FastAPI(title="DriftSystem 0-1 With Story Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tree_router, tags=["Tree"])
app.include_router(dsl_router, tags=["DSL"])
app.include_router(hint_router, tags=["Hint"])
app.include_router(world_router, tags=["World"])
app.include_router(story_router, tags=["Story"])

print(">>> DriftSystem Routers Loaded: TREE + DSL + HINT + WORLD + STORY")
print(">>> StoryEngine initialized. Starting node:", story_engine.start_node_id)

@app.get("/")
def home():
    return {
        "status": "running",
        "message": "Drift backend alive",
        "story_state": story_engine.get_public_state(),
        "routes": ["/tree/*", "/dsl/*", "/hint/*", "/world/*", "/story/*"]
    }