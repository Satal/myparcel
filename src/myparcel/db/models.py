"""Database models."""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class ParcelStatus(str, Enum):
    """Normalised parcel status across all carriers."""

    UNKNOWN = "unknown"
    PENDING = "pending"  # Label created, not yet with carrier
    RECEIVED = "received"  # Carrier has the parcel
    IN_TRANSIT = "in_transit"  # On the way
    OUT_FOR_DELIVERY = "out_for_delivery"  # With local driver
    DELIVERED = "delivered"  # Successfully delivered
    FAILED_ATTEMPT = "failed_attempt"  # Delivery attempted but failed
    HELD = "held"  # Held at depot/customs
    RETURNED = "returned"  # Returned to sender
    EXCEPTION = "exception"  # Problem with delivery


class Carrier(Base):
    """A shipping carrier (Royal Mail, DPD, etc.)."""

    __tablename__ = "carriers"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    parcels: Mapped[list["Parcel"]] = relationship(back_populates="carrier")


class Parcel(Base):
    """A tracked parcel."""

    __tablename__ = "parcels"

    id: Mapped[int] = mapped_column(primary_key=True)
    tracking_number: Mapped[str] = mapped_column(String(100), index=True)
    carrier_id: Mapped[str] = mapped_column(ForeignKey("carriers.id"))

    # User-provided info
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Current status
    status: Mapped[ParcelStatus] = mapped_column(default=ParcelStatus.UNKNOWN)
    last_status_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_delivery: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Tracking
    is_active: Mapped[bool] = mapped_column(default=True)
    last_checked: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    carrier: Mapped["Carrier"] = relationship(back_populates="parcels")
    events: Mapped[list["TrackingEvent"]] = relationship(
        back_populates="parcel", order_by="desc(TrackingEvent.timestamp)"
    )


class TrackingEvent(Base):
    """A tracking event for a parcel."""

    __tablename__ = "tracking_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    parcel_id: Mapped[int] = mapped_column(ForeignKey("parcels.id"))

    # Event details
    status: Mapped[ParcelStatus] = mapped_column()
    status_text: Mapped[str] = mapped_column(Text)  # Original carrier text
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    parcel: Mapped["Parcel"] = relationship(back_populates="events")
