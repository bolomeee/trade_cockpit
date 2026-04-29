import json
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

LAYOUTS_DIR = Path(__file__).parent.parent.parent / "layouts"

PageType = Literal["workbench", "cockpit", "news"]

router = APIRouter(prefix="/api/layouts", tags=["layouts"])


@router.get("/{page}")
def get_layout(page: PageType) -> JSONResponse:
    layout_file = LAYOUTS_DIR / f"{page}.json"
    if not layout_file.exists():
        return JSONResponse({"data": [], "message": "success"})
    data = json.loads(layout_file.read_text(encoding="utf-8"))
    return JSONResponse({"data": data, "message": "success"})


@router.put("/{page}")
def save_layout(
    page: PageType,
    layout: Annotated[list[dict[str, Any]], Body()],
) -> JSONResponse:
    LAYOUTS_DIR.mkdir(exist_ok=True)
    layout_file = LAYOUTS_DIR / f"{page}.json"
    layout_file.write_text(
        json.dumps(layout, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return JSONResponse({"data": None, "message": "success"})
