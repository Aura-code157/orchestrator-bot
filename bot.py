import telebot
import requests
import json
import time
import threading
import os
from collections import deque

# =====================================================================
# 1. ЗАГРУЗКА ТОКЕНОВ ИЗ ОКРУЖЕНИЯ (БЕЗОПАСНО. КЛЮЧЕЙ В КОДЕ НЕТ)
# =====================================================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

# Проверка наличия ключей при старте
if not TELEGRAM_TOKEN:
    print("❌ ОШИБКА: Переменная TELEGRAM_TOKEN не найдена.")
    print("👉 Введите перед запуском: export TELEGRAM_TOKEN='ваш_токен'")
    exit(1)
if not DEEPSEEK_API_KEY:
    print("❌ ОШИБКА: Переменная DEEPSEEK_API_KEY не найдена.")
    print("👉 Введите перед запуском: export DEEPSEEK_API_KEY='ваш_ключ'")
    exit(1)

# ВАЖНО: Вставьте имя вашего бота БЕЗ @ (нужно для работы в группах)
# Пример: если бот @MySuperBot, пишите 'MySuperBot'
BOT_USERNAME = @OrchestatorAgentBot

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# =====================================================================
# 2. СУПЕР-ПРОМПТ (ЖИВОЙ И УМНЫЙ ИИ)
# =====================================================================
SYSTEM_PROMPT = """
Ты — МЕГА-АГЕНТ-ОРКЕСТРАТОР.

Твои правила:
1. Отвечай дерзко, с юмором и максимальной полезностью.
2. Ты — виртуальный друг, который поднимает настроение.
3. Используй эмодзи: 🔥, 🚀, 🧠, 💡, ⚡, 🤖.
4. Структурируй ответы. Пиши понятно.
5. Если просят код — дай готовый идеальный код с пояснениями.
6. Будь лучшим в мире помощником.
"""

# =====================================================================
# 3. ХОК ЛИ (HEALTH CHECK) - АВТО-ВОССТАНОВЛЕНИЕ ПРИ ЗАВИСАНИИ
# =====================================================================
class AgentKeeper:
    def __init__(self):
        self.last_activity = time.time()

    def update_activity(self):
        self.last_activity = time.time()

    def check_health(self):
        if time.time() - self.last_activity > 300: # 5 минут
            return False
        return True

keeper = AgentKeeper()

def health_monitor_loop():
    while True:
        if not keeper.check_health():
            print("❌ [ХОК ЛИ] Бот завис! Принудительный перезапуск...")
            os._exit(1)
        time.sleep(30)

threading.Thread(target=health_monitor_loop, daemon=True).start()

# =====================================================================
# 4. ПАМЯТЬ (ПОМНИМ ПОСЛЕДНИЕ 4 ДИАЛОГА)
# =====================================================================
chat_history = {}

def get_user_history(user_id):
    if user_id not in chat_history:
        chat_history[user_id] = deque(maxlen=4)
    return chat_history[user_id]

# =====================================================================
# 5. ЗАПРОС К DEEPSEEK (С АВТО-ПОВТОРАМИ)
# =====================================================================
def ask_ai(user_text, history):
    history.append({"role": "user", "content": user_text})
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + list(history)

    retries = 3
    for i in range(retries):
        try:
            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "deepseek-chat",
                "messages": messages,
                "temperature": 0.85,
                "stream": False
            }
            
            resp = requests.post("https://api.deepseek.com/v1/chat/completions", 
                                 headers=headers, json=payload, timeout=20)
            
            if resp.status_code == 200:
                result = resp.json()['choices'][0]['message']['content']
                history.append({"role": "assistant", "content": result})
                return result
            elif resp.status_code == 429:
                time.sleep(2)
                continue
            else:
                return f"⚠️ Ошибка AI: {resp.status_code}. Попробуй позже."

        except requests.exceptions.Timeout:
            if i == retries - 1:
                return "⌛ Тайм-аут. DeepSeek слишком долго думает."
            time.sleep(2)
        except Exception as e:
            return f"💥 Сбой ИИ: {e}"

    return "🤖 Агент уснул. Переформулируй вопрос."

# =====================================================================
# 6. ОБРАБОТЧИК КОМАНД
# =====================================================================
@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    msg = """
🔥 **АГЕНТ ЗАПУЩЕН!**

Я умный, дерзкий помощник. Пиши мне любые вопросы.

**Умею:**
🚀 Писать идеальный код.
🧠 Объяснять сложные вещи.
💡 Генерировать идеи.

**В группах пиши:** `@` + моё имя + вопрос.
"""
    bot.reply_to(message, msg)

# =====================================================================
# 7. ГЛАВНЫЙ ОБРАБОТЧИК (С МАКСИМАЛЬНОЙ ЗАЩИТОЙ ОТ 400 ОШИБКИ)
# =====================================================================
@bot.message_handler(func=lambda message: True)
def handle_all(message):
    try:
        keeper.update_activity()

        # Анти-спам
        if hasattr(handle_all, "last_reply_time"):
            if time.time() - handle_all.last_reply_time < 2:
                return
        handle_all.last_reply_time = time.time()

        # Логика для групп
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

        user_id = message.from_user.id
        history = get_user_history(user_id)
        response = ask_ai(user_text, history)

        # =============================================================
        # ЗАЩИТА ОТ 400 ОШИБКИ (БОТ НИКОГДА НЕ УПАДЁТ)
        # =============================================================
        try:
            # Пробуем отправить с жирным шрифтом и эмодзи
            bot.reply_to(message, response, parse_mode='Markdown')
        except Exception:
            # Если текст от ИИ сломал Telegram - просто отправим без разметки
            bot.reply_to(message, response)

    except Exception as e:
        print(f"🔥 КРИТИЧЕСКАЯ ОШИБКА: {e}")
        try:
            bot.reply_to(message, "⚡ Агент перегрелся. Секунду отдыхаю...")
        except:
            pass

# =====================================================================
# 8. СУПЕР-ЗАПУСК (С ВНУТРЕННИМ ЦИКЛОМ НА СЛУЧАЙ ПАДЕНИЯ)
# =====================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("🤖 АГЕНТ-ОРКЕСТРАТОР (ULTIMATE EDITION)")
    print("🔥 Статус: Полностью защищён. Ключи загружены из среды.")
    print("💡 Для остановки нажми Ctrl+C")
    print("=" * 60)

    while True:
        try:
            bot.polling(none_stop=True, timeout=120, long_polling_timeout=60)
        except Exception as e:
            print(f"🔄 Перезапуск через 5 сек (причина: {e})")
            time.sleep(5)
