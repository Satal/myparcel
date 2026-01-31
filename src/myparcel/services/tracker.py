"""Service for tracking parcels."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from myparcel.carriers.base import TrackingResult
from myparcel.db.models import Carrier, Parcel, ParcelStatus, TrackingEvent
from myparcel.services.carrier_loader import carrier_loader


class TrackerService:
    """Service for managing parcel tracking."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def ensure_carriers_exist(self) -> None:
        """Ensure all loaded carriers exist in the database."""
        for config in carrier_loader.list_carriers():
            existing = await self.db.get(Carrier, config.id)
            if not existing:
                carrier = Carrier(
                    id=config.id,
                    name=config.name,
                    website=config.website,
                    enabled=config.enabled,
                )
                self.db.add(carrier)
        await self.db.commit()

    async def add_parcel(
        self,
        tracking_number: str,
        carrier_id: str | None = None,
        description: str | None = None,
        sender: str | None = None,
    ) -> Parcel | None:
        """Add a new parcel to track.

        If carrier_id is not provided, attempts to detect the carrier.
        """
        tracking_number = tracking_number.strip().upper()

        # Detect carrier if not provided
        if not carrier_id:
            matches = carrier_loader.detect_carrier(tracking_number)
            if not matches:
                return None
            carrier_id = matches[0].config.id

        # Check carrier exists
        carrier = await self.db.get(Carrier, carrier_id)
        if not carrier:
            return None

        # Check for duplicate
        existing = await self.db.execute(
            select(Parcel).where(
                Parcel.tracking_number == tracking_number,
                Parcel.carrier_id == carrier_id,
            )
        )
        if existing.scalar_one_or_none():
            return None  # Already tracking this parcel

        # Create parcel
        parcel = Parcel(
            tracking_number=tracking_number,
            carrier_id=carrier_id,
            description=description,
            sender=sender,
        )
        self.db.add(parcel)
        await self.db.commit()
        await self.db.refresh(parcel)

        return parcel

    async def refresh_parcel(self, parcel: Parcel) -> TrackingResult:
        """Refresh tracking status for a parcel."""
        carrier = carrier_loader.get_carrier(parcel.carrier_id)
        if not carrier:
            return TrackingResult(
                success=False,
                error=f"Carrier {parcel.carrier_id} not found",
            )

        result = await carrier.fetch_status(parcel.tracking_number)

        if result.success:
            parcel.status = result.status
            parcel.last_status_text = result.status_text
            parcel.expected_delivery = result.expected_delivery
            parcel.last_checked = datetime.now(timezone.utc)

            # Mark as inactive if delivered
            if result.status == ParcelStatus.DELIVERED:
                parcel.is_active = False

            # Add new events
            for event_data in result.events:
                # Check if event already exists (by timestamp and status text)
                existing = await self.db.execute(
                    select(TrackingEvent).where(
                        TrackingEvent.parcel_id == parcel.id,
                        TrackingEvent.timestamp == event_data.get("timestamp"),
                        TrackingEvent.status_text == event_data.get("status_text"),
                    )
                )
                if not existing.scalar_one_or_none():
                    event = TrackingEvent(
                        parcel_id=parcel.id,
                        status=carrier.normalise_status(event_data.get("status_text", "")),
                        status_text=event_data.get("status_text", ""),
                        location=event_data.get("location"),
                        timestamp=event_data.get("timestamp", datetime.now(timezone.utc)),
                    )
                    self.db.add(event)

            await self.db.commit()

        return result

    async def refresh_all_active(self) -> dict[int, TrackingResult]:
        """Refresh all active parcels."""
        result = await self.db.execute(select(Parcel).where(Parcel.is_active.is_(True)))
        parcels = result.scalars().all()

        results = {}
        for parcel in parcels:
            results[parcel.id] = await self.refresh_parcel(parcel)

        return results

    async def get_parcel(self, parcel_id: int) -> Parcel | None:
        """Get a parcel by ID."""
        return await self.db.get(Parcel, parcel_id)

    async def get_all_parcels(self, active_only: bool = False) -> list[Parcel]:
        """Get all parcels, optionally filtering to active only."""
        query = select(Parcel).order_by(Parcel.updated_at.desc())
        if active_only:
            query = query.where(Parcel.is_active.is_(True))

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def delete_parcel(self, parcel_id: int) -> bool:
        """Delete a parcel and its events."""
        parcel = await self.db.get(Parcel, parcel_id)
        if not parcel:
            return False

        # Delete events first
        await self.db.execute(
            TrackingEvent.__table__.delete().where(TrackingEvent.parcel_id == parcel_id)
        )
        await self.db.delete(parcel)
        await self.db.commit()
        return True
