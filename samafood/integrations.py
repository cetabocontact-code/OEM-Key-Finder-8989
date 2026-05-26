"""Integration adapter layer for the existing Sama Food systems.

Sama already runs:
  * SAP Business One  -> accounting (Service Layer REST/OData API)
  * Olive             -> sales: offers, inventory, GPS, invoicing

This module defines a single `ProductSource` interface plus concrete
connectors. The live connectors stay dormant until their credentials are
provided via environment variables; otherwise the app uses the seeded data
already loaded into SQLite. Nothing here replaces Olive or SAP — it only
pulls product/price/stock data so clients can self-serve orders.

Required env vars to switch on the live connectors (ask Sama's developer):
  SAP Business One Service Layer:
    SAP_SL_URL        e.g. https://sap-host:50000/b1s/v1
    SAP_SL_COMPANYDB  the company database name
    SAP_SL_USER
    SAP_SL_PASSWORD
  Olive:
    OLIVE_API_URL
    OLIVE_API_KEY
"""

from __future__ import annotations

import os
from typing import Any, Protocol

import requests


class ProductSource(Protocol):
    name: str

    def fetch_products(self) -> list[dict[str, Any]]:
        """Return product dicts: sku, name_en, name_ar, category, size, base_price, stock."""
        ...


class SapBusinessOneSource:
    """Pulls items from the SAP Business One Service Layer (Items endpoint)."""

    name = "sap_b1"

    def __init__(self) -> None:
        self.url = os.environ["SAP_SL_URL"].rstrip("/")
        self.company_db = os.environ["SAP_SL_COMPANYDB"]
        self.user = os.environ["SAP_SL_USER"]
        self.password = os.environ["SAP_SL_PASSWORD"]

    def _login(self, session: requests.Session) -> None:
        resp = session.post(
            f"{self.url}/Login",
            json={"CompanyDB": self.company_db, "UserName": self.user, "Password": self.password},
            timeout=20,
        )
        resp.raise_for_status()

    def fetch_products(self) -> list[dict[str, Any]]:
        session = requests.Session()
        self._login(session)
        resp = session.get(
            f"{self.url}/Items",
            params={"$select": "ItemCode,ItemName,QuantityOnStock,ItemsGroupCode"},
            timeout=30,
        )
        resp.raise_for_status()
        items = resp.json().get("value", [])
        products: list[dict[str, Any]] = []
        for item in items:
            products.append(
                {
                    "sku": item.get("ItemCode", ""),
                    "name_en": item.get("ItemName", ""),
                    "name_ar": item.get("ItemName", ""),
                    "category": "other",
                    "size": "",
                    "base_price": 0.0,
                    "stock": int(item.get("QuantityOnStock") or 0),
                }
            )
        return products


class OliveSource:
    """Pulls catalog/offers/inventory from Olive's API (endpoint shape TBD)."""

    name = "olive"

    def __init__(self) -> None:
        self.url = os.environ["OLIVE_API_URL"].rstrip("/")
        self.api_key = os.environ["OLIVE_API_KEY"]

    def fetch_products(self) -> list[dict[str, Any]]:
        # NOTE: Olive's exact endpoint/field names are unknown until Sama's
        # developer shares the API docs. This assumes a conventional REST shape
        # and must be adjusted to the real response.
        resp = requests.get(
            f"{self.url}/products",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30,
        )
        resp.raise_for_status()
        products: list[dict[str, Any]] = []
        for item in resp.json().get("products", []):
            products.append(
                {
                    "sku": item.get("sku", ""),
                    "name_en": item.get("name_en") or item.get("name", ""),
                    "name_ar": item.get("name_ar") or item.get("name", ""),
                    "category": item.get("category", "other"),
                    "size": item.get("size", ""),
                    "base_price": float(item.get("price") or 0),
                    "stock": int(item.get("stock") or 0),
                }
            )
        return products


def active_source() -> ProductSource | None:
    """Return the configured live source, or None to use seeded data."""
    if os.environ.get("OLIVE_API_URL") and os.environ.get("OLIVE_API_KEY"):
        return OliveSource()
    if all(os.environ.get(key) for key in ("SAP_SL_URL", "SAP_SL_COMPANYDB", "SAP_SL_USER", "SAP_SL_PASSWORD")):
        return SapBusinessOneSource()
    return None
