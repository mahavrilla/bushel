from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.consolidate.router import router as list_router
from app.kroger.router import router as kroger_router
from app.matching.router import router as matching_router
from app.pantry.router import router as pantry_router
from app.recipes.router import router as recipes_router
from app.ingredients.router import router as ingredients_router
from app.staples.router import router as staples_router

app = FastAPI(title="Bushel API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(recipes_router)
app.include_router(list_router)
app.include_router(kroger_router)
app.include_router(matching_router)
app.include_router(pantry_router)
app.include_router(ingredients_router)
app.include_router(staples_router)
