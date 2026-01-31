"""API routes for parcel tracking."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from myparcel.db import get_db
from myparcel.services.carrier_loader import carrier_loader
from myparcel.services.tracker import TrackerService

router = APIRouter()
templates = Jinja2Templates(directory="src/myparcel/templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: AsyncSession = Depends(get_db)):
    """Main dashboard showing all parcels."""
    tracker = TrackerService(db)
    await tracker.ensure_carriers_exist()

    parcels = await tracker.get_all_parcels()
    carriers = carrier_loader.list_carriers()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "parcels": parcels,
            "carriers": carriers,
        },
    )


@router.get("/parcel/{parcel_id}", response_class=HTMLResponse)
async def parcel_detail(
    request: Request,
    parcel_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Show details for a single parcel."""
    tracker = TrackerService(db)
    parcel = await tracker.get_parcel(parcel_id)

    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    carrier = carrier_loader.get_carrier(parcel.carrier_id)
    tracking_url = carrier.get_tracking_url(parcel.tracking_number) if carrier else None

    return templates.TemplateResponse(
        "parcel_detail.html",
        {
            "request": request,
            "parcel": parcel,
            "tracking_url": tracking_url,
        },
    )


@router.post("/parcel/add")
async def add_parcel(
    tracking_number: str = Form(...),
    carrier_id: str = Form(default=""),
    description: str = Form(default=""),
    sender: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
):
    """Add a new parcel to track."""
    tracker = TrackerService(db)

    # If no carrier specified, try to detect it
    if not carrier_id:
        matches = carrier_loader.detect_carrier(tracking_number)
        if matches:
            carrier_id = matches[0].config.id
        else:
            raise HTTPException(
                status_code=400,
                detail="Could not detect carrier. Please select one manually.",
            )

    parcel = await tracker.add_parcel(
        tracking_number=tracking_number,
        carrier_id=carrier_id,
        description=description or None,
        sender=sender or None,
    )

    if not parcel:
        raise HTTPException(
            status_code=400,
            detail="Could not add parcel. It may already exist.",
        )

    # Try to fetch initial status
    await tracker.refresh_parcel(parcel)

    return RedirectResponse(url="/", status_code=303)


@router.post("/parcel/{parcel_id}/refresh")
async def refresh_parcel(parcel_id: int, db: AsyncSession = Depends(get_db)):
    """Refresh tracking status for a parcel."""
    tracker = TrackerService(db)
    parcel = await tracker.get_parcel(parcel_id)

    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    result = await tracker.refresh_parcel(parcel)

    if not result.success:
        raise HTTPException(status_code=502, detail=result.error or "Failed to refresh")

    return RedirectResponse(url=f"/parcel/{parcel_id}", status_code=303)


@router.post("/parcel/{parcel_id}/delete")
async def delete_parcel(parcel_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a parcel."""
    tracker = TrackerService(db)

    if not await tracker.delete_parcel(parcel_id):
        raise HTTPException(status_code=404, detail="Parcel not found")

    return RedirectResponse(url="/", status_code=303)


@router.get("/api/detect-carrier")
async def detect_carrier(tracking_number: str):
    """API endpoint to detect carrier from tracking number."""
    matches = carrier_loader.detect_carrier(tracking_number)

    return {
        "tracking_number": tracking_number,
        "carriers": [
            {"id": c.config.id, "name": c.config.name}
            for c in matches
        ],
    }


@router.get("/api/carriers")
async def list_carriers():
    """API endpoint to list all carriers."""
    return {
        "carriers": [
            {"id": c.id, "name": c.name, "enabled": c.enabled}
            for c in carrier_loader.list_carriers()
        ],
    }
