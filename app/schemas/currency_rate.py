from pydantic import BaseModel, ConfigDict, Field


class CurrencyRateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    currency: str
    rate_to_gmd: float


class CurrencyRateUpsert(BaseModel):
    rate_to_gmd: float = Field(gt=0)