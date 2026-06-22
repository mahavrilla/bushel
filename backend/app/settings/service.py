"""Single-row app settings (home store, future prefs). Pure DB."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppSettings


def get_settings_row(db: Session) -> AppSettings:
    row = db.execute(select(AppSettings)).scalars().first()
    if row is None:
        row = AppSettings()
        db.add(row)
        db.flush()
    return row


def set_home_store(db: Session, location_id: str, name: str | None) -> AppSettings:
    row = get_settings_row(db)
    row.home_store_location_id = location_id
    row.home_store_name = name
    db.flush()
    return row


def get_home_store(db: Session) -> tuple[str | None, str | None]:
    row = get_settings_row(db)
    return row.home_store_location_id, row.home_store_name
