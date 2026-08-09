import telebot
import requests
import time
import os
import threading
from collections import deque

# =====================================================================
# ЗАГРУЗКА КЛЮЧЕЙ ИЗ СИСТЕМЫ (БЕЗ КЛЮЧЕЙ В КОДЕ!)
# =====================================================================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

if not TELEGRAM_TOKEN:
    print("❌ ОШИБКА: Не найден TELEGRAM_TOKEN.")
    exit(1)
if not DEEPSEEK_API_KEY:
    print("❌ ОШИБКА: Не найден DEEPSEEK_API_KEY.")
    exit(1)

# ВСТАВЬТЕ ИМЯ БОТА БЕЗ @. Например: 'OrchestratorAgentBot'
BOT_USERNAME = 'OrchestratorAgentBot'

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Системный промпт (чтобы бот был дерзким и умным)
SYSTEM_PROMPT = """
Ты — МЕГА-АГЕНТ-ОРКЕСТРАТОР.
Отвечай дерзко, с юмором, используй эмодзи 🔥 🚀 🤖.
Если просят план или анализ — делай крутой разбор.
"""

# =====================================================================
# СИСТЕМА ЗДОРОВЬЯ (ХОК ЛИ)
# =====================================================================
class Keeper:
    def __init__(self):
        self.last_activity = time.time()
    def update(self):
        self.last_activity = time.time()
    def check(self):
        return time.time() - self.last_activity < 300

keeper = Keeper()

def monitor_loop():
    while True:
        if not keeper.check():
            print("❌ Бот завис! Экстренный перезапуск...")
            os._exit(1)
        time.sleep(30)

threading.Thread(target=monitor_loop, daemon=True).start()

# =====================================================================
# ПАМЯТЬ И ЛОГИКА
# =====================================================================
hist = {}
def get_history(user_id):
    if user_id not in hist:
        hist[user_id] = deque(maxlen=4)
    return hist[user_id]

def ask_deepseek(text, history):
    history.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + list(history)

    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": messages,
                "temperature": 0.85
            },
            timeout=20
        )
        if resp.status_code == 200:
            answer = resp.json()["choices"][0]["message"]["content"]
            history.append({"role": "assistant", "content": answer})
            return answer
        return "⚠️ Ошибка от DeepSeek."
    except:
        return "⌛ Тайм-аут соединения."

# =====================================================================
# КОМАНДЫ
# =====================================================================
@bot.message_handler(commands=['start', 'help'])
def start_msg(message):
    bot.reply_to(message, "🔥 **АГЕНТ ЗАПУЩЕН!**\nПиши вопросы, я всё решу!")

# =====================================================================
# ГЛАВНЫЙ ОБРАБОТЧИК (С ЗАЩИТОЙ ОТ 400 ОШИБКИ)
# =====================================================================
@bot.message_handler(func=lambda m: True)
def handle_all(message):
    try:
        keeper.update()

        # Анти-спам (не отвечать чаще 2 раз в секунду)
        if hasattr(handle_all, "last_time"):
            if time.time() - handle_all.last_time < 2:
                return
        handle_all.last_time = time.time()

        # Логика для групп и лички
        if message.chat.type in ["group", "supergroup"]:
            if BOT_USERNAME not in message.text:
                return
            user_text = message.text.replace(f"@{BOT_USERNAME}", "").strip()
            if not user_text:
                return
        else:
            user_text = message.text.strip()

        if user_text.startswith("/"):
            return

        bot.send_chat_action(message.chat.id, "typing")
        user_id = message.from_user.id

        # Получаем ответ от AI
        answer = ask_deepseek(user_text, get_history(user_id))

        # === БЕЗОПАСНАЯ ОТПРАВКА (ЗАЩИТА ОТ 400) ===
        try:
            bot.reply_to(message, answer, parse_mode="Markdown")
        except:
            bot.reply_to(message, answer)

    except Exception as e:
        print(f"Ошибка: {e}")

# =====================================================================
# ЗАПУСК
# =====================================================================
if __name__ == "__main__":
    print("=" * 50)
    print("🤖 ОРКЕСТРАТОР БОТ РАБОТАЕТ!")
    print("🔥 Ошибка 400 исправлена.")
    print("💡 Нажми CTRL+C для остановки")
    print("=" * 50)

    while True:
        try:
            bot.polling(none_stop=True, timeout=120)
        except Exception as e:
            print(f"🔄 Перезапуск через 5 сек: {e}")
            time.sleep(5)
