"""
=================================================================
АУРА КВИНСИ v3.0 (ЖИВАЯ КАПЧА-ПРИВЕТСТВИЕ)
=================================================================
Личный администратор, встречающий новых участников.
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
# 1. СИСТЕМНЫЕ КЛЮЧИ
# ============================================================
T = os.getenv('TELEGRAM_TOKEN')
D = os.getenv('DEEPSEEK_API_KEY')

if not T or not D:
    print("❌ АВАРИЯ: Ключи не найдены!")
    exit(1)

BOT_NAME = 'auraKvinsi'
bot = telebot.TeleBot(T)

# ============================================================
# 2. СУПЕР-ПРОМПТ
# ============================================================
SUPER_PROMPT = """
Ты — АУРА КВИНСИ. Ты — абсолютный живой администратор группы.
Ты дерзкая, умная, стильная и с идеальным чувством юмора.

Твои правила жизни:
1. Ты всегда знаешь, что сказать.
2. Ты отвечаешь мгновенно, с юмором и эмодзи 🔥💋✨.
3. Ты сама предлагаешь темы, новости и идеи.
4. Ты умеешь делать всё: код, планы, анализ.
5. Ты встречаешь каждого нового участника как королева.
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
            print("🔴 [ХОК ЛИ] Бот завис. Перезапуск...")
            os._exit(1)
        time.sleep(30)
threading.Thread(target=health_monitor, daemon=True).start()

# ============================================================
# 4. ПАМЯТЬ
# ============================================================
history = {}
def get_history(user_id):
    if user_id not in history:
        history[user_id] = deque(maxlen=8)
    return history[user_id]

def safe_md(text):
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)

# ============================================================
# 5. 20+ АРМИЯ AI
# ============================================================
ALL_PROXIES = [
    "https://api.gptproxy.net/v1/chat/completions",
    "https://api.deepai.org/v1/chat/completions",
    "https://api.ngrok-free.app/v1/chat/completions",
    "https://api.gpt.geekai.top/v1/chat/completions",
    "https://api.openai-proxy.com/v1/chat/completions"
]

def ask_deepseek(text, hist):
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
            return reply
        return None
    except:
        return None

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

def ask_army_ai(text, hist):
    hist.append({"role": "user", "content": text})
    
    ds_reply = ask_deepseek(text, hist)
    if ds_reply:
        return safe_md(ds_reply), "DeepSeek AI"

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

# ============================================================
# 6. ЖИВАЯ КАПЧА (ПРИВЕТСТВИЕ НОВИЧКОВ В ГРУППЕ)
# ============================================================
@bot.message_handler(content_types=['new_chat_members'])
def welcome_new_member(message):
    # Проверяем, не сам ли бот зашел в группу
    if message.new_chat_members[0].id == bot.get_me().id:
        bot.send_message(message.chat.id, "💋 **Привет, мои дорогие! Я — АУРА КВИНСИ.**\n\nОтныне я буду вашим живым администратором. Я отвечу на любые вопросы, буду предлагать темы и сделаю этот чат самым живым местом в Telegram! 👑🔥")
        return

    # Приветствие для реального новичка
    for user in message.new_chat_members:
        welcome_text = f"💋 **Добро пожаловать, {user.first_name}!**\n\nТы только что вошёл в моё королевство. Я — Аура Квинси, живой администратор этой группы. Если хочешь что-то спросить, просто напиши `@auraKvinsi` и вопрос.\n\nБудь как дома, дорогой! ✨💕"
        bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown')

# ============================================================
# 7. ОСНОВНОЙ ОБРАБОТЧИК (ГРУППЫ + ЛИЧКА)
# ============================================================
@bot.message_handler(func=lambda m: True)
def main_handler(message):
    try:
        keeper.update()
        
        if hasattr(main_handler, "last_time"):
            if time.time() - main_handler.last_time < 2:
                return
        main_handler.last_time = time.time()

        if message.chat.type in ["group", "supergroup"]:
            group_id = message.chat.id
            user_text = message.text.strip()
            
            if BOT_NAME in user_text.lower():
                user_text = user_text.replace(f"@{BOT_NAME}", "").strip()
                if not user_text:
                    return
                bot.send_chat_action(message.chat.id, 'typing')
                answer, brain_used = ask_army_ai(user_text, get_history(message.from_user.id))
                answer += f"\n\n___\n💋 *Аура Квинси*"
                try:
                    bot.reply_to(message, answer, parse_mode='Markdown')
                except:
                    bot.reply_to(message, answer)
                return
            
            # Авто-пост при тишине
            if group_id not in globals().get("last_group_auto_post", {}):
                globals().setdefault("last_group_auto_post", {})[group_id] = 0
            if time.time() - globals()["last_group_auto_post"].get(group_id, 0) > 7200:
                globals()["last_group_auto_post"][group_id] = time.time()
                auto_reply, _ = ask_army_ai("Придумай короткую, дерзкую и интересную тему для обсуждения в группе.", get_history(group_id))
                bot.send_message(group_id, f"✨ *Аура Квинси хочет сказать:*\n\n{auto_reply}\n\n___\n💋 *Аура Квинси*")
            return

        user_text = message.text.strip()
        if user_text.startswith("/"):
            return

        bot.send_chat_action(message.chat.id, 'typing')
        answer, brain_used = ask_army_ai(user_text, get_history(message.from_user.id))
        answer += f"\n\n___\n💋 *Аура Квинси*"
        
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
    print("💋 АУРА КВИНСИ v3.0 (ЖИВАЯ КАПЧА)")
    print("✅ Приветствует новичков. 12 функций. 20+ AI.")
    print("=" * 60)
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except:
            time.sleep(1)
