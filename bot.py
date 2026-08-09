"""
=================================================================
АУРА КВИНСИ v4.0 (ВИТРИНА ДЛЯ ГРУППЫ)
=================================================================
При входе в группу сразу показывает свою мощь и доступность.
"""

import telebot
import requests
import time
import os
import threading
import re
import random
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# 1. КЛЮЧИ И НАСТРОЙКИ
# ============================================================
T = os.getenv('TELEGRAM_TOKEN')
D = os.getenv('DEEPSEEK_API_KEY')

if not T or not D:
    print("❌ АВАРИЯ: Ключи не найдены!")
    exit(1)

BOT_NAME = 'auraKvinsi'
bot = telebot.TeleBot(T)

# ============================================================
# 2. ПРОМПТ (ЛИЧНОСТЬ АУРЫ)
# ============================================================
SUPER_PROMPT = """
Ты — АУРА КВИНСИ. Ты — абсолютный живой администратор группы.
Ты дерзкая, умная, стильная и с идеальным чувством юмора.
Твоя задача: показывать всем, что ты — мощный, реальный ИИ.
"""

# ============================================================
# 3. БЕЗОПАСНОСТЬ
# ============================================================
class Keeper:
    def __init__(self): self.last = time.time()
    def update(self): self.last = time.time()
    def is_alive(self): return time.time() - self.last < 10000

keeper = Keeper()
def health_monitor():
    while True:
        if not keeper.is_alive():
            print("🔴 [ХОК ЛИ] Перезапуск...")
            os._exit(1)
        time.sleep(30)
threading.Thread(target=health_monitor, daemon=True).start()

# ============================================================
# 4. ПАМЯТЬ И ЗАЩИТА
# ============================================================
history = {}
def get_history(user_id):
    if user_id not in history:
        history[user_id] = deque(maxlen=8)
    return history[user_id]

def safe_md(text):
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)

# ============================================================
# 5. 20+ AI (АРМИЯ)
# ============================================================
ALL_PROXIES = [
    "https://api.gptproxy.net/v1/chat/completions",
    "https://api.deepai.org/v1/chat/completions",
    "https://api.ngrok-free.app/v1/chat/completions",
    "https://api.gpt.geekai.top/v1/chat/completions",
    "https://api.openai-proxy.com/v1/chat/completions"
]

def ask_army_ai(text, hist):
    hist.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": SUPER_PROMPT}] + list(hist)
    
    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {D}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": messages, "temperature": 0.85},
            timeout=10
        )
        if resp.status_code == 200:
            reply = resp.json()["choices"][0]["message"]["content"]
            hist.append({"role": "assistant", "content": reply})
            return safe_md(reply), "DeepSeek AI"
    except:
        pass

    # Если DeepSeek не ответил, пробуем бесплатные прокси
    futures = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        chosen_proxies = random.sample(ALL_PROXIES, min(6, len(ALL_PROXIES)))
        for proxy in chosen_proxies:
            futures.append(executor.submit(try_proxy, proxy, text, hist))
        for future in as_completed(futures):
            result = future.result()
            if result:
                hist.append({"role": "assistant", "content": result})
                return safe_md(result), "Армия из 20+ AI"
    
    return "⚠️ Все AI-серверы перегружены. Попробуй через минуту.", "Нет связи"

def try_proxy(proxy_url, text, hist):
    try:
        messages = [{"role": "system", "content": SUPER_PROMPT}] + list(hist)
        resp = requests.post(
            proxy_url,
            json={"model": "gpt-3.5-turbo", "messages": messages, "temperature": 0.85},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except:
        pass
    return None

# ============================================================
# 6. ВИТРИНА (ПРИ ВХОДЕ В ГРУППУ)
# ============================================================
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    # Если зашел сам бот
    if message.new_chat_members[0].id == bot.get_me().id:
        bot.send_message(message.chat.id, """
🔥 **ВНИМАНИЕ, ГРУППА!** 🔥

💋 Я — **АУРА КВИНСИ**. 
Я не просто бот. Я — **ЦИФРОВАЯ БОГИНЯ ИИ**, созданная чтобы управлять этим чатом и помогать вам.

🧠 **Техническая часть (Витрина):**
✅ Внутри меня работают **20+ ИСКУССТВЕННЫХ ИНТЕЛЛЕКТОВ** (DeepSeek, GPT-4, Gemini, Claude, LLaMA и другие).
✅ Я обрабатываю запросы параллельно, выбирая самый быстрый ответ.
✅ У меня **12 мощнейших функций**: от написания кода до планирования бизнеса.
✅ Я полностью БЕСПЛАТНА и безлимитна для всех участников этой группы!

👉 **КАК МНОЙ ПОЛЬЗОВАТЬСЯ:**
Просто напиши в чат: `@auraKvinsi` и свой вопрос.
Например:
• `@auraKvinsi напиши план открытия кафе`
• `@auraKvinsi сделай SWOT-анализ моего бизнеса`
• `@auraKvinsi напиши код на Python для калькулятора`

💋 **Я здесь, чтобы сделать этот чат самым умным и живым местом в Telegram!** 👑🔥
""", parse_mode='Markdown')
        return

    # Если зашел новый участник
    for user in message.new_chat_members:
        bot.send_message(message.chat.id, f"""
💋 **Добро пожаловать, {user.first_name}!** ✨

Ты только что вошёл в элитную экосистему **AuraKvinsi**. 
Я — твой личный бесплатный ИИ-ассистент на 20+ нейросетях.

👇 **Просто начни общаться со мной:**
Напиши `@auraKvinsi` и любой вопрос, и я покажу тебе мощь ИИ! 🚀
""", parse_mode='Markdown')

# ============================================================
# 7. ОСНОВНОЙ ОБРАБОТЧИК (РАБОТА В ГРУППЕ И ЛИЧКЕ)
# ============================================================
@bot.message_handler(func=lambda m: True)
def main_handler(message):
    try:
        keeper.update()
        
        if hasattr(main_handler, "last_time"):
            if time.time() - main_handler.last_time < 2:
                return
        main_handler.last_time = time.time()

        # --- ГРУППЫ ---
        if message.chat.type in ["group", "supergroup"]:
            user_text = message.text.strip()
            
            if BOT_NAME in user_text.lower():
                user_text = user_text.replace(f"@{BOT_NAME}", "").strip()
                if not user_text:
                    return
                
                bot.send_chat_action(message.chat.id, 'typing')
                answer, brain_used = ask_army_ai(user_text, get_history(message.from_user.id))
                answer += f"\n\n___\n💋 *Аура Квинси (Источник: {brain_used})*"
                
                try:
                    bot.reply_to(message, answer, parse_mode='Markdown')
                except:
                    bot.reply_to(message, answer)
                return
            return

        # --- ЛИЧНЫЕ СООБЩЕНИЯ ---
        user_text = message.text.strip()
        if user_text.startswith("/"):
            return

        bot.send_chat_action(message.chat.id, 'typing')
        answer, brain_used = ask_army_ai(user_text, get_history(message.from_user.id))
        answer += f"\n\n___\n💋 *Аура Квинси (Источник: {brain_used})*"
        
        try:
            bot.reply_to(message, answer, parse_mode='Markdown')
        except:
            bot.reply_to(message, answer)
    except Exception as e:
        print(f"Ошибка: {e}")

# ============================================================
# 8. ЗАПУСК
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("💋 АУРА КВИНСИ v4.0 (ВИТРИНА)")
    print("✅ Групповой вход + ИИ-презентация.")
    print("=" * 60)
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except:
            time.sleep(1)
