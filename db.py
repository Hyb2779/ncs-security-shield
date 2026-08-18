import sqlite3
import os
import time
import datetime
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'security.db')

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_conn() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS banned_hashes (
            hash TEXT PRIMARY KEY, reason TEXT, created_at REAL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at REAL,
            telegram_id TEXT, ip TEXT, user_agent TEXT, hash TEXT, result TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS admins (
            username TEXT PRIMARY KEY, password_hash TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS pending_verifications (
            telegram_id TEXT PRIMARY KEY, chat_id TEXT, created_at REAL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS welcome_messages (
            telegram_id TEXT PRIMARY KEY, chat_id TEXT, message_id TEXT, created_at REAL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id TEXT, chat_id TEXT,
            word TEXT, message_text TEXT, created_at REAL)''')

def add_violation(telegram_id, chat_id, word, message_text):
    with get_conn() as conn:
        conn.execute('INSERT INTO violations (telegram_id, chat_id, word, message_text, created_at) VALUES (?, ?, ?, ?, ?)',
                      (str(telegram_id), str(chat_id), word, message_text[:200], time.time()))

def get_violation_count(telegram_id, chat_id):
    with get_conn() as conn:
        row = conn.execute('SELECT COUNT(*) c FROM violations WHERE telegram_id = ? AND chat_id = ?',
                            (str(telegram_id), str(chat_id))).fetchone()
        return row['c'] if row else 0

def get_violations(limit=100):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM violations ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()]

def has_pending_welcome(telegram_id, within_seconds=60):
    # Sadece son X saniye icinde olusmus kaydi 'yakin zamanda gonderildi' say -
    # boylece kullanici cikip tekrar girerse (uzun sure sonra) yeniden dogrulanabilir,
    # sadece Telegram'in ayni katilim icin gonderdigi ani cift event'ler engellenir.
    with get_conn() as conn:
        row = conn.execute(
            'SELECT created_at FROM welcome_messages WHERE telegram_id = ?', (str(telegram_id),)
        ).fetchone()
        if not row:
            return False
        return (time.time() - row['created_at']) < within_seconds

def save_welcome_message(telegram_id, chat_id, message_id):
    with get_conn() as conn:
        conn.execute('INSERT OR REPLACE INTO welcome_messages (telegram_id, chat_id, message_id, created_at) VALUES (?, ?, ?, ?)',
                      (str(telegram_id), str(chat_id), str(message_id), time.time()))

def get_and_clear_welcome_message(telegram_id):
    with get_conn() as conn:
        row = conn.execute('SELECT chat_id, message_id FROM welcome_messages WHERE telegram_id = ?',
                            (str(telegram_id),)).fetchone()
        if row:
            conn.execute('DELETE FROM welcome_messages WHERE telegram_id = ?', (str(telegram_id),))
            return row['chat_id'], row['message_id']
        return None, None

def save_pending_chat(telegram_id, chat_id):
    with get_conn() as conn:
        conn.execute('INSERT OR REPLACE INTO pending_verifications (telegram_id, chat_id, created_at) VALUES (?, ?, ?)',
                      (str(telegram_id), str(chat_id), time.time()))

def get_pending_chat(telegram_id):
    with get_conn() as conn:
        row = conn.execute('SELECT chat_id FROM pending_verifications WHERE telegram_id = ?',
                            (str(telegram_id),)).fetchone()
        return row['chat_id'] if row else None

def is_banned(user_hash):
    with get_conn() as conn:
        return conn.execute('SELECT 1 FROM banned_hashes WHERE hash = ?', (user_hash,)).fetchone() is not None

def ban_hash(user_hash, reason='manuel'):
    with get_conn() as conn:
        conn.execute('INSERT OR REPLACE INTO banned_hashes (hash, reason, created_at) VALUES (?, ?, ?)',
                      (user_hash, reason, time.time()))

def unban_hash(user_hash):
    with get_conn() as conn:
        conn.execute('DELETE FROM banned_hashes WHERE hash = ?', (user_hash,))

def log_event(telegram_id, ip, user_agent, user_hash, result):
    with get_conn() as conn:
        conn.execute('''INSERT INTO events (created_at, telegram_id, ip, user_agent, hash, result)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (time.time(), str(telegram_id) if telegram_id else None, ip, user_agent, user_hash, result))

def latest_hash_for_telegram_id(telegram_id):
    with get_conn() as conn:
        row = conn.execute('SELECT hash FROM events WHERE telegram_id = ? ORDER BY created_at DESC LIMIT 1',
                            (str(telegram_id),)).fetchone()
        return row['hash'] if row else None

def get_stats():
    with get_conn() as conn:
        total_events = conn.execute('SELECT COUNT(*) c FROM events').fetchone()['c']
        total_banned = conn.execute('SELECT COUNT(*) c FROM banned_hashes').fetchone()['c']
        blocked = conn.execute("SELECT COUNT(*) c FROM events WHERE result = 'banned'").fetchone()['c']
        success = conn.execute("SELECT COUNT(*) c FROM events WHERE result = 'success'").fetchone()['c']
        since = time.time() - 86400
        last24 = conn.execute('SELECT COUNT(*) c FROM events WHERE created_at >= ?', (since,)).fetchone()['c']
        last24_blocked = conn.execute("SELECT COUNT(*) c FROM events WHERE created_at >= ? AND result='banned'", (since,)).fetchone()['c']
    return {'total_events': total_events, 'total_banned': total_banned, 'blocked_attempts': blocked,
            'success': success, 'last24_events': last24, 'last24_blocked': last24_blocked}

def get_hourly_chart(hours=24):
    since = time.time() - hours * 3600
    with get_conn() as conn:
        rows = conn.execute('SELECT created_at, result FROM events WHERE created_at >= ?', (since,)).fetchall()
    now_hour = int(time.time() // 3600)
    buckets = {now_hour - h: {'success': 0, 'banned': 0} for h in range(hours, -1, -1)}
    for r in rows:
        bh = int(r['created_at'] // 3600)
        if bh in buckets:
            buckets[bh]['banned' if r['result'] == 'banned' else 'success'] += 1
    labels, succ, ban = [], [], []
    for bh in sorted(buckets.keys()):
        labels.append(datetime.datetime.fromtimestamp(bh * 3600).strftime('%H:%M'))
        succ.append(buckets[bh]['success'])
        ban.append(buckets[bh]['banned'])
    return labels, succ, ban

def get_events(limit=50, search=None, result_filter=None):
    q = 'SELECT * FROM events WHERE 1=1'
    p = []
    if search:
        q += ' AND (telegram_id LIKE ? OR ip LIKE ? OR hash LIKE ?)'
        like = f'%{search}%'
        p += [like, like, like]
    if result_filter:
        q += ' AND result = ?'
        p.append(result_filter)
    q += ' ORDER BY created_at DESC LIMIT ?'
    p.append(limit)
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q, p).fetchall()]

def get_banned_list():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM banned_hashes ORDER BY created_at DESC').fetchall()]
