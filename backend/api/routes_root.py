import time
from fastapi import APIRouter, Request, status, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from backend.core.dependencies import get_current_user
from backend.logging_fastapi.logger_api import auth_logger
from backend.custom_metrics import (
    REQUEST_COUNT,
    REQUEST_DURATION,
    REQUEST_ERRORS,
    RESPONSE_STATUS,
)


router = APIRouter(tags=["Root"])
templates = Jinja2Templates(directory="backend/templates")


def _record_request_metrics(method: str, endpoint: str, status_code: str, start_time: float, error_type: str | None = None) -> None:
    REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(time.perf_counter() - start_time)
    RESPONSE_STATUS.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
    if error_type:
        REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type=error_type).inc()

@router.get("/", response_class=HTMLResponse)
def root(request: Request):
    start_time = time.perf_counter()
    endpoint = request.url.path
    method = request.method
    status_code = str(status.HTTP_200_OK)
    REQUEST_COUNT.labels(method=method, endpoint=endpoint).inc()
    success = None

    if request.query_params.get("logout") == "success":
        success = "You have been signed out successfully."

    try:
        get_current_user(request)
        status_code = str(status.HTTP_303_SEE_OTHER)
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
    except Exception as exc:
        status_code = str(status.HTTP_500_INTERNAL_SERVER_ERROR)
        REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="server_error").inc()
        raise
    finally:
        _record_request_metrics(method, endpoint, status_code, start_time)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    start_time = time.perf_counter()
    endpoint = request.url.path
    method = request.method
    status_code = str(status.HTTP_200_OK)
    REQUEST_COUNT.labels(method=method, endpoint=endpoint).inc()

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

    try:
        return templates.TemplateResponse(
            request=request,
            name = "dashboard.html",
            context={"user_id" : user_id}
        )
    except Exception:
        status_code = str(status.HTTP_500_INTERNAL_SERVER_ERROR)
        REQUEST_ERRORS.labels(method=method, endpoint=endpoint, error_type="server_error").inc()
        raise
    finally:
        _record_request_metrics(method, endpoint, status_code, start_time)
