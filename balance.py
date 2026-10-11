import os
from dotenv import load_dotenv

load_dotenv()

# ============ БАПТАУ ============
MIN_PCOIN = 200
MAX_PCOIN = 2000
RATE = 8  # 1 Pcoin = 8 TG

# Төлем әдістері
PAYMENT_METHODS = {
    "halyk": {
        "name": "HALYK BANK",
        "card": "4003 0351 4893 1012",  # ← ӨЗ КАРТАҢЫЗДЫ ҚОЙЫҢЫЗ
        "holder": "БЕРДИБЕК ҚАНАТ",         # ← ӨЗ АТЫҢЫЗДЫ ҚОЙЫҢЫЗ
    },
    "kaspi": {
        "name": "KASPI BANK",
        "card": "4400 4303 7747 3134",  # ← ӨЗ КАРТАҢЫЗДЫ ҚОЙЫҢЫЗ
        "holder": "БЕРДИБЕК ҚАНАТ",         # ← ӨЗ АТЫҢЫЗДЫ ҚОЙЫҢЫЗ
    },
}

# Админдер (чек жіберілетін)
ADMIN_ID = 8292802484  # ← ӨЗ TELEGRAM ID-ІҢІЗДІ ҚОЙЫҢЫЗ


def pcoin_to_tg(pcoin: int) -> int:
    """Pcoin → TG айналдыру"""
    return pcoin * RATE


def tg_to_pcoin(tg: int) -> int:
    """TG → Pcoin айналдыру"""
    return tg // RATE