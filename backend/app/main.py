from fastapi import FastAPI

app = FastAPI(title="Bushel API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
