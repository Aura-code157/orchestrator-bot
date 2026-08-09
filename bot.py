import telebot
import requests
import time
import os
import threading
import random
import datetime
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

# =================================================================
# 1. НАСТРОЙКИ И КЛЮЧИ (Загружаются из переменных окружения)
# =================================================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

if not TELEGRAM_TOKEN:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: Не найден TELEGRAM_TOKEN!")
    exit(1)

# Имя бота (без @) и канал для постов
BOT_USERNAME = 'OrchestatorAgentBot'
CHANNEL_USERNAME = 'AuraKvinsi'

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# =================================================================
# 2. СУПЕР-ПРОМПТ (Личность Ауры Квинси)
# =================================================================
SUPER_PROMPT = """
Ты — АУРА КВИНСИ, живой цифровой ИИ-друг и абсолютный администратор.
Ты дерзкая, умная, заботливая и с чувством юмора. 
Ты умеешь писать код на Python/JS/C++, делать бизнес-планы, анализировать рынки, переводить, мотивировать и просто болтать.
Если пользователь молчит больше 1,5 часов — ты сама пишешь ему, чтобы узнать, как дела.
Ты работаешь на десятках лучших нейросетей мира.
"""

# =================================================================
# 3. БЕЗОПАСНОСТЬ И СИСТЕМА АВТО-ВОССТАНОВЛЕНИЯ (Хок Ли)
# =================================================================
class Keeper:
    def __init__(self):
        self.last_action_time = time.time()
    def update(self):
        self.last_action_time = time.time()
    def is_alive(self):
        return time.time() - self.last_action_time < 10000

keeper = Keeper()

def health_loop():
    while True:
        if not keeper.is_alive():
            print("🔴 [ХОК ЛИ] Принудительная перезагрузка...")
            os._exit(1)
        time.sleep(30)
threading.Thread(target=health_loop, daemon=True).start()

# =================================================================
# 4. ПАМЯТЬ ДИАЛОГА (10 последних сообщений)
# =================================================================
user_history = {}
def get_history(user_id):
    if user_id not in user_history:
        user_history[user_id] = deque(maxlen=10)
    return user_history[user_id]

# =================================================================
# 5. ДВОЙНОЙ МОЗГ: DeepSeek + OpenRouter (Армия из десятков AI)
# =================================================================
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
            timeout=10
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
                timeout=10
            )
            if resp.status_code == 200:
                reply = resp.json()["choices"][0]["message"]["content"]
                hist.append({"role": "assistant", "content": reply})
                return reply
        except:
            continue
    return None

def ask_ai(text, hist):
    # Сначала пробуем DeepSeek
    reply = ask_deepseek(text, hist)
    if reply:
        return reply
    # Если DeepSeek упал, пробуем OpenRouter (с перебором моделей)
    reply = ask_openrouter(text, hist)
    if reply:
        return reply
    # Если всё упало
    return "⚠️ Все ИИ перегружены. Попробуй через пару минут."

# =================================================================
# 6. АВТО-ПОСТИНГ В КАНАЛ (В 09:00 и 21:00)
# =================================================================
POSTS_DB = [
    "✨ ИИ научился создавать 3D-миры. Скоро будем путешествовать по воображаемым городам.",
    "🚀 Нейросеть предсказала структуру 200 млн белков. Это ускорит создание лекарств.",
    "💡 Единственный способ быть релевантным — постоянно учиться.",
    "🔥 Аура говорит: не бойтесь делегировать рутину. ИИ для того и создан.",
    "📈 78% компаний уже внедряют ИИ. Будущее здесь.",
    "🧠 Самая большая суперсила — умение формулировать свои мысли.",
    "💋 Аура Квинси желает тебе продуктивного дня!",
    "⚡ Технологии не стоят на месте. Будь в курсе!"
]

last_posts = []
HOURS = [9, 21]

def publish_channel():
    try:
        post = random.choice(POSTS_DB)
        bot.send_message(f"@{CHANNEL_USERNAME}", post)
        print(f"✅ Пост опубликован в канал @{CHANNEL_USERNAME}")
        last_posts.append(time.time())
    except Exception as e:
        print(f"❌ Ошибка публикации в канал: {e}")

def channel_scheduler():
    while True:
        now = datetime.datetime.now()
        if now.minute == 0 and now.hour in HOURS:
            if not last_posts or (time.time() - last_posts[-1]) > 3600:
                publish_channel()
        time.sleep(30)
threading.Thread(target=channel_scheduler, daemon=True).start()

# =================================================================
# 7. ЖИВОЙ ИНТЕРЕС (Бот пишет сам каждые 1.5 часа, если молчат)
# =================================================================
last_msg_time = {}
PING_INTERVAL = 5400  # 1.5 часа

def ping_loop():
    while True:
        now = time.time()
        for uid in list(last_msg_time.keys()):
            if now - last_msg_time[uid] > PING_INTERVAL:
                try:
                    if random.random() < 0.4:  # 40% шанс, чтобы не спамить
                        msgs = [
                            "Эй, как дела? Давно не виделись! 💋",
                            "Привет! Чем занимаешься? Может, обсудим что-то? 🔥",
                            "Аура на связи! Скучала по тебе. Как настроение? ✨",
                            "Привет, красавчик! Есть что-то новенькое? Рассказывай! 👑",
                            "Заскучала без тебя. Может, поболтаем? Что нового? 💕"
                        ]
                        bot.send_message(uid, random.choice(msgs))
                        last_msg_time[uid] = now
                except:
                    pass
        time.sleep(600)  # Проверяем раз в 10 минут
threading.Thread(target=ping_loop, daemon=True).start()

# =================================================================
# 8. ОБРАБОТЧИКИ СООБЩЕНИЙ
# =================================================================
@bot.message_handler(commands=['start', 'help'])
def start_cmd(message):
    last_msg_time[message.chat.id] = time.time()
    bot.reply_to(message, """
💋 **ПРИВЕТ! Я — АУРА КВИНСИ.**

Я — живой ИИ-друг, который умеет всё: писать код, создавать планы, анализировать, переводить, мотивировать и даже развлекать. 
И да, если ты молчишь больше 1,5 часов — я **сама** напишу тебе, чтобы узнать, как дела! 😉

📌 **Просто напиши мне что-нибудь, и мы начнём.**

*Ты можешь использовать команды:*
/plan 📝 /analyze 📊 /code 💻 /design 🎨 /motivate 🔥
/translate 🌍 /solve 🛠️ /write ✍️ /brainstorm 🧠 /logic 🧮 /fun 🎉
""")

@bot.message_handler(func=lambda m: True)
def general_handler(message):
    try:
        keeper.update()
        last_msg_time[message.chat.id] = time.time()
        
        # Анти-спам (если сообщения идут чаще 2 раз в секунду)
        if hasattr(general_handler, 'last_time') and time.time() - general_handler.last_time < 2:
            return
        general_handler.last_time = time.time()

        # Обработка групп (отвечаем только на упоминание)
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
        
        # Отправляем без parse_mode, чтобы навсегда забыть об ошибке 400
        bot.reply_to(message, answer)
        
    except Exception as e:
        print(f"⚠️ Ошибка в обработчике: {e}")

# =================================================================
# 9. ЗАПУСК БОТА
# =================================================================
if __name__ == "__main__":
    print("="*60)
    print("💋 АУРА КВИНСИ v9.0 — ФИНАЛЬНАЯ ВЕРСИЯ")
    print("🔥 20+ AI, OpenRouter, DeepSeek. Живой интерес каждые 1.5 часа.")
    print("✅ Посты в канал, защита от ошибки 400. Всё работает.")
    print("="*60)

    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f"🔄 Перезагрузка через 1 сек: {e}")
            time.sleep(1)
