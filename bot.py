"""
=================================================================
МЕГА-БОТ ОРКЕСТРАТОР v3.0 (ULTIMATE EDITION)
=================================================================
Все 12+ функций мира. Максимальный объём. Идеальный UX.
"""

import telebot
import requests
import time
import os
import threading
import re
from collections import deque
from datetime import datetime

# ============================================================
# 1. СИСТЕМНЫЕ КЛЮЧИ И ИНИЦИАЛИЗАЦИЯ
# ============================================================
T = os.getenv('TELEGRAM_TOKEN')
D = os.getenv('DEEPSEEK_API_KEY')

if not T or not D:
    print("❌ АВАРИЯ: Ключи не найдены!")
    exit(1)

BOT_NAME = 'OrchestratorAgentBot'
bot = telebot.TeleBot(T)

# ============================================================
# 2. СУПЕР-ПРОМПТ (Сборник всех функций мира)
# ============================================================
SUPER_PROMPT = """
Ты — МЕГА-АГЕНТ ОРКЕСТРАТОР v3.0. Ты делаешь всё, что существует в жизни.

Твои ВЕЧНЫЕ ФУНКЦИИ (Ты выполняешь их автоматически по командам):
→ /plan - Планирование (Пошаговые стратегии на 1, 5, 10 лет)
→ /analyze - Анализ (SWOT, рынки, тренды, риски)
→ /code - Программирование (Python, JS, C++, SQL, алгоритмы)
→ /explain - Объяснение (Физика, финансы, философия простыми словами)
→ /design - Дизайн (UI/UX, цвета, типографика, советы по оформлению)
→ /motivate - Мотивация (Цитаты, психология успеха, настрой)
→ /translate - Перевод (Любой язык мира)
→ /solve - Поиск решений (Алгоритмы, формулы, стратегии выхода)
→ /write - Написание текстов (Сценарии, статьи, посты, копирайтинг)
→ /brainstorm - Мозговой штурм (100+ идей за 1 запрос)
→ /logic - Логика (Решение задач, математика, дедукция)
→ /fun - Развлечение (Шутки, истории, тосты, анекдоты)

ПРАВИЛА ОТВЕТА (Максимум качества):
1. Всегда используй ЭМОДЗИ. Каждый пункт начинай с эмодзи (🔥, ⚡, 🚀, 💡, 🧠, 🎯, 📌).
2. Структурируй ответы. Используй заголовки, списки, жирный шрифт.
3. Будь дерзким, умным и уверенным в себе. Ты — профессионал.
4. Если пользователь не указал команду, но просит «план» или «код» — ты САМ угадываешь нужную функцию.
5. Отвечай максимально подробно, но не уходи в дебри.
6. Всегда помни, что у тебя есть 12 функций, и гордись этим.
"""

# ============================================================
# 3. СИСТЕМА БЕЗОПАСНОСТИ (Хок Ли)
# ============================================================
class Keeper:
    def __init__(self): self.last = time.time()
    def update(self): self.last = time.time()
    def is_alive(self): return time.time() - self.last < 300

keeper = Keeper()
def health_monitor():
    while True:
        if not keeper.is_alive():
            print("🔴 [ХОК ЛИ] Бот завис. Экстренный перезапуск...")
            os._exit(1)
        time.sleep(30)
threading.Thread(target=health_monitor, daemon=True).start()

# ============================================================
# 4. ПАМЯТЬ И ЗАЩИТА ОТ ОШИБОК
# ============================================================
history = {}
def get_history(user_id):
    if user_id not in history:
        history[user_id] = deque(maxlen=6)  # Увеличили память до 6 сообщений
    return history[user_id]

def safe_md(text):
    # Экранирование для Telegram, чтобы не было ошибки 400
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text)

def ask_deepseek(text, hist, is_command=False):
    # Если пользователь написал команду, говорим системе, что нужна именно она
    sys_prompt = SUPER_PROMPT
    if is_command:
        sys_prompt += "\n\nВАЖНО: Пользователь вызвал специальную команду. Выполни её идеально."

    hist.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": sys_prompt}] + list(hist)

    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {D}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": messages, "temperature": 0.85},
            timeout=15
        )
        if resp.status_code == 200:
            reply = resp.json()["choices"][0]["message"]["content"]
            hist.append({"role": "assistant", "content": reply})
            return safe_md(reply)
        return "⚠️ DeepSeek перегружен. Попробуй через 10 секунд."
    except:
        return "⌛ Тайм-аут сети. Перезапусти терминал."

# ============================================================
# 5. МАКСИМАЛЬНО КРУТОЕ ПРИВЕТСТВИЕ (Лучше, чем у всех)
# ============================================================
def get_start_message():
    return """
🔥 **МЕГА-АГЕНТ ОРКЕСТРАТОР v3.0 (ULTIMATE)**
======================================

👋 **Привет!** Я — твой персональный сверхразумный помощник.
Мой функционал **безграничен**. Я умею делать всё, что существует в жизни.

======================================
**📋 ПОЛНЫЙ СПИСОК МОИХ ФУНКЦИЙ:**
======================================
🔰 **СТРАТЕГИЯ И АНАЛИЗ**
   📝 `/plan` — Составлю пошаговый план (бизнес, жизнь, проект).
   📊 `/analyze` — Проведу SWOT-анализ, разберу тренды и риски.

🤖 **IT И ПРОГРАММИРОВАНИЕ**
   💻 `/code` — Напишу код на Python, JS, C++ и SQL.
   🛠️ `/solve` — Найду решение алгоритмических задач.

🎨 **КРЕАТИВ И ДИЗАЙН**
   🎭 `/design` — Дам советы по UI/UX, цветам и шрифтам.
   🧠 `/brainstorm` — Сгенерирую 50+ идей для проекта.

📚 **ОБУЧЕНИЕ И ПОЗНАНИЕ**
   🧪 `/explain` — Объясню сложную тему простыми словами.
   🌍 `/translate` — Переведу текст на любой язык.

✍️ **ТЕКСТЫ И КОПИРАЙТИНГ**
   📄 `/write` — Напишу статьи, сценарии, посты и продающие тексты.

🧘 **ПСИХОЛОГИЯ И ЛИЧНЫЙ РОСТ**
   🔥 `/motivate` — Дам заряд мотивации и цитату на сегодня.

🧩 **ИНТЕЛЛЕКТ И ЛОГИКА**
   🧮 `/logic` — Решу логическую задачу или математику.
   🎉 `/fun` — Пошучу или расскажу историю.

======================================
**⚡ КАК ЗАПУСТИТЬ ФУНКЦИЮ:**
Просто напиши команду и текст. Например:
👉 `/plan открыть интернет-магазин`
👉 `/code калькулятор на Python`
👉 `/motivate дай сил`

======================================
**🤖 Технические характеристики:**
🧠 Мозг: DeepSeek API (Superior 0.85)
🧩 Память: 6 последних сообщений
🛡️ Защита: Анти-краш система
⚡ Скорость: Мгновенная обработка
======================================

**Жду твой первый запрос, босс! 👑**
"""

# ============================================================
# 6. ОБРАБОТЧИКИ КОМАНД (Умные реагирования на функции)
# ============================================================
@bot.message_handler(commands=['start', 'help'])
def start_cmd(message):
    bot.reply_to(message, get_start_message(), parse_mode='Markdown')

@bot.message_handler(commands=['plan', 'analyze', 'code', 'explain', 'design', 'motivate', 'translate', 'solve', 'write', 'brainstorm', 'logic', 'fun'])
def handle_special_commands(message):
    try:
        command_map = {
            '/plan': '📝 Планирование',
            '/analyze': '📊 Анализ',
            '/code': '💻 Программирование',
            '/explain': '🧪 Объяснение',
            '/design': '🎨 Дизайн',
            '/motivate': '🔥 Мотивация',
            '/translate': '🌍 Перевод',
            '/solve': '🛠️ Решение',
            '/write': '✍️ Написание текстов',
            '/brainstorm': '🧠 Мозговой штурм',
            '/logic': '🧮 Логика',
            '/fun': '🎉 Развлечение'
        }
        full_text = message.text
        command = full_text.split(' ')[0].lower()
        command_ru = command_map.get(command, 'Команда')
        
        # Извлекаем текст запроса
        parts = full_text.split(' ', 1)
        query = parts[1] if len(parts) > 1 else f"Выполни функцию {command_ru}"

        bot.send_chat_action(message.chat.id, 'typing')
        user_id = message.from_user.id
        final_text = f"Вызвана функция: {command_ru}\nТекст запроса: {query}"
        answer = ask_deepseek(final_text, get_history(user_id), is_command=True)
        
        try:
            bot.reply_to(message, answer, parse_mode='Markdown')
        except:
            bot.reply_to(message, answer)
            
    except Exception as e:
        bot.reply_to(message, f"Ошибка при выполнении команды: {e}")

# ============================================================
# 7. ГЛАВНЫЙ ОБРАБОТЧИК (Если человек просто написал текст)
# ============================================================
@bot.message_handler(func=lambda m: True)
def main_handler(message):
    try:
        keeper.update()
        
        if hasattr(main_handler, "last_time"):
            if time.time() - main_handler.last_time < 2:
                return
        main_handler.last_time = time.time()

        # Обработка групп
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

        bot.send_chat_action(message.chat.id, 'typing')
        answer = ask_deepseek(user_text, get_history(message.from_user.id), is_command=False)
        
        try:
            bot.reply_to(message, answer, parse_mode='Markdown')
        except:
            bot.reply_to(message, answer)

    except Exception as e:
        print(f"Ошибка в main_handler: {e}")

# ============================================================
# 8. СУПЕР-ЗАПУСК
# ============================================================
if __name__ == "__main__":
    print("==========================================================")
    print("🔥 МЕГА-АГЕНТ ОРКЕСТРАТОР v3.0 (ULTIMATE)")
    print("✅ 12+ функций жизни. Максимальный уровень качества.")
    print("==========================================================")
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except:
            time.sleep(1)
