"""Page routes (Naveen builds the shell; each owner edits their own template)."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

PAGES = [
    ("/", "Home", "index.html"),
    ("/operator", "Operator console", "operator.html"),
    ("/detection", "Detection", "detection.html"),
    ("/simulation", "Simulation", "simulation.html"),
    ("/incidents", "Incidents", "incidents.html"),
    ("/reports", "Reports", "reports.html"),
    ("/admin", "Admin", "admin.html"),
]


def _render(request: Request, path: str, template: str) -> HTMLResponse:
    return templates.TemplateResponse(request, template, {"pages": PAGES, "current": path})


def _make(path: str, template: str):
    async def view(request: Request) -> HTMLResponse:
        return _render(request, path, template)
    return view


for _path, _title, _template in PAGES:
    router.add_api_route(_path, _make(_path, _template), methods=["GET"], response_class=HTMLResponse,
                         name=_template.removesuffix(".html"))
