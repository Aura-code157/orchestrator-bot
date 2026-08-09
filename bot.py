#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import telebot
import requests
import json
import time
import os
import re
from datetime import datetime, timedelta
import sqlite3

# ============================================================
# КЛЮЧИ БЕРУТСЯ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
# ============================================================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not TELEGRAM_TOKEN or not DEEPSEEK_API_KEY:
    print("❌ ОШИБКА: Не найдены переменные окружения!")
    print("   Установи: TELEGRAM_TOKEN и DEEPSEEK_API_KEY")
    exit(1)

# ============================================================
# ИНИЦИАЛИЗАЦИЯ
# ============================================================

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def init_database():
    conn = sqlite3.connect('orchestrator.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            user_id INTEGER,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            remind_time DATETIME,
            is_done INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            style TEXT DEFAULT 'деловой'
        )
    ''')
    conn.commit()
    conn.close()

init_database()

def save_history(user_id, role, content):
    conn = sqlite3.connect('orchestrator.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO history (user_id, role, content) VALUES (?, ?, ?)',
        (user_id, role, content)
    )
    conn.commit()
    conn.close()

def get_history(user_id, limit=10):
    conn = sqlite3.connect('orchestrator.db')
    cursor = conn.cursor()
    cursor.execute(
        'SELECT role, content FROM history WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?',
        (user_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return list(reversed(rows))

def clear_history(user_id):
    conn = sqlite3.connect('orchestrator.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM history WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def ask_deepseek(user_id, user_message, system_prompt=None):
    save_history(user_id, 'user', user_message)
    history = get_history(user_id)
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    else:
        messages.append({
            "role": "system",
            "content": "Ты — Оркестр Агентов, цифровой дирижёр. Отвечай кратко, полезно, по делу."
        })
    
    for role, content in history:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})
    
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        result = response.json()
        ai_response = result["choices"][0]["message"]["content"]
        save_history(user_id, 'assistant', ai_response)
        return ai_response
    except Exception as e:
        return f"⚠️ Ошибка: {str(e)}"

@bot.message_handler(commands=['start'])
def start_command(message):
    welcome_text = """
🤖 **ОРКЕСТР АГЕНТОВ**
Твой цифровой дирижёр

**Что я умею:**
1️⃣ Умный диалог
2️⃣ Память
3️⃣ Планирование — /plan
4️⃣ Анализ — /analyze
5️⃣ Напоминания — /remind
"""
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = """
📋 **КОМАНДЫ**
/start — Приветствие
/help — Справка
/clear — Очистить историю
/plan — План
/analyze — Анализ
/remind — Напоминание
"""
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['clear'])
def clear_command(message):
    clear_history(message.from_user.id)
    bot.reply_to(message, "🧹 История очищена!")

@bot.message_handler(commands=['plan'])
def plan_command(message):
    text = message.text.replace('/plan', '').strip()
    if not text:
        bot.reply_to(message, "ℹ️ Напиши: /plan как начать бизнес")
        return
    bot.reply_to(message, "⏳ Составляю план...")
    response = ask_deepseek(message.from_user.id, f"Составь пошаговый план: {text}")
    bot.reply_to(message, f"📋 **ПЛАН:**\n\n{response}", parse_mode='Markdown')

@bot.message_handler(commands=['analyze'])
def analyze_command(message):
    text = message.text.replace('/analyze', '').strip()
    if not text:
        bot.reply_to(message, "ℹ️ Напиши: /analyze рынок")
        return
    bot.reply_to(message, "🔍 Анализирую...")
    response = ask_deepseek(message.from_user.id, f"Проведи анализ: {text}")
    bot.reply_to(message, f"📊 **АНАЛИЗ:**\n\n{response}", parse_mode='Markdown')

@bot.message_handler(commands=['remind'])
def remind_command(message):
    text = message.text.replace('/remind', '').strip()
    if not text:
        bot.reply_to(message, "ℹ️ Напиши: /remind купить продукты завтра в 19:00")
        return
    bot.reply_to(message, f"⏰ Напоминание сохранено: {text}")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text
    
    if not user_text:
        bot.reply_to(message, "📝 Напиши что-нибудь!")
        return
    
    bot.reply_to(message, "⏳ Думаю...")
    response = ask_deepseek(user_id, user_text)
    bot.reply_to(message, f"🤖 **Ответ:**\n\n{response}", parse_mode='Markdown')

def main():
    print("=" * 50)
    print("🤖 ОРКЕСТР АГЕНТОВ ЗАПУЩЕН!")
    print("=" * 50)
    print("📅", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("📊 Статус: Работает")
    print("=" * 50)
    
    try:
        bot.polling(none_stop=True)
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен.")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    main()
