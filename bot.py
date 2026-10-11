import asyncio
import os
import re
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bala import bala
from balance import (
    MIN_PCOIN, MAX_PCOIN, RATE,
    PAYMENT_METHODS, ADMIN_ID,
    pcoin_to_tg,
)
from db import (
    add_user, get_referrals_count,
    get_referrals_list, add_referral_reward,
    get_rewards_stats,
    get_total_users, get_total_referrals,
    get_all_users, search_user,
    get_balance, add_balance, subtract_balance, get_all_balances,
    get_balance_stats,
)

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_LINK = os.getenv("CHANNEL_LINK")
BOT_USERNAME = os.getenv("BOT_USERNAME", "your_bot")

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS or user_id == ADMIN_ID


bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

CATALOG = []
CATEGORIES = {}
WAITING = {}


# ============ САНАТ ============
def extract_category(product: dict) -> str:
    display = product.get("display_name", "").strip()
    name = product.get("name", "").strip()

    if "—" in display:
        cat = display.split("—")[0].strip()
        if cat:
            return cat
    if " - " in display:
        cat = display.split(" - ")[0].strip()
        if cat:
            return cat

    gid = product.get("group_id", "").strip()
    if gid:
        part = gid.split("/")[-1]
        return part.replace("_", " ").upper()

    return name


def clean_product_name(name: str, cat_name: str) -> str:
    short = name
    if cat_name.upper() in short.upper():
        idx = short.upper().find(cat_name.upper())
        short = (short[:idx] + short[idx + len(cat_name):]).strip(" -—/")
    if not short.strip():
        short = name
    return short.strip()


def extract_duration(name: str) -> str:
    patterns = [
        r"(\d+\s*(?:DAY|DAYS|ЧАС|ЧАСОВ|ДЕНЬ|ДНЯ|ДНЕЙ|HOUR|HOURS|день|дня|дней|час|часов))",
        r"(\d+\s*(?:H|D|ч|д|х))",
    ]
    for pat in patterns:
        m = re.search(pat, name, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return "—"


# ============ КАТАЛОГ ============
async def load_catalog():
    global CATALOG, CATEGORIES
    try:
        data = await bala.catalog()
        CATALOG = data.get("products") or data.get("items") or []
        CATEGORIES = {}
        for p in CATALOG:
            cat = extract_category(p)
            CATEGORIES.setdefault(cat, []).append(p)
        CATEGORIES = dict(sorted(CATEGORIES.items()))
        print(f"✅ Catalog: {len(CATALOG)} тауар, {len(CATEGORIES)} санат")
    except Exception as e:
        print(f"❌ Catalog қате: {e}")


# ============ /start ============
@dp.message(F.text == "/start")
async def start(message: Message):
    await load_catalog()

    user = message.from_user
    args = message.text.split()
    referrer_id = None

    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1][4:])
            if referrer_id == user.id:
                referrer_id = None
        except ValueError:
            referrer_id = None

    is_new = add_user(
        user_id=user.id,
        referrer_id=referrer_id,
        first_name=user.first_name or "",
        username=user.username or "",
    )

    if is_new and referrer_id:
        pcoins_given = add_referral_reward(referrer_id)
        total_refs, total_p, remaining = get_rewards_stats(referrer_id)

        if pcoins_given > 0:
            msg = (
                f"🎉 <b>Жаңа реферал!</b>\n\n"
                f"👤 {user.first_name} сіздің сілтемеңіз арқылы кірді!\n\n"
                f"💰 Сізге <b>+{pcoins_given} Pcoin</b> берілді!\n\n"
                f"📊 Барлығы: <b>{total_refs}</b> шақыру, "
                f"<b>{total_p} Pcoin</b> табыс"
            )
        else:
            needed = 5 - (remaining // 20)
            msg = (
                f"🎉 <b>Жаңа реферал!</b>\n\n"
                f"👤 {user.first_name} сіздің сілтемеңіз арқылы кірді!\n\n"
                f"📊 Барлығы: <b>{total_refs}</b> шақыру\n"
                f"⏳ Тағы <b>{needed}</b> шақыру — 1 Pcoin аласыз!"
            )

        try:
            await bot.send_message(referrer_id, msg)
        except Exception:
            pass

    text = (
        "🔐 <b>Қол жеткізу шектелген</b>\n\n"
        "📢 Ботты қолдану үшін каналымызға тіркеліңіз:\n\n"
        "👇 Төмендегі батырманы басып, тіркеліңіз"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 Каналға тіркелу", url=CHANNEL_LINK, style="success")
    kb.button(text="✅ Мен тіркелдім", callback_data="check_sub", style="success")
    kb.adjust(1, 1)
    await message.answer(text, reply_markup=kb.as_markup())


@dp.callback_query(F.data == "check_sub")
async def check_sub(call: CallbackQuery):
    await show_menu(call)


# ============ МЕНЮ ============
async def show_menu(call: CallbackQuery):
    await call.message.delete()
    user_balance = get_balance(call.from_user.id)

    text = (
        "🏪 — <b>XERZZ KEYBOT</b> — 🏪\n\n"
        f"🔑 <i>Сәлем, {call.from_user.first_name}!</i>\n\n"
        f"💰 Балансыңыз: <b>{user_balance} Pcoin</b>\n\n"
        "🛒 Бөлімді таңдаңыз 👇"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="🛒 Дүкен", callback_data="shop", style="success")
    kb.button(text="💳 Баланс", callback_data="balance", style="danger")
    kb.button(text="📦 Тапсырыстарым", callback_data="orders", style="primary")
    kb.button(text="👤 Профилім", callback_data="profile", style="primary")
    kb.button(text="🎁 Реферал", callback_data="refer", style="danger")
    kb.button(text="📚 Нұсқаулық", callback_data="tutorial", style="primary")
    kb.button(text="🔗 Бөлісу", callback_data="share", style="primary")
    kb.button(text="❓ Көмек", callback_data="help", style="danger")
    kb.adjust(1, 2, 2, 2, 1)
    await call.message.answer(text, reply_markup=kb.as_markup())
    await call.answer()


# ============ SHOP ============
@dp.callback_query(F.data == "shop")
async def shop(call):
    await call.message.delete()
    if not CATEGORIES:
        await load_catalog()
    if not CATEGORIES:
        await call.message.answer("❌ Тауарлар табылмады")
        await call.answer()
        return

    user_balance = get_balance(call.from_user.id)

    text = (
        "🏪 <b>XERZZ KEYBOT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Балансыңыз: <b>{user_balance} Pcoin</b>\n\n"
        "⭐ <b>Өнімдер желісі</b>\n\n"
        "➠ 🔑 Премиум кілттер\n"
        "➠ 🔥 Лезде жеткізу\n"
        "➠ 🔒 Қауіпсіз төлем\n"
        "➠ 💎 24/7 Қолдау\n\n"
        "🔑 <b>Қалағаныңызды таңдаңыз</b> 👇"
    )
    kb = InlineKeyboardBuilder()
    for cat_name in CATEGORIES.keys():
        kb.button(text=cat_name, callback_data=f"cat_{cat_name}", style="success")
    kb.button(text="⬅️ Артқа", callback_data="back_menu", style="danger")
    kb.adjust(2)
    await call.message.answer(text, reply_markup=kb.as_markup())
    await call.answer()


@dp.callback_query(F.data.startswith("cat_"))
async def category_click(call):
    cat_name = call.data[4:]
    products = CATEGORIES.get(cat_name, [])
    if not products:
        await call.answer("❌ Өнімдер жоқ", show_alert=True)
        return

    await call.message.delete()
    lines = [f"🏪 <b>{cat_name}</b>\n", "📄 <b>ЖОСПАРЛАР МЕН БАҒАЛАР:</b>\n"]

    for p in products:
        name = p.get("name", "?")
        price = p.get("price_pcoins", 0)
        stock = p.get("stock")
        available = p.get("available", True)
        short = clean_product_name(name, cat_name)

        if stock is None:
            st = "Қоймада бар" if available else "Қоймада жоқ"
        elif stock > 0:
            st = f"Қоймада бар ({stock})"
        else:
            st = "Қоймада жоқ"

        lines.append(f"✅ <b>{short.upper()}</b>")
        lines.append(f"➠ 🔑 Қойма: {st}")
        lines.append(f"➠ 💰 Бағасы: {price} Pcoin\n")

    lines.append("🏪 <b>ЖОСПАРДЫ ТАҢДАҢЫЗ:</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    text = "\n".join(lines)

    kb = InlineKeyboardBuilder()
    for p in products:
        pid = p.get("id")
        name = p.get("name", "?")
        price = p.get("price_pcoins", 0)
        short = clean_product_name(name, cat_name)
        kb.button(text=f"{short} — {price} PC", callback_data=f"buy_{pid}_{price}", style="success")

    kb.button(text="⬅️ Артқа", callback_data="shop", style="danger")
    kb.adjust(1)

    if len(text) > 4000:
        text = f"🏪 <b>{cat_name}</b>\n━━━━━━━━━━━━━━━━━━━━\n🔑 <b>Тауарды таңдаңыз:</b>"

    await call.message.answer(text, reply_markup=kb.as_markup())
    await call.answer()


# ============ САТЫП АЛУ (баланс тексерумен) ============
@dp.callback_query(F.data.startswith("buy_"))
async def buy(call: CallbackQuery):
    parts = call.data.split("_")
    pid = parts[1]
    price = int(parts[2])
    user_id = call.from_user.id
    customer_ref = f"telegram_{user_id}"

    pshort, pcat = "?", "?"
    for p in CATALOG:
        if str(p.get("id")) == str(pid):
            pshort = p.get("name", "?")
            pcat = extract_category(p)
            break

    # ===== 1. БАЛАНС ТЕКСЕРУ =====
    user_balance = get_balance(user_id)

    if user_balance < price:
        missing = price - user_balance
        text = (
            "❌ <b>Баланс жетпейді!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🛒 <b>Тауар:</b> {pshort}\n"
            f"💰 <b>Керек:</b> {price} Pcoin\n"
            f"💳 <b>Сіздің баланс:</b> {user_balance} Pcoin\n"
            f"⚠️ <b>Жетпейді:</b> {missing} Pcoin\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💳 Балансыңызды толтырыңыз 👇"
        )
        kb = InlineKeyboardBuilder()
        kb.button(text="💳 Баланс толтыру", callback_data="balance", style="success")
        kb.button(text="⬅️ Артқа", callback_data="shop", style="danger")
        kb.adjust(1, 1)
        await call.message.edit_text(text, reply_markup=kb.as_markup())
        await call.answer()
        return

    # ===== 2. БАЛАНСТАН ҰСТАЙМЫЗ =====
    if not subtract_balance(user_id, price):
        await call.answer("❌ Баланс қатесі", show_alert=True)
        return

    # ===== 3. BALA API =====
    try:
        result, order_id = await bala.create_order(customer_ref, pid, price)
    except Exception as e:
        add_balance(user_id, price)  # Қайтарамыз
        await call.message.edit_text(f"❌ <b>Байланыс қатесі</b>\n\n<code>{e}</code>")
        await call.answer()
        return

    if not result.get("ok"):
        add_balance(user_id, price)
        error = result.get("error") or "Белгісіз қате"
        await call.message.edit_text(f"❌ <b>Қате</b>\n\n<code>{error}</code>")
        await call.answer()
        return

    order = result.get("order") or {}
    status = order.get("status", "unknown")
    state = order.get("state", "")
    key_value = order.get("key")

    if status in ["completed", "success"] or state == "success":
        if not key_value:
            add_balance(user_id, price)
            await call.message.edit_text("⚠️ <b>Кілт алынбады</b>\n\nБаланс қайтарылды.")
            await call.answer()
            return

        new_balance = get_balance(user_id)

        text = (
            "✅ <b>Сатып алу сәтті!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🛒 <b>Тауар:</b> {pshort}\n"
            f"📂 <b>Бөлім:</b> {pcat}\n"
            f"⏱ <b>Мерзімі:</b> {extract_duration(pshort)}\n"
            f"💰 <b>Бағасы:</b> {price} Pcoin\n"
            f"💳 <b>Қалған баланс:</b> {new_balance} Pcoin\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🔑 <b>Сіздің кілтіңіз:</b>\n"
            f"<code>{key_value}</code>\n\n"
            "📋 <i>Көшіру үшін басыңыз</i>"
        )
        kb = InlineKeyboardBuilder()
        kb.button(text="📋 Кілтті көшіру", copy_text={"text": str(key_value)}, style="primary")
        kb.button(text="🛒 Дүкенге", callback_data="shop", style="success")
        kb.button(text="⬅️ Артқа", callback_data="back_menu", style="danger")
        kb.adjust(1, 1, 1)
        await call.message.edit_text(text, reply_markup=kb.as_markup())
    else:
        add_balance(user_id, price)
        error = order.get("error_code") or status
        kb = InlineKeyboardBuilder()
        kb.button(text="⬅️ Артқа", callback_data="shop", style="danger")
        kb.adjust(1)
        await call.message.edit_text(
            f"⚠️ <b>Статус:</b> {status}\n<code>{error}</code>\n\n💰 Баланс қайтарылды",
            reply_markup=kb.as_markup()
        )

    await call.answer()


# ============ 👤 ПРОФИЛЬ ============
@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    user = call.from_user
    customer_ref = f"telegram_{user.id}"

    user_balance = get_balance(user.id)

    try:
        keys_data = await bala.customer_keys(customer_ref)
        keys = keys_data.get("keys") or []
        total_keys = len(keys)
    except Exception:
        total_keys = 0

    ref_count = get_referrals_count(user.id)
    _, total_p, _ = get_rewards_stats(user.id)

    caption = (
        "👤 <b>МЕНІҢ ПРОФИЛІМ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
        f"👤 <b>Аты:</b> {user.first_name or '—'}\n"
        f"📛 <b>Username:</b> @{user.username or 'жоқ'}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Менің балансым:</b> {user_balance} Pcoin\n"
        f"🔑 <b>Кілттер:</b> {total_keys} дана\n"
        f"🎁 <b>Рефералдар:</b> {ref_count} адам\n"
        f"💵 <b>Реферал табыс:</b> {total_p} Pcoin\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Баланс толтыру", callback_data="balance", style="success")
    kb.button(text="📦 Менің кілттерім", callback_data="orders", style="primary")
    kb.button(text="🎁 Реферал", callback_data="refer", style="danger")
    kb.button(text="🛒 Дүкенге", callback_data="shop", style="success")
    kb.button(text="⬅️ Артқа", callback_data="back_menu", style="danger")
    kb.adjust(1, 1, 1, 1, 1)

    try:
        photos = await bot.get_user_profile_photos(user.id, limit=1)
        if photos.total_count > 0:
            await call.message.delete()
            await call.message.answer_photo(
                photo=photos.photos[0][-1].file_id,
                caption=caption,
                reply_markup=kb.as_markup(),
            )
            await call.answer()
            return
    except Exception:
        pass

    await call.message.edit_text(caption, reply_markup=kb.as_markup())
    await call.answer()


# ============ 🎁 РЕФЕРАЛ ============
@dp.callback_query(F.data == "refer")
async def refer(call: CallbackQuery):
    user_id = call.from_user.id
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

    ref_count = get_referrals_count(user_id)
    total_refs, total_p, remaining = get_rewards_stats(user_id)

    filled = int((remaining / 100) * 10)
    progress_bar = "█" * filled + "░" * (10 - filled)

    recent = get_referrals_list(user_id, limit=5)
    if recent:
        recent_text = "\n".join(
            f"   • {r[1] or 'Аты жоқ'} (@{r[2] or '—'})"
            for r in recent
        )
    else:
        recent_text = "   <i>Әзірге ешкім жоқ</i>"

    text = (
        "🎁 <b>РЕФЕРАЛ ЖҮЙЕСІ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔗 <b>Сіздің сілтемеңіз:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        "📊 <b>Статистика:</b>\n"
        f"   👥 Шақырғандар: <b>{ref_count}</b>\n"
        f"   💰 Табыс: <b>{total_p} Pcoin</b>\n"
        f"   🎁 Әр шақыру: <b>+0.2 Pcoin</b>\n\n"
        f"📈 <b>Кэш:</b> {progress_bar} {remaining}%\n"
        "   <i>(5 шақыру = 1 Pcoin)</i>\n\n"
        "👥 <b>Соңғы шақырғандар:</b>\n"
        f"{recent_text}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Сілтемеңізді досыңызға жіберіңіз. Ол тіркелсе — сізге 0.2 Pcoin!</i>"
    )

    kb = InlineKeyboardBuilder()
    kb.button(
        text="📤 Сілтемемен бөлісу",
        url=f"https://t.me/share/url?url={ref_link}&text=🎁 XERZZ KEYBOT - премиум кілттер!",
        style="success"
    )
    kb.button(
        text="📋 Сілтемені көшіру",
        copy_text={"text": ref_link},
        style="primary"
    )
    kb.button(text="⬅️ Артқа", callback_data="back_menu", style="danger")
    kb.adjust(1, 1, 1)

    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await call.answer()


# ============ 💳 БАЛАНС ============
@dp.callback_query(F.data == "balance")
async def balance(call: CallbackQuery):
    user_balance = get_balance(call.from_user.id)

    text = (
        "💳 <b>БАЛАНС ТОЛТЫРУ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Сіздің балансыңыз: <b>{user_balance} Pcoin</b>\n\n"
        f"📊 Мин: <b>{MIN_PCOIN} Pcoin</b> · Макс: <b>{MAX_PCOIN} Pcoin</b>\n"
        f"💱 Курс: <b>1 Pcoin = {RATE} TG</b>\n\n"
        "👇 Толтыру сомасын таңдаңыз:"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 200 Pcoin — 1600 TG", callback_data="dep_200", style="success")
    kb.button(text="💰 250 Pcoin — 2000 TG", callback_data="dep_250", style="success")
    kb.button(text="💰 500 Pcoin — 4000 TG", callback_data="dep_500", style="success")
    kb.button(text="💰 1000 Pcoin — 8000 TG", callback_data="dep_1000", style="success")
    kb.button(text="✍️ Custom сомасы", callback_data="dep_custom", style="primary")
    kb.button(text="⬅️ Артқа", callback_data="back_menu", style="danger")
    kb.adjust(1, 1, 1, 1, 1, 1)
    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await call.answer()


@dp.callback_query(F.data.startswith("dep_"))
async def deposit_choose(call: CallbackQuery):
    action = call.data[4:]

    if action == "custom":
        text = (
            "✍️ <b>CUSTOM СОМА</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Мин: <b>{MIN_PCOIN} Pcoin</b>\n"
            f"📊 Макс: <b>{MAX_PCOIN} Pcoin</b>\n"
            f"💱 Курс: <b>1 Pcoin = {RATE} TG</b>\n\n"
            f"✍️ Қанша <b>Pcoin</b> алғыңыз келеді?\n"
            f"<i>Мысалы: 300</i>"
        )
        kb = InlineKeyboardBuilder()
        kb.button(text="❌ Болдырмау", callback_data="balance", style="danger")
        kb.adjust(1)
        await call.message.edit_text(text, reply_markup=kb.as_markup())
        await call.answer()
        WAITING[call.from_user.id] = "custom_pcoin"
        return

    try:
        pcoin = int(action)
    except ValueError:
        await call.answer("❌ Қате", show_alert=True)
        return

    await show_payment_choice(call, pcoin)


@dp.message(F.text.regexp(r"^\d+$"))
async def custom_amount(message: Message):
    user_id = message.from_user.id
    if WAITING.get(user_id) != "custom_pcoin":
        return

    try:
        pcoin = int(message.text)
    except ValueError:
        return

    if pcoin < MIN_PCOIN or pcoin > MAX_PCOIN:
        await message.answer(
            f"❌ Сома <b>{MIN_PCOIN}</b> және <b>{MAX_PCOIN}</b> Pcoin арасында болуы керек"
        )
        return

    WAITING[user_id] = None
    await show_payment_choice_msg(message, pcoin)


async def show_payment_choice(call: CallbackQuery, pcoin: int):
    tg = pcoin_to_tg(pcoin)
    text = (
        "💳 <b>ТӨЛЕМ ӘДІСІН ТАҢДАҢЫЗ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Сома: <b>{pcoin} Pcoin</b>\n"
        f"💵 Төлем: <b>{tg} TG</b>\n\n"
        "👇 Төлем әдісін таңдаңыз:"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="🏦 HALYK BANK", callback_data=f"pay_halyk_{pcoin}", style="success")
    kb.button(text="🏦 KASPI BANK", callback_data=f"pay_kaspi_{pcoin}", style="success")
    kb.button(text="⬅️ Артқа", callback_data="balance", style="danger")
    kb.adjust(1, 1, 1)
    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await call.answer()


async def show_payment_choice_msg(message: Message, pcoin: int):
    tg = pcoin_to_tg(pcoin)
    text = (
        "💳 <b>ТӨЛЕМ ӘДІСІН ТАҢДАҢЫЗ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Сома: <b>{pcoin} Pcoin</b>\n"
        f"💵 Төлем: <b>{tg} TG</b>\n\n"
        "👇 Төлем әдісін таңдаңыз:"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="🏦 HALYK BANK", callback_data=f"pay_halyk_{pcoin}", style="success")
    kb.button(text="🏦 KASPI BANK", callback_data=f"pay_kaspi_{pcoin}", style="success")
    kb.button(text="⬅️ Артқа", callback_data="balance", style="danger")
    kb.adjust(1, 1, 1)
    await message.answer(text, reply_markup=kb.as_markup())


@dp.callback_query(F.data.startswith("pay_"))
async def payment_method(call: CallbackQuery):
    parts = call.data.split("_")
    method = parts[1]
    pcoin = int(parts[2])
    tg = pcoin_to_tg(pcoin)

    pm = PAYMENT_METHODS.get(method)
    if not pm:
        await call.answer("❌ Қате", show_alert=True)
        return

    text = (
        f"🏦 <b>{pm['name']}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Сома: <b>{pcoin} Pcoin</b>\n"
        f"💵 Төлем: <b>{tg} TG</b>\n\n"
        f"💳 <b>Карта нөмірі:</b>\n"
        f"<code>{pm['card']}</code>\n\n"
        f"👤 <b>Алушы:</b> {pm['holder']}\n\n"
        "📸 <b>Төлем жасаған соң:</b>\n"
        "1️⃣ Осы соманы жоғарыдағы картаға аударыңыз\n"
        "2️⃣ Чекті (скриншот) осы чатқа жіберіңіз\n"
        "3️⃣ Админ тексеріп, балансыңызды толтырады ✅"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Картаны көшіру", copy_text={"text": str(pm['card'])}, style="primary")
    kb.button(text="✅ Чек жібердім", callback_data=f"receipt_{pcoin}_{tg}", style="success")
    kb.button(text="⬅️ Артқа", callback_data="balance", style="danger")
    kb.adjust(1, 1, 1)
    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await call.answer()


@dp.callback_query(F.data.startswith("receipt_"))
async def receipt_ask(call: CallbackQuery):
    parts = call.data.split("_")
    pcoin = int(parts[1])
    tg = int(parts[2])

    text = (
        "📸 <b>ЧЕКТІ ЖІБЕРІҢІЗ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Сома: <b>{pcoin} Pcoin</b>\n"
        f"💵 Төлем: <b>{tg} TG</b>\n\n"
        "📎 Төлем чегін (скриншот немесе фото) осы чатқа жіберіңіз.\n\n"
        "⚠️ <i>Чексіз өтінім қабылданбайды</i>"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Болдырмау", callback_data="balance", style="danger")
    kb.adjust(1)
    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await call.answer()

    WAITING[call.from_user.id] = {
        "action": "receipt",
        "pcoin": pcoin,
        "tg": tg,
    }


# ============ ЧЕК ҚАБЫЛДАУ ============
@dp.message(F.photo | F.document)
async def get_receipt(message: Message):
    user_id = message.from_user.id
    wait = WAITING.get(user_id)

    if not wait or not isinstance(wait, dict) or wait.get("action") != "receipt":
        return

    pcoin = wait["pcoin"]
    tg = wait["tg"]

    try:
        admin_text = (
            "🔔 <b>ЖАҢА ТОЛТЫРУ ӨТІНІМІ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <a href='tg://user?id={user_id}'>{message.from_user.first_name}</a>\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"💰 Pcoin: <b>{pcoin}</b>\n"
            f"💵 TG: <b>{tg}</b>\n\n"
            "👇 Растау немесе қабылдамау:"
        )
        admin_kb = InlineKeyboardBuilder()
        admin_kb.button(
            text="✅ Растау",
            callback_data=f"approve_{user_id}_{pcoin}",
            style="success"
        )
        admin_kb.button(
            text="❌ Қабылдамау",
            callback_data=f"reject_{user_id}",
            style="danger"
        )
        admin_kb.adjust(2)

        if message.photo:
            await bot.send_photo(
                ADMIN_ID,
                photo=message.photo[-1].file_id,
                caption=admin_text,
                reply_markup=admin_kb.as_markup(),
            )
        elif message.document:
            await bot.send_document(
                ADMIN_ID,
                document=message.document.file_id,
                caption=admin_text,
                reply_markup=admin_kb.as_markup(),
            )

        await message.answer(
            "✅ <b>Чек қабылданды!</b>\n\n"
            "⏳ Админ тексереді. Біраз күте тұрыңыз..."
        )
    except Exception as e:
        await message.answer(f"❌ Қате: {e}")

    WAITING[user_id] = None


@dp.callback_query(F.data.startswith("approve_"))
async def approve(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Сіз админ емессіз", show_alert=True)
        return

    parts = call.data.split("_")
    user_id = int(parts[1])
    pcoin = int(parts[2])

    add_balance(user_id, pcoin)
    new_balance = get_balance(user_id)

    try:
        await bot.send_message(
            user_id,
            f"✅ <b>Баланс толтырылды!</b>\n\n"
            f"💰 +<b>{pcoin} Pcoin</b>\n"
            f"💳 Жаңа баланс: <b>{new_balance} Pcoin</b>\n\n"
            f"Рахмет! 🎉"
        )
    except Exception:
        pass

    try:
        await call.message.edit_caption(
            caption=(call.message.caption or "") + f"\n\n✅ <b>РАСТАЛДЫ</b>\n💰 +{pcoin} Pcoin"
        )
    except Exception:
        pass
    await call.answer("✅ Расталды")


@dp.callback_query(F.data.startswith("reject_"))
async def reject(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Сіз админ емессіз", show_alert=True)
        return

    user_id = int(call.data.split("_")[1])

    try:
        await bot.send_message(
            user_id,
            "❌ <b>Өтінім қабылданбады</b>\n\n"
            "Чек дұрыс емес немесе төлем табылмады.\n"
            "Қолдау қызметіне хабарласыңыз."
        )
    except Exception:
        pass

    try:
        await call.message.edit_caption(
            caption=(call.message.caption or "") + "\n\n❌ <b>ҚАБЫЛДАНБАДЫ</b>"
        )
    except Exception:
        pass
    await call.answer("❌ Қабылданбады")


# ============ 📦 ТАПСЫРЫСТАР ============
@dp.callback_query(F.data == "orders")
async def orders(call: CallbackQuery):
    customer_ref = f"telegram_{call.from_user.id}"
    try:
        data = await bala.customer_keys(customer_ref)
    except Exception as e:
        await call.answer(f"❌ {e}", show_alert=True)
        return

    if not data.get("ok"):
        await call.answer("❌ API қате", show_alert=True)
        return

    keys = data.get("keys") or []
    if not keys:
        text = (
            "📦 <b>Менің тапсырыстарым</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "❌ <i>Сізде әзірге кілттер жоқ</i>"
        )
    else:
        lines = [f"📦 <b>Сіздің кілттеріңіз ({len(keys)}):</b>\n"]
        for i, k in enumerate(keys[:10], 1):
            key_val = k.get("key", "—")
            pid = k.get("product_id", "?")
            created = k.get("created_at", "—")
            pname, pcat, pdur = "?", "?", "—"
            for p in CATALOG:
                if str(p.get("id")) == str(pid):
                    pname = p.get("name", "?")
                    pcat = extract_category(p)
                    pdur = extract_duration(pname)
                    break
            lines.append(
                f"<b>{i}. 🔑 <code>{key_val}</code></b>\n"
                f"    🛒 {pname}\n"
                f"    📂 {pcat}\n"
                f"    ⏱ {pdur}\n"
                f"    📅 {created}\n"
            )
        text = "\n".join(lines)

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Артқа", callback_data="back_menu", style="danger")
    kb.adjust(1)
    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await call.answer()


# ============ 📚 НҰСҚАУЛЫҚ ============
@dp.callback_query(F.data == "tutorial")
async def tutorial(call: CallbackQuery):
    text = (
        "📚 <b>НҰСҚАУЛЫҚ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ <b>Баланс толтыру:</b>\n"
        "   💳 Баланс → соманы таңдаңыз → картаға төлеңіз → чек жіберіңіз\n\n"
        "2️⃣ <b>Сатып алу:</b>\n"
        "   🛒 Дүкен → санат → өнім → батырманы басыңыз → кілт аласыз\n\n"
        "3️⃣ <b>Кілтті көшіру:</b>\n"
        "   📋 Кілтті көшіру батырмасын басыңыз\n\n"
        "4️⃣ <b>Реферал:</b>\n"
        "   🎁 Реферал → сілтемені досқа жіберіңіз → 0.2 Pcoin аласыз"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Артқа", callback_data="back_menu", style="danger")
    kb.adjust(1)
    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await call.answer()


@dp.callback_query(F.data == "share")
async def share(call: CallbackQuery):
    ref_link = f"https://t.me/{BOT_USERNAME}"
    text = (
        "🔗 <b>БӨЛІСУ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Ботты досыңызбен бөлісіңіз:\n\n"
        f"<code>{ref_link}</code>"
    )
    kb = InlineKeyboardBuilder()
    kb.button(
        text="📤 Бөлісу",
        url=f"https://t.me/share/url?url={ref_link}&text=🎁 XERZZ KEYBOT - премиум кілттер!",
        style="success"
    )
    kb.button(text="⬅️ Артқа", callback_data="back_menu", style="danger")
    kb.adjust(1, 1)
    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await call.answer()


@dp.callback_query(F.data == "help")
async def help_cmd(call: CallbackQuery):
    text = (
        "❓ <b>КӨМЕК</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔹 Сұрақтарыңыз болса, қолдау қызметіне хабарласыңыз:\n\n"
        "👤 <b>Админ:</b> @xerzzplayz\n\n"
        "⏰ <b>Жұмыс уақыты:</b> 24/7"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Артқа", callback_data="back_menu", style="danger")
    kb.adjust(1)
    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await call.answer()


# ============ 🛡️ АДМИН ПАНЕЛЬ ============
@dp.message(F.text == "/admin")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Сіз админ емессіз")
        return

    total_users = get_total_users()
    total_refs = get_total_referrals()
    stats = get_balance_stats()

    try:
        me = await bala.me()
        bal = me.get("balance_pcoins", 0)
    except Exception:
        bal = "?"

    text = (
        "🛡️ <b>АДМИН ПАНЕЛЬ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Пайдаланушылар: <b>{total_users}</b>\n"
        f"🎁 Рефералдар: <b>{total_refs}</b>\n"
        f"💰 Пайдаланушылар балансы: <b>{stats['total_pcoins']} Pcoin</b>\n"
        f"👤 Балансы бар: <b>{stats['users_with_balance']}</b> адам\n"
        f"🏦 BALA баланс: <b>{bal} Pcoin</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 Бөлімді таңдаңыз:"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="👥 Пайдаланушылар", callback_data="adm_users", style="primary")
    kb.button(text="🔍 Іздеу", callback_data="adm_search", style="primary")
    kb.button(text="📊 Статистика", callback_data="adm_stats", style="success")
    kb.button(text="💰 Баланстар", callback_data="adm_balances", style="success")
    kb.button(text="📢 Хабарлама", callback_data="adm_broadcast", style="danger")
    kb.button(text="🔑 Каталог", callback_data="adm_catalog", style="primary")
    kb.button(text="❌ Жабу", callback_data="adm_close", style="danger")
    kb.adjust(1, 2, 2, 2, 1)
    await message.answer(text, reply_markup=kb.as_markup())


@dp.callback_query(F.data == "adm_close")
async def adm_close(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await call.message.delete()
    await call.answer()


@dp.callback_query(F.data == "adm_users")
async def adm_users(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    users = get_all_users(limit=20)

    if not users:
        text = "👥 <b>Пайдаланушылар</b>\n\n❌ Ешкім жоқ"
    else:
        lines = [f"👥 <b>Соңғы 20 пайдаланушы:</b>\n"]
        for u in users:
            uid, name, username, created = u
            ub = get_balance(uid)
            lines.append(
                f"• <code>{uid}</code> — {name or '—'}"
                f"{' (@' + username + ')' if username else ''}\n"
                f"  💰 {ub} Pcoin · 📅 {created[:10] if created else '—'}"
            )
        text = "\n".join(lines)

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Артқа", callback_data="adm_back", style="danger")
    kb.adjust(1)
    try:
        await call.message.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        await call.message.answer(text, reply_markup=kb.as_markup())
    await call.answer()


@dp.callback_query(F.data == "adm_search")
async def adm_search_ask(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    text = (
        "🔍 <b>ПАЙДАЛАНУШЫНЫ ІЗДЕУ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 ID, username немесе ат жазыңыз:\n"
        "<i>Мысалы: 8292802484</i>"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Артқа", callback_data="adm_back", style="danger")
    kb.adjust(1)
    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await call.answer()

    WAITING[call.from_user.id] = "adm_search"


@dp.message(F.text.regexp(r"^[\w@]+$"))
async def adm_search_result(message: Message):
    user_id = message.from_user.id
    if WAITING.get(user_id) != "adm_search":
        return
    if not is_admin(user_id):
        return

    WAITING[user_id] = None
    query = message.text.strip().replace("@", "")
    results = search_user(query)

    if not results:
        await message.answer("❌ Ешкім табылмады")
        return

    lines = [f"🔍 <b>Іздеу нәтижесі:</b>\n"]
    for r in results:
        uid, name, username = r
        ub = get_balance(uid)
        lines.append(f"• <code>{uid}</code> — {name or '—'} (@{username or '—'})\n  💰 {ub} Pcoin")

    text = "\n".join(lines)
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Артқа", callback_data="adm_back", style="danger")
    kb.adjust(1)
    await message.answer(text, reply_markup=kb.as_markup())


@dp.callback_query(F.data == "adm_stats")
async def adm_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    total_users = get_total_users()
    total_refs = get_total_referrals()
    stats = get_balance_stats()

    try:
        me = await bala.me()
        bal = me.get("balance_pcoins", 0)
    except Exception:
        bal = "?"

    text = (
        "📊 <b>СТАТИСТИКА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Барлық пайдаланушылар: <b>{total_users}</b>\n"
        f"🎁 Реферал арқылы келгендер: <b>{total_refs}</b>\n"
        f"💰 Пайдаланушылар балансы: <b>{stats['total_pcoins']} Pcoin</b>\n"
        f"👤 Балансы бар: <b>{stats['users_with_balance']}</b> адам\n"
        f"🏦 BALA баланс: <b>{bal} Pcoin</b>\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Жаңарту", callback_data="adm_stats", style="success")
    kb.button(text="⬅️ Артқа", callback_data="adm_back", style="danger")
    kb.adjust(1, 1)
    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await call.answer()


@dp.callback_query(F.data == "adm_balances")
async def adm_balances(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    balances = get_all_balances()

    if not balances:
        text = "💰 <b>Баланстар</b>\n\n❌ Ешкімде баланс жоқ"
    else:
        lines = [f"💰 <b>Топ 50 баланстар:</b>\n"]
        total = 0
        for b in balances:
            uid, bal, name, username = b
            total += bal
            lines.append(f"• <code>{uid}</code> — <b>{bal} Pcoin</b> — {name or '—'}")
        lines.append(f"\n💰 <b>Жалпы:</b> {total} Pcoin")
        text = "\n".join(lines)

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Артқа", callback_data="adm_back", style="danger")
    kb.adjust(1)
    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await call.answer()


@dp.callback_query(F.data == "adm_broadcast")
async def adm_broadcast_ask(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    text = (
        "📢 <b>ХАБАРЛАМА ЖІБЕРУ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 Барлық пайдаланушыларға жіберілетін хабарлама мәтінін жазыңыз:"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Артқа", callback_data="adm_back", style="danger")
    kb.adjust(1)
    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await call.answer()

    WAITING[call.from_user.id] = "adm_broadcast"


@dp.message(F.text)
async def adm_broadcast_send(message: Message):
    user_id = message.from_user.id
    if WAITING.get(user_id) != "adm_broadcast":
        return
    if not is_admin(user_id):
        return

    WAITING[user_id] = None
    text_to_send = message.text

    users = get_all_users(limit=10000)
    success = 0
    failed = 0

    status_msg = await message.answer("⏳ Жіберілуде...")

    for u in users:
        try:
            await bot.send_message(u[0], text_to_send)
            success += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        "✅ <b>Хабарлама жіберілді!</b>\n\n"
        f"✅ Сәтті: <b>{success}</b>\n"
        f"❌ Қате: <b>{failed}</b>"
    )


@dp.callback_query(F.data == "adm_catalog")
async def adm_catalog(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    try:
        data = await bala.catalog()
        products = data.get("products") or []
        total = len(products)
    except Exception:
        total = 0

    text = (
        "🔑 <b>КАТАЛОГ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 Барлық өнімдер: <b>{total}</b>\n"
        f"📂 Санаттар: <b>{len(CATEGORIES)}</b>\n\n"
        "📋 <b>Санаттар тізімі:</b>\n"
    )
    for cat, items in list(CATEGORIES.items())[:15]:
        text += f"• {cat} ({len(items)})\n"

    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Жаңарту", callback_data="adm_catalog_refresh", style="success")
    kb.button(text="⬅️ Артқа", callback_data="adm_back", style="danger")
    kb.adjust(1, 1)
    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await call.answer()


@dp.callback_query(F.data == "adm_catalog_refresh")
async def adm_catalog_refresh(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return
    await load_catalog()
    await adm_catalog(call)


@dp.callback_query(F.data == "adm_back")
async def adm_back(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return

    total_users = get_total_users()
    total_refs = get_total_referrals()
    stats = get_balance_stats()

    try:
        me = await bala.me()
        bal = me.get("balance_pcoins", 0)
    except Exception:
        bal = "?"

    text = (
        "🛡️ <b>АДМИН ПАНЕЛЬ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Пайдаланушылар: <b>{total_users}</b>\n"
        f"🎁 Рефералдар: <b>{total_refs}</b>\n"
        f"💰 Пайдаланушылар балансы: <b>{stats['total_pcoins']} Pcoin</b>\n"
        f"👤 Балансы бар: <b>{stats['users_with_balance']}</b> адам\n"
        f"🏦 BALA баланс: <b>{bal} Pcoin</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 Бөлімді таңдаңыз:"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="👥 Пайдаланушылар", callback_data="adm_users", style="primary")
    kb.button(text="🔍 Іздеу", callback_data="adm_search", style="primary")
    kb.button(text="📊 Статистика", callback_data="adm_stats", style="success")
    kb.button(text="💰 Баланстар", callback_data="adm_balances", style="success")
    kb.button(text="📢 Хабарлама", callback_data="adm_broadcast", style="danger")
    kb.button(text="🔑 Каталог", callback_data="adm_catalog", style="primary")
    kb.button(text="❌ Жабу", callback_data="adm_close", style="danger")
    kb.adjust(1, 2, 2, 2, 1)
    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await call.answer()


# ============ BACK ============
@dp.callback_query(F.data == "back_menu")
async def back_menu(call):
    await show_menu(call)


# ============ ҚАЛҒАНДАРЫ ============
@dp.callback_query()
async def other(call: CallbackQuery):
    await call.answer()


# ============ ІСКЕ ҚОСУ ============
async def main():
    await load_catalog()
    try:
        me = await bala.me()
        print(f"✅ BALA API OK: balance={me.get('balance_pcoins')} pcoins")
    except Exception as e:
        print(f"⚠️ BALA API қате: {e}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())