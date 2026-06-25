from fastapi import APIRouter, Request, status, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from backend.core.dependencies import get_current_user
from backend.logging_fastapi.logger_api import auth_logger


router = APIRouter(tags=["Root"])
templates = Jinja2Templates(directory="backend/templates")

@router.get("/", response_class=HTMLResponse)
def root(request: Request):
    success = None

    if request.query_params.get("logout") == "success":
        success = "You have been signed out successfully."

    try:
        get_current_user(request)
        return RedirectResponse(
            url="/dashboard",
            status_code=status.HTTP_303_SEE_OTHER
        )
    except HTTPException:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"success": success}
        )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    try:
        user_id = get_current_user(request)

    except HTTPException as e:
        auth_logger.save_logs(
            f"Access validation failed while accessing dashboard page: {e.detail}",
            log_level="warning"
        )

        refresh_token = request.cookies.get("refresh_token")

        if e.detail == "expired" and refresh_token:
            auth_logger.save_logs(
                "Access token expired. Redirecting to refresh endpoint.",
                log_level="info"
            )
            return RedirectResponse(
                url="/auth/refresh?next=/dashboard",
                status_code=status.HTTP_303_SEE_OTHER
            )

        return RedirectResponse(
            url="/auth/login?session=expired",
            status_code=status.HTTP_303_SEE_OTHER
        )

    auth_logger.save_logs(
        "Access token valid. User can now see dashboard page.",
        log_level="info"
    )

    return templates.TemplateResponse(
        request=request,
        name = "dashboard.html",
        context={"user_id" : user_id}
    )