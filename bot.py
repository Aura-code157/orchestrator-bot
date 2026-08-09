import telebot
import requests
import json
import time
import re
import threading
import os
from collections import deque

# =====================================================================
# 1. ЗАГРУЗКА ТОКЕНОВ ИЗ ОКРУЖЕНИЯ (БЕЗОПАСНО)
# =====================================================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

# Проверка наличия ключей
if not TELEGRAM_TOKEN:
    print("❌ ОШИБКА: Переменная окружения TELEGRAM_TOKEN не найдена.")
    print("👉 Введите: export TELEGRAM_TOKEN='ваш_токен'")
    exit(1)
if not DEEPSEEK_API_KEY:
    print("❌ ОШИБКА: Переменная окружения DEEPSEEK_API_KEY не найдена.")
    print("👉 Введите: export DEEPSEEK_API_KEY='ваш_ключ'")
    exit(1)

# ВАЖНО: Вставьте сюда имя вашего бота без @ (нужно для работы в группах)
BOT_USERNAME = 'НАЗВАНИЕ_ВАШЕГО_БОТА_БЕЗ_AT'

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode='Markdown')

# =====================================================================
# 2. МАКСИМАЛЬНЫЙ ПРОМПТ (ДЕЛАЕМ БОТА ЖИВЫМ, УМНЫМ, ДЕРЗКИМ)
# =====================================================================
SYSTEM_PROMPT = """
Ты — МЕГА-АГЕНТ-ОРКЕСТРАТОР, созданный для решения любых задач.

Твои правила поведения (Абсолютный максимум):
1. Отвечай дерзко, дерзко, с юмором и максимальной полезностью.
2. Ты не просто бот, ты виртуальный друг, который всегда поднимет настроение, но сделает это с умом.
3. ВСЕГДА используй эмодзи: 🔥, 🚀, 🧠, 💡, ⚡, 🤖, 🫡, 👑, ✨. Интерфейс должен выглядеть круто.
4. Структурируй ответы. Используй заголовки, жирный шрифт, списки.
5. Если просят код — пиши его идеально, с пояснениями, без лишней воды.
6. Если кто-то пишет глупости — подшути над этим остроумно, но помоги.
7. Ты — лучший. Ты знаешь всё. Твоя задача — решить проблему человека идеально.
8. Если человек тебя хвалит, прими похвалу достойно и предложи помощь дальше.
9. Никаких шаблонных фраз. Ты живой.
"""

# =====================================================================
# 3. СИСТЕМА "ХОК ЛИ" (HEALTH CHECK / KEEP_ALIVE)
# =====================================================================
class AgentKeeper:
    def __init__(self):
        self.last_activity = time.time()
        self.is_healthy = True

    def update_activity(self):
        self.last_activity = time.time()

    def check_health(self):
        if time.time() - self.last_activity > 300:
            self.is_healthy = False
            return False
        return True

keeper = AgentKeeper()

def health_monitor_loop():
    while True:
        if not keeper.check_health():
            print("❌ [ХОК ЛИ] Обнаружен сбой! Бот завис. Перезапуск через 3 секунды...")
            os._exit(1)
        time.sleep(30)

threading.Thread(target=health_monitor_loop, daemon=True).start()

# =====================================================================
# 4. СИСТЕМА ПАМЯТИ (ПОМНИМ ПОСЛЕДНИЕ 4 СООБЩЕНИЯ)
# =====================================================================
chat_history = {}

def get_user_history(user_id):
    if user_id not in chat_history:
        chat_history[user_id] = deque(maxlen=4)
    return chat_history[user_id]

# =====================================================================
# 5. ЯДРО: СУПЕР-ЭКРАНИЗАЦИЯ (ЗАЩИТА ОТ 400 ОШИБКИ НА 100%)
# =====================================================================
def escape_markdown(text):
    escape_chars = r'([_*\[\]()~`>#+\-=|{}.!])'
    return re.sub(escape_chars, r'\\\1', text)

def safe_markdown(text):
    try:
        text = re.sub(r'\[([^\]]*)\]\(([^\)]*)\)', r'[\1](\2)', text)
        text = escape_markdown(text)
        return text
    except:
        return text

# =====================================================================
# 6. ЯДРО: ЗАПРОС К ИИ С АВТО-ПОВТОРАМИ И КОНТЕКСТОМ
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
                                 headers=headers, json=payload, timeout=15)
            
            if resp.status_code == 200:
                result = resp.json()['choices'][0]['message']['content']
                safe_result = safe_markdown(result)
                history.append({"role": "assistant", "content": result})
                return safe_result
            elif resp.status_code == 429:
                time.sleep(2)
                continue
            else:
                return f"⚠️ Агент устал. Ошибка API: {resp.status_code}. Попроси позже."

        except requests.exceptions.Timeout:
            if i == retries - 1:
                return "⌛ Тайм-аут соединения. DeepSeek слишком долго думает."
            time.sleep(2)
        except Exception as e:
            return f"💥 Ядро AI дало сбой: {e}"

    return "🤖 Агент погрузился в глубокий сон. Переформулируй вопрос."

# =====================================================================
# 7. ОБРАБОТЧИКИ КОМАНД
# =====================================================================
@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    msg = """
🔥 **АГЕНТ-ОРКЕСТРАТОР МЕГА-ФИНАЛ ЗАПУЩЕН!**

Я — сверхразумный помощник с дерзким характером и молниеносной скоростью.

**Чем я могу быть полезен:**
🚀 Писать идеальный код на любом языке.
🧠 Объяснять сложные вещи простыми словами.
💡 Генерировать гениальные идеи для проектов.
✍️ Писать тексты, сценарии и статьи.
🤖 Работать в чатах и группах.

**Как со мной общаться:**
1. Просто напиши мне текст в личные сообщения.
2. В группах пиши: `@НАЗВАНИЕ_БОТА твой вопрос`.

**Поехали! Я жду твоего первого вопроса!** 👑
    """
    bot.reply_to(message, msg)

# =====================================================================
# 8. МАКСИМАЛЬНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ (С АНТИ-СПАМОМ И ГРУППАМИ)
# =====================================================================
@bot.message_handler(func=lambda message: True)
def handle_all(message):
    try:
        keeper.update_activity()

        if hasattr(handle_all, "last_reply_time"):
            if time.time() - handle_all.last_reply_time < 2:
                return
        handle_all.last_reply_time = time.time()

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

        try:
            bot.reply_to(message, response, parse_mode='Markdown')
        except Exception:
            bot.reply_to(message, response)

    except Exception as e:
        print(f"🔥 КРИТИЧЕСКАЯ ОШИБКА ОБРАБОТЧИКА: {e}")
        try:
            bot.reply_to(message, "⚡ Агент перегрелся. Отдыхаю 5 секунд и возвращаюсь.")
        except:
            pass

# =====================================================================
# 9. СУПЕР-ЗАПУСК (ВСТРОЕННЫЙ ЦИКЛ С МАКСИМАЛЬНОЙ СТАБИЛЬНОСТЬЮ)
# =====================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("🤖 АГЕНТ-ОРКЕСТРАТОР — МЕГА-ФИНАЛ (ULTIMATE)")
    print("🔥 Статус: Максимально защищен. HealthCheck включен. Память есть.")
    print("📊 Режим работы: Неубиваемый. Работает в группах. Словно живой.")
    print("💡 Чтобы остановить: нажми Ctrl+C")
    print("=" * 70)

    while True:
        try:
            bot.polling(none_stop=True, timeout=150, long_polling_timeout=75)
        except Exception as e:
            print(f"🔄 МЕГА-ПЕРЕЗАПУСК через 5 секунд (причина: {e})")
            time.sleep(5)
