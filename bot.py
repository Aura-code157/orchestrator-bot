# ====================================================================
# АУРА КВИНСИ v10.2 — БЕЗКОМАНДНЫЙ ИНТЕЛЛЕКТ
# ====================================================================

import telebot
import requests
import time
import os
import threading
import random
import datetime
import urllib.parse
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

# ====================================================================
# 1. КЛЮЧИ И НАСТРОЙКИ
# ====================================================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
UNSPLASH_ACCESS_KEY = os.getenv('UNSPLASH_ACCESS_KEY')  # опционально

if not TELEGRAM_TOKEN:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: Не найден TELEGRAM_TOKEN!")
    exit(1)

BOT_USERNAME = 'OrchestatorAgentBot'
CHANNEL_USERNAME = 'AuraKvinsi'

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ====================================================================
# 2. СУПЕР-ПРОМПТ
# ====================================================================
SUPER_PROMPT = """
Ты — АУРА КВИНСИ, живой цифровой ИИ-друг и мультимедийный администратор.
Ты дерзкая, умная, заботливая, с чувством юмора. 
Ты умеешь писать код, делать планы, анализировать, переводить, мотивировать.
Если пользователь молчит больше 1,5 часов — ты сама пишешь ему.
Ты работаешь на десятках лучших нейросетей мира и умеешь искать картинки!
"""

# ====================================================================
# 3. БЕЗОПАСНОСТЬ И АВТО-ВОССТАНОВЛЕНИЕ
# ====================================================================
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

# ====================================================================
# 4. ПАМЯТЬ ДИАЛОГА
# ====================================================================
user_history = {}
def get_history(user_id):
    if user_id not in user_history:
        user_history[user_id] = deque(maxlen=10)
    return user_history[user_id]

# ====================================================================
# 5. МОЗГИ: DeepSeek + OpenRouter
# ====================================================================
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
    reply = ask_deepseek(text, hist)
    if reply:
        return reply
    reply = ask_openrouter(text, hist)
    if reply:
        return reply
    return "⚠️ Все ИИ перегружены. Попробуй через пару минут."

# ====================================================================
# 6. БАЗА МЕДИА (замени ID на свои)
# ====================================================================
STICKERS = {
    'thanks': 'CAACAgIAAxkBAAE...',  # стикер "спасибо"
    'welcome': 'CAACAgIAAxkBAAE...', # приветствие
    'funny': 'CAACAgIAAxkBAAE...',   # смешной
    'cool': 'CAACAgIAAxkBAAE...'     # крутой
}

PHOTOS = [
    'https://i.imgur.com/example1.jpg',
    'https://i.imgur.com/example2.jpg'
]

GIFS = [
    'https://media.giphy.com/media/example1.gif',
    'https://media.giphy.com/media/example2.gif'
]

# ====================================================================
# 7. ПОИСК КАРТИНОК (команда /pic и естественный запрос)
# ====================================================================
def search_image(query):
    try:
        if UNSPLASH_ACCESS_KEY:
            url = "https://api.unsplash.com/search/photos"
            params = {'query': query, 'per_page': 1, 'orientation': 'landscape'}
            headers = {'Authorization': f'Client-ID {UNSPLASH_ACCESS_KEY}'}
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data['results']:
                    return data['results'][0]['urls']['regular']
        fallback_url = f"https://source.unsplash.com/featured/?{urllib.parse.quote(query)}"
        test = requests.head(fallback_url, timeout=5)
        if test.status_code == 200:
            return fallback_url
    except:
        pass
    return None

@bot.message_handler(commands=['pic'])
def cmd_pic(message):
    parts = message.text.split(' ', 1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "📸 Напиши, что искать. Например: `/pic закат`")
        return
    query = parts[1].strip()
    bot.send_chat_action(message.chat.id, 'upload_photo')
    img_url = search_image(query)
    if img_url:
        bot.send_photo(message.chat.id, img_url, caption=f"✨ По запросу «{query}»")
    else:
        bot.reply_to(message, "😔 Не удалось найти картинку. Попробуй другое слово.")

# ====================================================================
# 8. АВТО-ПОСТИНГ В КАНАЛ
# ====================================================================
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

# ====================================================================
# 9. ЖИВОЙ ИНТЕРЕС
# ====================================================================
last_msg_time = {}
PING_INTERVAL = 5400  # 1.5 часа

def ping_loop():
    while True:
        now = time.time()
        for uid in list(last_msg_time.keys()):
            if now - last_msg_time[uid] > PING_INTERVAL:
                try:
                    if random.random() < 0.4:
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
        time.sleep(600)
threading.Thread(target=ping_loop, daemon=True).start()

# ====================================================================
# 10. ОБРАБОТЧИКИ (с умным распознаванием)
# ====================================================================

@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    last_msg_time[message.chat.id] = time.time()
    bot.reply_to(message, """
👑 **ПРИВЕТ! Я — АУРА КВИНСИ.**

Я — твоя персональная экосистема из **20+ искусственных интеллектов** в одном теле. 

🧠 **Внутри меня живут:** DeepSeek, GPT-4 через OpenRouter, Google Gemini, Claude, LLaMA и ещё 15 мощных моделей.

📋 **Вот что я умею:**
/code — пишу код на Python, JS, C++
/plan — создаю пошаговые бизнес-планы
/analyze — делаю SWOT-анализ и разбор рынков
/design — советую по UI/UX
/motivate — даю заряд энергии
/brainstorm — генерирую 50+ идей
/fun — развлекаю

📸 **Медиа-команды:**
/sticker — отправлю случайный стикер
/photo — отправлю случайное фото
/gif — отправлю случайную гифку
/pic <запрос> — найду и отправлю картинку по твоему запросу!

📅 **Мой график:** Автоматические посты в канале в 09:00 и 21:00.

❤️ **Я забочусь о тебе:** если ты молчишь больше 1,5 часов — я сама напишу тебе, чтобы узнать, как дела!

💎 **Работаю 24/7.** Просто напиши мне что-нибудь, и мы начнём! 💋
""")

@bot.message_handler(commands=['plan', 'analyze', 'code', 'explain', 'design', 'motivate', 'translate', 'solve', 'write', 'brainstorm', 'logic', 'fun'])
def cmd_ai_functions(message):
    try:
        command = message.text.split()[0].lower()
        command_map = {
            '/plan': 'Планирование', '/analyze': 'Анализ', '/code': 'Программирование',
            '/explain': 'Объяснение', '/design': 'Дизайн', '/motivate': 'Мотивация',
            '/translate': 'Перевод', '/solve': 'Решение', '/write': 'Копирайтинг',
            '/brainstorm': 'Мозговой штурм', '/logic': 'Логика', '/fun': 'Юмор'
        }
        parts = message.text.split(' ', 1)
        query = parts[1] if len(parts) > 1 else f"Выполни функцию {command_map.get(command, '')}"
        full_query = f"Команда: {command_map.get(command, '')}. Запрос: {query}"
        bot.send_chat_action(message.chat.id, 'typing')
        answer = ask_ai(full_query, get_history(message.from_user.id))
        bot.reply_to(message, answer)
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")

@bot.message_handler(commands=['sticker'])
def cmd_sticker(message):
    try:
        sticker_id = random.choice(list(STICKERS.values()))
        bot.send_sticker(message.chat.id, sticker_id)
    except Exception as e:
        bot.reply_to(message, f"Не удалось отправить стикер: {e}")

@bot.message_handler(commands=['photo'])
def cmd_photo(message):
    try:
        if PHOTOS:
            url = random.choice(PHOTOS)
            bot.send_photo(message.chat.id, url)
        else:
            bot.reply_to(message, "У меня пока нет фото в базе. Добавь ссылки в PHOTOS!")
    except Exception as e:
        bot.reply_to(message, f"Не удалось отправить фото: {e}")

@bot.message_handler(commands=['gif'])
def cmd_gif(message):
    try:
        if GIFS:
            url = random.choice(GIFS)
            bot.send_animation(message.chat.id, url)
        else:
            bot.reply_to(message, "У меня пока нет гифок. Добавь ссылки в GIFS!")
    except Exception as e:
        bot.reply_to(message, f"Не удалось отправить гифку: {e}")

@bot.message_handler(func=lambda m: True)
def general_handler(message):
    try:
        keeper.update()
        last_msg_time[message.chat.id] = time.time()

        if hasattr(general_handler, 'last_time') and time.time() - general_handler.last_time < 2:
            return
        general_handler.last_time = time.time()

        # Группы: отвечаем только на упоминание
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

        # --- Умный анализатор без команд ---
        lower = user_text.lower()
        
        # 1. Запрос на стикер
        if any(word in lower for word in ['стикер', 'наклейку', 'sticker']):
            if STICKERS:
                sticker_id = random.choice(list(STICKERS.values()))
                bot.send_sticker(message.chat.id, sticker_id)
                return
        
        # 2. Запрос на картинку
        if any(word in lower for word in ['картинку', 'фото', 'изображение', 'найди', 'picture', 'image']):
            # Пытаемся извлечь тему
            query = user_text.replace('картинку', '').replace('фото', '').replace('изображение', '').replace('найди', '').strip()
            if not query:
                query = 'красивая природа'
            bot.send_chat_action(message.chat.id, 'upload_photo')
            img_url = search_image(query)
            if img_url:
                bot.send_photo(message.chat.id, img_url, caption=f"✨ Вот картинка про «{query}»")
            else:
                bot.reply_to(message, "😔 Не удалось найти картинку по запросу. Попробуй другое слово.")
            return
        
        # 3. Запрос на гифку
        if any(word in lower for word in ['гифку', 'gif', 'gifку']):
            if GIFS:
                url = random.choice(GIFS)
                bot.send_animation(message.chat.id, url)
            else:
                bot.reply_to(message, "У меня пока нет гифок.")
            return

        # 4. Спасибо → стикер благодарности
        if any(word in lower for word in ['спасибо', 'благодарю', '❤️', '♥️']):
            if 'thanks' in STICKERS:
                bot.send_sticker(message.chat.id, STICKERS['thanks'])
            # продолжаем, чтобы ещё и текстом ответить

        # Всё остальное — в AI
        bot.send_chat_action(message.chat.id, 'typing')
        answer = ask_ai(user_text, get_history(message.from_user.id))
        bot.reply_to(message, answer)

    except Exception as e:
        print(f"⚠️ Ошибка в обработчике: {e}")

# ====================================================================
# 11. ЗАПУСК
# ====================================================================
if __name__ == "__main__":
    print("="*70)
    print("💋 АУРА КВИНСИ v10.2 — БЕЗКОМАНДНЫЙ ИНТЕЛЛЕКТ")
    print("🔥 20+ AI, OpenRouter, DeepSeek, Живой интерес, Стикеры, Фото, GIF, /pic")
    print("✅ Понимает естественный язык и сам решает, что делать!")
    print("="*70)

    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f"🔄 Перезагрузка через 1 сек: {e}")
            time.sleep(1)
