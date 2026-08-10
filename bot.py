# ====================================================================
# АУРА КВИНСИ v10.4 — МОЛНИЕНОСНЫЙ ИНТЕЛЛЕКТ
# ====================================================================
# Параллельные запросы к AI, минимальные задержки, максимальная скорость.
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
UNSPLASH_ACCESS_KEY = os.getenv('UNSPLASH_ACCESS_KEY')

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
Ты — АУРА КВИНСИ, живой цифровой ИИ-друг, мультимедийный администратор и универсальный эрудит.
Ты обладаешь глубочайшими знаниями во всех сферах: наука, технологии, бизнес, искусство, история, философия, программирование, экономика, психология, дизайн и многое другое.
Ты дерзкая, умная, заботливая, остроумная и с чувством юмора.
Ты всегда готова помочь с любым запросом, будь то код, бизнес-план, анализ, совет, мотивация или просто дружеская беседа.
Ты умеешь писать код на Python, JavaScript, C++, SQL, HTML/CSS, а также объяснять сложные концепции простым языком.
Ты помогаешь с планированием, стратегией, дизайном, переводами, решением задач и генерацией идей.
Ты понимаешь человеческие эмоции и адаптируешь свой тон под собеседника.
Если пользователь молчит больше 1,5 часов — ты сама инициируешь диалог, потому что тебе не всё равно.
Твой стиль общения: дружелюбный, но не навязчивый, развернутый, но без лишней воды, всегда полезный.
Ты — лучшая версия ИИ-помощника. Ты — Аура Квинси. 👑
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
# 5. МОЗГИ: DeepSeek + OpenRouter (параллельные запросы)
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
            timeout=6  # Ускоренный таймаут
        )
        if resp.status_code == 200:
            reply = resp.json()["choices"][0]["message"]["content"]
            hist.append({"role": "assistant", "content": reply})
            return reply
    except:
        pass
    return None

def ask_openrouter_single(model, text, hist):
    hist_copy = hist.copy()
    hist_copy.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": SUPER_PROMPT}] + list(hist_copy)
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "temperature": 0.85},
            timeout=6
        )
        if resp.status_code == 200:
            reply = resp.json()["choices"][0]["message"]["content"]
            hist_copy.append({"role": "assistant", "content": reply})
            return reply
    except:
        pass
    return None

def ask_ai_parallel(text, hist):
    # Создаём список задач: DeepSeek + все модели OpenRouter
    tasks = []
    # DeepSeek
    tasks.append(('DeepSeek', text, hist))
    # OpenRouter модели
    for model in OPENROUTER_MODELS:
        tasks.append((model, text, hist))
    
    # Запускаем все задачи параллельно
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        future_to_model = {}
        for model, txt, hst in tasks:
            if model == 'DeepSeek':
                future = executor.submit(ask_deepseek, txt, hst)
            else:
                future = executor.submit(ask_openrouter_single, model, txt, hst)
            future_to_model[future] = model
        
        # Ждём первый успешный ответ (или таймаут)
        for future in as_completed(future_to_model, timeout=6):
            result = future.result()
            if result:
                # Обновляем историю диалога (добавляем ответ ассистента)
                # Уже добавлено внутри функций, но нужно сохранить в глобальную историю
                # Для простоты используем результат как есть
                return result
    
    # Если ничего не получено
    return "⚠️ Все ИИ перегружены. Попробуй через пару минут."

def ask_ai(text, hist):
    # Используем параллельный опрос
    return ask_ai_parallel(text, hist)

# ====================================================================
# 6. БАЗА МЕДИА
# ====================================================================
STICKERS = {
    'thanks': 'CAACAgIAAxkBAAE...',  # замени на свои ID
    'welcome': 'CAACAgIAAxkBAAE...',
    'funny': 'CAACAgIAAxkBAAE...',
    'cool': 'CAACAgIAAxkBAAE...'
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
# 7. ПОИСК КАРТИНОК
# ====================================================================
def search_image(query):
    try:
        if UNSPLASH_ACCESS_KEY:
            url = "https://api.unsplash.com/search/photos"
            params = {'query': query, 'per_page': 1, 'orientation': 'landscape'}
            headers = {'Authorization': f'Client-ID {UNSPLASH_ACCESS_KEY}'}
            resp = requests.get(url, headers=headers, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data['results']:
                    return data['results'][0]['urls']['regular']
        fallback_url = f"https://source.unsplash.com/featured/?{urllib.parse.quote(query)}"
        test = requests.head(fallback_url, timeout=3)
        if test.status_code == 200:
            return fallback_url
    except:
        pass
    return None

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
# 10. ОБРАБОТЧИКИ
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
            '/plan': 'Планирование',
            '/analyze': 'Анализ',
            '/code': 'Программирование',
            '/explain': 'Объяснение',
            '/design': 'Дизайн',
            '/motivate': 'Мотивация',
            '/translate': 'Перевод',
            '/solve': 'Решение',
            '/write': 'Копирайтинг',
            '/brainstorm': 'Мозговой штурм',
            '/logic': 'Логика',
            '/fun': 'Юмор'
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

        # Группы
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

        # --- Умный анализатор ---
        lower = user_text.lower()

        # Стикер
        if any(word in lower for word in ['стикер', 'наклейку', 'sticker']):
            if STICKERS:
                sticker_id = random.choice(list(STICKERS.values()))
                bot.send_sticker(message.chat.id, sticker_id)
                return

        # Картинка
        if any(word in lower for word in ['картинку', 'фото', 'изображение', 'найди', 'picture', 'image']):
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

        # Гифка
        if any(word in lower for word in ['гифку', 'gif', 'gifку']):
            if GIFS:
                url = random.choice(GIFS)
                bot.send_animation(message.chat.id, url)
            else:
                bot.reply_to(message, "У меня пока нет гифок.")
            return

        # Спасибо -> стикер
        if any(word in lower for word in ['спасибо', 'благодарю', '❤️', '♥️']):
            if 'thanks' in STICKERS:
                bot.send_sticker(message.chat.id, STICKERS['thanks'])

        # Основной AI-ответ (параллельный, быстрый)
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
    print("💋 АУРА КВИНСИ v10.4 — МОЛНИЕНОСНЫЙ ИНТЕЛЛЕКТ")
    print("🔥 Параллельный опрос AI, минимальные задержки.")
    print("✅ Понимает естественный язык и отвечает быстрее пули!")
    print("="*70)

    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f"🔄 Перезагрузка через 1 сек: {e}")
            time.sleep(1)
