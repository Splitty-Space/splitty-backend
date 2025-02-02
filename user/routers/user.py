import fastapi
from fastapi import status

from app import orm
from user.dtos import (
    UpdateSettings, UserInfo,
)
from user.models import User

router = fastapi.APIRouter()


@router.get("/me")
def get_me(user_id: int) -> UserInfo:
    with orm.Session.begin() as transaction:
        user = transaction.query(User).get(user_id)

        if not user:
            raise fastapi.HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

        return UserInfo(
            id=user.id,
            username=user.username,
            name=user.fullname,
            photo_url=user.photo_url,
            default_currency=user.default_currency,
            language=user.language,
            referral_code=user.referral_code,
        )


@router.put("/settings")
def update_settings(update_settings: UpdateSettings):
    with orm.Session.begin() as transaction:
        user = transaction.query(User).get(update_settings.user_id)

        if not user:
            raise fastapi.HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

        if update_settings.default_currency:
            user.default_currency = update_settings.default_currency

        if update_settings.language:
            user.language = update_settings.language

        transaction.commit()

        return True