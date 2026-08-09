import telebot
import requests
import time
import os
import threading
from collections import deque

T = os.getenv('TELEGRAM_TOKEN')
D = os.getenv('DEEPSEEK_API_KEY')

if not T or not D:
    print("❌ ОШИБКА: Ключи не найдены! Запустите через start.sh")
    exit(1)

BOT_NAME = 'OrchestratorAgentBot'
bot = telebot.TeleBot(T)

PROMPT = """
Ты — МЕГА-АГЕНТ-ОРКЕСТРАТОР.
Отвечай дерзко, с юмором, структурно и используй эмодзи 🔥🚀🤖.
Если просят план или код — давай сразу готовое решение.
"""

print("⚡ МЕГА-БОТ ЗАГРУЖЕН И ЖДЁТ КОМАНД...")

class Keeper:
    def __init__(self): self.last = time.time()
    def update(self): self.last = time.time()
    def is_alive(self): return time.time() - self.last < 300

keeper = Keeper()

def health_monitor():
    while True:
        if not keeper.is_alive():
            print("🔴 Обнаружен сбой. Экстренный перезапуск...")
            os._exit(1)
        time.sleep(30)

threading.Thread(target=health_monitor, daemon=True).start()

history = {}
def get_history(user_id):
    if user_id not in history:
        history[user_id] = deque(maxlen=4)
    return history[user_id]

def ask_deepseek(text, hist):
    hist.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": PROMPT}] + list(hist)
    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {D}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": messages, "temperature": 0.85},
            timeout=12
        )
        if resp.status_code == 200:
            reply = resp.json()["choices"][0]["message"]["content"]
            hist.append({"role": "assistant", "content": reply})
            return reply
        return "⚠️ DeepSeek перегружен. Попробуй позже."
    except:
        return "⌛ Тайм-аут соединения."

@bot.message_handler(commands=['start', 'help'])
def start_cmd(message):
    bot.reply_to(message, """
🔥 **МЕГА-БОТ ГОТОВ К БОЮ!**

**Технические характеристики:**
🤖 Язык: Python 3
🧠 Мозг: DeepSeek API
🧩 Память: 4 последних сообщения
🛡️ Защита: Авто-рестарт при сбоях

**Что я умею:**
🚀 Писать код и алгоритмы
💡 Генерировать идеи
🧠 Анализировать данные

Просто напиши мне вопрос! 👑
""")

@bot.message_handler(func=lambda m: True)
def main_handler(message):
    try:
        keeper.update()
        if hasattr(main_handler, "last_time"):
            if time.time() - main_handler.last_time < 2:
                return
        main_handler.last_time = time.time()

        if message.chat.type in ["group", "supergroup"]:
            if BOT_NAME not in message.text:
                return
            user_text = message.text.replace(f"@{BOT_NAME}", "").strip()
            if not user_text:
                return
        else:
            user_text = message.text.strip()

        if user_text.startswith("/"):
            return

        bot.send_chat_action(message.chat.id, "typing")
        answer = ask_deepseek(user_text, get_history(message.from_user.id))
        
        try:
            bot.reply_to(message, answer, parse_mode="Markdown")
        except:
            bot.reply_to(message, answer)

    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except:
            time.sleep(1)
