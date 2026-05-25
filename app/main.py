from fastapi import FastAPI

from app.api.v1 import sop

app = FastAPI(title="Change Quality Agent")
app.include_router(sop.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
