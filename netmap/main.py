import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.responses import RedirectResponse

from netmap.config import config
from netmap.db import init_databases
from netmap.ping_engine import ping_engine
from netmap.api.auth import router as auth_router
from netmap.api.public import router as public_router
from netmap.api.poll import router as poll_router
from netmap.api.admin import router as admin_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize databases and start ping background poller
    await init_databases()
    ping_engine.start()
    yield
    # Shutdown: Stop ping poller
    ping_engine.stop()

class ReverseProxyPrefixMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            forwarded_prefix = ""
            for k, v in scope.get("headers", []):
                if k.lower() == b"x-forwarded-prefix":
                    forwarded_prefix = v.decode("latin1").strip()
                    break

            prefix = (forwarded_prefix or config.url_prefix or scope.get("root_path", "")).strip().rstrip("/")
            if prefix and not prefix.startswith("/"):
                prefix = "/" + prefix

            path = scope.get("path", "")

            if prefix:
                if path == prefix:
                    response = RedirectResponse(url=f"{prefix}/", status_code=307)
                    await response(scope, receive, send)
                    return
                scope["root_path"] = prefix
                if not path.startswith(prefix):
                    scope["path"] = prefix + (path if path.startswith("/") else "/" + path)
            elif not scope.get("root_path"):
                scope["root_path"] = ""

        if scope["type"] == "http":
            async def send_with_security_headers(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    existing = {h[0].lower() for h in headers}
                    if b"x-content-type-options" not in existing:
                        headers.append((b"x-content-type-options", b"nosniff"))
                    if b"x-frame-options" not in existing:
                        headers.append((b"x-frame-options", b"SAMEORIGIN"))
                    if b"referrer-policy" not in existing:
                        headers.append((b"referrer-policy", b"strict-origin-when-cross-origin"))
                    message["headers"] = headers
                await send(message)
            await self.app(scope, receive, send_with_security_headers)
        else:
            await self.app(scope, receive, send)

app = FastAPI(
    title="NetMap - Network Tree Status Monitor",
    description="Asynchronous parallel network polling and left-to-right widescreen status tree",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(ReverseProxyPrefixMiddleware)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Include API routers
app.include_router(auth_router)
app.include_router(public_router)
app.include_router(poll_router)
app.include_router(admin_router)

def get_base_path(request: Request) -> str:
    return request.scope.get("root_path", "").rstrip("/")

@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"base_path": get_base_path(request)}
    )

@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={"base_path": get_base_path(request)}
    )
