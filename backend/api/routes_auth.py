from fastapi import APIRouter,HTTPException,status,Depends,Request,Form
from fastapi.responses import RedirectResponse,HTMLResponse
from backend.core.security import create_access_tokens, create_refresh_tokens,verify_refresh_token,verify_password,hash_password,hash_refresh_token,verify_hashed_refresh_token
from backend.schema.users_auth import UserCreate,UserLogin
from backend.core.dependencies import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.concurrency import run_in_threadpool
from backend.db.users import User
from backend.db.refresh_token import RefreshToken
from datetime import datetime, timezone
from backend.core.rate_limiter import login_rate_limiter , refresh_rate_limiter
from backend.logging_fastapi.logger_api import auth_logger
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError


router = APIRouter(prefix="/auth",tags=["Auth"])
templates = Jinja2Templates(directory="backend/templates")


ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"

@router.get("/signup",response_class=HTMLResponse)
async def signup_page(request:Request):
    return templates.TemplateResponse(
        request=request,
        name = "signup.html",
    )

@router.get("/login",response_class=HTMLResponse)
async def login_page(request:Request):
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
    
    return templates.TemplateResponse(
    request=request,
    name="login.html",
    context={"success": success, "info": info, "error": error}
    )

@router.post("/signup",response_class=HTMLResponse)
async def signup(request:Request, 
                username: str = Form(...) ,
                email: str = Form(...),
                password: str = Form(...), 
                db:AsyncSession = Depends(get_db)):
    
    try:
        user_input = UserCreate(
            username=username,
            email=email,
            password=password
        )
    except ValidationError as exc:
        error_message = exc.errors()[0]['msg']
        auth_logger.save_logs(f"User Creation Failed - Validation Error: {error_message}", log_level="error")
        return templates.TemplateResponse(
                request=request,
                name="signup.html",
                context={"error": error_message},
                status_code=status.HTTP_400_BAD_REQUEST
        )

    stmt = select(User).where(User.email == user_input.email)
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        auth_logger.save_logs(f"User Creation Failed - Email already exists", log_level="error")
        return templates.TemplateResponse(
            request = request ,
            name="signup.html",
            context=
            {
                "error":"Email already exists"
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )
    # CPU Based Operation
    password_hash = await run_in_threadpool(
        hash_password, user_input.password
    )
    new_user = User(
        username = user_input.username,
        email = user_input.email,
        password_hash = password_hash
    )
    try:
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
    except Exception:
        await db.rollback()
        auth_logger.save_logs(
            f"User Creation Failed - DB Error",
            log_level="error"
        )
        
        return templates.TemplateResponse(
            request = request,
            name = "signup.html",
            context=
            {
                "error":"Could not create user, please try again"
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    return RedirectResponse(
        url="/auth/login?signup=success",
        status_code=status.HTTP_303_SEE_OTHER
    )

@router.post("/login",response_class=HTMLResponse)
async def login(request:Request , 
                email:str = Form(...), 
                password: str = Form(...),
                db:AsyncSession = Depends(get_db) , 
                _ = Depends(login_rate_limiter)):
    if _ == "rate_limited":
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Too many login attempts. Please try again later."},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )

    if _ == "redis_unavailable":
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Service temporarily unavailable. Please try again later."},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    try:
        user_input = UserLogin(
            email = email,
            password= password
        )
    except ValidationError as exc:
        error_msg = exc.errors()[0]["msg"]
        auth_logger.save_logs(f"User Login Falied : Validation Error {error_msg}")
        return templates.TemplateResponse(
            request = request,
            name = "login.html",
            context =
            {
                "error" : error_msg
            },
            status_code= status.HTTP_400_BAD_REQUEST
        )

    stmt = select(User).where(User.email == user_input.email)
    result = await db.execute(stmt)
    db_user = result.scalar_one_or_none()

    if not db_user:
        auth_logger.save_logs(f"Login Failed - User not found", log_level="error")
        
        return templates.TemplateResponse(
            request = request,
            name = "login.html",
            context = {
                "error": "Invalid credentials"
            },
            status_code= status.HTTP_401_UNAUTHORIZED
        )
    
    password_valid = await run_in_threadpool(
        verify_password,
        user_input.password,
        db_user.password_hash,
    )

    if not password_valid:
        auth_logger.save_logs(f"Login Failed - Invalid password for user", log_level="error")
        # raise HTTPException(
        #     status_code=status.HTTP_401_UNAUTHORIZED,
        #     detail = "Invalid credentials"
        # )

        return templates.TemplateResponse(
            request = request,
            name ="login.html",
            context = 
            {
                "error" : "Invalid Credentials"
            },
            status_code= status.HTTP_401_UNAUTHORIZED
        )
    
    access_token = create_access_tokens(str(db_user.id))
    refresh_token,expires_at = create_refresh_tokens(str(db_user.id))
    
    hashed_refresh_token = await run_in_threadpool(
        hash_refresh_token, refresh_token
    )
    stmt = select(RefreshToken).where(
        RefreshToken.user_id == db_user.id
    )
    result = await db.execute(stmt)
    existing_token = result.scalar_one_or_none()
    
    try:
        if existing_token:
            existing_token.token = hashed_refresh_token
            existing_token.expires_at = expires_at
        else :
            db.add(
                RefreshToken(
                    user_id=db_user.id,
                    token=hashed_refresh_token,
                    expires_at=expires_at,
                )
            )
            
        await db.commit()
    except Exception:
        await db.rollback()
        auth_logger.save_logs(f"Token Creation Failed for user - DB Error", log_level="error")
        # raise HTTPException(
        #     status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        #     detail = "Could not create tokens , please try again"
        # )
        return templates.TemplateResponse(
            request= request,
            name = "login.html",
            context = 
            {
                "error" : "Could not log in PLease try again."
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # response = JSONResponse(
    #     content= {
    #         "access_token" : access_token,
    #         "token_type" : "bearer"
    #     }
    # )
    response = RedirectResponse(
            url = "/dashboard",
            status_code= status.HTTP_303_SEE_OTHER
    )
    # refresh_max_age = int((expires_at - datetime.now(timezone.utc)).total_seconds())

    response.set_cookie(
        key = ACCESS_COOKIE_NAME,
        value = access_token,
        httponly=True,
        secure = False,
        samesite= "lax",
        path="/"
    )

    response.set_cookie(
        key = REFRESH_COOKIE_NAME,
        value = refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        path = "/"
        # max_age = refresh_max_age
    )
    return response


@router.get("/refresh")
async def refresh_access_tokens(request:Request, db:AsyncSession = Depends(get_db), _= Depends(refresh_rate_limiter)):
    auth_logger.save_logs("Hit Refresh Endpoint" , log_level="info")
    next_url = request.query_params.get("next","/")

    if _ == "rate_limited":
        return RedirectResponse(
            url="/auth/login?refresh=rate_limited",
            status_code=status.HTTP_303_SEE_OTHER
        )

    if _ == "redis_unavailable":
        return RedirectResponse(
            url="/auth/login?refresh=service_unavailable",
            status_code=status.HTTP_303_SEE_OTHER
        )

    if not next_url.startswith("/"):
        next_url = "/"

    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)

    if not refresh_token:
     auth_logger.save_logs(f"Token Refresh Failed - No refresh token provided", log_level="error")
     return RedirectResponse(
         url = "/auth/login?session=expired",
         status_code=status.HTTP_303_SEE_OTHER
     )
    #  raise HTTPException(
    #     status_code=status.HTTP_401_UNAUTHORIZED,
    #     detail="Refresh token missing"
    # )

    token_result = verify_refresh_token(refresh_token)
    payload = token_result.get("payload")
    error = token_result.get("error")

# Using Nested Dependecies
    if payload is None :
        auth_logger.save_logs(f"Token Refresh Failed - Invalid or expired refresh token", log_level="error")
        response = RedirectResponse(
            url="/auth/login?session=expired",
            status_code=status.HTTP_303_SEE_OTHER
        )
        response.delete_cookie(key=ACCESS_COOKIE_NAME, path="/")
        response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/")
        return response
        # raise HTTPException(
        #     status_code=status.HTTP_401_UNAUTHORIZED,
        #     detail = "Invalid or expired refresh token"
        # )
    
    user_id = payload.get("sub")

    try:
        # BEGIN TRANSACTION
        stmt = (
            select(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .with_for_update()
            # It does row_locking
        )

        result = await db.execute(stmt)
        db_token = result.scalar_one_or_none()

        if not db_token:
            auth_logger.save_logs(f"Token Refresh Failed - No token found in DB for user", log_level="error")
            response = RedirectResponse(
                url="/auth/login?session=expired",
                status_code=status.HTTP_303_SEE_OTHER
            )
            response.delete_cookie(key=ACCESS_COOKIE_NAME, path="/")
            response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/")
            return response
            # raise HTTPException(
            #     status_code=status.HTTP_401_UNAUTHORIZED,
            #     detail="Refresh token not found. Please login again",
            # )
        
        is_valid_token = await run_in_threadpool(
            verify_hashed_refresh_token,
            refresh_token,
            db_token.token
        )

        if not is_valid_token:
            auth_logger.save_logs(f"Token Refresh Failed - Refresh token does not match DB record", log_level="error")
            response = RedirectResponse(
                url="/auth/login?session=expired",
                status_code=status.HTTP_303_SEE_OTHER
            )
            response.delete_cookie(key=ACCESS_COOKIE_NAME, path="/")
            response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/")
            return response
            # raise HTTPException(
            #     status_code=status.HTTP_401_UNAUTHORIZED,
            #     detail="Invalid refresh token",
            # )

        if db_token.expires_at < datetime.now(timezone.utc):
            auth_logger.save_logs(f"Token Refresh Failed - Refresh token expired for user", log_level="error")
            response = RedirectResponse(
                url="/auth/login?session=expired",
                status_code=status.HTTP_303_SEE_OTHER
            )
            response.delete_cookie(key=ACCESS_COOKIE_NAME, path="/")
            response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/")
            return response
            # raise HTTPException(
            #     status_code=status.HTTP_401_UNAUTHORIZED,
            #     detail="Refresh token expired",
            # )

        # ROTATE TOKENS
        new_access_token = create_access_tokens(user_id)
        new_refresh_token, expires_at = create_refresh_tokens(user_id)
        hash_new_token = await run_in_threadpool(
            hash_refresh_token,
            new_refresh_token
        )
        db_token.token = hash_new_token
        db_token.expires_at = expires_at

        await db.commit()

        auth_logger.save_logs(f"Token Refresh Successful for user", log_level="info")

    except HTTPException:
        await db.rollback()
        return RedirectResponse(
            url="/auth/login?session=expired",
            status_code= status.HTTP_303_SEE_OTHER
        )

    # except Exception:
    #     await db.rollback()
    #     auth_logger.save_logs(f"Token Refresh Failed - Error occurred while refreshing tokens for user", log_level="error")
    #     raise HTTPException(
    #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         detail="Could not refresh tokens",
    #     )

    response = RedirectResponse(
        url = next_url,
        status_code=status.HTTP_303_SEE_OTHER
    )

    # refresh_max_age = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    
    response.set_cookie(
        key = ACCESS_COOKIE_NAME,
        value = new_access_token,
        httponly=True,
        secure = False,
        samesite="lax",
        path="/"
    )

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=new_refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/"
        # max_age=refresh_max_age,
    )

    return response

@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)

    if refresh_token:
        payload = verify_refresh_token(refresh_token)
        
        if payload:
            user_id = payload.get("sub")
            
            try:
                # Find and delete refresh token
                stmt = select(RefreshToken).where(
                    RefreshToken.user_id == user_id
                )
                result = await db.execute(stmt)
                db_token = result.scalar_one_or_none()
                
                if db_token:
                    await db.delete(db_token)
                    await db.commit()
                    
                    auth_logger.save_logs("User logged out successfully",log_level="info")
                else:
                    auth_logger.save_logs("User logged out - token already gone",log_level="info")
                    
            except Exception:
                await db.rollback()
                auth_logger.save_logs("Logout DB operation failed - continuing anyway",log_level="error")
                # Don't raise - still clear cookie and return success
        else:
            auth_logger.save_logs("Logout with invalid/expired token - clearing cookie",log_level="info")
    else:
        auth_logger.save_logs("Logout with no refresh token - clearing cookie",log_level="info")

    # Always clear the cookie and return success (idempotent)
    response = RedirectResponse(
        url = "/?logout=success",
        status_code=status.HTTP_303_SEE_OTHER
    )
    
    response.delete_cookie(
        key = ACCESS_COOKIE_NAME,
        path = "/",
        secure=False,
        httponly=True,
        samesite="lax"
    )

    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/",
        secure=False,
        httponly=True,
        samesite="lax"
    )
    
    return response