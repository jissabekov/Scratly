from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .routes.admin import router as admin_router
from .routes.learning import router as learning_router
from .routes.learning_checkins import router as learning_checkins_router
from .routes.learning_quiz import router as learning_quiz_router
from .routes.public import router as public_router

app = FastAPI(title="Scratly API", version="0.1.0")

# Local teacher console (Next.js) calls the API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}


@app.get("/health/ready", tags=["system"])
async def readiness(db: AsyncSession = Depends(get_db)):
    await db.execute(text("SELECT 1"))
    return {"status": "ready", "database": "reachable"}


app.include_router(public_router, prefix="/v1")
app.include_router(learning_router, prefix="/v1")
app.include_router(learning_quiz_router, prefix="/v1")
app.include_router(learning_checkins_router, prefix="/v1")
app.include_router(admin_router, prefix="/v1/admin")
