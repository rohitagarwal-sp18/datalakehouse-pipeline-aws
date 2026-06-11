from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..auth import hash_password, verify_password, create_access_token, get_current_user
from ..database import get_db
from ..models import User

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = "", next: str = "/"):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error,
        "next": next,
    })


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form(default="/"),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == email.lower().strip()).first()
    if not user or not verify_password(password, user.password_hash):
        return RedirectResponse(
            url=f"/login?error=Invalid+email+or+password&next={next}",
            status_code=303,
        )
    token = create_access_token(user.id)
    response = RedirectResponse(url=next or "/", status_code=303)
    response.set_cookie(
        "access_token", token,
        httponly=True, max_age=86400, samesite="lax",
    )
    return response


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, error: str = ""):
    return templates.TemplateResponse("register.html", {
        "request": request,
        "error": error,
    })


@router.post("/register")
def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if len(password) < 8:
        return RedirectResponse(
            url="/register?error=Password+must+be+at+least+8+characters",
            status_code=303,
        )
    user = User(
        name=name.strip(),
        email=email.lower().strip(),
        password_hash=hash_password(password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return RedirectResponse(
            url="/register?error=Email+already+registered",
            status_code=303,
        )
    token = create_access_token(user.id)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        "access_token", token,
        httponly=True, max_age=86400, samesite="lax",
    )
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("access_token")
    return response
