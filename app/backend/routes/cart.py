import json
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Product, User

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")


def _read_cart(request: Request) -> list[dict]:
    try:
        return json.loads(request.cookies.get("cart", "[]"))
    except Exception:
        return []


def _cart_count(request: Request) -> int:
    try:
        return sum(i.get("quantity", 0) for i in json.loads(request.cookies.get("cart", "[]")))
    except Exception:
        return 0


@router.get("/cart", response_class=HTMLResponse)
def cart_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    cart_raw = _read_cart(request)
    cart_items = []
    total = 0

    for item in cart_raw:
        product = db.get(Product, item["product_id"])
        if product:
            subtotal = float(product.price) * item["quantity"]
            cart_items.append({
                "product": product,
                "quantity": item["quantity"],
                "subtotal": round(subtotal, 2),
            })
            total += subtotal

    return templates.TemplateResponse("cart.html", {
        "request": request,
        "cart_items": cart_items,
        "total": round(total, 2),
        "cart_count": sum(i["quantity"] for i in cart_raw),
        "current_user": current_user,
    })


@router.post("/cart/add")
def add_to_cart(
    request: Request,
    product_id: int = Form(...),
    quantity: int = Form(default=1),
):
    cart = _read_cart(request)
    for item in cart:
        if item["product_id"] == product_id:
            item["quantity"] += quantity
            break
    else:
        cart.append({"product_id": product_id, "quantity": quantity})

    response = RedirectResponse(url="/cart", status_code=303)
    response.set_cookie("cart", json.dumps(cart), max_age=604800, samesite="lax")
    return response


@router.post("/cart/remove")
def remove_from_cart(
    request: Request,
    product_id: int = Form(...),
):
    cart = _read_cart(request)
    cart = [item for item in cart if item["product_id"] != product_id]

    response = RedirectResponse(url="/cart", status_code=303)
    response.set_cookie("cart", json.dumps(cart), max_age=604800, samesite="lax")
    return response


@router.post("/cart/update")
def update_cart(
    request: Request,
    product_id: int = Form(...),
    quantity: int = Form(...),
):
    cart = _read_cart(request)
    if quantity <= 0:
        cart = [item for item in cart if item["product_id"] != product_id]
    else:
        for item in cart:
            if item["product_id"] == product_id:
                item["quantity"] = quantity
                break

    response = RedirectResponse(url="/cart", status_code=303)
    response.set_cookie("cart", json.dumps(cart), max_age=604800, samesite="lax")
    return response
