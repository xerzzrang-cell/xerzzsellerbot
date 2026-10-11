import asyncio
from bala import bala


async def main():
    print("=" * 60)
    print("1) /me — баланс")
    print("=" * 60)
    me = await bala.me()
    print(f"💰 Balance: {me.get('balance_pcoins')} Pcoin")
    print(f"🚫 Banned: {me.get('banned')}")
    print(f"✅ API enabled: {me.get('api_enabled')}")

    print("\n" + "=" * 60)
    print("2) /catalog — өнімді табу (id=109)")
    print("=" * 60)
    data = await bala.catalog()
    products = data.get("products") or data.get("items") or []
    p = next((x for x in products if str(x.get("id")) == "109"), None)
    if p:
        print(f"ID: {p.get('id')}")
        print(f"Name: {p.get('name')}")
        print(f"Price: {p.get('price_pcoins')} Pcoin")
        print(f"Available: {p.get('available')}")
        print(f"Stock: {p.get('stock')}")
    else:
        print("❌ ID=109 табылмады")

    print("\n" + "=" * 60)
    print("3) POST /orders — сатып алуға әрекет")
    print("=" * 60)
    customer_ref = "telegram_123456789"  # тест ID
    pid = "109"
    price = 49

    print(f"📤 Жіберілетін деректер:")
    print(f"   customer_ref: {customer_ref}")
    print(f"   product_id: {pid}")
    print(f"   max_price_pcoins: {price}")

    try:
        result, order_id = await bala.create_order(customer_ref, pid, price)
        print(f"\n🆔 Order ID: {order_id}")
        print(f"\n📥 API ЖАУАБЫ:")
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")

    print("\n" + "=" * 60)
    print("4) Кілттерді тексеру")
    print("=" * 60)
    try:
        keys = await bala.customer_keys(customer_ref)
        print(f"📥 Keys response:")
        import json
        print(json.dumps(keys, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")


asyncio.run(main())