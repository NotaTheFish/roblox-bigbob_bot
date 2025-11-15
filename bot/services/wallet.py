"""Minimal async client for the @wallet merchant API."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Mapping

import requests


@dataclass(slots=True)
class WalletInvoice:
    """Represents an invoice returned by the Wallet Pay API."""

    provider_invoice_id: str
    external_invoice_id: str
    pay_link: str
    amount: Decimal
    currency_code: str
    status: str
    expires_at: datetime | None


class WalletPayError(RuntimeError):
    """Base error for wallet pay failures."""


class WalletPayConfigurationError(WalletPayError):
    """Raised when the wallet credentials are missing or invalid."""


class WalletPayClient:
    """Async helper for creating invoices via the Wallet Pay store API."""

    def __init__(
        self,
        *,
        api_base: str,
        api_key: str,
        store_id: str,
        timeout: float = 10.0,
    ) -> None:
        if not api_key or not store_id:
            raise WalletPayConfigurationError("Wallet Pay credentials are not configured")
        self._api_base = api_base.rstrip("/") or "https://pay.wallet.tg"
        self._api_key = api_key
        self._store_id = store_id
        self._timeout = timeout

    @property
    def _orders_url(self) -> str:
        return f"{self._api_base}/wpay/store-api/v1/orders"

    async def create_invoice(
        self,
        *,
        external_invoice_id: str,
        amount: Decimal,
        currency_code: str,
        description: str,
        expires_in: int,
        customer_telegram_id: int,
        metadata: Mapping[str, Any] | None = None,
    ) -> WalletInvoice:
        payload = {
            "orderId": external_invoice_id,
            "amount": str(amount),
            "currencyCode": currency_code,
            "description": description,
            "expiresIn": expires_in,
            "customerTelegramUserId": customer_telegram_id,
            "metadata": metadata or {},
        }
        headers = {
            "X-API-KEY": self._api_key,
            "X-STORE-ID": self._store_id,
        }

        data = await asyncio.to_thread(self._send_request, payload, headers)
        expires_at_raw = data.get("expiresAt")
        expires_at: datetime | None = None
        if isinstance(expires_at_raw, str) and expires_at_raw:
            expires_at = _parse_datetime(expires_at_raw)

        provider_invoice_id = data.get("invoiceId") or data.get("orderId") or external_invoice_id
        pay_link = data.get("payLink") or data.get("invoiceUrl")
        status = data.get("status", "pending")
        amount_raw = data.get("amount") or payload["amount"]
        currency_code = data.get("currencyCode") or payload["currencyCode"]

        return WalletInvoice(
            provider_invoice_id=str(provider_invoice_id),
            external_invoice_id=external_invoice_id,
            pay_link=str(pay_link) if pay_link else "",
            amount=Decimal(str(amount_raw)),
            currency_code=str(currency_code),
            status=str(status).lower(),
            expires_at=expires_at,
        )

    def _send_request(self, payload: Mapping[str, Any], headers: Mapping[str, str]) -> Dict[str, Any]:
        try:
            response = requests.post(
                self._orders_url,
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:  # pragma: no cover - depends on API
            status_code = exc.response.status_code if exc.response else "unknown"
            detail = exc.response.text if exc.response else str(exc)
            raise WalletPayError(
                f"Wallet Pay responded with {status_code}: {detail}"
            ) from exc
        except requests.RequestException as exc:  # pragma: no cover - network failure
            raise WalletPayError("Cannot reach Wallet Pay API") from exc
        return response.json()


def _parse_datetime(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


__all__ = [
    "WalletInvoice",
    "WalletPayClient",
    "WalletPayConfigurationError",
    "WalletPayError",
]