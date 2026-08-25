from typing import ClassVar

from pydantic import BaseModel, ConfigDict, field_validator


class BaseModelConfig(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    @field_validator("*", mode="before")
    @classmethod
    def null_string_to_none(cls, value: object) -> object:
        return value if value != "null" else None


class SteamData(BaseModelConfig):
    last_30d: float | None = None


class BuffStartingAt(BaseModelConfig):
    price: float | None = None


class BuffData(BaseModelConfig):
    starting_at: BuffStartingAt | None = None


class PriceData(BaseModelConfig):
    price: float | None = None


class RarityData(BaseModelConfig):
    name: str | None = None


class ItemData(BaseModelConfig):
    market_hash_name: str | None = None
    rarity: RarityData | None = None


class ItemPrices(BaseModelConfig):
    steam: SteamData | None = None
    buff163: BuffData | None = None
    csgotrader: PriceData | None = None
