from fastapi import FastAPI

app = FastAPI(title="Change Quality Agent")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
