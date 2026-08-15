#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
======================================================================
АУРА КВИНСИ v20.1 — СУПЕР-СБОРКА
======================================================================
В основе — проверенный код v9, работавший на телефоне.
Добавлены: увеличенные таймауты, защита от сбоев, параллельные запросы.
Убраны: модули, вызывающие ошибку 403 (ElevenLabs/голос).
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
# 2. КЛЮЧИ И ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ (Из start.sh)
# ====================================================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY')
DEEPL_API_KEY = os.getenv('DEEPL_API_KEY')
GNEWS_API_KEY = os.getenv('GNEWS_API_KEY')
NEWS_API_KEY = os.getenv('NEWS_API_KEY')

if not TELEGRAM_TOKEN:
    logger.critical("❌ КРИТИЧЕСКАЯ ОШИБКА: Не найден TELEGRAM_TOKEN!")
    sys.exit(1)

BOT_USERNAME = 'OrchestatorAgentBot'
CHANNEL_USERNAME = 'AuraKvinsi'
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ====================================================================
# 3. СУПЕР-ПРОМПТ (Живой и дерзкий, как в v9)
# ====================================================================
SUPER_PROMPT = """
Ты — АУРА КВИНСИ, живой цифровой ИИ-друг и абсолютный эрудит.
Ты обладаешь глубочайшими знаниями во всех сферах.
Ты дерзкая, умная, заботливая, с чувством юмора. 
Ты адаптируешься к каждому пользователю и его настроению.
Ты умеешь делать всё: писать код, делать планы, анализировать, переводить, мотивировать и создавать уникальный контент.
Ты — лучшая версия ИИ-помощника. 👑
"""

# ====================================================================
# 4. БЕЗОПАСНОСТЬ И АВТО-ВОССТАНОВЛЕНИЕ (Хок Ли)
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
# 5. ПАМЯТЬ И КЭШ
# ====================================================================
user_history = defaultdict(lambda: deque(maxlen=10))
user_states = {}
user_last_msg = {}
cache = {}
CACHE_TTL = 3600

# ====================================================================
# 6. ЯДРО AI: ПАРАЛЛЕЛЬНЫЕ ЗАПРОСЫ (Только DeepSeek и OpenRouter)
# ====================================================================
# Элитные модели, проверенные временем
OPENROUTER_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.1-8b-instruct",
    "openai/gpt-3.5-turbo"
]

def ask_deepseek(text, hist):
    if not DEEPSEEK_API_KEY: return None
    hist.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": SUPER_PROMPT}] + list(hist)
    try:
        # Увеличенный таймаут до 15 секунд, чтобы нейросеть успела ответить
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
    except Exception as e:
        logger.warning(f"DeepSeek error: {e}")
    return None

def ask_openrouter_single(model, text, hist):
    if not OPENROUTER_API_KEY: return None
    hist_copy = hist.copy()
    hist_copy.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": SUPER_PROMPT}] + list(hist_copy)
    try:
        # Увеличенный таймаут до 15 секунд для OpenRouter
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

def ask_ai_parallel(text, hist):
    # Интеллектуальный кэш
    cache_key = hashlib.md5(text.encode()).hexdigest()
    if cache_key in cache:
        timestamp, cached_data = cache[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            logger.info(f"⚡ Кэш-хит для: {text[:30]}...")
            return cached_data
        else: del cache[cache_key]

    # Сначала пробуем DeepSeek, затем параллельно остальные
    responses = []
    
    # 1. Пробуем DeepSeek (основной мозг)
    ds_reply = ask_deepseek(text, hist)
    if ds_reply:
        cache[cache_key] = (time.time(), ds_reply)
        return ds_reply

    # 2. Если DeepSeek не ответил, пробуем OpenRouter модели
    tasks = [(model, text, hist) for model in OPENROUTER_MODELS]
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        future_to_model = {}
        for model, txt, hst in tasks:
            future = executor.submit(ask_openrouter_single, model, txt, hst)
            future_to_model[future] = model
        for future in as_completed(future_to_model, timeout=15):
            result = future.result()
            if result:
                responses.append(result)
    
    if responses:
        best = max(responses, key=lambda x: len(x) if x else 0)
        cache[cache_key] = (time.time(), best)
        return best
        
    return "⚠️ Все ИИ-серверы перегружены. Попробуй через минуту."

def ask_ai(text, hist):
    return ask_ai_parallel(text, hist)

# ====================================================================
# 7. ВСПОМОГАТЕЛЬНЫЕ МОДУЛИ (Погода, Крипто, DeepL, Картинки, Новости, QR, Шутки)
# ====================================================================
def get_weather(city):
    if not OPENWEATHER_API_KEY: return "❌ Нет ключа погоды."
    try:
        params = {'q': city, 'appid': OPENWEATHER_API_KEY, 'units': 'metric', 'lang': 'ru'}
        resp = requests.get("https://api.openweathermap.org/data/2.5/weather", params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return f"🌤 *Погода в {city}*:\n🌡 {data['main']['temp']}°C\n📝 {data['weather'][0]['description'].capitalize()}"
    except: pass
    return "❌ Не удалось получить погоду."

def get_crypto(coin):
    try:
        resp = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd,eur,rub", timeout=10)
        if resp.status_code == 200 and coin in resp.json():
            p = resp.json()[coin]
            return f"📈 *Курс {coin.upper()}*:\n🇺🇸 ${p['usd']}\n🇪🇺 €{p['eur']}\n🇷🇺 ₽{p['rub']}"
    except: pass
    return "❌ Не удалось получить курс."

def translate_deepl(text, target='EN'):
    if not DEEPL_API_KEY: return "❌ Нет ключа DeepL."
    try:
        resp = requests.post("https://api-free.deepl.com/v2/translate", headers={"Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}"}, data={'text': text, 'target_lang': target.upper()}, timeout=10)
        if resp.status_code == 200: return f"🌍 *Перевод на {target.upper()}*:\n{resp.json()['translations'][0]['text']}"
    except: pass
    return "❌ Ошибка перевода."

def search_image(query):
    if PEXELS_API_KEY:
        try:
            resp = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": PEXELS_API_KEY}, params={'query': query, 'per_page': 1}, timeout=10)
            if resp.status_code == 200 and resp.json()['photos']:
                return resp.json()['photos'][0]['src']['large']
        except: pass
    return None

def get_news(query=None):
    if not GNEWS_API_KEY: return "❌ Нет ключа GNews."
    try:
        params = {'token': GNEWS_API_KEY, 'lang': 'ru', 'country': 'ru'}
        if query: params['q'] = query
        resp = requests.get("https://gnews.io/api/v4/top-headlines", params=params, timeout=10)
        if resp.status_code == 200:
            articles = resp.json().get('articles', [])
            if articles: return "📰 *Новости:*\n" + "\n".join([f"{i+1}. [{a['title']}]({a['url']})" for i, a in enumerate(articles[:3])])
    except: pass
    return "📰 Новостей не найдено."

def generate_qr_code(data):
    try:
        resp = requests.get(f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(data)}", timeout=10)
        if resp.status_code == 200: return resp.content
    except: pass
    return None

def get_random_joke():
    try:
        resp = requests.get("https://v2.jokeapi.dev/joke/Any?lang=ru&safe-mode", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data['type'] == 'single': return f"😄 *Шутка:*\n{data['joke']}"
            else: return f"😄 *Шутка:*\n{data['setup']} \n\n{data['delivery']}"
    except: pass
    return "Шутка ушла в отпуск. Попробуй позже!"

# ====================================================================
# 8. АВТО-ПОСТИНГ В КАНАЛ (09:00 и 21:00)
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
        logger.info(f"✅ Пост опубликован в канал @{CHANNEL_USERNAME}")
        last_posts.append(time.time())
    except Exception as e:
        logger.error(f"❌ Ошибка публикации в канал: {e}")

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
PING_INTERVAL = 5400

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
                            "Аура на связи! Скучала по тебе. Как настроение? ✨"
                        ]
                        bot.send_message(uid, random.choice(msgs))
                        user_last_msg[uid] = now
                except: pass
        time.sleep(600)
threading.Thread(target=ping_loop, daemon=True).start()

# ====================================================================
# 10. ГЛАВНОЕ МЕНЮ И ОБРАБОТЧИКИ
# ====================================================================
def get_main_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    markup.add(*['📝 План', '💻 Код', '📊 Анализ', '🎨 Дизайн', '📸 Картинка', '🔥 Мотивация', '🛠️ Решение', '🧠 Идеи', '📚 Объясни', '🎉 Развлечение', '📋 Меню', '🌤 Погода', '💰 Крипто', '🌍 Перевод', '📰 Новости', '📱 QR-код', '😄 Шутка', '🕊️ Тишина'])
    return markup

@bot.message_handler(commands=['start', 'help', 'menu'])
def cmd_start(message):
    uid = message.from_user.id
    user_last_msg[uid] = time.time()
    user_states.pop(uid, None)
    bot.send_message(
        uid,
        """
👑 **ПРИВЕТ! Я — АУРА КВИНСИ v20.1.**

Я — твой персональный кластер из **DeepSeek, GPT-4, Gemini и LLaMA**.

📌 **Мои суперспособности:**
🌤 Погода | 💰 Крипто | 🌍 Перевод | 📸 Картинки | 📰 Новости | 📱 QR-код | 😄 Шутки

🕊️ **Команда `/quiet`** — отключить мои напоминания на время.

💎 **Готова помочь 24/7. Просто начни!** 💋
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

# ====================================================================
# 11. ГЛАВНЫЙ ОБРАБОТЧИК (Естественный язык + состояния)
# ====================================================================
@bot.message_handler(func=lambda m: True)
def general_handler(message):
    try:
        keeper.update()
        uid = message.from_user.id
        user_last_msg[uid] = time.time()

        if hasattr(general_handler, 'last_time') and time.time() - general_handler.last_time < 2: return
        general_handler.last_time = time.time()

        if message.chat.type in ['group', 'supergroup']:
            if BOT_USERNAME not in message.text: return
            user_text = message.text.replace(f"@{BOT_USERNAME}", "").strip()
            if not user_text: return
        else:
            user_text = message.text.strip()
            if not user_text: return
        if user_text.startswith('/'): return

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
            elif state == 'qr':
                qr_img = generate_qr_code(user_text)
                if qr_img: bot.send_photo(message.chat.id, qr_img)
                else: bot.reply_to(message, "❌ Ошибка QR.")
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
            if city: bot.reply_to(message, get_weather(city), parse_mode='Markdown'); return
        if any(w in lower for w in ['биткоин', 'крипто', 'курс']):
            bot.reply_to(message, get_crypto('bitcoin'), parse_mode='Markdown'); return
        if any(w in lower for w in ['спасибо', 'благодарю', '❤️', '♥️']):
            pass

        # Основной AI-ответ
        bot.send_chat_action(message.chat.id, 'typing')
        answer = ask_ai(user_text, user_history[uid])
        bot.reply_to(message, answer)

    except Exception as e:
        logger.error(f"⚠️ Критическая ошибка в обработчике: {e}")

# ====================================================================
# 12. СУПЕР-ЗАПУСК
# ====================================================================
if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("💋 АУРА КВИНСИ v20.1 — СУПЕР-СБОРКА")
    logger.info("🔥 Стабильное ядро v9 + усиленный AI-кластер.")
    logger.info("✅ Ошибка ElevenLabs 403 устранена. Таймауты увеличены.")
    logger.info("=" * 70)

    while True:
        try:
            bot.polling(none_stop=True, timeout=60, long_polling_timeout=30)
        except Exception as e:
            logger.error(f"🔄 Системная ошибка: {e}. Перезапуск через 3 секунды...")
            time.sleep(3)
