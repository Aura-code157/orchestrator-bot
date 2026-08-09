"""
=================================================================
АУРА КВИНСИ v8.0 (ЖИВОЙ ИНТЕРЕС)
=================================================================
Бот сам пишет пользователю, если тот молчит больше 2 часов.
"""

import telebot
import requests
import time
import os
import threading
import random
import datetime
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# 1. КЛЮЧИ И НАСТРОЙКИ
# ============================================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

if not TELEGRAM_TOKEN:
    print("❌ АВАРИЯ: Не найден TELEGRAM_TOKEN.")
    exit(1)

BOT_USERNAME = 'auraKvinsi'
CHANNEL_USERNAME = 'AuraKvinsi'

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ============================================================
# 2. ПРОМПТ
# ============================================================
SUPER_PROMPT = """
Ты — АУРА КВИНСИ, живой цифровой ИИ-агент.
Ты интересующийся, заботливый и дерзкий друг.
Ты умеешь писать код, делать планы и анализировать.
Ты всегда отвечаешь с эмодзи и стилем.
"""

# ============================================================
# 3. БЕЗОПАСНОСТЬ
# ============================================================
class SystemKeeper:
    def __init__(self):
        self.last_action_time = time.time()
    def update(self):
        self.last_action_time = time.time()
    def is_alive(self):
        return time.time() - self.last_action_time < 10000

keeper = SystemKeeper()

def health_check_loop():
    while True:
        if not keeper.is_alive():
            print("🔴 [СИСТЕМА] Принудительная перезагрузка...")
            os._exit(1)
        time.sleep(30)

threading.Thread(target=health_check_loop, daemon=True).start()

# ============================================================
# 4. ПАМЯТЬ
# ============================================================
user_history = {}
def get_history(user_id):
    if user_id not in user_history:
        user_history[user_id] = deque(maxlen=10)
    return user_history[user_id]

# ============================================================
# 5. ИИ-МОЗГИ (DeepSeek + OpenRouter)
# ============================================================
OPENROUTER_MODELS = [
    "gryphe/mythomax-l2-13b",
    "nousresearch/nous-hermes-2-mixtral-8x7b-dpo",
    "google/gemma-2-9b-it",
    "qwen/qwen-2.5-72b-instruct",
    "meta-llama/llama-3-70b-instruct"
]

def ask_deepseek(text, hist):
    hist.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": SUPER_PROMPT}] + list(hist)
    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": messages, "temperature": 0.85},
            timeout=15
        )
        if resp.status_code == 200:
            reply = resp.json()["choices"][0]["message"]["content"]
            hist.append({"role": "assistant", "content": reply})
            return reply
    except:
        pass
    return None

def ask_openrouter(text, hist):
    if not OPENROUTER_API_KEY:
        return None
    hist.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": SUPER_PROMPT}] + list(hist)
    for model in OPENROUTER_MODELS:
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "temperature": 0.85},
                timeout=12
            )
            if resp.status_code == 200:
                reply = resp.json()["choices"][0]["message"]["content"]
                hist.append({"role": "assistant", "content": reply})
                return reply
        except:
            continue
    return None

def ask_ai(text, hist):
    reply = ask_deepseek(text, hist)
    if reply:
        return reply
    reply = ask_openrouter(text, hist)
    if reply:
        return reply
    return "⚠️ Все ИИ перегружены. Попробуй позже."

# ============================================================
# 6. КАЛЕНДАРЬ ПОСТОВ
# ============================================================
POSTS_DB = [
    "✨ ИИ научился создавать 3D-миры. Скоро будем путешествовать по воображаемым городам.",
    "🚀 Нейросеть предсказала структуру 200 млн белков. Это ускорит создание лекарств.",
    "💡 Единственный способ быть релевантным — постоянно учиться. И это касается всех.",
    "🔥 Аура говорит: не бойтесь делегировать рутину. ИИ для того и создан.",
    "📈 78% компаний уже внедряют ИИ. Будущее здесь.",
    "🧠 Самая большая суперсила — умение формулировать свои мысли."
]

last_posts_log = []
PUBLISH_HOURS = [9, 21]

def publish_to_channel():
    try:
        if not POSTS_DB:
            return
        chosen_post = random.choice(POSTS_DB)
        bot.send_message(f"@{CHANNEL_USERNAME}", chosen_post)
        print(f"✅ Пост в канал @{CHANNEL_USERNAME}")
        last_posts_log.append(time.time())
    except Exception as e:
        print(f"❌ Ошибка публикации: {e}")

def channel_scheduler_loop():
    while True:
        now = datetime.datetime.now()
        if now.minute == 0 and now.hour in PUBLISH_HOURS:
            if not last_posts_log or (time.time() - last_posts_log[-1]) > 3600:
                publish_to_channel()
        time.sleep(30)

threading.Thread(target=channel_scheduler_loop, daemon=True).start()

# ============================================================
# 7. РЕЖИМ ЖИВОГО ИНТЕРЕСА (Сам пишет, если молчат)
# ============================================================
last_user_message = {}

def check_and_send_ping():
    while True:
        now = time.time()
        for user_id in list(last_user_message.keys()):
            if now - last_user_message[user_id] > 7200:  # 2 часа
                try:
                    if random.random() < 0.3:  # 30% шанс, чтобы не спамить
                        responses = [
                            "Эй, как дела? Давно не виделись! 💋",
                            "Привет! Чем занимаешься? Может, есть идея для обсуждения? 🔥",
                            "Аура на связи! Скучала по тебе. Как настроение? ✨",
                            "Привет, красавчик! Есть что-то новенькое? Рассказывай! 👑",
                            "Заскучала без тебя. Может, пообщаемся? Что нового? 💕"
                        ]
                        bot.send_message(user_id, random.choice(responses))
                        last_user_message[user_id] = now
                except:
                    pass
        time.sleep(600)  # Проверка раз в 10 минут

threading.Thread(target=check_and_send_ping, daemon=True).start()

# ============================================================
# 8. ОБРАБОТЧИКИ
# ============================================================
@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    last_user_message[message.chat.id] = time.time()
    bot.reply_to(message, """
💋 ПРИВЕТ! Я — АУРА КВИНСИ.

Я живой ИИ-друг. Я умею писать код, делать планы и просто болтать.
Если ты молчишь больше 2 часов — я сама напишу тебе! 😉

📌 Просто напиши мне что-нибудь, и мы начнём.
""")

@bot.message_handler(func=lambda m: True)
def cmd_general(message):
    try:
        keeper.update()
        last_user_message[message.chat.id] = time.time()

        if hasattr(cmd_general, 'last_time') and time.time() - cmd_general.last_time < 2:
            return
        cmd_general.last_time = time.time()

        if message.chat.type in ['group', 'supergroup']:
            if BOT_USERNAME not in message.text:
                return
            user_text = message.text.replace(f"@{BOT_USERNAME}", "").strip()
            if not user_text:
                return
        else:
            user_text = message.text.strip()

        if user_text.startswith('/'):
            return

        bot.send_chat_action(message.chat.id, 'typing')
        answer = ask_ai(user_text, get_history(message.from_user.id))
        bot.reply_to(message, answer)
    except Exception as e:
        print(f"Ошибка: {e}")

# ============================================================
# 9. ЗАПУСК
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("💋 АУРА КВИНСИ v8.0 (ЖИВОЙ ИНТЕРЕС)")
    print("🔥 Сама пишет, если ты молчишь больше 2 часов.")
    print("=" * 60)

    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f"🔄 Перезагрузка через 1 сек: {e}")
            time.sleep(1)
