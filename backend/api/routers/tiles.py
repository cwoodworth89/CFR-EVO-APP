"""
Offline Map Tile Proxy & Fallback Router for CFR EVO API Gateway.
Proxies map tile requests to containerized mbtileserver on port 8080/8081 with local loose-file fallback.
"""
import os
import re
import urllib.request
import logging
from typing import Optional

from fastapi import APIRouter, Response
from fastapi.responses import FileResponse

router = APIRouter(tags=["tiles"])

# MBTiles Server Forwarder Base URL (internal container service http://tiles:8080 or host http://127.0.0.1:8081)
TILE_SERVER_URL = os.environ.get("TILE_SERVER_URL", "http://tiles:8080").rstrip("/")

# Local Map Tiles Cache Directory (Legacy loose-file fallback)
TILES_BASE_DIR = os.environ.get(
    "TILES_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "tiles")
)
os.makedirs(TILES_BASE_DIR, exist_ok=True)

# 1x1 Transparent PNG (68 bytes) for missing/uncached tile fallbacks
TRANSPARENT_1X1_PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"


def _serve_tile(layer: str, z: int, x: int, y: int, ext: Optional[str] = None):
    """Forward tile requests to mbtileserver, falling back to local files or 1x1 transparent PNG."""
    clean_layer = re.sub(r"[^a-zA-Z0-9_-]", "", layer)
    file_ext = (ext.lower().lstrip(".") if ext else ("jpg" if clean_layer == "satellite" else "png"))

    # 1. Forward request to containerized mbtileserver
    target_url = f"{TILE_SERVER_URL}/services/{clean_layer}/tiles/{z}/{x}/{y}.{file_ext}"
    try:
        req = urllib.request.Request(target_url, headers={"User-Agent": "CFR-EVO-Gateway"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            if resp.status == 200:
                content = resp.read()
                media_type = resp.headers.get_content_type() or f"image/{'jpeg' if file_ext in ['jpg', 'jpeg'] else 'png'}"
                return Response(
                    content=content,
                    media_type=media_type,
                    status_code=200,
                    headers={
                        "Cache-Control": "public, max-age=604800",
                        "Access-Control-Allow-Origin": "*",
                    }
                )
    except Exception:
        # If mbtileserver internal hostname fails (e.g. outside docker), try host fallback on 127.0.0.1:8081
        if "tiles:8080" in TILE_SERVER_URL:
            try:
                fallback_url = f"http://127.0.0.1:8081/services/{clean_layer}/tiles/{z}/{x}/{y}.{file_ext}"
                req = urllib.request.Request(fallback_url, headers={"User-Agent": "CFR-EVO-Gateway"})
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    if resp.status == 200:
                        content = resp.read()
                        media_type = resp.headers.get_content_type() or f"image/{'jpeg' if file_ext in ['jpg', 'jpeg'] else 'png'}"
                        return Response(
                            content=content,
                            media_type=media_type,
                            status_code=200,
                            headers={
                                "Cache-Control": "public, max-age=604800",
                                "Access-Control-Allow-Origin": "*",
                            }
                        )
            except Exception:
                pass

    # 2. Check local loose-file cache if present (legacy support)
    layer_dir = os.path.join(TILES_BASE_DIR, clean_layer)
    tile_dir = os.path.join(layer_dir, str(z), str(x))
    candidates = [
        (os.path.join(tile_dir, f"{y}.{file_ext}"), f"image/{'jpeg' if file_ext in ['jpg', 'jpeg'] else 'png'}"),
        (os.path.join(tile_dir, f"{y}.png"), "image/png"),
        (os.path.join(tile_dir, f"{y}.jpg"), "image/jpeg"),
    ]
    for file_path, media_type in candidates:
        if os.path.isfile(file_path):
            return FileResponse(
                path=file_path,
                media_type=media_type,
                headers={
                    "Cache-Control": "public, max-age=604800",
                    "Access-Control-Allow-Origin": "*",
                }
            )

    # 3. Return transparent 1x1 PNG with 200 OK to prevent OpaqueResponseBlocking (ORB) browser errors
    return Response(
        content=TRANSPARENT_1X1_PNG,
        media_type="image/png",
        status_code=200,
        headers={
            "Cache-Control": "public, max-age=86400",
            "Access-Control-Allow-Origin": "*",
        }
    )


@router.get("/services/{layer}/tiles/{z}/{x}/{y}.{ext}")
def get_service_tile_with_ext(layer: str, z: int, x: int, y: int, ext: str):
    """Direct proxy path conforming to mbtileserver service URL structure."""
    return _serve_tile(layer, z, x, y, ext=ext)


@router.get("/api/tiles/{layer}/{z}/{x}/{y}.png")
def get_tile_png(layer: str, z: int, x: int, y: int):
    """Serve tile as PNG."""
    return _serve_tile(layer, z, x, y, ext="png")


@router.get("/api/tiles/{layer}/{z}/{x}/{y}.jpg")
def get_tile_jpg(layer: str, z: int, x: int, y: int):
    """Serve tile as JPG."""
    return _serve_tile(layer, z, x, y, ext="jpg")


@router.get("/api/tiles/{layer}/{z}/{x}/{y}.jpeg")
def get_tile_jpeg(layer: str, z: int, x: int, y: int):
    """Serve tile as JPEG."""
    return _serve_tile(layer, z, x, y, ext="jpeg")


@router.get("/api/tiles/{layer}/{z}/{x}/{y}")
def get_tile_default(layer: str, z: int, x: int, y: int):
    """Serve tile without file extension."""
    return _serve_tile(layer, z, x, y, ext=None)
