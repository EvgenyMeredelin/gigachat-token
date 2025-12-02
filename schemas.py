from datetime import datetime
from typing import Annotated, Self
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta as reldelta
from environs import env
from pydantic import (
    AwareDatetime, BaseModel, Field, PositiveInt,
    field_validator, model_validator
)


class GigaChatAccessToken(BaseModel):
    """
    A temporary access token to the GigaChat API.
    https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/post-token
    """

    token: Annotated[
        str,
        Field(alias="access_token", serialization_alias="token")
    ]
    minutes_valid: PositiveInt = env.int("GIGACHAT_TOKEN_TTL")
    released: AwareDatetime | None = None
    expires: Annotated[
        AwareDatetime,
        Field(alias="expires_at", serialization_alias="expires")
    ]
    obs_key: str

    @field_validator("expires", mode="before")
    @classmethod
    def convert_epoch_to_datetime(cls, value: int) -> AwareDatetime:
        """
        Truncate milliseconds and convert seconds since epoch
        to a localized datetime object in the Moscow timezone.
        """
        timezone = ZoneInfo("Europe/Moscow")
        return datetime.fromtimestamp(value // 1000, timezone)

    @model_validator(mode="after")
    def restore_release_date(self) -> Self:
        """
        Restore the moment in time when the token was released.
        """
        self.released = self.expires - reldelta(minutes=self.minutes_valid)
        return self
