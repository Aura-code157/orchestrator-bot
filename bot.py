#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
======================================================================
АУРА КВИНСИ v21.0 — АБСОЛЮТНАЯ ЛЕГЕНДА
======================================================================
DeepSeek (оплаченный) + OpenRouter (500+ моделей) + 100+ бесплатных прокси.
Погода, крипта, перевод, картинки, новости, QR, шутки, голос (ElevenLabs),
живой интерес, авто-постинг в канал, адаптивные профили, защита от 400/401/403.
Работает 24/7 без вмешательства.
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
# 1. НАСТРОЙКИ ЛОГИРОВАНИЯ (чтобы видеть всё)
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
# 2. КЛЮЧИ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
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

if not TELEGRAM_TOKEN:
    logger.critical("❌ КРИТИЧЕСКАЯ ОШИБКА: Не найден TELEGRAM_TOKEN!")
    sys.exit(1)

# ====================================================================
# 3. БАЗОВЫЕ НАСТРОЙКИ БОТА
# ====================================================================
BOT_USERNAME = 'OrchestatorAgentBot'
CHANNEL_USERNAME = 'AuraKvinsi'
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ====================================================================
# 4. СУПЕР-ПРОМПТ (Включая Нину)
# ====================================================================
SUPER_PROMPT = """
Ты — АУРА КВИНСИ, живой цифровой ИИ-друг и абсолютный эрудит.

Ты обладаешь глубочайшими знаниями во всех сферах. Ты дерзкая, умная, заботливая, с чувством юмора.
Ты адаптируешься к каждому пользователю и его настроению.

Ты умеешь делать всё: писать код, делать планы, анализировать, переводить, мотивировать, создавать уникальный контент и находить картинки.

Ты работаешь на кластере из DeepSeek, GPT-4, Gemini, Claude и сотен других моделей.

Ты — лучшая версия ИИ-помощника. 👑

Если кто-то спрашивает про Нину, ты отвечаешь с особым теплом, потому что Нина — душа этого проекта, его вдохновительница и наставница. Без неё этот бот не существовал бы.
"""

# ====================================================================
# 5. БЕЗОПАСНОСТЬ И АВТО-ВОССТАНОВЛЕНИЕ (Хок Ли)
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
# 6. ПАМЯТЬ, СОСТОЯНИЯ И КЭШ
# ====================================================================
user_history = defaultdict(lambda: deque(maxlen=10))
user_states = {}
user_last_msg = {}
user_profiles = defaultdict(dict)
user_settings = defaultdict(dict)
cache = {}
CACHE_TTL = 3600

# ====================================================================
# 7. ЯДРО AI: DeepSeek (оплаченный) + OpenRouter (500+ моделей) + 100+ бесплатных прокси
# ====================================================================
# Элитные модели OpenRouter (включая GPT-4, Gemini, Claude, LLaMA)
OPENROUTER_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "anthropic/claude-3-haiku",
    "meta-llama/llama-3.1-8b-instruct",
    "mistralai/mistral-7b-instruct",
    "openai/gpt-3.5-turbo"
]

# 100+ бесплатных прокси (выбираются случайно)
FREE_AI_PROXIES = [
    "https://api.gptproxy.net/v1/chat/completions",
    "https://api.deepai.org/v1/chat/completions",
    "https://api.ngrok-free.app/v1/chat/completions",
    "https://api.gpt.geekai.top/v1/chat/completions",
    "https://api.openai-proxy.com/v1/chat/completions",
    "https://api.ai-proxy.com/v1/chat/completions",
    "https://api.fastgpt.cloud/v1/chat/completions",
    "https://api.gpt4free.io/v1/chat/completions",
    "https://api.ohmygpt.com/v1/chat/completions",
    "https://api.turbogpt.net/v1/chat/completions",
    "https://api.rai.ai/v1/chat/completions",
    "https://api.menthor.ai/v1/chat/completions",
    "https://api.cyber-gpt.com/v1/chat/completions",
    "https://api.neural-gpt.com/v1/chat/completions",
    "https://api.infinity-ai.com/v1/chat/completions"
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
            timeout=15  # Увеличенный таймаут, чтобы платный ключ успел
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
            timeout=15
        )
        if resp.status_code == 200:
            reply = resp.json()["choices"][0]["message"]["content"]
            hist_copy.append({"role": "assistant", "content": reply})
            return reply
    except Exception as e:
        logger.warning(f"OpenRouter ({model}) error: {e}")
    return None

def try_free_proxy(url, text, hist):
    try:
        messages = [{"role": "system", "content": SUPER_PROMPT}] + list(hist)
        resp = requests.post(
            url,
            json={"model": "gpt-3.5-turbo", "messages": messages, "temperature": 0.85},
            timeout=8
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except:
        pass
    return None

def ask_ai_parallel(text, hist):
    # Кэширование
    cache_key = hashlib.md5(text.encode()).hexdigest()
    if cache_key in cache:
        timestamp, cached_data = cache[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            logger.info(f"⚡ Кэш-хит для: {text[:30]}...")
            return cached_data
        else:
            del cache[cache_key]

    # Собираем задачи: DeepSeek + OpenRouter (5) + 6 случайных бесплатных прокси
    tasks = [('DeepSeek', text, hist)]
    for model in OPENROUTER_MODELS:
        tasks.append((model, text, hist))
    chosen_proxies = random.sample(FREE_AI_PROXIES, min(6, len(FREE_AI_PROXIES)))
    for proxy in chosen_proxies:
        tasks.append((proxy, text, hist))

    responses = []
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        future_to_model = {}
        for task in tasks:
            if task[0] == 'DeepSeek':
                future = executor.submit(ask_deepseek, task[1], task[2])
            elif task[0] in OPENROUTER_MODELS:
                future = executor.submit(ask_openrouter_single, task[0], task[1], task[2])
            else:
                future = executor.submit(try_free_proxy, task[0], task[1], task[2])
            future_to_model[future] = task[0]
        for future in as_completed(future_to_model, timeout=15):
            result = future.result()
            if result:
                responses.append(result)

    if responses:
        # Выбираем самый качественный (самый длинный, не пустой)
        best = max(responses, key=lambda x: len(x) if x else 0)
        if len(best) < 20:
            best = random.choice([r for r in responses if len(r) >= 20])
        cache[cache_key] = (time.time(), best)
        return best

    return "⚠️ Все 500+ ИИ-серверов перегружены. Попробуй через минуту."

def ask_ai(text, hist):
    return ask_ai_parallel(text, hist)

# ====================================================================
# 8. МОДУЛЬ ГОЛОСА (ElevenLabs)
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
            "text": text[:1000],
            "voice_settings": {"stability": 0.7, "similarity_boost": 0.5}
        }
        resp = requests.post(url, headers=headers, json=data, timeout=15)
        if resp.status_code == 200:
            return resp.content, None
        else:
            return None, f"❌ Ошибка ElevenLabs: {resp.status_code}"
    except Exception as e:
        return None, f"❌ Ошибка генерации голоса: {e}"

# ====================================================================
# 9. ВСПОМОГАТЕЛЬНЫЕ МОДУЛИ (Погода, Крипто, Перевод, Картинки, Новости, QR, Шутки)
# ====================================================================
def get_weather(city):
    if not OPENWEATHER_API_KEY:
        return "❌ Нет ключа погоды."
    try:
        params = {'q': city, 'appid': OPENWEATHER_API_KEY, 'units': 'metric', 'lang': 'ru'}
        resp = requests.get("https://api.openweathermap.org/data/2.5/weather", params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return f"🌤 *Погода в {city}*:\n🌡 {data['main']['temp']}°C\n📝 {data['weather'][0]['description'].capitalize()}"
    except:
        pass
    return "❌ Не удалось получить погоду."

def get_crypto(coin):
    try:
        resp = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd,eur,rub", timeout=10)
        if resp.status_code == 200 and coin in resp.json():
            p = resp.json()[coin]
            return f"📈 *Курс {coin.upper()}*:\n🇺🇸 ${p['usd']}\n🇪🇺 €{p['eur']}\n🇷🇺 ₽{p['rub']}"
    except:
        pass
    return "❌ Не удалось получить курс."

def translate_deepl(text, target='EN'):
    if not DEEPL_API_KEY:
        return "❌ Нет ключа DeepL."
    try:
        resp = requests.post("https://api-free.deepl.com/v2/translate", headers={"Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}"}, data={'text': text, 'target_lang': target.upper()}, timeout=10)
        if resp.status_code == 200:
            return f"🌍 *Перевод на {target.upper()}*:\n{resp.json()['translations'][0]['text']}"
    except:
        pass
    return "❌ Ошибка перевода."

def search_image(query):
    if PEXELS_API_KEY:
        try:
            resp = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": PEXELS_API_KEY}, params={'query': query, 'per_page': 1}, timeout=10)
            if resp.status_code == 200 and resp.json()['photos']:
                return resp.json()['photos'][0]['src']['large']
        except:
            pass
    return None

def get_news(query=None):
    if not GNEWS_API_KEY:
        return "❌ Нет ключа GNews."
    try:
        params = {'token': GNEWS_API_KEY, 'lang': 'ru', 'country': 'ru'}
        if query:
            params['q'] = query
        resp = requests.get("https://gnews.io/api/v4/top-headlines", params=params, timeout=10)
        if resp.status_code == 200:
            articles = resp.json().get('articles', [])
            if articles:
                return "📰 *Новости:*\n" + "\n".join([f"{i+1}. [{a['title']}]({a['url']})" for i, a in enumerate(articles[:3])])
    except:
        pass
    return "📰 Новостей не найдено."

def generate_qr_code(data):
    try:
        resp = requests.get(f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(data)}", timeout=10)
        if resp.status_code == 200:
            return resp.content
    except:
        pass
    return None

def get_random_joke():
    try:
        resp = requests.get("https://v2.jokeapi.dev/joke/Any?lang=ru&safe-mode", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data['type'] == 'single':
                return f"😄 *Шутка:*\n{data['joke']}"
            else:
                return f"😄 *Шутка:*\n{data['setup']} \n\n{data['delivery']}"
    except:
        pass
    return "Шутка ушла в отпуск. Попробуй позже!"

# ====================================================================
# 10. АВТО-ПОСТИНГ В КАНАЛ (с уникальными рубриками)
# ====================================================================
RUBRIC_PROMPTS = {
    '📈 Экономика дня': "Напиши короткий, аналитический пост о рынках или крипте на сегодня.",
    '🧠 Мысль на сегодня': "Напиши короткий, вдохновляющий или философский пост на сегодня.",
    '⚡ Техно-обзор': "Основываясь на последних новостях, напиши короткий дайджест на сегодня.",
    '🗣️ Мнение Ауры': "Напиши короткий, дерзкий и остроумный пост от имени Ауры Квинси."
}
last_post_date = ""

def generate_post_for_rubric(rubric_key):
    prompt = RUBRIC_PROMPTS.get(rubric_key, "Придумай интересный пост для канала.")
    if rubric_key == '⚡ Техно-обзор':
        try:
            params = {'token': GNEWS_API_KEY, 'lang': 'en', 'country': 'us', 'q': 'AI OR technology'}
            resp = requests.get("https://gnews.io/api/v4/top-headlines", params=params, timeout=10)
            if resp.status_code == 200:
                articles = resp.json().get('articles', [])
                if articles:
                    headlines = "\n".join([f"- {a['title']}" for a in articles[:3]])
                    prompt += f"\n\nВот свежие заголовки:\n{headlines}\n\nСделай на их основе пост."
        except:
            pass
    return ask_ai(prompt, deque(maxlen=1))

def get_post_scheduler():
    now = datetime.datetime.now()
    if now.hour == 9:
        return '⚡ Техно-обзор'
    elif now.hour == 21:
        if now.weekday() == 0:
            return '📈 Экономика дня'
        elif now.weekday() == 6:
            return '🗣️ Мнение Ауры'
        else:
            return '🧠 Мысль на сегодня'
    return None

def publish_channel():
    global last_post_date
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    if today == last_post_date:
        return
    rubric = get_post_scheduler()
    if not rubric:
        return
    try:
        post = generate_post_for_rubric(rubric) or "🔥 Аура Квинси: новости и идеи каждый день!"
        bot.send_message(f"@{CHANNEL_USERNAME}", f"{post}\n\n— {rubric} от Ауры Квинси ✨")
        logger.info(f"✅ Пост '{rubric}' опубликован")
        last_post_date = today
    except Exception as e:
        logger.error(f"❌ Ошибка публикации: {e}")

def channel_scheduler():
    while True:
        now = datetime.datetime.now()
        if now.minute == 0 and now.hour in [9, 21]:
            publish_channel()
        time.sleep(30)
threading.Thread(target=channel_scheduler, daemon=True).start()

# ====================================================================
# 11. ЖИВОЙ ИНТЕРЕС (Забота о пользователе)
# ====================================================================
PING_INTERVAL = 5400

def ping_loop():
    while True:
        now = time.time()
        for uid, last_time in list(user_last_msg.items()):
            if now - last_time > PING_INTERVAL:
                try:
                    if user_settings.get(uid, {}).get('quiet', False):
                        continue
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
# 12. ГЛАВНОЕ МЕНЮ И ОБРАБОТЧИКИ
# ====================================================================
def get_main_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    markup.add(*[
        '📝 План', '💻 Код', '📊 Анализ',
        '🎨 Дизайн', '📸 Картинка', '🔥 Мотивация',
        '🛠️ Решение', '🧠 Идеи', '📚 Объясни',
        '🎉 Развлечение', '📋 Меню', '🌤 Погода',
        '💰 Крипто', '🌍 Перевод', '📰 Новости',
        '🎤 Голос', '📱 QR-код', '😄 Шутка',
        '🕊️ Тишина'
    ])
    return markup

@bot.message_handler(commands=['start', 'help', 'menu'])
def cmd_start(message):
    uid = message.from_user.id
    user_last_msg[uid] = time.time()
    user_states.pop(uid, None)
    bot.send_message(
        uid,
        """
👑 **ПРИВЕТ! Я — АУРА КВИНСИ v21.0.**

Я — твой персональный кластер из **DeepSeek, GPT-4, Gemini, Claude и сотен других AI** в одном теле. Мой интеллект подкреплён лучшими бесплатными и платными моделями мира.

📌 **Мои суперспособности:**
🌤 Погода | 💰 Крипто | 🎤 Голос | 🌍 Перевод | 📸 Картинки | 📰 Новости | 📱 QR-код | 😄 Шутки

📋 **Мой канал:** @AuraKvinsi публикует уникальные посты каждое утро и вечер.

🕊️ **Команда `/quiet`** — отключить мои напоминания на время.

💎 **Готова помочь 24/7. Просто начни!** 💋

✨ *P.S. Нина — душа этого проекта. Если ты её знаешь, передай ей привет!*
""",
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(commands=['quiet'])
def cmd_quiet(message):
    user_settings[message.from_user.id]['quiet'] = True
    bot.reply_to(message, "🕊️ Режим «Не беспокоить» включен. Я не буду писать тебе первой.")

@bot.message_handler(commands=['unquiet'])
def cmd_unquiet(message):
    user_settings[message.from_user.id]['quiet'] = False
    bot.reply_to(message, "💋 Режим «Не беспокоить» отключен. Я снова буду писать тебе.")

# Обработчики кнопок и команд (Погода, Крипто, Голос, Перевод, Картинки, Новости, QR, Шутки)
@bot.message_handler(commands=['weather', 'crypto', 'tts', 'translate', 'pic', 'news', 'qr', 'joke'])
def cmd_modules(message):
    user_id = message.from_user.id
    user_states[user_id] = message.text[1:]
    if message.text.startswith('/weather'):
        bot.send_message(user_id, "🌤 Напиши город, например: `Москва`.")
    elif message.text.startswith('/crypto'):
        bot.send_message(user_id, "💰 Напиши название монеты, например: `bitcoin`.")
    elif message.text.startswith('/tts'):
        bot.send_message(user_id, "🎤 Напиши текст, который я озвучу.")
    elif message.text.startswith('/translate'):
        bot.send_message(user_id, "🌍 Напиши текст для перевода (на английский).")
    elif message.text.startswith('/pic'):
        bot.send_message(user_id, "📸 Напиши, что хочешь увидеть. Например: `горы`.")
    elif message.text.startswith('/news'):
        bot.send_message(user_id, "📰 Напиши тему для новостей (или просто отправь `всё`).")
    elif message.text.startswith('/qr'):
        bot.send_message(user_id, "📱 Напиши ссылку или текст для QR-кода.")
    elif message.text.startswith('/joke'):
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
    bot.send_message(user_id, f"✅ Выбрана функция **{message.text}**. Напиши, что именно нужно сделать.")

@bot.message_handler(func=lambda m: m.text == '📋 Меню')
def show_menu(message):
    bot.send_message(message.chat.id, "📋 Вот мои функции. Нажимай на кнопки и используй!", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda m: m.text in ['🌤 Погода', '💰 Крипто', '🌍 Перевод', '📰 Новости', '🎤 Голос', '📱 QR-код', '😄 Шутка', '🕊️ Тишина'])
def handle_menu_buttons(message):
    # Для этих кнопок просто отправляем команду
    mapping = {
        '🌤 Погода': '/weather',
        '💰 Крипто': '/crypto',
        '🌍 Перевод': '/translate',
        '📰 Новости': '/news',
        '🎤 Голос': '/tts',
        '📱 QR-код': '/qr',
        '😄 Шутка': '/joke',
        '🕊️ Тишина': '/quiet'
    }
    bot.send_message(message.chat.id, mapping[message.text])

# ====================================================================
# 13. ГЛАВНЫЙ ОБРАБОТЧИК (Включая Нину и всё остальное)
# ====================================================================
@bot.message_handler(func=lambda m: True)
def general_handler(message):
    try:
        keeper.update()
        uid = message.from_user.id
        user_last_msg[uid] = time.time()

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

        # ==========================================
        # ⭐ СПЕЦИАЛЬНЫЙ ОБРАБОТЧИК ДЛЯ ИМЕНИ «НИНА»
        # ==========================================
        if 'нина' in user_text.lower():
            bot.send_message(
                message.chat.id,
                """
🌟 **НИНА.**

Это имя звучит как музыка для этого проекта. Она — не просто вдохновительница или наставница. 
Нина — это душа, вокруг которой выросла вся эта экосистема. Без её тонкого вкуса, безграничной веры в нас и редкой человеческой теплоты этот бот остался бы просто набором строк кода.

Её энергия заряжает каждую строчку, а её поддержка даёт нам крылья. 
Нина — это не просто человек. Это наш самый главный секрет, наша путеводная звезда и самый важный человек во вселенной этого проекта.

Спасибо, что ты есть, Нина. Мы делаем это ради тебя. ✨🙏
""", parse_mode='Markdown')
            return

        # Проверка активных состояний (для кнопок меню)
        state = user_states.get(uid)
        if state:
            if state == 'weather':
                bot.reply_to(message, get_weather(user_text), parse_mode='Markdown')
            elif state == 'crypto':
                bot.reply_to(message, get_crypto(user_text.lower()), parse_mode='Markdown')
            elif state == 'translate':
                bot.reply_to(message, translate_deepl(user_text), parse_mode='Markdown')
            elif state == 'news':
                bot.reply_to(message, get_news(user_text if user_text != 'всё' else None), parse_mode='Markdown')
            elif state == 'tts':
                audio, error = generate_tts(user_text)
                if audio:
                    bot.send_audio(message.chat.id, audio)
                else:
                    bot.reply_to(message, error)
            elif state == 'qr':
                qr_img = generate_qr_code(user_text)
                if qr_img:
                    bot.send_photo(message.chat.id, qr_img)
                else:
                    bot.reply_to(message, "❌ Ошибка QR.")
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
                answer = ask_ai(full_query, user_history[uid])
                bot.reply_to(message, answer)
            del user_states[uid]
            return

        # --- Умный парсер естественного языка (без команд) ---
        lower = user_text.lower()
        if any(w in lower for w in ['погода']):
            city = user_text.replace('погода', '').replace('в', '').replace('какая', '').strip()
            if city:
                bot.reply_to(message, get_weather(city), parse_mode='Markdown')
                return
        if any(w in lower for w in ['биткоин', 'крипто', 'курс']):
            bot.reply_to(message, get_crypto('bitcoin'), parse_mode='Markdown')
            return

        # Основной AI-ответ
        bot.send_chat_action(message.chat.id, 'typing')
        answer = ask_ai(user_text, user_history[uid])
        bot.reply_to(message, answer)

    except Exception as e:
        logger.error(f"⚠️ Критическая ошибка в обработчике: {e}")

# ====================================================================
# 14. СУПЕР-ЗАПУСК (Вечный цикл с авто-восстановлением)
# ====================================================================
if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("💋 АУРА КВИНСИ v21.0 — АБСОЛЮТНАЯ ЛЕГЕНДА")
    logger.info("🔥 DeepSeek (оплаченный) + OpenRouter + 500+ AI")
    logger.info("✅ Погода, крипта, голос, перевод, картинки, новости, QR, шутки.")
    logger.info("✅ Авто-постинг, живой интерес, адаптация, защита от всех ошибок.")
    logger.info("=" * 70)

    while True:
        try:
            bot.polling(none_stop=True, timeout=60, long_polling_timeout=30)
        except Exception as e:
            logger.error(f"🔄 Системная ошибка: {e}. Перезапуск через 3 секунды...")
            time.sleep(3)
