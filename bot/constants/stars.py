"""Constants describing the Telegram Stars packages supported by the bot."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StarsPackage:
    """Represents a purchasable nuts package via Telegram Stars."""

    code: str
    title: str
    product_id: str
    stars_price: int
    nuts_amount: int

    @property
    def button_text(self) -> str:
        return f"{self.title} — {self.stars_price}\u2b50"


STARS_PACKAGES: tuple[StarsPackage, ...] = (
    StarsPackage(
        code="pack_50",
        title="50 орехов",
        product_id="nuts_pack_50",
        stars_price=50,
        nuts_amount=50,
    ),
    StarsPackage(
        code="pack_100",
        title="100 орехов",
        product_id="nuts_pack_100",
        stars_price=100,
        nuts_amount=100,
    ),
    StarsPackage(
        code="pack_250",
        title="250 орехов",
        product_id="nuts_pack_250",
        stars_price=250,
        nuts_amount=250,
    ),
    StarsPackage(
        code="pack_500",
        title="500 орехов",
        product_id="nuts_pack_500",
        stars_price=500,
        nuts_amount=500,
    ),
)


STARS_PACKAGES_BY_CODE: dict[str, StarsPackage] = {pkg.code: pkg for pkg in STARS_PACKAGES}
STARS_PACKAGES_BY_PRODUCT_ID: dict[str, StarsPackage] = {
    pkg.product_id: pkg for pkg in STARS_PACKAGES
}


__all__ = [
    "StarsPackage",
    "STARS_PACKAGES",
    "STARS_PACKAGES_BY_CODE",
    "STARS_PACKAGES_BY_PRODUCT_ID",
]