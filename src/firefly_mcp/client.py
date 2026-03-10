from __future__ import annotations

import httpx


class FireflyClient:
    """HTTP client for Firefly III and Data Importer APIs."""

    def __init__(
        self,
        firefly_url: str,
        token: str,
        importer_url: str,
        importer_secret: str,
    ) -> None:
        self.firefly_url = firefly_url.rstrip("/")
        self.importer_url = importer_url.rstrip("/")
        self.importer_secret = importer_secret

        self._firefly = httpx.AsyncClient(
            base_url=f"{self.firefly_url}/api/v1",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        self._importer = httpx.AsyncClient(
            base_url=self.importer_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=120.0,
        )

    async def close(self) -> None:
        await self._firefly.aclose()
        await self._importer.aclose()

    # -- Transactions --

    async def list_transactions(
        self,
        start: str | None = None,
        end: str | None = None,
        type: str = "withdrawal",
        page: int = 1,
    ) -> dict:
        params: dict = {"type": type, "page": page}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        resp = await self._firefly.get("/transactions", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_transaction(self, transaction_id: int) -> dict:
        resp = await self._firefly.get(f"/transactions/{transaction_id}")
        resp.raise_for_status()
        return resp.json()

    async def update_transaction(self, transaction_id: int, payload: dict) -> dict:
        resp = await self._firefly.put(
            f"/transactions/{transaction_id}", json=payload
        )
        resp.raise_for_status()
        return resp.json()

    async def search_transactions(self, query: str, page: int = 1) -> dict:
        resp = await self._firefly.get(
            "/search/transactions", params={"query": query, "page": page}
        )
        resp.raise_for_status()
        return resp.json()

    # -- Accounts --

    async def list_accounts(self, account_type: str = "asset") -> dict:
        resp = await self._firefly.get(
            "/accounts", params={"type": account_type}
        )
        resp.raise_for_status()
        return resp.json()

    # -- Tags --

    async def list_tags(self) -> dict:
        resp = await self._firefly.get("/tags")
        resp.raise_for_status()
        return resp.json()

    async def create_tag(self, name: str) -> dict:
        resp = await self._firefly.post("/tags", json={"tag": name})
        resp.raise_for_status()
        return resp.json()

    # -- Categories --

    async def list_categories(self) -> dict:
        resp = await self._firefly.get("/categories")
        resp.raise_for_status()
        return resp.json()

    async def create_category(self, name: str) -> dict:
        resp = await self._firefly.post("/categories", json={"name": name})
        resp.raise_for_status()
        return resp.json()

    # -- Budgets --

    async def list_budgets(self) -> dict:
        resp = await self._firefly.get("/budgets")
        resp.raise_for_status()
        return resp.json()

    async def create_budget(self, name: str) -> dict:
        resp = await self._firefly.post("/budgets", json={"name": name})
        resp.raise_for_status()
        return resp.json()

    async def create_budget_limit(
        self, budget_id: int, amount: float, start: str, end: str, currency_code: str = "MYR"
    ) -> dict:
        resp = await self._firefly.post(
            f"/budgets/{budget_id}/limits",
            json={
                "amount": str(amount),
                "start": start,
                "end": end,
                "currency_code": currency_code,
            },
        )
        resp.raise_for_status()
        return resp.json()

    # -- Bills --

    async def list_bills(self) -> dict:
        resp = await self._firefly.get("/bills")
        resp.raise_for_status()
        return resp.json()

    # -- Insights --

    async def get_insight(
        self, insight_type: str, group: str, start: str, end: str
    ) -> list:
        resp = await self._firefly.get(
            f"/insight/{insight_type}/{group}",
            params={"start": start, "end": end},
        )
        resp.raise_for_status()
        return resp.json()

    # -- Summary --

    async def get_summary(self, start: str, end: str) -> dict:
        resp = await self._firefly.get(
            "/summary/basic", params={"start": start, "end": end}
        )
        resp.raise_for_status()
        return resp.json()

    # -- Data Importer --

    async def upload_csv(self, csv_bytes: bytes, config_json: str) -> str:
        # Build request manually to avoid the base client's Content-Type header
        # conflicting with the multipart boundary that httpx needs to set
        request = self._importer.build_request(
            "POST",
            "/autoupload",
            params={"secret": self.importer_secret},
            files={
                "importable": ("import.csv", csv_bytes, "text/csv"),
                "json": ("config.json", config_json.encode(), "application/json"),
            },
        )
        resp = await self._importer.send(request)
        resp.raise_for_status()
        return resp.text
