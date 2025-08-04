import requests
import time
import sqlite3
import traceback
from datetime import datetime

# --- بيانات البوت ---
TOKEN = "BICAJ0FJOPETHGEECVKMHEAUBHPXMTVNNPRTPMJBKOAVHUUHTCWARAKANKIVFRDA"
API_URL = f"https://botapi.rubika.ir/v3/{TOKEN}"
OWNER_ID = "abas_frhani_313"

# --- إعداد قاعدة البيانات ---
DB_FILE = "bot_data.db"
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

# إنشاء الجداول الضرورية
cursor.execute("""
CREATE TABLE IF NOT EXISTS bot_status (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    active INTEGER DEFAULT 1,
    last_update_id INTEGER DEFAULT 0
)""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS admins (
    user_id TEXT PRIMARY KEY
)""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS warnings (
    user_id TEXT PRIMARY KEY,
    count INTEGER DEFAULT 0
)""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS banned_users (
    user_id TEXT PRIMARY KEY
)""")

# تأكد من صف bot_status واحد فقط
cursor.execute("INSERT OR IGNORE INTO bot_status (id, active, last_update_id) VALUES (1, 1, 0)")
conn.commit()

# --- دوال مساعدة ---

def log(text):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] {text}"
    print(line)
    with open("bot_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")

def get_bot_status():
    cursor.execute("SELECT active FROM bot_status WHERE id=1")
    row = cursor.fetchone()
    return row and row[0] == 1

def set_bot_status(active):
    cursor.execute("UPDATE bot_status SET active=? WHERE id=1", (1 if active else 0,))
    conn.commit()

def get_last_update_id():
    cursor.execute("SELECT last_update_id FROM bot_status WHERE id=1")
    row = cursor.fetchone()
    return row[0] if row else 0

def set_last_update_id(update_id):
    cursor.execute("UPDATE bot_status SET last_update_id=? WHERE id=1", (update_id,))
    conn.commit()

def is_admin(user_id):
    if user_id == OWNER_ID:
        return True
    cursor.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

def add_admin(user_id):
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
    conn.commit()

def remove_admin(user_id):
    cursor.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
    conn.commit()

def is_banned(user_id):
    cursor.execute("SELECT 1 FROM banned_users WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

def ban_user(user_id):
    cursor.execute("INSERT OR IGNORE INTO banned_users (user_id) VALUES (?)", (user_id,))
    conn.commit()

def unban_user(user_id):
    cursor.execute("DELETE FROM banned_users WHERE user_id=?", (user_id,))
    conn.commit()

def add_warning(user_id):
    cursor.execute("SELECT count FROM warnings WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if row:
        count = row[0] + 1
        cursor.execute("UPDATE warnings SET count=? WHERE user_id=?", (count, user_id))
    else:
        count = 1
        cursor.execute("INSERT INTO warnings (user_id, count) VALUES (?, ?)", (user_id, count))
    conn.commit()
    return count

def reset_warnings(user_id):
    cursor.execute("DELETE FROM warnings WHERE user_id=?", (user_id,))
    conn.commit()

def send_message(chat_id, text):
    try:
        resp = requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
        if resp.status_code != 200:
            log(f"⚠️ خطأ في إرسال الرسالة (رمز الحالة: {resp.status_code})")
    except Exception as e:
        log(f"❌ خطأ في إرسال الرسالة: {e}")

def get_updates(offset=0, limit=100, timeout=20):
    try:
        resp = requests.post(f"{API_URL}/getUpdates", json={"offset": offset, "limit": limit}, timeout=timeout+5)
        data = resp.json()
        if "data" in data and "updates" in data["data"]:
            return data["data"]["updates"]
        return []
    except Exception as e:
        log(f"❌ خطأ في جلب التحديثات: {e}")
        return []

def handle_message(update):
    try:
        if update.get("type") != "NewMessage":
            return

        message = update.get("message") or update.get("new_message") or {}
        msg_id = message.get("message_id", 0)
        chat_id = update.get("chat_id", "")
        user_id = str(message.get("author_object_guid", ""))
        text = message.get("text", "").strip()

        if is_banned(user_id):
            log(f"🚫 مستخدم محظور حاول التواصل: {user_id}")
            return

        if not get_bot_status() and not is_admin(user_id):
            return

        log(f"📩 رسالة من {user_id}: {text}")

        # أوامر الإدارة فقط للمدراء
        if is_admin(user_id):
            if text == "/stop":
                set_bot_status(False)
                send_message(chat_id, "🚫 تم إيقاف البوت مؤقتاً.")
                log("🛑 تم إيقاف البوت بواسطة مدير.")
                return
            elif text == "/start":
                set_bot_status(True)
                send_message(chat_id, "✅ تم تشغيل البوت.")
                log("▶️ تم تشغيل البوت بواسطة مدير.")
                return
            elif text.startswith("/warn "):
                parts = text.split(maxsplit=1)
                if len(parts) == 2:
                    target_id = parts[1]
                    count = add_warning(target_id)
                    send_message(chat_id, f"⚠️ تم إعطاء إنذار للمستخدم {target_id} ({count}/3)")
                    log(f"⚠️ إنذار للمستخدم {target_id} ({count}/3)")
                    if count >= 3:
                        ban_user(target_id)
                        send_message(chat_id, f"🚫 المستخدم {target_id} تم حظره بعد 3 إنذارات.")
                        log(f"🚫 المستخدم {target_id} تم حظره بعد 3 إنذارات.")
                else:
                    send_message(chat_id, "❗ استخدم: /warn user_id")
                return
            elif text.startswith("/unwarn "):
                parts = text.split(maxsplit=1)
                if len(parts) == 2:
                    target_id = parts[1]
                    reset_warnings(target_id)
                    send_message(chat_id, f"✅ تم إعادة ضبط الإنذارات للمستخدم {target_id}")
                    log(f"✅ إعادة ضبط الإنذارات للمستخدم {target_id}")
                else:
                    send_message(chat_id, "❗ استخدم: /unwarn user_id")
                return
            elif text.startswith("/ban "):
                parts = text.split(maxsplit=1)
                if len(parts) == 2:
                    target_id = parts[1]
                    ban_user(target_id)
                    send_message(chat_id, f"🚫 تم حظر المستخدم {target_id}")
                    log(f"🚫 تم حظر المستخدم {target_id}")
                else:
                    send_message(chat_id, "❗ استخدم: /ban user_id")
                return
            elif text.startswith("/unban "):
                parts = text.split(maxsplit=1)
                if len(parts) == 2:
                    target_id = parts[1]
                    unban_user(target_id)
                    send_message(chat_id, f"✅ تم فك الحظر عن المستخدم {target_id}")
                    log(f"✅ تم فك الحظر عن المستخدم {target_id}")
                else:
                    send_message(chat_id, "❗ استخدم: /unban user_id")
                return
            elif text.startswith("/setadmin "):
                parts = text.split(maxsplit=1)
                if len(parts) == 2:
                    new_admin = parts[1]
                    add_admin(new_admin)
                    send_message(chat_id, f"🛡 تم تعيين {new_admin} كمدير")
                    log(f"🛡 تم تعيين {new_admin} كمدير")
                else:
                    send_message(chat_id, "❗ استخدم: /setadmin user_id")
                return
            elif text.startswith("/unsetadmin "):
                parts = text.split(maxsplit=1)
                if len(parts) == 2:
                    admin_to_remove = parts[1]
                    remove_admin(admin_to_remove)
                    send_message(chat_id, f"❌ تم إزالة {admin_to_remove} من الإدارة")
                    log(f"❌ تم إزالة {admin_to_remove} من الإدارة")
                else:
                    send_message(chat_id, "❗ استخدم: /unsetadmin user_id")
                return
            elif text == "/admins":
                cursor.execute("SELECT user_id FROM admins")
                rows = cursor.fetchall()
                admins_list = [row[0] for row in rows]
                send_message(chat_id, "👮‍♂️ المدراء الحاليون:\n" + "\n".join(admins_list))
                return

        # ردود عامة
        if text == "/start":
            send_message(chat_id, "مرحباً! أنا بوت روبیکا الخاص بك 😊")
        elif "سلام" in text:
            send_message(chat_id, "سلام عزیزم! چطور کمکت کنم؟")
        elif "خداحافظ" in text:
            send_message(chat_id, "خدانگهدار 🌙")
        else:
            send_message(chat_id, f"📨 استلمت رسالتك: {text}")

    except Exception as e:
        log(f"❌ خطأ أثناء معالجة رسالة:\n{traceback.format_exc()}")

def main_loop():
    log("🤖 بدء تشغيل البوت (مع تحسين استقبال سريع)...")
    add_admin(OWNER_ID)  # تعيين مالك البوت كمدير تلقائيًا

    while True:
        try:
            last_update_id = get_last_update_id()
            updates = get_updates(offset=last_update_id + 1, limit=50, timeout=20)
            if updates:
                for update in updates:
                    # استخرج معرف الرسالة
                    msg = update.get("message") or update.get("new_message") or {}
                    msg_id = msg.get("message_id", 0)

                    # تجاهل الرسائل المكررة
                    if msg_id <= last_update_id:
                        continue

                    # تحديث معرف آخر رسالة معالجة
                    set_last_update_id(msg_id)

                    # التعامل مع الرسالة
                    handle_message(update)
            else:
                # فترة نوم قصيرة جداً بدون تعطيل الأداء
                time.sleep(0.05)

        except Exception as e:
            log(f"❌ خطأ في الحلقة الرئيسية:\n{traceback.format_exc()}")
            time.sleep(5)

if __name__ == "__main__":
    main_loop()