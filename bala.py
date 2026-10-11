import os
import uuid
import aiohttp
from dotenv import load_dotenv

load_dotenv()

BALA_BASE_URL = os.getenv("BALA_BASE_URL")
BALA_API_KEY = os.getenv("BALA_API_KEY")


class BalaAPI:
    def __init__(self):
        self.base_url = BALA_BASE_URL
        self.headers = {"X-API-Key": BALA_API_KEY}

    async def _get(self, path, params=None):
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{self.base_url}{path}", headers=self.headers, params=params, ssl=False) as r:
                return await r.json()

    async def _post(self, path, data, key=None):
        h = {**self.headers, "Content-Type": "application/json"}
        if key:
            h["Idempotency-Key"] = key
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{self.base_url}{path}", headers=h, json=data, ssl=False) as r:
                return await r.json()

    async def me(self):
        return await self._get("/me")

    async def catalog(self):
        return await self._get("/catalog")

    async def create_order(self, customer_ref, product_id, max_price, order_id=None):
        if not order_id:
            order_id = f"order_{uuid.uuid4().hex[:8]}"
        data = {"customer_ref": customer_ref, "product_id": product_id, "max_price_pcoins": max_price}
        return await self._post("/orders", data, key=order_id), order_id

    async def order_status(self, order_id):
        return await self._get("/orders/status", params={"request_id": order_id})

    async def customer_keys(self, customer_ref):
        return await self._get("/customers/keys", params={"customer_ref": customer_ref})


bala = BalaAPI()