from fastapi import FastAPI

from app.consolidate.router import router as list_router
from app.recipes.router import router as recipes_router

app = FastAPI(title="Bushel API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(recipes_router)
app.include_router(list_router)
