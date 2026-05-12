from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.user_settings_repository import UserSettingsRepository
from app.schemas.cockpit.user_settings import (
    UserSettingsData,
    UserSettingsResponse,
    UserSettingsUpdate,
)

router = APIRouter(prefix="/user-settings", tags=["cockpit-user-settings"])


def _get_repo(db: Session = Depends(get_db)) -> UserSettingsRepository:
    return UserSettingsRepository(db)


@router.get("", response_model=UserSettingsResponse)
def get_user_settings(repo: UserSettingsRepository = Depends(_get_repo)) -> UserSettingsResponse:
    return UserSettingsResponse(data=UserSettingsData(**repo.get_or_default()))


@router.put("", response_model=UserSettingsResponse)
def put_user_settings(
    patch: UserSettingsUpdate,
    repo: UserSettingsRepository = Depends(_get_repo),
) -> UserSettingsResponse:
    row = repo.upsert(patch.model_dump(exclude_unset=True, by_alias=False))
    return UserSettingsResponse(data=UserSettingsData.model_validate(row))
