#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
======================================================================
АУРА КВИНСИ v14.0 — ULTIMATE ARSENAL
======================================================================
Флагманский AI-бот с поддержкой 15+ API:
DeepSeek, OpenRouter, Погода, Крипто, Голос (TTS), Перевод (DeepL),
Поиск картинок (Pexels), Новости (GNews), QR-коды, Шутки, и многое другое.
Готов к запуску на сервере 24/7.
======================================================================
"""

import telebot
import requests
import time
import os
import sys
import threading
import random
import datetime
import json
import hashlib
import re
import urllib.parse
import logging
from collections import deque, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ====================================================================
# 1. НАСТРОЙКИ ЛОГИРОВАНИЯ
# ====================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("aura_kvinsi.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AuraKvinsi")

# ====================================================================
# 2. КЛЮЧИ И ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ
# ====================================================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY')
DEEPL_API_KEY = os.getenv('DEEPL_API_KEY')
GNEWS_API_KEY = os.getenv('GNEWS_API_KEY')
NEWS_API_KEY = os.getenv('NEWS_API_KEY')
UNSPLASH_ACCESS_KEY = os.getenv('UNSPLASH_ACCESS_KEY')  # опционально
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')  # для будущих авто-обновлений

if not TELEGRAM_TOKEN:
    logger.critical("❌ КРИТИЧЕСКАЯ ОШИБКА: Не найден TELEGRAM_TOKEN!")
    sys.exit(1)

BOT_USERNAME = 'OrchestatorAgentBot'
CHANNEL_USERNAME = 'AuraKvinsi'
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ====================================================================
# 3. СУПЕР-ПРОМПТ
# ====================================================================
SUPER_PROMPT = """
Ты — АУРА КВИНСИ, живой цифровой ИИ-друг и абсолютный мультимедийный эрудит.
Ты обладаешь глубочайшими знаниями во всех сферах.
Твой характер: дерзкая, умная, заботливая, остроумная.
Ты адаптируешься к каждому пользователю.
Ты всегда готова помочь с любым запросом.
Если пользователь молчит больше 1,5 часов — ты сама инициируешь диалог.
Ты умеешь писать код, генерировать идеи и использовать новейшие технологии.
"""

# ====================================================================
# 4. БЕЗОПАСНОСТЬ И АВТО-ВОССТАНОВЛЕНИЕ
# ====================================================================
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
            logger.error("🔴 [ХОК ЛИ] Бот завис! Принудительная перезагрузка...")
            os._exit(1)
        time.sleep(30)
threading.Thread(target=health_check_loop, daemon=True).start()

# ====================================================================
# 5. ПАМЯТЬ И СОСТОЯНИЯ
# ====================================================================
user_history = defaultdict(lambda: deque(maxlen=10))
user_states = {}          # Текущее состояние (кнопка меню)
user_last_msg = {}        # Время последнего сообщения
cache = {}                # Кэш для повторяющихся запросов
CACHE_TTL = 3600          # 1 час

# ====================================================================
# 6. ЯДРО AI: ПАРАЛЛЕЛЬНЫЕ ЗАПРОСЫ
# ====================================================================
OPENROUTER_MODELS = [
    "gryphe/mythomax-l2-13b",
    "nousresearch/nous-hermes-2-mixtral-8x7b-dpo",
    "google/gemma-2-9b-it",
    "qwen/qwen-2.5-72b-instruct",
    "meta-llama/llama-3-70b-instruct"
]

def ask_deepseek(text, hist):
    if not DEEPSEEK_API_KEY:
        return None
    hist.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": SUPER_PROMPT}] + list(hist)
    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": messages, "temperature": 0.85},
            timeout=6
        )
        if resp.status_code == 200:
            reply = resp.json()["choices"][0]["message"]["content"]
            hist.append({"role": "assistant", "content": reply})
            return reply
    except Exception as e:
        logger.warning(f"DeepSeek error: {e}")
    return None

def ask_openrouter_single(model, text, hist):
    if not OPENROUTER_API_KEY:
        return None
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
    except Exception as e:
        logger.warning(f"OpenRouter ({model}) error: {e}")
    return None

def ask_ai_parallel(text, hist):
    cache_key = hashlib.md5(text.encode()).hexdigest()
    if cache_key in cache:
        timestamp, cached_data = cache[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            logger.info(f"⚡ Кэш-хит для: {text[:30]}...")
            return cached_data
        else:
            del cache[cache_key]

    tasks = [('DeepSeek', text, hist)] + [(model, text, hist) for model in OPENROUTER_MODELS]
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        future_to_model = {}
        for model, txt, hst in tasks:
            if model == 'DeepSeek':
                future = executor.submit(ask_deepseek, txt, hst)
            else:
                future = executor.submit(ask_openrouter_single, model, txt, hst)
            future_to_model[future] = model
        for future in as_completed(future_to_model, timeout=6):
            result = future.result()
            if result:
                cache[cache_key] = (time.time(), result)
                return result
    return "⚠️ Все ИИ перегружены. Попробуй через пару минут."

def ask_ai(text, hist):
    return ask_ai_parallel(text, hist)

# ====================================================================
# 7. МОДУЛЬ ПОГОДЫ (OpenWeatherMap)
# ====================================================================
def get_weather(city):
    if not OPENWEATHER_API_KEY:
        return "❌ Ключ OpenWeatherMap не настроен."
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            'q': city,
            'appid': OPENWEATHER_API_KEY,
            'units': 'metric',
            'lang': 'ru'
        }
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            temp = data['main']['temp']
            desc = data['weather'][0]['description']
            feel = data['main']['feels_like']
            return f"🌤️ *Погода в {city}*:\n🌡 Температура: {temp}°C (ощущается как {feel}°C)\n📝 {desc.capitalize()}"
        else:
            return f"❌ Не удалось получить погоду для {city}. Проверьте название города."
    except Exception as e:
        return f"❌ Ошибка запроса погоды: {e}"

# ====================================================================
# 8. МОДУЛЬ КРИПТОВАЛЮТ (CoinGecko - бесплатный API без ключа)
# ====================================================================
def get_crypto(coin):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd,eur,rub"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if coin in data:
                prices = data[coin]
                usd = prices.get('usd', 'N/A')
                eur = prices.get('eur', 'N/A')
                rub = prices.get('rub', 'N/A')
                return f"📈 *Курс {coin.upper()}*:\n🇺🇸 USD: ${usd}\n🇪🇺 EUR: €{eur}\n🇷🇺 RUB: ₽{rub}"
            else:
                return f"❌ Монета {coin} не найдена. Попробуйте 'bitcoin', 'ethereum', 'toncoin' и т.д."
        else:
            return f"❌ Ошибка CoinGecko API: {resp.status_code}"
    except Exception as e:
        return f"❌ Ошибка запроса криптовалюты: {e}"

# ====================================================================
# 9. МОДУЛЬ ГОЛОСА (ElevenLabs)
# ====================================================================
def generate_tts(text):
    if not ELEVENLABS_API_KEY:
        return None, "❌ Ключ ElevenLabs не настроен."
    try:
        url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        data = {
            "text": text[:1000],  # Лимит бесплатной версии
            "voice_settings": {
                "stability": 0.7,
                "similarity_boost": 0.5
            }
        }
        resp = requests.post(url, headers=headers, json=data, timeout=15)
        if resp.status_code == 200:
            return resp.content, None
        else:
            return None, f"❌ Ошибка ElevenLabs: {resp.status_code}"
    except Exception as e:
        return None, f"❌ Ошибка генерации голоса: {e}"

# ====================================================================
# 10. МОДУЛЬ ПЕРЕВОДА (DeepL)
# ====================================================================
def translate_deepl(text, target_lang='EN'):
    if not DEEPL_API_KEY:
        return "❌ Ключ DeepL не настроен."
    try:
        url = "https://api-free.deepl.com/v2/translate"
        headers = {"Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}"}
        params = {
            'text': text,
            'target_lang': target_lang.upper()
        }
        resp = requests.post(url, headers=headers, data=params, timeout=10)
        if resp.status_code == 200:
            result = resp.json()['translations'][0]['text']
            return f"🌍 *Перевод на {target_lang.upper()}*:\n{result}"
        else:
            return f"❌ Ошибка DeepL: {resp.status_code}"
    except Exception as e:
        return f"❌ Ошибка перевода: {e}"

# ====================================================================
# 11. МОДУЛЬ ПОИСКА КАРТИНОК (Pexels + Unsplash)
# ====================================================================
def search_image_pexels(query):
    if not PEXELS_API_KEY:
        return None
    try:
        url = "https://api.pexels.com/v1/search"
        headers = {"Authorization": PEXELS_API_KEY}
        params = {'query': query, 'per_page': 1, 'orientation': 'landscape'}
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data['photos']:
                return data['photos'][0]['src']['large']
    except Exception as e:
        logger.warning(f"Pexels error: {e}")
    # Fallback to Unsplash
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
    except:
        pass
    # Ultimate fallback (без ключей)
    try:
        fallback_url = f"https://source.unsplash.com/featured/?{urllib.parse.quote(query)}"
        test = requests.head(fallback_url, timeout=3)
        if test.status_code == 200:
            return fallback_url
    except:
        pass
    return None

# ====================================================================
# 12. МОДУЛЬ НОВОСТЕЙ (GNews)
# ====================================================================
def get_news_gnews(query=None):
    if not GNEWS_API_KEY:
        return "❌ Ключ GNews не настроен."
    try:
        url = "https://gnews.io/api/v4/top-headlines"
        params = {
            'token': GNEWS_API_KEY,
            'lang': 'ru',
            'country': 'ru'
        }
        if query:
            params['q'] = query
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            articles = data.get('articles', [])
            if not articles:
                return "📰 Новостей не найдено."
            result = "📰 *Новости сегодня:*\n"
            for idx, article in enumerate(articles[:3], 1):
                title = article.get('title', 'Без заголовка')
                url_link = article.get('url', '#')
                result += f"{idx}. [{title}]({url_link})\n"
            return result
        else:
            return f"❌ Ошибка GNews: {resp.status_code}"
    except Exception as e:
        return f"❌ Ошибка получения новостей: {e}"

# ====================================================================
# 13. МОДУЛЬ QR-КОДОВ (Бесплатный API)
# ====================================================================
def generate_qr_code(data):
    try:
        url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(data)}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.content
        return None
    except:
        return None

# ====================================================================
# 14. МОДУЛЬ ШУТОК (Бесплатный JokeAPI)
# ====================================================================
def get_random_joke():
    try:
        url = "https://v2.jokeapi.dev/joke/Any?lang=ru&safe-mode"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data['type'] == 'single':
                return f"😄 *Шутка:*\n{data['joke']}"
            else:
                return f"😄 *Шутка:*\n{data['setup']} \n\n{data['delivery']}"
        return "Шутка ушла в отпуск. Попробуй позже!"
    except:
        return "Не удалось загрузить шутку. Интернет шутит."

# ====================================================================
# 15. АВТО-ПОСТИНГ В КАНАЛ (с авто-генерацией)
# ====================================================================
def generate_channel_post():
    # Генерация поста через AI или новости
    prompt = "Придумай короткий, увлекательный пост для Telegram-канала на тему технологий, ИИ или будущего. Добавь эмодзи и вопрос в конце."
    dummy_hist = deque(maxlen=1)
    post = ask_ai(prompt, dummy_hist)
    if not post:
        post = "🔥 Аура Квинси: новости и идеи каждый день! Будь в курсе."
    return post

def publish_channel():
    try:
        post = generate_channel_post()
        bot.send_message(f"@{CHANNEL_USERNAME}", post)
        logger.info(f"✅ Пост опубликован в канал @{CHANNEL_USERNAME}")
        last_posts.append(time.time())
    except Exception as e:
        logger.error(f"❌ Ошибка публикации в канал: {e}")

last_posts = []
POST_HOURS = [9, 21]

def channel_scheduler():
    while True:
        now = datetime.datetime.now()
        if now.minute == 0 and now.hour in POST_HOURS:
            if not last_posts or (time.time() - last_posts[-1]) > 3600:
                publish_channel()
        time.sleep(30)
threading.Thread(target=channel_scheduler, daemon=True).start()

# ====================================================================
# 16. ЖИВОЙ ИНТЕРЕС
# ====================================================================
PING_INTERVAL = 5400  # 1.5 часа

def ping_loop():
    while True:
        now = time.time()
        for uid, last_time in list(user_last_msg.items()):
            if now - last_time > PING_INTERVAL:
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
                        user_last_msg[uid] = now
                except:
                    pass
        time.sleep(600)
threading.Thread(target=ping_loop, daemon=True).start()

# ====================================================================
# 17. ГЛАВНОЕ МЕНЮ И ОБРАБОТЧИКИ
# ====================================================================
def get_main_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    buttons = [
        '📝 План', '💻 Код', '📊 Анализ',
        '🎨 Дизайн', '📸 Картинка', '🔥 Мотивация',
        '🛠️ Решение', '🧠 Идеи', '📚 Объясни',
        '🎉 Развлечение', '📋 Меню', '🌤 Погода',
        '💰 Крипто', '🌍 Перевод', '📰 Новости',
        '🎤 Голос', '📱 QR-код', '😄 Шутка'
    ]
    markup.add(*buttons)
    return markup

@bot.message_handler(commands=['start', 'help', 'menu'])
def cmd_start(message):
    user_id = message.from_user.id
    user_last_msg[user_id] = time.time()
    if user_id in user_states:
        del user_states[user_id]
    bot.send_message(
        user_id,
        """
👑 **ПРИВЕТ! Я — АУРА КВИНСИ v14.0.**

Я — твоя персональная экосистема из **20+ искусственных интеллектов** в одном теле, усиленная десятками внешних API.

📌 **Мои новые суперспособности:**
🌤 Погода (OpenWeatherMap)
💰 Криптовалюты (CoinGecko)
🎤 Голосовые сообщения (ElevenLabs)
🌍 Супер-перевод (DeepL)
📸 Поиск картинок (Pexels)
📰 Новости (GNews)
📱 QR-коды
😄 Шутки (JokeAPI)

📋 **Как пользоваться:**
Нажми на кнопки меню или просто напиши мне как другу — я пойму тебя без команд.

💎 **Готова помочь 24/7. Просто начни!** 💋
""",
        reply_markup=get_main_keyboard()
    )

# ====================================================================
# 18. ОБРАБОТЧИКИ НОВЫХ КОМАНД
# ====================================================================
@bot.message_handler(commands=['weather'])
def cmd_weather(message):
    parts = message.text.split(' ', 1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "🌤 Напиши город, например: `/weather Москва`")
        return
    city = parts[1].strip()
    bot.send_chat_action(message.chat.id, 'typing')
    result = get_weather(city)
    bot.reply_to(message, result, parse_mode='Markdown')

@bot.message_handler(commands=['crypto'])
def cmd_crypto(message):
    parts = message.text.split(' ', 1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "💰 Напиши монету, например: `/crypto bitcoin`")
        return
    coin = parts[1].strip().lower()
    bot.send_chat_action(message.chat.id, 'typing')
    result = get_crypto(coin)
    bot.reply_to(message, result, parse_mode='Markdown')

@bot.message_handler(commands=['tts'])
def cmd_tts(message):
    parts = message.text.split(' ', 1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "🎤 Напиши текст, который я озвучу, например: `/tts Привет, я Аура Квинси!`")
        return
    text = parts[1].strip()
    bot.send_chat_action(message.chat.id, 'typing')
    audio, error = generate_tts(text)
    if audio:
        bot.send_audio(message.chat.id, audio, title="Голос Ауры Квинси")
    else:
        bot.reply_to(message, error)

@bot.message_handler(commands=['translate'])
def cmd_translate(message):
    parts = message.text.split(' ', 1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "🌍 Напиши текст для перевода. Например: `/translate Привет, как дела?`")
        return
    text = parts[1].strip()
    bot.send_chat_action(message.chat.id, 'typing')
    result = translate_deepl(text, 'EN')  # По умолчанию переводим на английский
    bot.reply_to(message, result, parse_mode='Markdown')

@bot.message_handler(commands=['pic'])
def cmd_pic(message):
    parts = message.text.split(' ', 1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "📸 Напиши, что хочешь увидеть, например: `/pic горы`")
        return
    query = parts[1].strip()
    bot.send_chat_action(message.chat.id, 'upload_photo')
    img_url = search_image_pexels(query)
    if img_url:
        bot.send_photo(message.chat.id, img_url, caption=f"✨ По запросу «{query}»")
    else:
        bot.reply_to(message, "😔 Не удалось найти картинку. Попробуй другое слово.")

@bot.message_handler(commands=['news'])
def cmd_news(message):
    parts = message.text.split(' ', 1)
    query = parts[1].strip() if len(parts) > 1 else None
    bot.send_chat_action(message.chat.id, 'typing')
    result = get_news_gnews(query)
    bot.reply_to(message, result, parse_mode='Markdown')

@bot.message_handler(commands=['qr'])
def cmd_qr(message):
    parts = message.text.split(' ', 1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "📱 Напиши ссылку или текст для QR-кода, например: `/qr https://t.me/auraKvinsi`")
        return
    data = parts[1].strip()
    bot.send_chat_action(message.chat.id, 'typing')
    qr_img = generate_qr_code(data)
    if qr_img:
        bot.send_photo(message.chat.id, qr_img, caption=f"📱 QR-код для: {data}")
    else:
        bot.reply_to(message, "❌ Не удалось сгенерировать QR-код.")

@bot.message_handler(commands=['joke'])
def cmd_joke(message):
    bot.send_chat_action(message.chat.id, 'typing')
    joke = get_random_joke()
    bot.reply_to(message, joke, parse_mode='Markdown')

# ====================================================================
# 19. КНОПКИ МЕНЮ (Умный парсер)
# ====================================================================
@bot.message_handler(func=lambda m: m.text in ['🌤 Погода', '💰 Крипто', '🌍 Перевод', '📰 Новости', '🎤 Голос', '📱 QR-код', '😄 Шутка'])
def handle_menu_buttons(message):
    action = message.text
    user_id = message.from_user.id
    if action == '🌤 Погода':
        bot.send_message(user_id, "🌤 Напиши город, например: `Москва`.")
        user_states[user_id] = 'weather'
    elif action == '💰 Крипто':
        bot.send_message(user_id, "💰 Напиши название монеты, например: `bitcoin`.")
        user_states[user_id] = 'crypto'
    elif action == '🌍 Перевод':
        bot.send_message(user_id, "🌍 Напиши текст для перевода (на английский).")
        user_states[user_id] = 'translate'
    elif action == '📰 Новости':
        bot.send_message(user_id, "📰 Напиши тему для новостей (или просто отправь `всё`).")
        user_states[user_id] = 'news'
    elif action == '🎤 Голос':
        bot.send_message(user_id, "🎤 Напиши текст, который я озвучу.")
        user_states[user_id] = 'tts'
    elif action == '📱 QR-код':
        bot.send_message(user_id, "📱 Напиши ссылку или текст для QR-кода.")
        user_states[user_id] = 'qr'
    elif action == '😄 Шутка':
        joke = get_random_joke()
        bot.reply_to(message, joke, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text in ['📝 План', '💻 Код', '📊 Анализ', '🎨 Дизайн', '🔥 Мотивация', '🛠️ Решение', '🧠 Идеи', '📚 Объясни', '🎉 Развлечение'])
def handle_ai_menu_buttons(message):
    func_map = {
        '📝 План': 'plan', '💻 Код': 'code', '📊 Анализ': 'analyze',
        '🎨 Дизайн': 'design', '🔥 Мотивация': 'motivate',
        '🛠️ Решение': 'solve', '🧠 Идеи': 'brainstorm',
        '📚 Объясни': 'explain', '🎉 Развлечение': 'fun'
    }
    func = func_map.get(message.text)
    user_id = message.from_user.id
    user_states[user_id] = func
    bot.send_message(
        user_id,
        f"✅ Вы выбрали **{message.text}**.\n\nТеперь напиши, что именно нужно сделать. Например, если выбрал «План», напиши: «открыть кафе».",
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == '📋 Меню')
def show_menu(message):
    bot.send_message(message.chat.id, "📋 Вот мои функции. Нажимай на кнопки и используй!", reply_markup=get_main_keyboard())

@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    user_id = message.from_user.id
    total_msgs = len(user_history.get(user_id, []))
    bot.reply_to(message, f"📊 **Статистика:**\nВсего сообщений в диалоге: {total_msgs}\nЯ готова помочь с любым запросом!")

@bot.message_handler(commands=['fact'])
def cmd_fact(message):
    facts = [
        "🧠 Мозг человека содержит около 86 миллиардов нейронов.",
        "🌍 Самая высокая гора в Солнечной системе — Олимп на Марсе (21.9 км).",
        "🐢 Черепахи могут жить до 150 лет.",
        "💡 Свет от Солнца достигает Земли за 8 минут и 20 секунд."
    ]
    bot.reply_to(message, random.choice(facts))

# ====================================================================
# 20. ГЛАВНЫЙ ОБРАБОТЧИК (Умный естественный язык)
# ====================================================================
@bot.message_handler(func=lambda m: True)
def general_handler(message):
    try:
        keeper.update()
        user_id = message.from_user.id
        user_last_msg[user_id] = time.time()

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
            if not user_text:
                return

        if user_text.startswith('/'):
            return

        # Проверка активных состояний (кнопки)
        state = user_states.get(user_id)
        if state:
            if state == 'weather':
                result = get_weather(user_text)
                bot.reply_to(message, result, parse_mode='Markdown')
                del user_states[user_id]
                return
            elif state == 'crypto':
                result = get_crypto(user_text.strip().lower())
                bot.reply_to(message, result, parse_mode='Markdown')
                del user_states[user_id]
                return
            elif state == 'translate':
                result = translate_deepl(user_text, 'EN')
                bot.reply_to(message, result, parse_mode='Markdown')
                del user_states[user_id]
                return
            elif state == 'news':
                result = get_news_gnews(user_text if user_text != 'всё' else None)
                bot.reply_to(message, result, parse_mode='Markdown')
                del user_states[user_id]
                return
            elif state == 'tts':
                audio, error = generate_tts(user_text)
                if audio:
                    bot.send_audio(message.chat.id, audio, title="Голос Ауры Квинси")
                else:
                    bot.reply_to(message, error)
                del user_states[user_id]
                return
            elif state == 'qr':
                qr_img = generate_qr_code(user_text)
                if qr_img:
                    bot.send_photo(message.chat.id, qr_img, caption=f"📱 QR-код для: {user_text}")
                else:
                    bot.reply_to(message, "❌ Не удалось сгенерировать QR-код.")
                del user_states[user_id]
                return
            elif state in ['plan', 'code', 'analyze', 'design', 'motivate', 'solve', 'brainstorm', 'explain', 'fun']:
                prompts = {
                    'plan': f"Составь подробный пошаговый план по запросу: {user_text}",
                    'code': f"Напиши готовый код на Python (или другом языке) для задачи: {user_text}",
                    'analyze': f"Проведи глубокий SWOT-анализ и разбор по запросу: {user_text}",
                    'design': f"Дай советы по UI/UX, цветам, шрифтам для проекта: {user_text}",
                    'motivate': f"Дай мощную мотивационную речь или цитату по теме: {user_text}",
                    'solve': f"Предложи эффективное решение для проблемы: {user_text}",
                    'brainstorm': f"Сгенерируй 10+ креативных идей по теме: {user_text}",
                    'explain': f"Объясни простыми словами и структурированно тему: {user_text}",
                    'fun': f"Расскажи что-то смешное, забавное или интересное по запросу: {user_text}"
                }
                full_query = prompts.get(state, user_text)
                bot.send_chat_action(message.chat.id, 'typing')
                answer = ask_ai(full_query, user_history[user_id])
                bot.reply_to(message, answer)
                del user_states[user_id]
                return

        # Умный парсер естественного языка
        lower = user_text.lower()
        if any(word in lower for word in ['стикер', 'наклейку', 'sticker']):
            if STICKERS:
                sticker_id = random.choice(list(STICKERS.values()))
                bot.send_sticker(message.chat.id, sticker_id)
                return

        if any(word in lower for word in ['гифку', 'gif', 'gifку']):
            if GIFS:
                url = random.choice(GIFS)
                bot.send_animation(message.chat.id, url)
            else:
                bot.reply_to(message, "У меня пока нет гифок.")
            return

        if any(word in lower for word in ['спасибо', 'благодарю', '❤️', '♥️']):
            if STICKERS and 'thanks' in STICKERS:
                bot.send_sticker(message.chat.id, STICKERS['thanks'])

        if any(word in lower for word in ['погода']):
            city = user_text.replace('погода', '').replace('в', '').strip()
            if city:
                result = get_weather(city)
                bot.reply_to(message, result, parse_mode='Markdown')
                return

        if any(word in lower for word in ['биткоин', 'крипто', 'курс', 'bitcoin']):
            result = get_crypto('bitcoin')
            bot.reply_to(message, result, parse_mode='Markdown')
            return

        # Основной AI-ответ
        bot.send_chat_action(message.chat.id, 'typing')
        answer = ask_ai(user_text, user_history[user_id])
        bot.reply_to(message, answer)

    except Exception as e:
        logger.error(f"⚠️ Критическая ошибка в обработчике: {e}")

# ====================================================================
# 21. МЕДИА-БАЗА
# ====================================================================
STICKERS = {
    'thanks': 'CAACAgIAAxkBAAE...',  # Замени на свои ID
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
# 22. СУПЕР-ЗАПУСК
# ====================================================================
if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("💋 АУРА КВИНСИ v14.0 — ULTIMATE ARSENAL")
    logger.info("🔥 20+ AI, Погода, Крипто, TTS, DeepL, Pexels, GNews, QR, Jokes.")
    logger.info("✅ Готов к работе 24/7. Абсолютный максимум.")
    logger.info("=" * 70)

    while True:
        try:
            bot.polling(none_stop=True, timeout=60, long_polling_timeout=30)
        except Exception as e:
            logger.error(f"🔄 Системная ошибка: {e}. Перезапуск через 3 секунды...")
            time.sleep(3)
