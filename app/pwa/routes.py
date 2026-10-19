from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.web import PASTA_APP, render

router = APIRouter()
ESTATICOS = PASTA_APP / "static"


@router.get("/manifest.webmanifest")
def manifest():
    return FileResponse(ESTATICOS / "manifest.webmanifest", media_type="application/manifest+json")


@router.get("/sw.js")
def service_worker():
    return FileResponse(
        ESTATICOS / "sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )


@router.get("/offline")
def offline(request: Request):
    return render(request, "offline.html")


@router.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(ESTATICOS / "icons" / "icon-192.png", media_type="image/png")
