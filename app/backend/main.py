import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .database import engine, SessionLocal
from .models import Base
from .seed import seed_products
from .routes import auth, products, cart, orders


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_products(db)
    finally:
        db.close()
    yield


app = FastAPI(title="ShopPulse", version="1.0.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(orders.router)


@app.middleware("http")
async def session_middleware(request: Request, call_next) -> Response:
    response = await call_next(request)
    if not request.cookies.get("session_id"):
        response.set_cookie(
            "session_id",
            str(uuid.uuid4()),
            max_age=86400,
            httponly=False,
            samesite="lax",
        )
    return response
