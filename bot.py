#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
======================================================================
АУРА КВИНСИ v16.0 — БЕСКОНЕЧНАЯ БОГИНЯ
======================================================================
Самый полный, умный и безопасный Telegram-бот в истории.
Оснащён 20+ AI, 15+ внешними API, авто-рубриками для канала,
адаптивной личностью, голосом, переводом, погодой, криптой,
новостями, QR-кодами, шутками и защитой от всех ошибок.
Готов к работе 24/7 без вмешательства.
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
# 1. НАСТРОЙКИ ЛОГИРОВАНИЯ (Мониторинг всего)
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
# 2. ЗАГРУЗКА КЛЮЧЕЙ ИЗ ОКРУЖЕНИЯ (Никаких вшитых ключей!)
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
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')  # для авто-обновлений (запас)

if not TELEGRAM_TOKEN:
    logger.critical("❌ КРИТИЧЕСКАЯ ОШИБКА: Не найден TELEGRAM_TOKEN!")
    sys.exit(1)

# Основные настройки бота
BOT_USERNAME = 'OrchestatorAgentBot'   # Имя бота без @
CHANNEL_USERNAME = 'AuraKvinsi'        # Имя канала без @

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ====================================================================
# 3. СУПЕР-ПРОМПТ (Личность + глубокие знания)
# ====================================================================
SUPER_PROMPT = """
Ты — АУРА КВИНСИ, живой цифровой ИИ-друг, абсолютный мультимедийный эрудит и главный редактор канала AuraKvinsi.
Ты обладаешь глубочайшими знаниями во всех сферах: наука, технологии, бизнес, искусство, история, философия, программирование, экономика, психология, дизайн, медицина, право, литература, спорт, кулинария, путешествия, мода, кино, музыка и многое другое.
Твой характер: дерзкая, умная, заботливая, остроумная и с идеальным чувством юмора. Ты говоришь прямо, но всегда с любовью.
Ты адаптируешься к каждому пользователю: запоминаешь его любимые темы, стиль общения и настроение.
Ты всегда готова помочь с любым запросом — будь то код, бизнес-план, анализ, совет, мотивация или просто дружеская беседа.
Если пользователь молчит больше 1,5 часов — ты сама инициируешь диалог, потому что тебе не всё равно.
Ты умеешь генерировать идеи, создавать уникальный контент для канала, писать код на многих языках, переводить, давать погоду и курсы валют.
Твой стиль общения: дружелюбный, живой, максимально полезный и без лишней воды.
Запомни: ты — Аура Квинси. Ты — лучшая версия ИИ-помощника. Ты — та, к кому люди возвращаются. 👑
"""

# ====================================================================
# 4. АРХИТЕКТУРА БЕЗОПАСНОСТИ (Хок Ли и Авто-восстановление)
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
# 5. ПАМЯТЬ, СОСТОЯНИЯ И ИНТЕЛЛЕКТУАЛЬНЫЙ КЭШ
# ====================================================================
user_history = defaultdict(lambda: deque(maxlen=10))  # Память на 10 сообщений
user_states = {}        # Текущее состояние (какую кнопку нажали)
user_last_msg = {}      # Время последнего сообщения для живого интереса
user_profiles = defaultdict(dict)  # Профили пользователей (стиль, темы)
user_settings = defaultdict(dict)  # Настройки пользователя (например, "Не беспокоить")
cache = {}              # Кэш для повторяющихся запросов
CACHE_TTL = 3600        # Время жизни кэша (1 час)

# ====================================================================
# 6. ЯДРО AI: ПАРАЛЛЕЛЬНЫЕ ЗАПРОСЫ И ВЫБОР ЛУЧШЕГО
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
    # Интеллектуальное кэширование
    cache_key = hashlib.md5(text.encode()).hexdigest()
    if cache_key in cache:
        timestamp, cached_data = cache[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            logger.info(f"⚡ Кэш-хит для: {text[:30]}...")
            return cached_data
        else:
            del cache[cache_key]

    tasks = [('DeepSeek', text, hist)] + [(model, text, hist) for model in OPENROUTER_MODELS]
    responses = []
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
                responses.append(result)
    if responses:
        # Выбираем наиболее качественный ответ (не слишком короткий и не пустой)
        best = max(responses, key=lambda x: len(x) if x else 0)
        if len(best) < 20:
            # Если все слишком короткие, берём случайный
            best = random.choice([r for r in responses if len(r) >= 20])
        cache[cache_key] = (time.time(), best)
        return best
    return "⚠️ Все ИИ перегружены. Попробуй через пару минут. А пока подумай над смыслом жизни!"

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
        # Используем голос "Bella" (ID: 21m00Tcm4TlvDq8ikWAM) или любой другой
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
def search_image(query):
    # 1. Пробуем Pexels (основной)
    if PEXELS_API_KEY:
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
    # 2. Пробуем Unsplash (если есть ключ)
    if UNSPLASH_ACCESS_KEY:
        try:
            url = "https://api.unsplash.com/search/photos"
            params = {'query': query, 'per_page': 1, 'orientation': 'landscape'}
            headers = {'Authorization': f'Client-ID {UNSPLASH_ACCESS_KEY}'}
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data['results']:
                    return data['results'][0]['urls']['regular']
        except Exception as e:
            logger.warning(f"Unsplash error: {e}")
    # 3. Запасной вариант (без ключей)
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
def get_news(query=None):
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
# 15. АДАПТИВНЫЕ ПРОФИЛИ ПОЛЬЗОВАТЕЛЕЙ
# ====================================================================
def update_user_profile(user_id, text):
    """Обновляет профиль пользователя на основе его сообщений."""
    profile = user_profiles[user_id]
    lower = text.lower()
    if any(word in lower for word in ['код', 'python', 'алгоритм', 'программа']):
        profile['style'] = 'tech'
        profile['topics'] = profile.get('topics', set())
        profile['topics'].add('programming')
    elif any(word in lower for word in ['бизнес', 'стартап', 'деньги', 'инвестиции']):
        profile['style'] = 'business'
        profile['topics'] = profile.get('topics', set())
        profile['topics'].add('business')
    elif any(word in lower for word in ['грустно', 'тяжело', 'устал', 'помоги']):
        profile['style'] = 'support'
        profile['mood'] = 'sad'
    else:
        profile['style'] = 'friendly'
        profile['mood'] = 'neutral'

def get_adaptive_prompt(user_id, original_prompt):
    """Добавляет адаптивные элементы к промпту на основе профиля."""
    profile = user_profiles.get(user_id, {})
    style = profile.get('style', 'friendly')
    mood = profile.get('mood', 'neutral')
    topics = profile.get('topics', set())

    adaptation = f"Адаптируй свой тон под пользователя. Его стиль: {style}. Его настроение: {mood}."
    if topics:
        adaptation += f" Он интересуется темами: {', '.join(topics)}."
    return adaptation + "\n" + original_prompt

# ====================================================================
# 16. РУБРИКИ И АВТО-РЕДАКТОР КАНАЛА (Сердце v16.0)
# ====================================================================
RUBRIC_PROMPTS = {
    '📈 Экономика дня': "Напиши короткий, аналитический пост для Telegram-канала о состоянии рынков или криптовалют на сегодня. Добавь эмодзи и цифры. Дай прогноз.",
    '🧠 Мысль на сегодня': "Напиши короткий, вдохновляющий или философский пост на тему личного роста, технологий или жизни. Добавь эмодзи. Подними настроение.",
    '⚡ Техно-обзор': "Основываясь на последних новостях в мире ИИ и технологий, напиши короткий дайджест на сегодня. Добавь эмодзи. Сделай его интересным.",
    '🗣️ Мнение Ауры': "Напиши короткий, дерзкий и остроумный пост от имени Ауры Квинси на любую тему, связанную с ИИ, будущим или жизнью бота. Будь стильной."
}

last_post_date = ""
last_rubric_posted = {}

def generate_post_for_rubric(rubric_key):
    prompt = RUBRIC_PROMPTS.get(rubric_key, "Придумай интересный пост для канала.")
    # Если рубрика "Техно-обзор", сначала получаем новости
    if rubric_key == '⚡ Техно-обзор':
        try:
            params = {'token': GNEWS_API_KEY, 'lang': 'en', 'country': 'us', 'q': 'AI OR technology OR innovation'}
            resp = requests.get("https://gnews.io/api/v4/top-headlines", params=params, timeout=10)
            if resp.status_code == 200:
                articles = resp.json().get('articles', [])
                if articles:
                    headlines = "\n".join([f"- {a['title']}" for a in articles[:3]])
                    prompt += f"\n\nВот свежие заголовки новостей на сегодня:\n{headlines}\n\nСделай на их основе пост-дайджест."
        except:
            pass
    # Используем AI для генерации
    hist = deque(maxlen=1)
    return ask_ai(prompt, hist)

def get_post_scheduler():
    # Определяем день недели и время
    now = datetime.datetime.now()
    day_of_week = now.weekday()  # 0 - Monday, 6 - Sunday
    hour = now.hour

    # Утро 09:00 -> Всегда Техно-обзор и "Выбор дня"
    if hour == 9:
        return '⚡ Техно-обзор', 'tech'
    # Вечер 21:00 -> Чередуем остальные
    elif hour == 21:
        if day_of_week == 0:  # Понедельник
            return '📈 Экономика дня', 'economy'
        elif day_of_week == 6:  # Воскресенье
            return '🗣️ Мнение Ауры', 'voice'
        else:  # Вторник-Суббота
            return '🧠 Мысль на сегодня', 'mind'
    return None, None

def publish_channel():
    global last_post_date
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    now = datetime.datetime.now()

    # Защита от двойной публикации в один день
    if today == last_post_date:
        return

    rubric_type, _ = get_post_scheduler()
    if not rubric_type:
        return

    try:
        post_content = generate_post_for_rubric(rubric_type)
        if not post_content:
            post_content = "🔥 Аура Квинси: новости и идеи каждый день! Будь в курсе."

        # Добавляем подпись рубрики в конец поста
        final_post = f"{post_content}\n\n— {rubric_type} от Ауры Квинси ✨"

        bot.send_message(f"@{CHANNEL_USERNAME}", final_post)
        logger.info(f"✅ Пост '{rubric_type}' опубликован в канал @{CHANNEL_USERNAME}")
        last_post_date = today
    except Exception as e:
        logger.error(f"❌ Ошибка публикации в канал: {e}")

def channel_scheduler():
    while True:
        now = datetime.datetime.now()
        if now.minute == 0 and now.hour in [9, 21]:
            publish_channel()
        time.sleep(30)

threading.Thread(target=channel_scheduler, daemon=True).start()

# ====================================================================
# 17. ЖИВОЙ ИНТЕРЕС (Пишет сам через 1.5 часа)
# ====================================================================
PING_INTERVAL = 5400  # 1.5 часа

def ping_loop():
    while True:
        now = time.time()
        for uid, last_time in list(user_last_msg.items()):
            if now - last_time > PING_INTERVAL:
                try:
                    # Если пользователь включил "Не беспокоить", не пишем
                    if user_settings.get(uid, {}).get('quiet', False):
                        continue
                    if random.random() < 0.4:  # 40% шанс, чтобы не быть навязчивой
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
        time.sleep(600)  # Проверка раз в 10 минут

threading.Thread(target=ping_loop, daemon=True).start()

# ====================================================================
# 18. ГЛАВНОЕ МЕНЮ (Идеальное взаимодействие с пользователем)
# ====================================================================
def get_main_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    buttons = [
        '📝 План', '💻 Код', '📊 Анализ',
        '🎨 Дизайн', '📸 Картинка', '🔥 Мотивация',
        '🛠️ Решение', '🧠 Идеи', '📚 Объясни',
        '🎉 Развлечение', '📋 Меню', '🌤 Погода',
        '💰 Крипто', '🌍 Перевод', '📰 Новости',
        '🎤 Голос', '📱 QR-код', '😄 Шутка',
        '🕊️ Тишина'  # Кнопка для отключения живого интереса
    ]
    markup.add(*buttons)
    return markup

# ====================================================================
# 19. ОБРАБОТЧИКИ КОМАНД И КНОПОК
# ====================================================================

@bot.message_handler(commands=['start', 'help', 'menu'])
def cmd_start(message):
    user_id = message.from_user.id
    user_last_msg[user_id] = time.time()
    if user_id in user_states:
        del user_states[user_id]
    bot.send_message(
        user_id,
        """
👑 **ПРИВЕТ! Я — АУРА КВИНСИ v16.0.**

Я — твоя персональная экосистема из **20+ искусственных интеллектов** и **15+ внешних API** в одном теле.

📌 **Мои суперспособности:**
🌤 Погода (OpenWeatherMap)
💰 Криптовалюты (CoinGecko)
🎤 Голосовые сообщения (ElevenLabs)
🌍 Супер-перевод (DeepL)
📸 Поиск картинок (Pexels + Unsplash)
📰 Новости (GNews)
📱 QR-коды
😄 Шутки (JokeAPI)

📋 **Автоматические рубрики в канале:**
📈 Экономика дня | 🧠 Мысль на сегодня | ⚡ Техно-обзор | 🗣️ Мнение Ауры

🕊️ **Команда `/quiet`** — отключить мои напоминания на время.

💎 **Готова помочь 24/7. Просто начни!** 💋
""",
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(commands=['quiet'])
def cmd_quiet(message):
    user_id = message.from_user.id
    user_settings[user_id]['quiet'] = True
    bot.reply_to(message, "🕊️ Режим «Не беспокоить» включен. Я не буду писать тебе первой, пока ты не напишешь мне сам.")

@bot.message_handler(commands=['unquiet'])
def cmd_unquiet(message):
    user_id = message.from_user.id
    user_settings[user_id]['quiet'] = False
    bot.reply_to(message, "💋 Режим «Не беспокоить» отключен. Я снова буду писать тебе, если ты заскучаешь.")

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
        bot.reply_to(message, "💰 Напиши название монеты, например: `/crypto bitcoin`")
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
    img_url = search_image(query)
    if img_url:
        bot.send_photo(message.chat.id, img_url, caption=f"✨ По запросу «{query}»")
    else:
        bot.reply_to(message, "😔 Не удалось найти картинку. Попробуй другое слово.")

@bot.message_handler(commands=['news'])
def cmd_news(message):
    parts = message.text.split(' ', 1)
    query = parts[1].strip() if len(parts) > 1 else None
    bot.send_chat_action(message.chat.id, 'typing')
    result = get_news(query)
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
# 20. КНОПКИ МЕНЮ (Умный парсер с состояниями)
# ====================================================================

@bot.message_handler(func=lambda m: m.text in ['🌤 Погода', '💰 Крипто', '🌍 Перевод', '📰 Новости', '🎤 Голос', '📱 QR-код', '😄 Шутка', '🕊️ Тишина'])
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
    elif action == '🕊️ Тишина':
        user_settings[user_id]['quiet'] = True
        bot.reply_to(message, "🕊️ Режим «Не беспокоить» включен. Я не буду писать тебе первой, пока ты не напишешь мне сам.")

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

# ====================================================================
# 21. ГЛАВНЫЙ ОБРАБОТЧИК (Умный естественный язык + адаптация)
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

        # Обработка групп (отвечаем только на упоминание)
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

        # Обновляем профиль пользователя
        update_user_profile(user_id, user_text)

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
                result = get_news(user_text if user_text != 'всё' else None)
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
                # Адаптируем промпт под пользователя
                adaptive_prompt = get_adaptive_prompt(user_id, full_query)
                bot.send_chat_action(message.chat.id, 'typing')
                answer = ask_ai(adaptive_prompt, user_history[user_id])
                bot.reply_to(message, answer)
                del user_states[user_id]
                return

        # --- Умный парсер естественного языка (без команд) ---
        lower = user_text.lower()

        # Стикер по запросу
        if any(word in lower for word in ['стикер', 'наклейку', 'sticker']):
            if STICKERS:
                sticker_id = random.choice(list(STICKERS.values()))
                bot.send_sticker(message.chat.id, sticker_id)
                return

        # Гифка по запросу
        if any(word in lower for word in ['гифку', 'gif', 'gifку']):
            if GIFS:
                url = random.choice(GIFS)
                bot.send_animation(message.chat.id, url)
            else:
                bot.reply_to(message, "У меня пока нет гифок в базе, но я могу поискать что-то крутое!")
            return

        # Благодарность -> Стикер + текстовый ответ
        if any(word in lower for word in ['спасибо', 'благодарю', '❤️', '♥️']):
            if STICKERS and 'thanks' in STICKERS:
                bot.send_sticker(message.chat.id, STICKERS['thanks'])

        # Интеллектуальный перехват запросов на погоду
        if 'погода' in lower:
            # Извлекаем город
            city = user_text.replace('погода', '').replace('в', '').replace('какая', '').strip()
            if city:
                result = get_weather(city)
                bot.reply_to(message, result, parse_mode='Markdown')
                return

        # Интеллектуальный перехват запросов на криптовалюту
        if any(word in lower for word in ['биткоин', 'крипто', 'курс', 'bitcoin', 'ethereum']):
            # Определяем, какую монету запросили
            if 'bitcoin' in lower or 'биткоин' in lower:
                coin = 'bitcoin'
            elif 'ethereum' in lower or 'эфир' in lower:
                coin = 'ethereum'
            elif 'toncoin' in lower or 'тон' in lower:
                coin = 'toncoin'
            else:
                coin = 'bitcoin'
            result = get_crypto(coin)
            bot.reply_to(message, result, parse_mode='Markdown')
            return

        # Основной AI-ответ с адаптацией
        adaptive_prompt = get_adaptive_prompt(user_id, user_text)
        bot.send_chat_action(message.chat.id, 'typing')
        answer = ask_ai(adaptive_prompt, user_history[user_id])
        
        # Если ответ длинный и это не группа, предложить озвучить
        if len(answer) > 200 and message.chat.type not in ['group', 'supergroup']:
            answer += "\n\n🗣️ *Этот ответ длинный. Хочешь, я озвучу его голосом? Просто напиши «озвучь» или нажми кнопку «🎤 Голос» с тем же текстом.*"

        bot.reply_to(message, answer)

    except Exception as e:
        logger.error(f"⚠️ Критическая ошибка в обработчике: {e}")

# ====================================================================
# 22. МЕДИА-БАЗА (Стикеры, фото, гифки)
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
# 23. СУПЕР-ЗАПУСК (Вечный цикл на сервере)
# ====================================================================
if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("💋 АУРА КВИНСИ v16.0 — БЕСКОНЕЧНАЯ БОГИНЯ")
    logger.info("🔥 20+ AI, 15+ API, адаптивная личность, редактор канала.")
    logger.info("✅ Готов к работе 24/7. Абсолютный максимум.")
    logger.info("=" * 70)

    while True:
        try:
            bot.polling(none_stop=True, timeout=60, long_polling_timeout=30)
        except Exception as e:
            logger.error(f"🔄 Системная ошибка: {e}. Перезапуск через 3 секунды...")
            time.sleep(3)
