from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import UUID

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from backend.app.db import get_db, init_db, SessionLocal
from backend.app.domain.models import Money, Product, User
from backend.app.persistence.models import ProductORM, UserORM
from backend.app.repositories.sqlalchemy_order_repo import SqlAlchemyOrderRepository
from backend.app.repositories.sqlalchemy_product_repo import SqlAlchemyProductRepository
from backend.app.repositories.sqlalchemy_user_repo import SqlAlchemyUserRepository
from backend.app.services.auth_service import AuthService
from backend.app.services.cart_service import CartService
from backend.app.services.order_service import OrderService
from backend.app.services.product_service import ProductService
from backend.app.services.admin_product_service import AdminProductService
from backend.app.repositories.sqlalchemy_product_repo import SqlAlchemyProductRepository
from backend.app.domain.orders import OrderStatus
from fastapi import Query
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from backend.app.repositories.sqlalchemy_address_repo import SqlAlchemyAddressRepository
from backend.app.services.address_service import AddressService
from backend.app.repositories.sqlalchemy_review_repo import SqlAlchemyReviewRepository
from backend.app.services.review_service import ReviewService
from pydantic import BaseModel, Field
from backend.app.repositories.sqlalchemy_payment_repo import SqlAlchemyPaymentRepository
from backend.app.services.payment_service import PaymentService
from backend.app.services.receipt_service import ReceiptService
from backend.app.domain.payment import PaymentStatus
import os
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import HTMLResponse
from starlette.requests import Request
from fastapi.staticfiles import StaticFiles
from pathlib import Path


app = FastAPI(title="MiniShop", version="...")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web" / "static")), name="static")


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return HTMLResponse(
        "<h1>404 - Page Not Found</h1><p>The page you requested does not exist.</p>",
        status_code=404,
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    return HTMLResponse(
        "<h1>500 - Internal Server Error</h1><p>Something went wrong.</p>",
        status_code=500,
    )


origins = os.environ.get("MINISHOP_CORS_ORIGINS", "")
origin_list = [o.strip() for o in origins.split(",") if o.strip()]

if origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# --- Sessions ---
from backend.app.config import settings
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

class ReviewCreateIn(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    title: str = Field(default="", max_length=120)
    body: str = Field(default="", max_length=2000)

def api_data(data, *, status_code: int = 200, meta: dict | None = None) -> JSONResponse:
    payload = {"data": data}
    if meta:
        payload["meta"] = meta
    return JSONResponse(payload, status_code=status_code)


def api_list(items: list, *, total: int, limit: int, offset: int, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        {"items": items, "meta": {"total": total, "limit": limit, "offset": offset}},
        status_code=status_code,
    )


def api_error(message: str, *, code: str = "error", status_code: int = 400, details=None) -> JSONResponse:
    err = {"code": code, "message": message}
    if details is not None:
        err["details"] = details
    return JSONResponse({"error": err}, status_code=status_code)


def paginate(items: list, *, limit: int, offset: int) -> tuple[list, int]:
    total = len(items)
    if offset >= total:
        return [], total
    return items[offset: offset + limit], total

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

SECRET_KEY = os.environ.get("MINISHOP_SECRET_KEY", "dev-secret-change-me")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)


# ---------- Startup: create tables + seed sample products ----------
@app.on_event("startup")
def startup() -> None:
    init_db()

    db = SessionLocal()
    try:
        count = db.scalar(select(func.count()).select_from(ProductORM))
        if (count or 0) == 0:
            repo = SqlAlchemyProductRepository(db)
            repo.add(
                Product.create(
                    sku="BK-1001",
                    name="Python OOP Book",
                    description="Learn OOP patterns with practical examples.",
                    price=Money.from_dollars(29.99),
                    quantity_available=12,
                )
            )
            repo.add(
                Product.create(
                    sku="EL-2002",
                    name="Wireless Mouse",
                    description="Ergonomic mouse with 2.4GHz receiver.",
                    price=Money.from_dollars(19.50),
                    quantity_available=35,
                )
            )
            db.commit()
    finally:
        db.close()


# ---------- Flash helpers ----------
def flash_error(request: Request, message: str) -> None:
    request.session["flash_error"] = message


def pop_flash_error(request: Request) -> str | None:
    return request.session.pop("flash_error", None)

def require_admin(request: Request, db: Session, next_url: str = "/admin/products"):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login(next_url)

    if not user.is_admin:
        flash_error(request, "Admin access required.")
        return RedirectResponse(url="/", status_code=303)

    return user

# ---------- Builders (repos/services per request) ----------
def build_services(db: Session):
    product_repo = SqlAlchemyProductRepository(db)
    user_repo = SqlAlchemyUserRepository(db)
    order_repo = SqlAlchemyOrderRepository(db)

    product_service = ProductService(product_repo)
    auth_service = AuthService(user_repo)
    cart_service = CartService(product_repo)
    order_service = OrderService(order_repo, product_repo)

    return product_service, auth_service, cart_service, order_service, user_repo

def build_services_cached(request: Request, db: Session):
    # Cache services on the request so repeated calls in the same request reuse it
    if not hasattr(request.state, "services"):
        request.state.services = build_services(db)
    return request.state.services

def build_address_services(db: Session):
    repo = SqlAlchemyAddressRepository(db)
    svc = AddressService(repo)
    return svc, repo


def build_address_services_cached(request: Request, db: Session):
    if not hasattr(request.state, "address_services"):
        request.state.address_services = build_address_services(db)
    return request.state.address_services

def build_review_services_cached(request: Request, db: Session) -> ReviewService:
    if not hasattr(request.state, "review_service"):
        review_repo = SqlAlchemyReviewRepository(db)
        order_repo = SqlAlchemyOrderRepository(db)
        # reuse the same user_repo used by auth
        _, _, _, _, user_repo = build_services_cached(request, db)
        request.state.review_service = ReviewService(review_repo, order_repo, user_repo)
    return request.state.review_service

def build_payment_services(db: Session):
    repo = SqlAlchemyPaymentRepository(db)
    svc = PaymentService(repo)
    receipt = ReceiptService(base_dir=Path(__file__).resolve().parents[2])  # .../shop
    return svc, repo, receipt


def build_payment_services_cached(request: Request, db: Session):
    if not hasattr(request.state, "payment_services"):
        request.state.payment_services = build_payment_services(db)
    return request.state.payment_services

def get_services(request: Request, db: Session):
    core = build_services_cached(request, db)
    address = build_address_services_cached(request, db)
    payment = build_payment_services_cached(request, db)

    return {
        "core": core,
        "address": address,
        "payment": payment,
    }

def get_current_user(request: Request, db: Session) -> User | None:
    _, _, _, _, user_repo = build_services_cached(request, db)
    uid = request.session.get("user_id")
    if not uid:
        return None
    try:
        return user_repo.get_by_id(UUID(str(uid)))
    except Exception:
        return None


def template_context(request: Request, db: Session, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    user = get_current_user(request, db)
    _, _, cart_service, _, _ = build_services_cached(request, db)

    ctx = {
        "request": request,
        "user": user.to_public_dict() if user else None,
        "cart_count": cart_service.count_items(request.session),
        "flash_error": pop_flash_error(request),
        "q": request.query_params.get("q", ""),
    }
    if extra:
        ctx.update(extra)
    return ctx


def redirect_to_login(next_url: str) -> RedirectResponse:
    return RedirectResponse(url=f"/login?next={quote(next_url)}", status_code=303)

def format_shipping_address(
    *,
    line1: str,
    line2: str,
    city: str,
    state: str,
    postal_code: str,
    country: str,
    phone: str,
) -> str:
    line1 = (line1 or "").strip()
    line2 = (line2 or "").strip()
    city = (city or "").strip()
    state = (state or "").strip()
    postal_code = (postal_code or "").strip()
    country = (country or "").strip()
    phone = (phone or "").strip()

    lines = [line1]
    if line2:
        lines.append(line2)

    city_state_zip = " ".join([state, postal_code]).strip()
    if city and city_state_zip:
        lines.append(f"{city}, {city_state_zip}")
    elif city:
        lines.append(city)
    elif city_state_zip:
        lines.append(city_state_zip)

    if country:
        lines.append(country)

    if phone:
        lines.append(f"Phone: {phone}")

    return "\n".join([x for x in lines if x.strip()])

# ---------- APIs ----------
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}

@app.get("/api/version")
def version():
    return {"app": settings.app_name, "version": settings.version}


@app.get("/api/products")
def api_products(
    request: Request,
    q: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> JSONResponse:
    product_service, _, _, _, _ = build_services_cached(request, db)

    products = [p.to_dict() for p in product_service.list_products(q=q)]
    page, total = paginate(products, limit=limit, offset=offset)

    return api_list(page, total=total, limit=limit, offset=offset)


@app.get("/api/products/{product_id}")
def api_product(product_id: str, request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    product_service, _, _, _, _ = build_services_cached(request, db)
    try:
        pid = UUID(product_id)
        p = product_service.get_product(pid).to_dict()
        return api_data(p)
    except Exception:
        raise HTTPException(status_code=404, detail="Product not found")

@app.exception_handler(StarletteHTTPException)
async def api_http_exception_handler(request: Request, exc: StarletteHTTPException):
    # Only wrap /api errors. Keep normal behavior for HTML pages.
    if request.url.path.startswith("/api"):
        return api_error(
            str(exc.detail),
            code=f"http_{exc.status_code}",
            status_code=exc.status_code,
        )
    return await http_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def api_validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.url.path.startswith("/api"):
        return api_error(
            "Validation error",
            code="validation_error",
            status_code=422,
            details=exc.errors(),
        )
    return await request_validation_exception_handler(request, exc)


@app.get("/api/me")
def api_me(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    user = get_current_user(request, db)
    return api_data(user.to_public_dict() if user else None)


@app.get("/api/orders")
def api_orders(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> JSONResponse:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in")

    _, _, _, order_service, _ = build_services_cached(request, db)
    orders = [o.to_dict() for o in order_service.list_orders_for_user(user.id)]

    page, total = paginate(orders, limit=limit, offset=offset)
    return api_list(page, total=total, limit=limit, offset=offset)

@app.get("/api/products/{product_id}/reviews")
def api_product_reviews(
    request: Request,
    product_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> JSONResponse:
    review_service = build_review_services_cached(request, db)

    try:
        pid = UUID(product_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Product not found")

    review_count, avg_rating = review_service.get_stats(product_id=pid)
    items = review_service.list_reviews(product_id=pid, limit=limit, offset=offset)

    return JSONResponse(
        {
            "items": items,
            "meta": {
                "total": review_count,
                "limit": limit,
                "offset": offset,
                "avg_rating": avg_rating,
                "review_count": review_count,
            },
        }
    )


@app.post("/api/products/{product_id}/reviews")
def api_create_review(
    request: Request,
    product_id: str,
    payload: ReviewCreateIn,
    db: Session = Depends(get_db),
) -> JSONResponse:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in")

    product_service, _, _, _, _ = build_services_cached(request, db)
    review_service = build_review_services_cached(request, db)

    try:
        pid = UUID(product_id)
        product_service.get_product(pid)
        review = review_service.create_or_update_review(
            user=user,
            product_id=pid,
            rating=payload.rating,
            title=payload.title,
            body=payload.body,
        )
        db.commit()
        return JSONResponse({"data": review.to_dict()}, status_code=201)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.rollback()
        raise

# ---------- Pages ----------
@app.get("/", response_class=HTMLResponse)
def home(request: Request, q: str | None = None, db: Session = Depends(get_db)) -> HTMLResponse:
    product_service, _, _, _, _ = build_services(db)
    products = [p.to_dict() for p in product_service.list_products(q=q)]
    return templates.TemplateResponse(
        "index.html",
        template_context(request, db, {"products": products, "title": "MiniShop"}),
    )


@app.get("/product/{product_id}", response_class=HTMLResponse, response_model=None)
def product_detail_page(request: Request, product_id: str, db: Session = Depends(get_db)):
    product_service, _, _, _, _ = build_services_cached(request, db)
    review_service = build_review_services_cached(request, db)

    try:
        pid = UUID(product_id)
        product = product_service.get_product(pid).to_dict()
    except Exception:
        raise HTTPException(status_code=404, detail="Product not found")

    user = get_current_user(request, db)

    review_count, avg_rating = review_service.get_stats(product_id=pid)
    reviews = review_service.list_reviews(product_id=pid, limit=20, offset=0)

    my_review = None
    can_review = False
    if user:
        existing = review_service.get_user_review(user_id=user.id, product_id=pid)
        if existing:
            my_review = existing.to_dict()
            can_review = True
        else:
            can_review = review_service.user_can_review(user_id=user.id, product_id=pid)

    return templates.TemplateResponse(
        "product_detail.html",
        template_context(
            request,
            db,
            {
                "product": product,
                "avg_rating": avg_rating or 0.0,
                "review_count": review_count,
                "reviews": reviews,
                "my_review": my_review,
                "can_review": can_review,
                "title": product["name"],
            },
        ),
    )

@app.post("/product/{product_id}/review", response_model=None)
def submit_review(
    request: Request,
    product_id: str,
    rating: int = Form(...),
    title: str = Form(""),
    body: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login(f"/product/{product_id}")

    product_service, _, _, _, _ = build_services_cached(request, db)
    review_service = build_review_services_cached(request, db)

    try:
        pid = UUID(product_id)
        # ensure product exists
        product_service.get_product(pid)

        review_service.create_or_update_review(
            user=user,
            product_id=pid,
            rating=int(rating),
            title=title,
            body=body,
        )
        db.commit()
    except ValueError as e:
        db.rollback()
        flash_error(request, str(e))
    except Exception:
        db.rollback()
        flash_error(request, "Could not submit review.")

    return RedirectResponse(url=f"/product/{product_id}", status_code=303)

@app.get("/api/orders/{order_id}")
def api_order_detail(
    order_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in")

    _, _, _, order_service, _ = build_services_cached(request, db)

    try:
        oid = UUID(order_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Order not found")

    order = order_service.get_order_for_user(user_id=user.id, order_id=oid)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return api_data(order.to_dict())


# ---------- Auth ----------
@app.get("/register", response_class=HTMLResponse)
def register_form(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse("register.html", template_context(request, db, {"error": None, "title": "Register"}))


@app.post("/register", response_model=None)
def register(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    _, auth_service, _, _, _ = build_services(db)
    try:
        user_count = db.scalar(select(func.count()).select_from(UserORM)) or 0
        is_admin = (user_count == 0)
        user = auth_service.register(email=email, full_name=full_name, password=password, is_admin=is_admin)
        db.commit()
        request.session["user_id"] = str(user.id)
        return RedirectResponse(url="/", status_code=303)
    except ValueError as e:
        db.rollback()
        return templates.TemplateResponse(
            "register.html",
            template_context(request, db, {"error": str(e), "title": "Register"}),
            status_code=400,
        )
    except Exception:
        db.rollback()
        #  show a generic error
        return templates.TemplateResponse(
            "register.html",
            template_context(request, db, {"error": "Registration failed.", "title": "Register"}),
            status_code=500,
        )


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, next: str = "/", db: Session = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse("login.html", template_context(request, db, {"error": None, "next": next, "title": "Login"}))


@app.post("/login", response_model=None)
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    db: Session = Depends(get_db),
):
    _, auth_service, _, _, _ = build_services(db)
    user = auth_service.authenticate(email=email, password=password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            template_context(request, db, {"error": "Invalid email or password", "next": next, "title": "Login"}),
            status_code=400,
        )
    request.session["user_id"] = str(user.id)
    return RedirectResponse(url=next or "/", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


#----------admin----------

@app.get("/admin", response_model=None)
def admin_root(request: Request, db: Session = Depends(get_db)):
    gate = require_admin(request, db, "/admin/products")
    if not isinstance(gate, User):
        return gate
    return RedirectResponse(url="/admin/products", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
def admin_home(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)

    if not user or not user.is_admin:
        return redirect_to_login("/admin")

    return HTMLResponse("""
        <h1>Admin Dashboard</h1>
        <ul>
            <li><a href="/admin/products">Manage Products</a></li>
            <li><a href="/admin/orders">Manage Orders</a></li>
        </ul>
    """)

@app.get("/admin/products", response_class=HTMLResponse, response_model=None)
def admin_products_page(request: Request, db: Session = Depends(get_db)):
    gate = require_admin(request, db, "/admin/products")
    if not isinstance(gate, User):
        return gate

    product_repo = SqlAlchemyProductRepository(db)
    products = [p.to_dict() for p in product_repo.list_all()]

    return templates.TemplateResponse(
        "admin_products.html",
        template_context(request, db, {"products": products, "title": "Admin — Products"}),
    )


@app.get("/admin/products/new", response_class=HTMLResponse, response_model=None)
def admin_new_product_form(request: Request, db: Session = Depends(get_db)):
    gate = require_admin(request, db, "/admin/products/new")
    if not isinstance(gate, User):
        return gate

    empty = {
        "sku": "",
        "name": "",
        "description": "",
        "price": {"cents": 0, "display": "USD 0.00"},
        "quantity_available": 0,
        "is_active": True,
        "id": "",
    }

    return templates.TemplateResponse(
        "admin_product_form.html",
        template_context(
            request,
            db,
            {
                "title": "Admin — New Product",
                "action": "/admin/products/new",
                "product": empty,
                "price_value": "0.00",
                "error": None,
            },
        ),
    )


@app.post("/admin/products/new", response_model=None)
def admin_create_product(
    request: Request,
    sku: str = Form(...),
    name: str = Form(...),
    description: str = Form(...),
    price: str = Form(...),
    quantity_available: int = Form(...),
    is_active: str | None = Form(None),
    db: Session = Depends(get_db),
):
    gate = require_admin(request, db, "/admin/products/new")
    if not isinstance(gate, User):
        return gate

    product_repo = SqlAlchemyProductRepository(db)
    admin_service = AdminProductService(product_repo)

    try:
        admin_service.create_product(
            sku=sku,
            name=name,
            description=description,
            price_str=price,
            quantity_available=quantity_available,
            is_active=bool(is_active),
        )
        db.commit()
        return RedirectResponse(url="/admin/products", status_code=303)
    except ValueError as e:
        db.rollback()
        filled = {
            "sku": sku,
            "name": name,
            "description": description,
            "price": {"cents": 0, "display": "USD"},
            "quantity_available": quantity_available,
            "is_active": bool(is_active),
            "id": "",
        }
        return templates.TemplateResponse(
            "admin_product_form.html",
            template_context(
                request,
                db,
                {
                    "title": "Admin — New Product",
                    "action": "/admin/products/new",
                    "product": filled,
                    "price_value": price,
                    "error": str(e),
                },
            ),
            status_code=400,
        )


@app.get("/admin/products/{product_id}/edit", response_class=HTMLResponse, response_model=None)
def admin_edit_product_form(request: Request, product_id: str, db: Session = Depends(get_db)):
    gate = require_admin(request, db, f"/admin/products/{product_id}/edit")
    if not isinstance(gate, User):
        return gate

    product_repo = SqlAlchemyProductRepository(db)
    try:
        pid = UUID(product_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Product not found")

    product = product_repo.get_by_id(pid)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    p = product.to_dict()
    price_value = f"{p['price']['cents'] / 100:.2f}"

    return templates.TemplateResponse(
        "admin_product_form.html",
        template_context(
            request,
            db,
            {
                "title": "Admin — Edit Product",
                "action": f"/admin/products/{product_id}/edit",
                "product": p,
                "price_value": price_value,
                "error": None,
            },
        ),
    )


@app.post("/admin/products/{product_id}/edit", response_model=None)
def admin_edit_product(
    request: Request,
    product_id: str,
    sku: str = Form(...),
    name: str = Form(...),
    description: str = Form(...),
    price: str = Form(...),
    quantity_available: int = Form(...),
    is_active: str | None = Form(None),
    db: Session = Depends(get_db),
):
    gate = require_admin(request, db, f"/admin/products/{product_id}/edit")
    if not isinstance(gate, User):
        return gate

    product_repo = SqlAlchemyProductRepository(db)
    admin_service = AdminProductService(product_repo)

    try:
        pid = UUID(product_id)
        admin_service.update_product(
            product_id=pid,
            sku=sku,
            name=name,
            description=description,
            price_str=price,
            quantity_available=quantity_available,
            is_active=bool(is_active),
        )
        db.commit()
        return RedirectResponse(url="/admin/products", status_code=303)
    except ValueError as e:
        db.rollback()
        filled = {
            "id": product_id,
            "sku": sku,
            "name": name,
            "description": description,
            "price": {"cents": 0, "display": "USD"},
            "quantity_available": quantity_available,
            "is_active": bool(is_active),
        }
        return templates.TemplateResponse(
            "admin_product_form.html",
            template_context(
                request,
                db,
                {
                    "title": "Admin — Edit Product",
                    "action": f"/admin/products/{product_id}/edit",
                    "product": filled,
                    "price_value": price,
                    "error": str(e),
                },
            ),
            status_code=400,
        )


@app.post("/admin/products/{product_id}/toggle", response_model=None)
def admin_toggle_product(request: Request, product_id: str, db: Session = Depends(get_db)):
    gate = require_admin(request, db, "/admin/products")
    if not isinstance(gate, User):
        return gate

    product_repo = SqlAlchemyProductRepository(db)
    admin_service = AdminProductService(product_repo)

    try:
        pid = UUID(product_id)
        admin_service.toggle_active(product_id=pid)
        db.commit()
    except Exception as e:
        db.rollback()
        flash_error(request, f"Could not toggle product: {e}")

    return RedirectResponse(url="/admin/products", status_code=303)


@app.post("/admin/products/{product_id}/stock", response_model=None)
def admin_update_stock(
    request: Request,
    product_id: str,
    quantity_available: int = Form(...),
    db: Session = Depends(get_db),
):
    gate = require_admin(request, db, "/admin/products")
    if not isinstance(gate, User):
        return gate

    product_repo = SqlAlchemyProductRepository(db)
    admin_service = AdminProductService(product_repo)

    try:
        pid = UUID(product_id)
        admin_service.set_stock(product_id=pid, quantity_available=quantity_available)
        db.commit()
    except ValueError as e:
        db.rollback()
        flash_error(request, str(e))
    except Exception:
        db.rollback()
        flash_error(request, "Could not update stock.")

    return RedirectResponse(url="/admin/products", status_code=303)


@app.get("/admin/orders", response_class=HTMLResponse, response_model=None)
def admin_orders_page(request: Request, db: Session = Depends(get_db)):
    gate = require_admin(request, db, "/admin/orders")
    if not isinstance(gate, User):
        return gate

    _, _, _, order_service, user_repo = build_services(db)
    orders = order_service.list_all_orders()

    view = []
    for o in orders:
        d = o.to_dict()
        u = user_repo.get_by_id(o.user_id)
        d["user_email"] = u.email if u else str(o.user_id)
        view.append(d)

    return templates.TemplateResponse(
        "admin_orders.html",
        template_context(request, db, {"orders": view, "title": "Admin — Orders"}),
    )

@app.get("/admin/orders/{order_id}", response_class=HTMLResponse, response_model=None)
def admin_order_detail_page(request: Request, order_id: str, db: Session = Depends(get_db)):
    gate = require_admin(request, db, f"/admin/orders/{order_id}")
    if not isinstance(gate, User):
        return gate

    _, _, _, order_service, user_repo = build_services(db)

    try:
        oid = UUID(order_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Order not found")

    order = order_service.get_order(oid)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    d = order.to_dict()
    u = user_repo.get_by_id(order.user_id)
    d["user_email"] = u.email if u else str(order.user_id)

    return templates.TemplateResponse(
        "admin_order_detail.html",
        template_context(
            request,
            db,
            {
                "order": d,
                "status_options": OrderStatus.ALL,
                "error": None,
                "title": "Admin — Order",
            },
        ),
    )

@app.post("/admin/orders/{order_id}/status", response_model=None)
def admin_order_update_status(
    request: Request,
    order_id: str,
    new_status: str = Form(...),
    db: Session = Depends(get_db),
):
    gate = require_admin(request, db, f"/admin/orders/{order_id}")
    if not isinstance(gate, User):
        return gate

    _, _, _, order_service, _ = build_services(db)

    try:
        oid = UUID(order_id)
        order_service.update_status_admin(order_id=oid, new_status=new_status)
        db.commit()
    except ValueError as e:
        db.rollback()
        flash_error(request, str(e))
    except Exception:
        db.rollback()
        flash_error(request, "Could not update order status.")

    return RedirectResponse(url=f"/admin/orders/{order_id}", status_code=303)


@app.post("/admin/orders/{order_id}/cancel", response_model=None)
def admin_order_cancel(request: Request, order_id: str, db: Session = Depends(get_db)):
    gate = require_admin(request, db, f"/admin/orders/{order_id}")
    if not isinstance(gate, User):
        return gate

    _, _, _, order_service, _ = build_services(db)

    try:
        oid = UUID(order_id)
        order_service.cancel_order_admin(order_id=oid)
        payment_service, _, _ = build_payment_services_cached(request, db)
        payment_service.refund_if_paid(order_id=oid)
        db.commit()
    except ValueError as e:
        db.rollback()
        flash_error(request, str(e))
    except Exception:
        db.rollback()
        flash_error(request, "Could not cancel order.")

    return RedirectResponse(url=f"/admin/orders/{order_id}", status_code=303)

# ---------- Cart ----------
@app.post("/cart/add/{product_id}", response_model=None)
def cart_add(
    request: Request,
    product_id: str,
    qty: int = Form(1),
    next: str = Form("/"),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login(next)

    _, _, cart_service, _, _ = build_services(db)

    try:
        pid = UUID(product_id)
        cart_service.add(request.session, pid, qty=qty)
    except ValueError as e:
        flash_error(request, str(e))
    except Exception:
        flash_error(request, "Could not add product to cart.")

    return RedirectResponse(url=next or "/", status_code=303)


@app.get("/cart", response_class=HTMLResponse, response_model=None)
def cart_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login("/cart")

    _, _, cart_service, _, _ = build_services(db)
    lines, total_display = cart_service.build_view(request.session)

    return templates.TemplateResponse(
        "cart.html",
        template_context(request, db, {"lines": lines, "total_display": total_display, "title": "Your Cart"}),
    )


@app.post("/cart/set/{product_id}", response_model=None)
def cart_set_qty(
    request: Request,
    product_id: str,
    qty: int = Form(...),
    next: str = Form("/cart"),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login(next)

    _, _, cart_service, _, _ = build_services(db)

    try:
        pid = UUID(product_id)
        cart_service.set_qty(request.session, pid, qty=qty)
    except ValueError as e:
        flash_error(request, str(e))
    except Exception:
        flash_error(request, "Could not update cart.")

    return RedirectResponse(url=next or "/cart", status_code=303)


@app.post("/cart/remove/{product_id}")
def cart_remove(request: Request, product_id: str, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login("/cart")

    _, _, cart_service, _, _ = build_services(db)

    try:
        pid = UUID(product_id)
        cart_service.remove(request.session, pid)
    except Exception:
        pass

    return RedirectResponse(url="/cart", status_code=303)


@app.post("/cart/clear")
def cart_clear(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login("/cart")

    _, _, cart_service, _, _ = build_services(db)
    cart_service.clear(request.session)
    return RedirectResponse(url="/cart", status_code=303)

@app.get("/addresses", response_class=HTMLResponse, response_model=None)
def addresses_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login("/addresses")

    address_service, _ = build_address_services_cached(request, db)
    addresses = [a.to_dict() for a in address_service.list_addresses(user.id)]

    return templates.TemplateResponse(
        "addresses.html",
        template_context(request, db, {"addresses": addresses, "title": "Addresses"}),
    )


@app.get("/addresses/new", response_class=HTMLResponse, response_model=None)
def address_new_form(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login("/addresses/new")

    empty = {
        "label": "",
        "recipient_name": user.full_name,
        "line1": "",
        "line2": "",
        "city": "",
        "state": "",
        "postal_code": "",
        "country": "",
        "phone": "",
    }

    return templates.TemplateResponse(
        "address_form.html",
        template_context(
            request,
            db,
            {
                "title": "New Address",
                "action": "/addresses/new",
                "a": empty,
                "make_default": True,
                "error": None,
            },
        ),
    )


@app.post("/addresses/new", response_model=None)
def address_create(
    request: Request,
    label: str = Form(""),
    recipient_name: str = Form(...),
    line1: str = Form(...),
    line2: str = Form(""),
    city: str = Form(...),
    state: str = Form(""),
    postal_code: str = Form(""),
    country: str = Form(""),
    phone: str = Form(""),
    make_default: str | None = Form(None),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login("/addresses/new")

    address_service, _ = build_address_services_cached(request, db)

    try:
        address_service.create_address(
            user_id=user.id,
            label=label,
            recipient_name=recipient_name,
            line1=line1,
            line2=line2,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
            phone=phone,
            make_default=bool(make_default),
        )
        db.commit()
        return RedirectResponse(url="/addresses", status_code=303)
    except ValueError as e:
        db.rollback()
        filled = {
            "label": label,
            "recipient_name": recipient_name,
            "line1": line1,
            "line2": line2,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "country": country,
            "phone": phone,
        }
        return templates.TemplateResponse(
            "address_form.html",
            template_context(
                request,
                db,
                {
                    "title": "New Address",
                    "action": "/addresses/new",
                    "a": filled,
                    "make_default": bool(make_default),
                    "error": str(e),
                },
            ),
            status_code=400,
        )


@app.get("/addresses/{address_id}/edit", response_class=HTMLResponse, response_model=None)
def address_edit_form(request: Request, address_id: str, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login(f"/addresses/{address_id}/edit")

    address_service, _ = build_address_services_cached(request, db)

    try:
        aid = UUID(address_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Address not found")

    addr = address_service.get_address_for_user(user.id, aid)
    if not addr:
        raise HTTPException(status_code=404, detail="Address not found")

    a = addr.to_dict()
    return templates.TemplateResponse(
        "address_form.html",
        template_context(
            request,
            db,
            {
                "title": "Edit Address",
                "action": f"/addresses/{address_id}/edit",
                "a": a,
                "make_default": a.get("is_default", False),
                "error": None,
            },
        ),
    )


@app.post("/addresses/{address_id}/edit", response_model=None)
def address_edit(
    request: Request,
    address_id: str,
    label: str = Form(""),
    recipient_name: str = Form(...),
    line1: str = Form(...),
    line2: str = Form(""),
    city: str = Form(...),
    state: str = Form(""),
    postal_code: str = Form(""),
    country: str = Form(""),
    phone: str = Form(""),
    make_default: str | None = Form(None),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login(f"/addresses/{address_id}/edit")

    address_service, _ = build_address_services_cached(request, db)

    try:
        aid = UUID(address_id)
        address_service.update_address(
            user_id=user.id,
            address_id=aid,
            label=label,
            recipient_name=recipient_name,
            line1=line1,
            line2=line2,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
            phone=phone,
            make_default=bool(make_default),
        )
        db.commit()
        return RedirectResponse(url="/addresses", status_code=303)
    except ValueError as e:
        db.rollback()
        filled = {
            "id": address_id,
            "label": label,
            "recipient_name": recipient_name,
            "line1": line1,
            "line2": line2,
            "city": city,
            "state": state,
            "postal_code": postal_code,
            "country": country,
            "phone": phone,
        }
        return templates.TemplateResponse(
            "address_form.html",
            template_context(
                request,
                db,
                {
                    "title": "Edit Address",
                    "action": f"/addresses/{address_id}/edit",
                    "a": filled,
                    "make_default": bool(make_default),
                    "error": str(e),
                },
            ),
            status_code=400,
        )


@app.post("/addresses/{address_id}/delete", response_model=None)
def address_delete(request: Request, address_id: str, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login("/addresses")

    address_service, _ = build_address_services_cached(request, db)

    try:
        aid = UUID(address_id)
        address_service.delete_address(user_id=user.id, address_id=aid)
        db.commit()
    except ValueError as e:
        db.rollback()
        flash_error(request, str(e))
    except Exception:
        db.rollback()
        flash_error(request, "Could not delete address.")

    return RedirectResponse(url="/addresses", status_code=303)


@app.post("/addresses/{address_id}/default", response_model=None)
def address_make_default(request: Request, address_id: str, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login("/addresses")

    address_service, _ = build_address_services_cached(request, db)

    try:
        aid = UUID(address_id)
        address_service.set_default(user_id=user.id, address_id=aid)
        db.commit()
    except ValueError as e:
        db.rollback()
        flash_error(request, str(e))
    except Exception:
        db.rollback()
        flash_error(request, "Could not set default address.")

    return RedirectResponse(url="/addresses", status_code=303)

# ---------- Checkout + Orders ----------
@app.get("/checkout", response_class=HTMLResponse, response_model=None)
def checkout_page(request: Request, address_id: str | None = None, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login("/checkout")

    _, _, cart_service, _, _ = build_services_cached(request, db)
    address_service, _ = build_address_services_cached(request, db)

    lines, total_display = cart_service.build_view(request.session)
    if not lines:
        return RedirectResponse(url="/cart", status_code=303)

    addresses = [a.to_dict() for a in address_service.list_addresses(user.id)]

    selected = None
    if address_id:
        try:
            selected = address_service.get_address_for_user(user.id, UUID(address_id))
        except Exception:
            selected = None

    if not selected:
        selected = address_service.get_default_address(user.id)

    ctx = {
        "lines": lines,
        "total_display": total_display,
        "error": None,
        "addresses": addresses,
        "save_address": False,
        "label": "",
        "make_default": False,
    }

    if selected:
        d = selected.to_dict()
        ctx.update(
            {
                "shipping_name": d["recipient_name"],
                "line1": d["line1"],
                "line2": d["line2"],
                "city": d["city"],
                "state": d["state"],
                "postal_code": d["postal_code"],
                "country": d["country"],
                "phone": d["phone"],
            }
        )
    else:
        ctx.update(
            {
                "shipping_name": user.full_name,
                "line1": "",
                "line2": "",
                "city": "",
                "state": "",
                "postal_code": "",
                "country": "",
                "phone": "",
            }
        )

    return templates.TemplateResponse("checkout.html", template_context(request, db, ctx))


@app.post("/checkout", response_model=None)
def checkout_submit(
    request: Request,
    shipping_name: str = Form(...),
    line1: str = Form(...),
    line2: str = Form(""),
    city: str = Form(...),
    state: str = Form(""),
    postal_code: str = Form(""),
    country: str = Form(""),
    phone: str = Form(""),
    save_address: str | None = Form(None),
    label: str = Form(""),
    make_default: str | None = Form(None),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login("/checkout")

    _, _, cart_service, order_service, _ = build_services_cached(request, db)
    address_service, _ = build_address_services_cached(request, db)

    cart_items = cart_service.items(request.session)
    lines, total_display = cart_service.build_view(request.session)
    addresses = [a.to_dict() for a in address_service.list_addresses(user.id)]

    shipping_address_text = format_shipping_address(
        line1=line1,
        line2=line2,
        city=city,
        state=state,
        postal_code=postal_code,
        country=country,
        phone=phone,
    )

    try:
        order = order_service.place_order(
            user=user,
            cart_items=cart_items,
            shipping_name=shipping_name,
            shipping_address=shipping_address_text,
        )

        # Optional: save address (don’t block checkout if save fails)
        if bool(save_address):
            try:
                address_service.create_address(
                    user_id=user.id,
                    label=label,
                    recipient_name=shipping_name,
                    line1=line1,
                    line2=line2,
                    city=city,
                    state=state,
                    postal_code=postal_code,
                    country=country,
                    phone=phone,
                    make_default=bool(make_default),
                )
            except ValueError as e:
                flash_error(request, f"Order placed, but address not saved: {e}")

        cart_service.clear(request.session)
        payment_service, _, _ = build_payment_services_cached(request, db)
        payment_service.get_or_create(order_id=order.id, user_id=user.id, amount=order.total)

        db.commit()
        return RedirectResponse(url=f"/pay/{order.id}", status_code=303)

    except ValueError as e:
        db.rollback()
        return templates.TemplateResponse(
            "checkout.html",
            template_context(
                request,
                db,
                {
                    "lines": lines,
                    "total_display": total_display,
                    "error": str(e),
                    "addresses": addresses,
                    "shipping_name": shipping_name,
                    "line1": line1,
                    "line2": line2,
                    "city": city,
                    "state": state,
                    "postal_code": postal_code,
                    "country": country,
                    "phone": phone,
                    "save_address": bool(save_address),
                    "label": label,
                    "make_default": bool(make_default),
                    "title": "Checkout",
                },
            ),
            status_code=400,
        )

@app.get("/orders", response_class=HTMLResponse, response_model=None)
def orders_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login("/orders")

    _, _, _, order_service, _ = build_services(db)
    orders = [o.to_dict() for o in order_service.list_orders_for_user(user.id)]
    return templates.TemplateResponse("orders.html", template_context(request, db, {"orders": orders, "title": "Your Orders"}))


@app.get("/orders/{order_id}", response_class=HTMLResponse, response_model=None)
def order_detail_page(request: Request, order_id: str, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login(f"/orders/{order_id}")

    # services
    _, _, _, order_service, _ = build_services_cached(request, db)
    payment_service, payment_repo, _ = build_payment_services_cached(request, db)

    try:
        oid = UUID(order_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Order not found")

    order = order_service.get_order_for_user(user_id=user.id, order_id=oid)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Get payment (and create one if missing)
    payment = payment_repo.get_by_order(order.id)
    if not payment:
        payment = payment_service.get_or_create(order_id=order.id, user_id=user.id, amount=order.total)
        db.commit()  # important if it had to create it

    return templates.TemplateResponse(
        "order_detail.html",
        template_context(
            request,
            db,
            {
                "order": order.to_dict(),
                "payment": payment.to_dict(),   
                "title": "Order",
            },
        ),
    )

@app.post("/orders/{order_id}/cancel", response_model=None)
def cancel_order_customer(request: Request, order_id: str, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login(f"/orders/{order_id}")

    _, _, _, order_service, _ = build_services(db)

    try:
        oid = UUID(order_id)
        order_service.cancel_order_for_user(user=user, order_id=oid)
        payment_service, _, _ = build_payment_services_cached(request, db)
        payment_service.refund_if_paid(order_id=oid)
        db.commit()
    except ValueError as e:
        db.rollback()
        flash_error(request, str(e))
    except Exception:
        db.rollback()
        flash_error(request, "Could not cancel order.")

    return RedirectResponse(url=f"/orders/{order_id}", status_code=303)

@app.get("/pay/{order_id}", response_class=HTMLResponse, response_model=None)
def pay_page(request: Request, order_id: str, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login(f"/pay/{order_id}")

    _, _, _, order_service, user_repo = build_services_cached(request, db)
    payment_service, _, _ = build_payment_services_cached(request, db)

    try:
        oid = UUID(order_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Order not found")

    order = order_service.get_order_for_user(user_id=user.id, order_id=oid)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    payment = payment_service.get_or_create(order_id=order.id, user_id=user.id, amount=order.total)

    return templates.TemplateResponse(
        "pay.html",
        template_context(
            request,
            db,
            {
                "order": order.to_dict(),
                "payment": payment.to_dict(),
                "title": "Payment",
            },
        ),
    )

@app.post("/pay/{order_id}/success", response_model=None)
def pay_success(request: Request, order_id: str, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login(f"/pay/{order_id}")

    _, _, _, order_service, user_repo = build_services_cached(request, db)
    payment_service, _, receipt_service = build_payment_services_cached(request, db)

    try:
        oid = UUID(order_id)
        order = order_service.get_order_for_user(user_id=user.id, order_id=oid)
        if not order:
            raise ValueError("Order not found.")

        payment = payment_service.mark_paid(order_id=oid)

        # email simulation + receipt file write
        receipt_service.simulate_email_send(order=order, payment=payment, user_email=user.email)

        db.commit()
        return RedirectResponse(url=f"/orders/{order_id}/receipt", status_code=303)

    except ValueError as e:
        db.rollback()
        flash_error(request, str(e))
    except Exception:
        db.rollback()
        flash_error(request, "Payment could not be completed.")

    return RedirectResponse(url=f"/pay/{order_id}", status_code=303)

@app.post("/pay/{order_id}/fail", response_model=None)
def pay_fail(request: Request, order_id: str, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login(f"/pay/{order_id}")

    payment_service, _, _ = build_payment_services_cached(request, db)

    try:
        oid = UUID(order_id)
        payment_service.mark_failed(order_id=oid, message="Mock gateway: declined")
        db.commit()
    except Exception:
        db.rollback()
        flash_error(request, "Could not update payment.")

    return RedirectResponse(url=f"/pay/{order_id}", status_code=303)

@app.get("/orders/{order_id}/receipt", response_class=HTMLResponse, response_model=None)
def receipt_page(request: Request, order_id: str, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return redirect_to_login(f"/orders/{order_id}/receipt")

    _, _, _, order_service, _ = build_services_cached(request, db)
    payment_service, _, _ = build_payment_services_cached(request, db)

    try:
        oid = UUID(order_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Order not found")

    order = order_service.get_order_for_user(user_id=user.id, order_id=oid)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    payment = payment_service.get_or_create(order_id=oid, user_id=user.id, amount=order.total)
    if payment.status != PaymentStatus.PAID:
        flash_error(request, "Receipt is available only after payment.")
        return RedirectResponse(url=f"/pay/{order_id}", status_code=303)

    return templates.TemplateResponse(
        "receipt.html",
        template_context(request, db, {"order": order.to_dict(), "payment": payment.to_dict(), "title": "Receipt"}),
    )