import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

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

app = FastAPI(
    title="NetMap - Network Tree Status Monitor",
    description="Asynchronous parallel network polling and left-to-right widescreen status tree",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Include API routers
app.include_router(auth_router)
app.include_router(public_router)
app.include_router(poll_router)
app.include_router(admin_router)

@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin.html")
