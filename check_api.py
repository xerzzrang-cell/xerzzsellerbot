import asyncio
import json
from bala import bala


async def main():
    print("=" * 60)
    print("1) /me — аккаунт")
    print("=" * 60)
    me = await bala.me()
    print(json.dumps(me, indent=2, ensure_ascii=False))

    print("\n" + "=" * 60)
    print("2) /catalog — тауарлар (АЛҒАШҚЫ 5)")
    print("=" * 60)
    data = await bala.catalog()
    products = data.get("products") or data.get("items") or []
    print(f"Барлығы: {len(products)} тауар\n")
    for p in products[:5]:
        print(json.dumps(p, indent=2, ensure_ascii=False))
        print("-" * 40)

    # Барлық кілттерді жинаймыз
    print("\n" + "=" * 60)
    print("3) Барлық өрістер (кілттер)")
    print("=" * 60)
    keys = set()
    for p in products:
        keys.update(p.keys())
    print(sorted(keys))


asyncio.run(main())