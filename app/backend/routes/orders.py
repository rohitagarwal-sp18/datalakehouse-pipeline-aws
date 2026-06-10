import json
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Order, OrderItem, Payment, Product, User

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")

TAX_RATE = Decimal("0.10")


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


@router.get("/checkout", response_class=HTMLResponse)
def checkout_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse(url="/login?next=/checkout", status_code=302)

    cart_raw = _read_cart(request)
    if not cart_raw:
        return RedirectResponse(url="/cart", status_code=302)

    cart_items = []
    subtotal = Decimal("0.00")
    for item in cart_raw:
        product = db.get(Product, item["product_id"])
        if product:
            line_total = product.price * item["quantity"]
            cart_items.append({"product": product, "quantity": item["quantity"], "subtotal": line_total})
            subtotal += line_total

    tax = (subtotal * TAX_RATE).quantize(Decimal("0.01"))
    total = subtotal + tax

    return templates.TemplateResponse("checkout.html", {
        "request": request,
        "cart_items": cart_items,
        "subtotal": subtotal,
        "tax": tax,
        "total": total,
        "current_user": current_user,
        "cart_count": _cart_count(request),
    })


@router.post("/checkout")
def process_checkout(
    request: Request,
    shipping_address: str = Form(...),
    payment_method: str = Form(...),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse(url="/login?next=/checkout", status_code=302)

    cart_raw = _read_cart(request)
    if not cart_raw:
        return RedirectResponse(url="/cart", status_code=302)

    # Resolve products and calculate totals
    items_data = []
    subtotal = Decimal("0.00")
    for item in cart_raw:
        product = db.get(Product, item["product_id"])
        if product and product.stock_qty >= item["quantity"]:
            subtotal += product.price * item["quantity"]
            items_data.append((product, item["quantity"]))

    if not items_data:
        return RedirectResponse(url="/cart?error=1", status_code=302)

    tax = (subtotal * TAX_RATE).quantize(Decimal("0.01"))
    total = subtotal + tax

    # Create order
    order = Order(
        user_id=current_user.id,
        status="confirmed",
        subtotal=subtotal,
        tax=tax,
        total=total,
        shipping_address=shipping_address,
    )
    db.add(order)
    db.flush()

    # Create order items + decrement stock
    for product, quantity in items_data:
        db.add(OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=quantity,
            unit_price=product.price,
        ))
        product.stock_qty -= quantity

    # Simulate payment (always succeeds in dev)
    db.add(Payment(
        order_id=order.id,
        amount=total,
        method=payment_method,
        status="completed",
        transaction_ref=str(uuid.uuid4()),
    ))

    db.commit()

    response = RedirectResponse(url=f"/orders/{order.id}?success=1", status_code=303)
    response.delete_cookie("cart")
    return response


@router.get("/orders", response_class=HTMLResponse)
def orders_list(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse(url="/login?next=/orders", status_code=302)

    orders = (
        db.query(Order)
        .filter(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
        .all()
    )

    return templates.TemplateResponse("orders.html", {
        "request": request,
        "orders": orders,
        "current_user": current_user,
        "cart_count": _cart_count(request),
    })


@router.get("/orders/{order_id}", response_class=HTMLResponse)
def order_detail(
    order_id: int,
    request: Request,
    success: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    if not current_user:
        return RedirectResponse(url=f"/login?next=/orders/{order_id}", status_code=302)

    order = db.get(Order, order_id)
    if not order or order.user_id != current_user.id:
        return HTMLResponse("Order not found", status_code=404)

    return templates.TemplateResponse("order_detail.html", {
        "request": request,
        "order": order,
        "success": success == "1",
        "current_user": current_user,
        "cart_count": _cart_count(request),
    })
