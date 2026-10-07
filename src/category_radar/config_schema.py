"""Type-safe configuration with Pydantic validation."""

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


class ChannelType(str, Enum):
    PRICE_COMPARISON = "price_comparison"
    RETAILER = "retailer"


class FetcherMode(str, Enum):
    AUTO = "auto"
    HTTP = "http"
    BROWSER = "browser"


class CrawlConfig(BaseModel):
    delay_seconds: float = Field(default=4.0, ge=1.0, le=30.0)
    timeout_seconds: float = Field(default=30.0, ge=5.0, le=120.0)
    max_retries: int = Field(default=2, ge=0, le=5)
    respect_robots_txt: bool = True
    user_agent: str = "CategoryRadar/1.0 (personal market-research project; contact: berksaraloglu@gmail.com)"
    fetcher: FetcherMode = FetcherMode.AUTO


class MarketConfig(BaseModel):
    name: str
    currency: str
    language: str


class ChannelConfig(BaseModel):
    market: str
    adapter: str
    type: ChannelType
    start_url: HttpUrl
    max_pages: int = Field(default=1, ge=1, le=10)
    keep_keywords: str | None = None
    exclude_keywords: str | None = None


class ClaimConfig(BaseModel):
    label: str
    pattern: str

    @field_validator("pattern")
    @classmethod
    def validate_regex(cls, v: str) -> str:
        import re

        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid regex: {e}")
        return v


class NeedConfig(BaseModel):
    label: str
    pattern: str

    @field_validator("pattern")
    @classmethod
    def validate_regex(cls, v: str) -> str:
        import re

        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid regex: {e}")
        return v


class PriceTierConfig(BaseModel):
    name: str
    max_pct: float = Field(ge=0.0, le=100.0)


class ReviewsConfig(BaseModel):
    top_n_products: int = Field(default=8, ge=0, le=20)


class CategoryConfigSchema(BaseModel):
    id: str
    name: str
    base_currency: str = "EUR"
    crawl: CrawlConfig = CrawlConfig()
    markets: dict[str, MarketConfig]
    channels: dict[str, ChannelConfig]
    brands: dict[str, list[str]] = Field(default_factory=dict)
    price_tiers: list[PriceTierConfig] = Field(default_factory=list)
    claims: dict[str, ClaimConfig]
    needs: dict[str, NeedConfig]
    reviews: ReviewsConfig = ReviewsConfig()

    @model_validator(mode="after")
    def validate_channels(self) -> "CategoryConfigSchema":
        """Ensure all channel markets exist in markets dict."""
        for cid, ch in self.channels.items():
            if ch.market not in self.markets:
                raise ValueError(f"Channel {cid}: unknown market '{ch.market}'")
        return self

    @model_validator(mode="after")
    def validate_adapter_exists(self) -> "CategoryConfigSchema":
        """Ensure all adapters are registered."""
        from .channels import available_adapters

        adapters = set(available_adapters())
        for cid, ch in self.channels.items():
            if ch.adapter not in adapters:
                raise ValueError(f"Channel {cid}: unknown adapter '{ch.adapter}'. Available: {sorted(adapters)}")
        return self


class RawConfigSchema(BaseModel):
    category: CategoryConfigSchema
    crawl: CrawlConfig = CrawlConfig()
    markets: dict[str, MarketConfig]
    channels: dict[str, ChannelConfig]
    brands: dict[str, list[str]] = Field(default_factory=dict)
    price_tiers: list[PriceTierConfig] = Field(default_factory=list)
    claims: dict[str, ClaimConfig]
    needs: dict[str, NeedConfig]
    reviews: ReviewsConfig = ReviewsConfig()


def load_config_schema(path: str | Path) -> CategoryConfigSchema:
    """Load and validate YAML config against Pydantic schema."""
    import yaml
    from pydantic import ValidationError

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    # Extract category section and merge with top-level
    category_section = raw.get("category", {})
    crawl_section = raw.get("crawl", {})

    # Build schema with category fields
    schema_data = {
        "id": category_section.get("id"),
        "name": category_section.get("name"),
        "base_currency": category_section.get("base_currency", "EUR"),
        "crawl": crawl_section or {},
        "markets": raw.get("markets", {}),
        "channels": raw.get("channels", {}),
        "brands": raw.get("brands", {}),
        "price_tiers": raw.get("price_tiers", []),
        "claims": raw.get("claims", {}),
        "needs": raw.get("needs", {}),
        "reviews": raw.get("reviews", {}),
    }

    try:
        return CategoryConfigSchema(**schema_data)
    except ValidationError as e:
        raise ValueError(f"Config validation failed:\n{e}")
