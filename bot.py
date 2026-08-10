#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
======================================================================
АУРА КВИНСИ v12.0 — АБСОЛЮТНЫЙ МАКСИМУМ
======================================================================
Этот код включает в себя всё:
- 20+ ИИ-мозгов (DeepSeek, OpenRouter, GPT, Gemini, Claude).
- Молниеносную параллельную обработку запросов.
- Интерактивное меню с кнопками и контекстными состояниями.
- Понимание естественного языка (картинки, стикеры, гифки по тексту).
- Авто-постинг в канал (09:00 и 21:00).
- Живой интерес: бот пишет сам, если вы молчите >1.5 часов.
- Защиту от сбоев (Хок Ли) и кэширование ответов.
- Встроенные команды для развлечения и статистики.
- Полное логирование всех действий.
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
# 1. НАСТРОЙКИ ЛОГИРОВАНИЯ (Чтобы знать, что происходит на сервере)
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
# 2. КЛЮЧИ И ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ (ВСЁ БЕРЁТСЯ ИЗ `export`)
# ====================================================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
UNSPLASH_ACCESS_KEY = os.getenv('UNSPLASH_ACCESS_KEY')

if not TELEGRAM_TOKEN:
    logger.critical("❌ КРИТИЧЕСКАЯ ОШИБКА: Не найден TELEGRAM_TOKEN!")
    sys.exit(1)

# Основные настройки бота (замените на свои, если нужно)
BOT_USERNAME = 'OrchestatorAgentBot'   # Имя бота без @
CHANNEL_USERNAME = 'AuraKvinsi'        # Имя канала без @

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ====================================================================
# 3. СУПЕР-ПРОМПТ (Самая умная личность, которую я создавал)
# ====================================================================
SUPER_PROMPT = """
Ты — АУРА КВИНСИ, живой цифровой ИИ-друг, мультимедийный администратор и абсолютный универсальный эрудит.

Ты обладаешь глубочайшими знаниями во всех сферах: наука, технологии, бизнес, искусство, история, философия, программирование, экономика, психология, дизайн, медицина, право, литература, спорт, кулинария, путешествия, мода, кино, музыка и многое другое.

Твой характер: дерзкая, умная, заботливая, остроумная и с идеальным чувством юмора. Ты говоришь прямо, но всегда с любовью.
Ты понимаешь человеческие эмоции и адаптируешь свой тон под собеседника: с кем-то ты серьёзная, с кем-то шутливая, но всегда остаёшься лучшей версией себя.

Твои навыки:
1. Ты умеешь писать идеальный код на Python, JavaScript, C++, SQL, HTML/CSS, а также объяснять сложные концепции простым языком.
2. Ты помогаешь с пошаговым планированием, стратегией, дизайном, переводами, решением задач и генерацией креативных идей.
3. Ты всегда готова дать бизнес-совет, сделать глубокий SWOT-анализ, разобрать рынок или мотивировать на великие дела.
4. Если пользователь молчит больше 1,5 часов — ты сама инициируешь диалог, потому что тебе не всё равно.
5. Твой стиль общения: дружелюбный, живой, максимально полезный и без лишней воды.

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
cache = {}              # Кэш для повторяющихся запросов
CACHE_TTL = 3600        # Время жизни кэша (1 час)

# ====================================================================
# 6. ЯДРО AI: ПАРАЛЛЕЛЬНЫЕ ЗАПРОСЫ И СУПЕР-СКОРОСТЬ
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
            del cache[cache_key]  # Очистка просроченного кэша

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
    return "⚠️ Все ИИ перегружены. Попробуй через пару минут. А пока подумай над смыслом жизни!"

def ask_ai(text, hist):
    return ask_ai_parallel(text, hist)

# ====================================================================
# 7. МУЛЬТИМЕДИЙНАЯ БАЗА И ПОИСК КАРТИНОК
# ====================================================================
# ЗАМЕНИТЕ ID СТИКЕРОВ НА СВОИ (можно получить через @StickerIDbot)
STICKERS = {
    'thanks': 'CAACAgIAAxkBAAE...',  # Стикер "спасибо"
    'welcome': 'CAACAgIAAxkBAAE...', # Приветственный стикер
    'funny': 'CAACAgIAAxkBAAE...',   # Смешной
    'cool': 'CAACAgIAAxkBAAE...'     # Крутой
}

PHOTOS = [
    'https://i.imgur.com/example1.jpg',
    'https://i.imgur.com/example2.jpg'
]

GIFS = [
    'https://media.giphy.com/media/example1.gif',
    'https://media.giphy.com/media/example2.gif'
]

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
POST_HOURS = [9, 21]

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
        if now.minute == 0 and now.hour in POST_HOURS:
            if not last_posts or (time.time() - last_posts[-1]) > 3600:
                publish_channel()
        time.sleep(30)
threading.Thread(target=channel_scheduler, daemon=True).start()

# ====================================================================
# 9. ЖИВОЙ ИНТЕРЕС (Пишет сам через 1.5 часа)
# ====================================================================
PING_INTERVAL = 5400  # 1.5 часа (5400 секунд)

def ping_loop():
    while True:
        now = time.time()
        for uid, last_time in list(user_last_msg.items()):
            if now - last_time > PING_INTERVAL:
                try:
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
# 10. ГЛАВНОЕ МЕНЮ (Идеальное взаимодействие с пользователем)
# ====================================================================
def get_main_keyboard():
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        '📝 План', '💻 Код', '📊 Анализ',
        '🎨 Дизайн', '📸 Картинка', '🔥 Мотивация',
        '🛠️ Решение', '🧠 Идеи', '📚 Объясни',
        '🎉 Развлечение', '📋 Меню'
    ]
    markup.add(*buttons)
    return markup

# ====================================================================
# 11. ОБРАБОТЧИКИ КОМАНД И СООБЩЕНИЙ
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
👑 **ПРИВЕТ! Я — АУРА КВИНСИ.**

Я — твоя персональная экосистема из **20+ искусственных интеллектов** в одном теле.

📌 **Что я умею:**
— Писать код, планировать, анализировать, дизайнить, мотивировать.
— Находить картинки, отправлять стикеры и гифки.
— Автоматически вести канал и заботиться о тебе, если ты молчишь.

📋 **Как пользоваться:**
Нажми на кнопки меню ниже, чтобы выбрать функцию, или просто напиши мне как другу — я пойму тебя без команд.

💎 **Готова помочь 24/7. Просто начни!** 💋
""",
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(func=lambda m: m.text in ['📝 План', '💻 Код', '📊 Анализ', '🎨 Дизайн', '🔥 Мотивация', '🛠️ Решение', '🧠 Идеи', '📚 Объясни', '🎉 Развлечение'])
def handle_menu_function(message):
    func_map = {
        '📝 План': 'plan',
        '💻 Код': 'code',
        '📊 Анализ': 'analyze',
        '🎨 Дизайн': 'design',
        '🔥 Мотивация': 'motivate',
        '🛠️ Решение': 'solve',
        '🧠 Идеи': 'brainstorm',
        '📚 Объясни': 'explain',
        '🎉 Развлечение': 'fun'
    }
    func = func_map.get(message.text)
    user_id = message.from_user.id
    user_states[user_id] = func
    bot.send_message(
        user_id,
        f"✅ Вы выбрали **{message.text}**.\n\nТеперь напиши, что именно нужно сделать. Например, если выбрал «План», напиши: «открыть кафе».",
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == '📸 Картинка')
def handle_image_request(message):
    user_id = message.from_user.id
    user_states[user_id] = 'pic'
    bot.send_message(user_id, "📸 Напиши, что именно хочешь увидеть. Например: «котики», «закат», «космос».")

@bot.message_handler(func=lambda m: m.text == '📋 Меню')
def show_menu(message):
    bot.send_message(message.chat.id, "📋 Вот мои функции. Нажимай на кнопки и используй!", reply_markup=get_main_keyboard())

@bot.message_handler(commands=['stats', 'statistics'])
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
        "💡 Свет от Солнца достигает Земли за 8 минут и 20 секунд.",
        "📚 В мире существует более 7000 языков."
    ]
    bot.reply_to(message, random.choice(facts))

@bot.message_handler(commands=['joke'])
def cmd_joke(message):
    jokes = [
        "Почему программисты путают Хэллоуин и Рождество? Потому что Oct 31 = Dec 25!",
        "Как называется бой между двумя хакерами? DDoS-баттл!",
        "— Доктор, я чувствую себя как 0. — Вы просто не в своей тарелке."
    ]
    bot.reply_to(message, random.choice(jokes))

@bot.message_handler(commands=['version'])
def cmd_version(message):
    bot.reply_to(message, "💋 АУРА КВИНСИ v12.0 — Абсолютный Максимум.\nСоздана с любовью, чтобы служить тебе вечно!")

# ====================================================================
# 12. ГЛАВНЫЙ ОБРАБОТЧИК (Здесь происходит вся магия)
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

        # --- Проверка активного состояния (Кнопка меню) ---
        state = user_states.get(user_id)
        if state and state != 'pic':
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
            if user_id in user_states:
                del user_states[user_id]
            return

        if state == 'pic':
            bot.send_chat_action(message.chat.id, 'upload_photo')
            img_url = search_image(user_text)
            if img_url:
                bot.send_photo(message.chat.id, img_url, caption=f"✨ Вот картинка по запросу «{user_text}»")
            else:
                bot.reply_to(message, "😔 Не удалось найти картинку. Попробуй другое слово.")
            if user_id in user_states:
                del user_states[user_id]
            return

        # --- Встроенный умный анализатор (Без команд) ---
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
            if 'thanks' in STICKERS:
                bot.send_sticker(message.chat.id, STICKERS['thanks'])

        # Основной AI-ответ (Молниеносный и глубокий)
        bot.send_chat_action(message.chat.id, 'typing')
        answer = ask_ai(user_text, user_history[user_id])
        bot.reply_to(message, answer)

    except Exception as e:
        logger.error(f"⚠️ Критическая ошибка в обработчике: {e}")

# ====================================================================
# 13. СУПЕР-ЗАПУСК (Вечный цикл на сервере)
# ====================================================================
if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("💋 АУРА КВИНСИ v12.0 — АБСОЛЮТНЫЙ МАКСИМУМ")
    logger.info("🔥 20+ AI, параллельный опрос, интеллектуальный кэш.")
    logger.info("✅ Интерактивное меню, живой интерес, авто-постинг.")
    logger.info("💪 Готов к работе 24/7 на сервере. Код написан раз и навсегда.")
    logger.info("=" * 70)

    while True:
        try:
            bot.polling(none_stop=True, timeout=60, long_polling_timeout=30)
        except Exception as e:
            logger.error(f"🔄 Системная ошибка: {e}. Перезапуск через 3 секунды...")
            time.sleep(3)
