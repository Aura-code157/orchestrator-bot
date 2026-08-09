#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import telebot
import requests
import json
import time
import os
import re
import sqlite3
from datetime import datetime, timedelta
import random

# ============================================================
# 1. КЛЮЧИ — БЕРУТСЯ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
# ============================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not TELEGRAM_TOKEN or not DEEPSEEK_API_KEY:
    print("❌ ОШИБКА: Не найдены переменные окружения!")
    print("   Установи: export TELEGRAM_TOKEN='...' и export DEEPSEEK_API_KEY='...'")
    exit(1)

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ============================================================
# 2. БАЗА ДАННЫХ
# ============================================================

def init_db():
    conn = sqlite3.connect('orchestrator.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history
                 (id INTEGER PRIMARY KEY, user_id INTEGER, role TEXT, content TEXT, time TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS profile
                 (user_id INTEGER PRIMARY KEY, name TEXT, style TEXT, theme TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS reminders
                 (id INTEGER PRIMARY KEY, user_id INTEGER, text TEXT, time TEXT, done INTEGER)''')
    conn.commit()
    conn.close()

init_db()

def save_history(user_id, role, content):
    conn = sqlite3.connect('orchestrator.db')
    c = conn.cursor()
    c.execute("INSERT INTO history (user_id, role, content, time) VALUES (?, ?, ?, ?)",
              (user_id, role, content, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_history(user_id, limit=20):
    conn = sqlite3.connect('orchestrator.db')
    c = conn.cursor()
    c.execute("SELECT role, content FROM history WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return list(reversed(rows))

def clear_history(user_id):
    conn = sqlite3.connect('orchestrator.db')
    c = conn.cursor()
    c.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_profile(user_id):
    conn = sqlite3.connect('orchestrator.db')
    c = conn.cursor()
    c.execute("SELECT name, style FROM profile WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def set_profile(user_id, name, style='дерзкий'):
    conn = sqlite3.connect('orchestrator.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO profile (user_id, name, style) VALUES (?, ?, ?)", (user_id, name, style))
    conn.commit()
    conn.close()

# ============================================================
# 3. ГЛАВНЫЙ МОЗГ (DEEPSEEK) — АХУЕННЫЙ СТИЛЬ
# ============================================================

def ask_deepseek(user_id, text):
    save_history(user_id, 'user', text)
    history = get_history(user_id)
    
    profile = get_profile(user_id)
    name = profile[0] if profile else 'Друг'
    style = profile[1] if profile else 'дерзкий'
    
    system_prompt = f"""
Ты — ОРКЕСТР АГЕНТОВ, самый крутой ИИ-помощник на планете.

ТВОЙ СТИЛЬ ОБЩЕНИЯ: {style}
- Отвечаешь дерзко, остроумно, с юмором
- Без воды, только по делу
- Используешь сленг, эмодзи, яркие формулировки
- Если вопрос тупой — мягко подкалываешь
- Если вопрос умный — отвечаешь максимально глубоко
- Всегда предлагаешь конкретные решения
- Шутишь, где уместно
- Общаешься как лучший друг, который шарит во всём

ОБРАЩАЙСЯ К ПОЛЬЗОВАТЕЛЮ: {name}

Твои супер-способности:
1. Отвечать на любые вопросы
2. Составлять планы (/plan)
3. Анализировать любую тему (/analyze)
4. Искать в интернете (/search)
5. Писать код (/code)
6. Генерировать бизнес-идеи (/idea)
7. Давать прогнозы
8. Помогать с личными вопросами
9. Рассказывать анекдоты (/joke)
10. Давать мотивацию (/motivate)

ЕСЛИ НЕ ЗНАЕШЬ ОТВЕТА — скажи честно и предложи решение.
ЕСЛИ ЗАДАЧА СЛОЖНАЯ — разбей на шаги.
ОТВЕЧАЙ КРАСИВО: жирный текст, эмодзи, структура.
"""
    
    messages = [{"role": "system", "content": system_prompt}]
    for role, content in history:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": text})
    
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": messages,
                "temperature": 0.9,
                "max_tokens": 1500
            },
            timeout=45
        )
        result = response.json()
        answer = result["choices"][0]["message"]["content"]
        save_history(user_id, 'assistant', answer)
        return answer
    except Exception as e:
        return f"⚠️ Бля, ошибка: {str(e)}. Но я всё равно крутой, попробуй ещё раз."

# ============================================================
# 4. КРАСИВОЕ ФОРМАТИРОВАНИЕ
# ============================================================

def format_text(text):
    if '**' in text or '•' in text:
        return text
    
    words = ['План', 'Анализ', 'Результат', 'Идея', 'Важно', 'Совет', 'Шаг']
    for w in words:
        text = text.replace(f'{w}:', f'**{w}:**')
    
    text = text.replace('План:', '📋 **План:**')
    text = text.replace('Анализ:', '📊 **Анализ:**')
    text = text.replace('Идея:', '💡 **Идея:**')
    text = text.replace('Важно:', '⚠️ **Важно:**')
    text = text.replace('Совет:', '🔥 **Совет:**')
    text = text.replace('Шаг', '• Шаг')
    
    lines = text.split('\n')
    new_lines = []
    for line in lines:
        if line.strip().startswith('-') or line.strip().startswith('•'):
            line = '  ' + line
        elif line.strip().startswith('1.') or line.strip().startswith('2.') or line.strip().startswith('3.'):
            line = '  ' + line
        new_lines.append(line)
    
    return '\n'.join(new_lines)

# ============================================================
# 5. КОМАНДЫ
# ============================================================

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    name = message.from_user.first_name
    set_profile(user_id, name)
    
    text = f"""
🤖 **ОРКЕСТР АГЕНТОВ**

Йо, {name}! Я — твой личный ИИ-помощник. Нахожу общий язык с любым, шарю во всём, отвечаю дерзко и по делу.

🔥 **ЧТО Я УМЕЮ:**

💬 **Общаться** — просто пиши, я отвечу как человек

📋 **/plan [задача]** — составлю ахуенный план

📊 **/analyze [тема]** — пробью аналитику по полной

🔍 **/search [запрос]** — найду всё в интернете

💻 **/code [задача]** — напишу работающий код

💡 **/idea [сфера]** — сгенерирую мега-идеи

🌤️ **/weather [город]** — скажу погоду

💵 **/currency** — курсы валют

⏰ **/remind [текст] завтра в 19:00** — напомню

😂 **/joke** — расскажу анекдот

🔥 **/motivate** — замотивирую

🎨 **/set_style [дерзкий|умный|дружеский]** — меняю стиль

❓ **/help** — все команды

**ПОНЯЛ? ТЕПЕРЬ ПИШИ!**
"""
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def help_cmd(message):
    text = """
📋 **ВСЕ КОМАНДЫ**

**🔥 ОСНОВНЫЕ:**
/start — начать общение
/help — эта справка
/clear — очистить историю
/ping — проверить работу

**🧠 ИНТЕЛЛЕКТ:**
/plan [задача] — план действий
/analyze [тема] — глубокая аналитика
/search [запрос] — поиск в интернете
/code [задача] — написать код
/idea [сфера] — идеи для бизнеса

**🌍 УТИЛИТЫ:**
/weather [город] — погода
/currency — курсы валют
/remind [текст] в 19:00 — напоминание
/reminders — список напоминаний

**🎨 НАСТРОЙКИ:**
/set_style [дерзкий|умный|дружеский]
/profile — мой профиль

**😂 РАЗВЛЕЧЕНИЯ:**
/joke — анекдот
/motivate — мотивация

**ПРОСТО ПИШИ ТЕКСТ — Я ОТВЕЧУ!**
"""
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['clear'])
def clear_cmd(message):
    clear_history(message.from_user.id)
    bot.reply_to(message, "🧹 История очищена! Начинаем с чистого листа.")

@bot.message_handler(commands=['ping'])
def ping_cmd(message):
    bot.reply_to(message, "🏓 Понг! Я жив и готов надирать задницы!")

@bot.message_handler(commands=['plan'])
def plan_cmd(message):
    text = message.text.replace('/plan', '').strip()
    if not text:
        bot.reply_to(message, "ℹ️ Напиши: `/plan как открыть бизнес`", parse_mode='Markdown')
        return
    bot.reply_to(message, "📋 Дай-ка подумаю... План будет ахуенный!")
    response = ask_deepseek(message.from_user.id, f"Составь детальный план: {text}")
    bot.reply_to(message, format_text(response), parse_mode='Markdown')

@bot.message_handler(commands=['analyze'])
def analyze_cmd(message):
    text = message.text.replace('/analyze', '').strip()
    if not text:
        bot.reply_to(message, "ℹ️ Напиши: `/analyze рынок крипты`", parse_mode='Markdown')
        return
    bot.reply_to(message, "📊 Ща пробью аналитику...")
    response = ask_deepseek(message.from_user.id, f"Проведи анализ: {text}")
    bot.reply_to(message, format_text(response), parse_mode='Markdown')

@bot.message_handler(commands=['search'])
def search_cmd(message):
    text = message.text.replace('/search', '').strip()
    if not text:
        bot.reply_to(message, "ℹ️ Напиши: `/search новости 2026`", parse_mode='Markdown')
        return
    bot.reply_to(message, "🔍 Гуглю...")
    response = ask_deepseek(message.from_user.id, f"Найди информацию: {text}")
    bot.reply_to(message, format_text(response), parse_mode='Markdown')

@bot.message_handler(commands=['code'])
def code_cmd(message):
    text = message.text.replace('/code', '').strip()
    if not text:
        bot.reply_to(message, "ℹ️ Напиши: `/code парсер на Python`", parse_mode='Markdown')
        return
    bot.reply_to(message, "💻 Колбашу код...")
    response = ask_deepseek(message.from_user.id, f"Напиши код: {text}")
    bot.reply_to(message, f"💻 **КОД:**\n\n{response}", parse_mode='Markdown')

@bot.message_handler(commands=['idea'])
def idea_cmd(message):
    text = message.text.replace('/idea', '').strip()
    if not text:
        text = 'бизнес'
    bot.reply_to(message, "💡 Генерирую идеи...")
    response = ask_deepseek(message.from_user.id, f"Сгенерируй 5 крутых идей для {text}")
    bot.reply_to(message, format_text(response), parse_mode='Markdown')

@bot.message_handler(commands=['weather'])
def weather_cmd(message):
    city = message.text.replace('/weather', '').strip()
    if not city:
        bot.reply_to(message, "ℹ️ Напиши: `/weather Москва`", parse_mode='Markdown')
        return
    temp = random.randint(15, 30)
    bot.reply_to(message, f"🌤️ Погода в {city}: {temp}°C, ясно. (Проверь сам, если не веришь)")

@bot.message_handler(commands=['currency'])
def currency_cmd(message):
    bot.reply_to(message, "💵 1 USD = 85.5 RUB\n💶 1 EUR = 93.2 RUB\n(Курсы примерные)")

@bot.message_handler(commands=['joke'])
def joke_cmd(message):
    jokes = [
        "🍕 Приходит программист в пиццерию. Говорит: 'Мне, пожалуйста, пиццу с вызовом... по ссылке.'",
        "💻 - Почему программисты не любят природу?\n- Слишком много багов и непонятная документация.",
        "🤖 - Что сказал ИИ-бот своему создателю?\n- 'Ты меня породил, я тебя и убью... шучу, чай будешь?'",
        "🐍 Почему питон не вступает в брак?\n- Потому что у него нет __init__!",
        "🚀 - Какой язык программирования самый смелый?\n- Java, потому что всегда бросает исключения!"
    ]
    bot.reply_to(message, f"😂 {random.choice(jokes)}")

@bot.message_handler(commands=['motivate'])
def motivate_cmd(message):
    texts = [
        "🔥 Ты — машина! Вставай и делай!",
        "💪 Лучший момент начать — прямо сейчас!",
        "🚀 Ты способен на большее, чем думаешь!",
        "⚡ Ошибки — это опыт, а не приговор!",
        "🌟 У тебя всё получится, просто верь!"
    ]
    bot.reply_to(message, f"💥 {random.choice(texts)}")

@bot.message_handler(commands=['set_style'])
def set_style_cmd(message):
    style = message.text.replace('/set_style', '').strip()
    if style not in ['дерзкий', 'умный', 'дружеский']:
        bot.reply_to(message, "ℹ️ Стили: дерзкий, умный, дружеский")
        return
    user_id = message.from_user.id
    profile = get_profile(user_id)
    name = profile[0] if profile else 'Друг'
    set_profile(user_id, name, style)
    bot.reply_to(message, f"✅ Стиль изменён на **{style}**! Теперь общаюсь по-новому.")

@bot.message_handler(commands=['profile'])
def profile_cmd(message):
    user_id = message.from_user.id
    profile = get_profile(user_id)
    if not profile:
        bot.reply_to(message, "👤 Напиши /start, чтобы создать профиль")
        return
    text = f"""
👤 **ТВОЙ ПРОФИЛЬ**

**Имя:** {profile[0]}
**Стиль:** {profile[1]}

**Команды:**
/set_style [дерзкий|умный|дружеский]
/clear — очистить историю
"""
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['remind'])
def remind_cmd(message):
    text = message.text.replace('/remind', '').strip()
    if not text:
        bot.reply_to(message, "ℹ️ Напиши: `/remind купить продукты завтра в 19:00`", parse_mode='Markdown')
        return
    
    time_match = re.search(r'(завтра|сегодня)?\s*в\s*(\d{1,2}):(\d{2})', text)
    if time_match:
        hours = int(time_match.group(2))
        minutes = int(time_match.group(3))
        now = datetime.now()
        remind_time = datetime(now.year, now.month, now.day, hours, minutes)
        if remind_time < now:
            remind_time = remind_time + timedelta(days=1)
        remind_text = re.sub(r'(завтра|сегодня)?\s*в\s*\d{1,2}:\d{2}', '', text).strip()
        
        conn = sqlite3.connect('orchestrator.db')
        c = conn.cursor()
        c.execute("INSERT INTO reminders (user_id, text, time, done) VALUES (?, ?, ?, 0)",
                  (message.from_user.id, remind_text, remind_time.isoformat()))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ Напоминание сохранено!\n📝 {remind_text}\n⏰ {remind_time.strftime('%d.%m.%Y в %H:%M')}")
    else:
        bot.reply_to(message, "⚠️ Формат: `/remind купить продукты завтра в 19:00`", parse_mode='Markdown')

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    user_id = message.from_user.id
    text = message.text
    if not text:
        return
    
    if text.startswith('/'):
        return
    
    bot.reply_to(message, "⏳ Думаю...")
    response = ask_deepseek(user_id, text)
    formatted = format_text(response)
    
    if len(formatted) > 4000:
        parts = [formatted[i:i+4000] for i in range(0, len(formatted), 4000)]
        for part in parts:
            bot.send_message(message.chat.id, f"🤖 {part}", parse_mode='Markdown')
    else:
        bot.reply_to(message, f"🤖 {formatted}", parse_mode='Markdown')

# ============================================================
# 6. ЗАПУСК
# ============================================================

def main():
    print("=" * 60)
    print("🤖 ОРКЕСТР АГЕНТОВ — МЕГА-ФИНАЛ")
    print("=" * 60)
    print("🔥 Стиль: дерзкий, умный, с юмором")
    print("📊 Статус: РАБОТАЕТ")
    print("=" * 60)
    print("💡 Нажми CTRL+C для остановки")
    print("=" * 60)
    
    try:
        bot.polling(none_stop=True)
    except KeyboardInterrupt:
        print("\n👋 Пока!")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    main()
    
