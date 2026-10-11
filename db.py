import sqlite3

DB_PATH = "referrals.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            user_id INTEGER PRIMARY KEY,
            referrer_id INTEGER,
            first_name TEXT,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS rewards (
            user_id INTEGER PRIMARY KEY,
            total_referrals INTEGER DEFAULT 0,
            total_pcoins INTEGER DEFAULT 0,
            remaining_cents INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS balances (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def add_user(user_id, referrer_id=None, first_name="", username=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM referrals WHERE user_id = ?", (user_id,))
    if c.fetchone():
        conn.close()
        return False
    c.execute(
        "INSERT INTO referrals (user_id, referrer_id, first_name, username) VALUES (?, ?, ?, ?)",
        (user_id, referrer_id, first_name, username),
    )
    # Баланс жасаймыз
    c.execute("INSERT OR IGNORE INTO balances (user_id, balance) VALUES (?, 0)", (user_id,))
    conn.commit()
    conn.close()
    return True


def add_referral_reward(referrer_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT total_referrals, total_pcoins, remaining_cents FROM rewards WHERE user_id = ?",
        (referrer_id,),
    )
    row = c.fetchone()
    if row:
        total_refs, total_p, remaining = row
    else:
        total_refs, total_p, remaining = 0, 0, 0
        c.execute("INSERT INTO rewards (user_id) VALUES (?)", (referrer_id,))

    total_refs += 1
    remaining += 20

    pcoins_given = 0
    if remaining >= 100:
        pcoins_given = remaining // 100
        remaining = remaining % 100
        total_p += pcoins_given

    c.execute(
        "UPDATE rewards SET total_referrals = ?, total_pcoins = ?, remaining_cents = ? WHERE user_id = ?",
        (total_refs, total_p, remaining, referrer_id),
    )
    conn.commit()
    conn.close()

    # Реферал сыйақысын балансқа қосамыз
    if pcoins_given > 0:
        add_balance(referrer_id, pcoins_given)

    return pcoins_given


def get_referrals_count(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count


def get_referrals_list(user_id, limit=20):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT user_id, first_name, username, created_at FROM referrals WHERE referrer_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def get_rewards_stats(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT total_referrals, total_pcoins, remaining_cents FROM rewards WHERE user_id = ?",
        (user_id,),
    )
    row = c.fetchone()
    conn.close()
    return row if row else (0, 0, 0)


# ============ БАЛАНС ============

def get_balance(user_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT balance FROM balances WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0


def add_balance(user_id: int, amount: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM balances WHERE user_id = ?", (user_id,))
    if c.fetchone():
        c.execute(
            "UPDATE balances SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (amount, user_id),
        )
    else:
        c.execute("INSERT INTO balances (user_id, balance) VALUES (?, ?)", (user_id, amount))
    conn.commit()
    conn.close()


def subtract_balance(user_id: int, amount: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT balance FROM balances WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    current = row[0] if row else 0

    if current < amount:
        conn.close()
        return False

    c.execute(
        "UPDATE balances SET balance = balance - ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
        (amount, user_id),
    )
    conn.commit()
    conn.close()
    return True


def get_all_balances():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT b.user_id, b.balance, r.first_name, r.username FROM balances b LEFT JOIN referrals r ON b.user_id = r.user_id WHERE b.balance > 0 ORDER BY b.balance DESC LIMIT 50"
    )
    rows = c.fetchall()
    conn.close()
    return rows


# ============ АДМИН ============

def get_total_users() -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM referrals")
    count = c.fetchone()[0]
    conn.close()
    return count


def get_total_referrals() -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id IS NOT NULL")
    count = c.fetchone()[0]
    conn.close()
    return count


def get_all_users(limit: int = 50, offset: int = 0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT user_id, first_name, username, created_at FROM referrals ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def search_user(query: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    q = f"%{query}%"
    c.execute(
        "SELECT user_id, first_name, username FROM referrals WHERE CAST(user_id AS TEXT) LIKE ? OR username LIKE ? OR first_name LIKE ? LIMIT 10",
        (q, q, q),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def get_balance_stats() -> dict:
    """Жалпы статистика"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*), COALESCE(SUM(balance), 0) FROM balances WHERE balance > 0")
    row = c.fetchone()
    conn.close()
    return {"users_with_balance": row[0], "total_pcoins": row[1]}


init_db()