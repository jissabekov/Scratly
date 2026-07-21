from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .routes.public import router as public_router
from .routes.admin import router as admin_router
app = FastAPI(title='Scratly API', version='0.1.0')
@app.get('/health', tags=['system'])
async def health(): return {'status':'ok'}


@app.get('/health/ready', tags=['system'])
async def readiness(db: AsyncSession = Depends(get_db)):
    await db.execute(text('SELECT 1'))
    return {'status': 'ready', 'database': 'reachable'}


app.include_router(public_router, prefix='/v1')
app.include_router(admin_router, prefix='/v1/admin')
