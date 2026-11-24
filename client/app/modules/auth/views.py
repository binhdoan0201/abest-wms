"""Web Controller cho phân hệ Xác thực (Auth)."""

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from client.app.core.api_client import ApiClient, ClientApiError
from client.app.core.auth_guard import get_optional_user, home_path
from client.app.core.session import clear_session_cookie, set_session_cookie

router = APIRouter(tags=["Auth Views"])


def get_templates(request: Request) -> Jinja2Templates:
    templates: Jinja2Templates = request.app.state.templates
    return templates


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> Response:
    """Hiển thị trang đăng nhập. Nếu đã đăng nhập thì chuyển hướng vào hệ thống."""
    user = get_optional_user(request)
    if user:
        return RedirectResponse(url=home_path(user), status_code=303)

    templates = get_templates(request)
    return templates.TemplateResponse(
        request=request,
        name="auth/login.html",
        context={"request": request, "user": None, "menu": []},
    )


@router.post("/login", response_class=HTMLResponse)
def login_action(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
) -> Response:
    """Xử lý xác thực đăng nhập từ Form người dùng gửi lên."""
    templates = get_templates(request)
    api = ApiClient()

    try:
        response_data = api.post(
            "/auth/login",
            json_data={"username": username, "password": password},
        )
        token_data = response_data.get("data", {})
        token = token_data.get("access_token")

        if not token:
            return templates.TemplateResponse(
                request=request,
                name="auth/login.html",
                context={
                    "request": request,
                    "error_msg": "Máy chủ không cấp phát token xác thực.",
                    "username": username,
                },
                status_code=400,
            )

        # Chuyển hướng tới trang đầu theo vai trò
        redirect_resp = RedirectResponse(url=home_path(token_data.get("user")), status_code=303)
        set_session_cookie(redirect_resp, token)
        return redirect_resp

    except ClientApiError as exc:
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={
                "request": request,
                "error_msg": exc.message,
                "error_code": exc.code,
                "username": username,
            },
            status_code=exc.http_status if exc.http_status < 500 else 400,
        )


@router.post("/logout")
@router.get("/logout")
def logout_action(request: Request) -> Response:
    """Đăng xuất tài khoản và xóa cookie phiên."""
    redirect_resp = RedirectResponse(url="/login", status_code=303)
    clear_session_cookie(redirect_resp)
    return redirect_resp
