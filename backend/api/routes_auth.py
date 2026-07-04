import time
from fastapi import APIRouter, HTTPException, status, Depends, Request, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from backend.core.security import (
    create_access_tokens,
    create_refresh_tokens,
    verify_refresh_token,
    verify_password,
    hash_password,
    hash_refresh_token,
    verify_hashed_refresh_token,
)
from backend.schema.users_auth import UserCreate, UserLogin
from backend.core.dependencies import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.concurrency import run_in_threadpool
from backend.db.users import User
from backend.db.refresh_token import RefreshToken
from datetime import datetime, timezone
from backend.core.rate_limiter import login_rate_limiter, refresh_rate_limiter
from backend.logging_fastapi.logger_api import auth_logger
from backend.custom_metrics import (
    REQUEST_COUNT,
    REQUEST_DURATION,
    REQUEST_ERRORS,
    RESPONSE_STATUS,
)
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

router = APIRouter(prefix="/auth", tags=["Auth"])
templates = Jinja2Templates(directory="backend/templates")

ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"


def _record_request_metrics(method: str, endpoint: str, status_code: str, start_time: float) -> None:
    REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(time.perf_counter() - start_time)
    RESPONSE_STATUS.labels(method=method, endpoint=endpoint, status_code=status_code).inc()


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    start_time = time.perf_counter()
    endpoint = request.url.path
    method = request.method
    status_code = "200"
    REQUEST_COUNT.labels(method=method, endpoint=endpoint).inc()
    try:
        return templates.TemplateResponse(
            request=request,
            name="signup.html",
        )
    finally:
        _record_request_metrics(method, endpoint, status_code, start_time)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    start_time = time.perf_counter()
    endpoint = request.url.path
    method = request.method
    status_code = "200"
    REQUEST_COUNT.labels(method=method, endpoint=endpoint).inc()
    success = None
    info = None
    error = None

    if request.query_params.get("signup") == "success":
        success = "Account created successfully. Please sign in."

    if request.query_params.get("logout") == "success":
        success = "You have been signed out successfully."

    if request.query_params.get("session") == "expired":
        info = "Your session expired. Please log in again."

    if request.query_params.get("refresh") == "rate_limited":
        error = "Too many refresh attempts. Please log in again shortly."

    if request.query_params.get("refresh") == "service_unavailable":
        error = "Session service is temporarily unavailable. Please log in again later."

    try:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"success": success, "info": info, "error": error},
        )
    finally:
        _record_request_metrics(method, endpoint, status_code, start_time)


@router.post("/signup", response_class=HTMLResponse)
async def signup(request: Request,
                 username: str = Form(...),
                 email: str = Form(...),
                 password: str = Form(...),
                 db: AsyncSession = Depends(get_db)):
    start_time = time.perf_counter()
    endpoint = request.url.path
    method = request.method
    status_code = "200"
    REQUEST_COUNT.labels(method=method, endpoint=endpoint).inc()
    try:
        try:
            user_input = UserCreate(
                username=username,
                email=email,
                password=password,
            )
        except ValidationError as exc:
            status_code = str(status.HTTP_400_BAD_REQUEST)
            REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="validation_error").inc()
            error_message = exc.errors()[0]["msg"]
            auth_logger.save_logs(f"User Creation Failed - Validation Error: {error_message}", log_level="error")
            return templates.TemplateResponse(
                request=request,
                name="signup.html",
                context={"error": error_message},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        stmt = select(User).where(User.email == user_input.email)
        result = await db.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            status_code = str(status.HTTP_400_BAD_REQUEST)
            REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="email_exists").inc()
            auth_logger.save_logs("User Creation Failed - Email already exists", log_level="error")
            return templates.TemplateResponse(
                request=request,
                name="signup.html",
                context={"error": "Email already exists"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        password_hash = await run_in_threadpool(hash_password, user_input.password)
        new_user = User(
            username=user_input.username,
            email=user_input.email,
            password_hash=password_hash,
        )

        try:
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
        except Exception:
            status_code = str(status.HTTP_500_INTERNAL_SERVER_ERROR)
            REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="db_error").inc()
            await db.rollback()
            auth_logger.save_logs("User Creation Failed - DB Error", log_level="error")
            return templates.TemplateResponse(
                request=request,
                name="signup.html",
                context={"error": "Could not create user, please try again"},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        status_code = str(status.HTTP_303_SEE_OTHER)
        return RedirectResponse(
            url="/auth/login?signup=success",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    finally:
        _record_request_metrics(method, endpoint, status_code, start_time)


@router.post("/login", response_class=HTMLResponse)
async def login(request: Request,
                email: str = Form(...),
                password: str = Form(...),
                db: AsyncSession = Depends(get_db),
                _=Depends(login_rate_limiter)):
    start_time = time.perf_counter()
    endpoint = request.url.path
    method = request.method
    status_code = "200"
    REQUEST_COUNT.labels(method=method, endpoint=endpoint).inc()
    try:
        if _ == "rate_limited":
            status_code = str(status.HTTP_429_TOO_MANY_REQUESTS)
            REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="rate_limited").inc()
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={"error": "Too many login attempts. Please try again later."},
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if _ == "redis_unavailable":
            status_code = str(status.HTTP_503_SERVICE_UNAVAILABLE)
            REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="redis_unavailable").inc()
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={"error": "Service temporarily unavailable. Please try again later."},
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            user_input = UserLogin(
                email=email,
                password=password,
            )
        except ValidationError as exc:
            status_code = str(status.HTTP_400_BAD_REQUEST)
            REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="validation_error").inc()
            error_msg = exc.errors()[0]["msg"]
            auth_logger.save_logs(f"User Login Failed : Validation Error {error_msg}", log_level="error")
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={"error": error_msg},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        stmt = select(User).where(User.email == user_input.email)
        result = await db.execute(stmt)
        db_user = result.scalar_one_or_none()

        if not db_user:
            status_code = str(status.HTTP_401_UNAUTHORIZED)
            REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="invalid_credentials").inc()
            auth_logger.save_logs("Login Failed - User not found", log_level="error")
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={"error": "Invalid credentials"},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        password_valid = await run_in_threadpool(
            verify_password,
            user_input.password,
            db_user.password_hash,
        )

        if not password_valid:
            status_code = str(status.HTTP_401_UNAUTHORIZED)
            REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="invalid_credentials").inc()
            auth_logger.save_logs("Login Failed - Invalid password for user", log_level="error")
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={"error": "Invalid Credentials"},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        access_token = create_access_tokens(str(db_user.id))
        refresh_token, expires_at = create_refresh_tokens(str(db_user.id))
        hashed_refresh_token = await run_in_threadpool(
            hash_refresh_token,
            refresh_token,
        )

        stmt = select(RefreshToken).where(RefreshToken.user_id == db_user.id)
        result = await db.execute(stmt)
        existing_token = result.scalar_one_or_none()

        try:
            if existing_token:
                existing_token.token = hashed_refresh_token
                existing_token.expires_at = expires_at
            else:
                db.add(
                    RefreshToken(
                        user_id=db_user.id,
                        token=hashed_refresh_token,
                        expires_at=expires_at,
                    )
                )
            await db.commit()
        except Exception:
            status_code = str(status.HTTP_500_INTERNAL_SERVER_ERROR)
            REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="db_error").inc()
            await db.rollback()
            auth_logger.save_logs("Token Creation Failed for user - DB Error", log_level="error")
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={"error": "Could not log in please try again."},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        status_code = str(status.HTTP_303_SEE_OTHER)
        response = RedirectResponse(
            url="/dashboard",
            status_code=status.HTTP_303_SEE_OTHER,
        )
        response.set_cookie(
            key=ACCESS_COOKIE_NAME,
            value=access_token,
            httponly=True,
            secure=False,
            samesite="lax",
            path="/",
        )
        response.set_cookie(
            key=REFRESH_COOKIE_NAME,
            value=refresh_token,
            httponly=True,
            secure=False,
            samesite="lax",
            path="/",
        )
        return response
    finally:
        _record_request_metrics(method, endpoint, status_code, start_time)


@router.get("/refresh")
async def refresh_access_tokens(request: Request, db: AsyncSession = Depends(get_db), _=Depends(refresh_rate_limiter)):
    start_time = time.perf_counter()
    endpoint = request.url.path
    method = request.method
    status_code = "200"
    REQUEST_COUNT.labels(method=method, endpoint=endpoint).inc()
    auth_logger.save_logs("Hit Refresh Endpoint", log_level="info")
    next_url = request.query_params.get("next", "/")
    try:
        if _ == "rate_limited":
            status_code = str(status.HTTP_303_SEE_OTHER)
            REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="rate_limited").inc()
            return RedirectResponse(
                url="/auth/login?refresh=rate_limited",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        if _ == "redis_unavailable":
            status_code = str(status.HTTP_303_SEE_OTHER)
            REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="redis_unavailable").inc()
            return RedirectResponse(
                url="/auth/login?refresh=service_unavailable",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        if not next_url.startswith("/"):
            next_url = "/"

        refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)

        if not refresh_token:
            status_code = str(status.HTTP_303_SEE_OTHER)
            REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="missing_refresh_token").inc()
            auth_logger.save_logs("Token Refresh Failed - No refresh token provided", log_level="error")
            return RedirectResponse(
                url="/auth/login?session=expired",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        token_result = verify_refresh_token(refresh_token)
        payload = token_result.get("payload")

        if payload is None:
            status_code = str(status.HTTP_303_SEE_OTHER)
            REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="invalid_refresh_token").inc()
            auth_logger.save_logs("Token Refresh Failed - Invalid or expired refresh token", log_level="error")
            response = RedirectResponse(
                url="/auth/login?session=expired",
                status_code=status.HTTP_303_SEE_OTHER,
            )
            response.delete_cookie(key=ACCESS_COOKIE_NAME, path="/")
            response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/")
            return response

        user_id = payload.get("sub")
        try:
            stmt = (
                select(RefreshToken)
                .where(RefreshToken.user_id == user_id)
                .with_for_update()
            )
            result = await db.execute(stmt)
            db_token = result.scalar_one_or_none()

            if not db_token:
                status_code = str(status.HTTP_303_SEE_OTHER)
                REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="token_not_found").inc()
                auth_logger.save_logs("Token Refresh Failed - No token found in DB for user", log_level="error")
                response = RedirectResponse(
                    url="/auth/login?session=expired",
                    status_code=status.HTTP_303_SEE_OTHER,
                )
                response.delete_cookie(key=ACCESS_COOKIE_NAME, path="/")
                response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/")
                return response

            is_valid_token = await run_in_threadpool(
                verify_hashed_refresh_token,
                refresh_token,
                db_token.token,
            )

            if not is_valid_token:
                status_code = str(status.HTTP_303_SEE_OTHER)
                REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="invalid_refresh_token").inc()
                auth_logger.save_logs("Token Refresh Failed - Refresh token does not match DB record", log_level="error")
                response = RedirectResponse(
                    url="/auth/login?session=expired",
                    status_code=status.HTTP_303_SEE_OTHER,
                )
                response.delete_cookie(key=ACCESS_COOKIE_NAME, path="/")
                response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/")
                return response

            if db_token.expires_at < datetime.now(timezone.utc):
                status_code = str(status.HTTP_303_SEE_OTHER)
                REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="expired_refresh_token").inc()
                auth_logger.save_logs("Token Refresh Failed - Refresh token expired for user", log_level="error")
                response = RedirectResponse(
                    url="/auth/login?session=expired",
                    status_code=status.HTTP_303_SEE_OTHER,
                )
                response.delete_cookie(key=ACCESS_COOKIE_NAME, path="/")
                response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/")
                return response

            new_access_token = create_access_tokens(user_id)
            new_refresh_token, expires_at = create_refresh_tokens(user_id)
            hash_new_token = await run_in_threadpool(
                hash_refresh_token,
                new_refresh_token,
            )
            db_token.token = hash_new_token
            db_token.expires_at = expires_at
            await db.commit()
            auth_logger.save_logs("Token Refresh Successful for user", log_level="info")
        except Exception:
            await db.rollback()
            status_code = str(status.HTTP_303_SEE_OTHER)
            REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="token_refresh_error").inc()
            return RedirectResponse(
                url="/auth/login?session=expired",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        status_code = str(status.HTTP_303_SEE_OTHER)
        response = RedirectResponse(
            url=next_url,
            status_code=status.HTTP_303_SEE_OTHER,
        )
        response.set_cookie(
            key=ACCESS_COOKIE_NAME,
            value=new_access_token,
            httponly=True,
            secure=False,
            samesite="lax",
            path="/",
        )
        response.set_cookie(
            key=REFRESH_COOKIE_NAME,
            value=new_refresh_token,
            httponly=True,
            secure=False,
            samesite="lax",
            path="/",
        )
        return response
    finally:
        _record_request_metrics(method, endpoint, status_code, start_time)


@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    start_time = time.perf_counter()
    endpoint = request.url.path
    method = request.method
    status_code = "200"
    REQUEST_COUNT.labels(method=method, endpoint=endpoint).inc()
    try:
        refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)

        if refresh_token:
            payload = verify_refresh_token(refresh_token)
            if payload:
                user_id = payload.get("sub")
                try:
                    stmt = select(RefreshToken).where(RefreshToken.user_id == user_id)
                    result = await db.execute(stmt)
                    db_token = result.scalar_one_or_none()
                    if db_token:
                        await db.delete(db_token)
                        await db.commit()
                        auth_logger.save_logs("User logged out successfully", log_level="info")
                    else:
                        auth_logger.save_logs("User logged out - token already gone", log_level="info")
                except Exception:
                    status_code = str(status.HTTP_500_INTERNAL_SERVER_ERROR)
                    REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="db_error").inc()
                    await db.rollback()
                    auth_logger.save_logs("Logout DB operation failed - continuing anyway", log_level="error")
            else:
                auth_logger.save_logs("Logout with invalid/expired token - clearing cookie", log_level="info")
        else:
            auth_logger.save_logs("Logout with no refresh token - clearing cookie", log_level="info")

        status_code = str(status.HTTP_303_SEE_OTHER)
        response = RedirectResponse(
            url="/?logout=success",
            status_code=status.HTTP_303_SEE_OTHER,
        )
        response.delete_cookie(
            key=ACCESS_COOKIE_NAME,
            path="/",
            secure=False,
            httponly=True,
            samesite="lax",
        )
        response.delete_cookie(
            key=REFRESH_COOKIE_NAME,
            path="/",
            secure=False,
            httponly=True,
            samesite="lax",
        )
        return response
    finally:
        _record_request_metrics(method, endpoint, status_code, start_time)
