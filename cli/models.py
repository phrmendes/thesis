from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class BaseModelConfig(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")


class SteamData(BaseModelConfig):
    last_24h: float | None = None
    last_7d: float | None = None
    last_30d: float | None = None
    last_90d: float | None = None


class BuffStartingAt(BaseModelConfig):
    price: float | None = None


class BuffHighestOrder(BaseModelConfig):
    price: float | None = None


class BuffData(BaseModelConfig):
    starting_at: BuffStartingAt | str | None = None
    highest_order: BuffHighestOrder | str | None = None


class PriceData(BaseModelConfig):
    price: float | None = None


class ItemPrices(BaseModelConfig):
    steam: SteamData | None = None
    buff163: BuffData | None = None
    csgotrader: PriceData | None = None
