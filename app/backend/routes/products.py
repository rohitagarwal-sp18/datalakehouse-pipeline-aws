import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db, SessionLocal
from ..models import Product, PageView, User

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")


def _log_page_view(path: str, session_id: str, user_id: Optional[int], referrer: Optional[str]) -> None:
    db = SessionLocal()
    try:
        db.add(PageView(
            path=path,
            session_id=session_id,
            user_id=user_id,
            referrer=referrer,
        ))
        db.commit()
    finally:
        db.close()


def _cart_count(request: Request) -> int:
    try:
        return sum(i.get("quantity", 0) for i in json.loads(request.cookies.get("cart", "[]")))
    except Exception:
        return 0


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    query = db.query(Product)
    if category:
        query = query.filter(Product.category == category)
    products = query.order_by(Product.category, Product.name).all()

    categories = db.query(Product.category).distinct().order_by(Product.category).all()
    categories = [c[0] for c in categories]

    session_id = request.cookies.get("session_id", str(uuid.uuid4()))
    _log_page_view(
        path=request.url.path + (f"?category={category}" if category else ""),
        session_id=session_id,
        user_id=current_user.id if current_user else None,
        referrer=request.headers.get("referer"),
    )

    return templates.TemplateResponse("index.html", {
        "request": request,
        "products": products,
        "categories": categories,
        "active_category": category,
        "current_user": current_user,
        "cart_count": _cart_count(request),
    })


@router.get("/products/{product_id}", response_class=HTMLResponse)
def product_detail(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    product = db.get(Product, product_id)
    if not product:
        return HTMLResponse("Product not found", status_code=404)

    related = (
        db.query(Product)
        .filter(Product.category == product.category, Product.id != product.id)
        .limit(4)
        .all()
    )

    session_id = request.cookies.get("session_id", str(uuid.uuid4()))
    _log_page_view(
        path=f"/products/{product_id}",
        session_id=session_id,
        user_id=current_user.id if current_user else None,
        referrer=request.headers.get("referer"),
    )

    return templates.TemplateResponse("product.html", {
        "request": request,
        "product": product,
        "related": related,
        "current_user": current_user,
        "cart_count": _cart_count(request),
    })
