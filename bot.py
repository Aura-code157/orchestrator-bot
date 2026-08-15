#!/usr/bin/env python3
import os, sys, asyncio, logging, json, time, random, re, sqlite3, subprocess
from datetime import datetime, timedelta
from io import BytesIO
from typing import List, Dict, Optional
import requests, qrcode, aiohttp
from PIL import Image
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, InputMediaPhoto, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ----- КОНФИГ -----
def get_config():
    required = ["TELEGRAM_BOT_TOKEN", "OPENROUTER_API_KEY", "DEEPSEEK_API_KEY", "ELEVENLABS_API_KEY",
                "OPENWEATHERMAP_API_KEY", "PEXELS_API_KEY", "DEEPL_API_KEY", "GNEWS_API_KEY",
                "NEWSAPI_API_KEY", "GITHUB_TOKEN"]
    cfg = {}
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        logger.critical(f"Missing: {', '.join(missing)}")
        sys.exit(1)
    for k in required:
        cfg[k] = os.getenv(k)
    cfg["GITHUB_REPO"] = os.getenv("GITHUB_REPO", "AuraKvinsi/AuraBot")
    cfg["CHANNEL_ID"] = os.getenv("CHANNEL_ID", "@AuraKvinsi")
    cfg["DB_FILE"] = os.getenv("DB_FILE", "aura_bot.db")
    return cfg
CONFIG = get_config()

# ----- БАЗА ДАННЫХ (простая) -----
def init_db():
    conn = sqlite3.connect(CONFIG["DB_FILE"])
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        last_name TEXT, joined_at TIMESTAMP, last_interaction TIMESTAMP, quiet_until TIMESTAMP, style TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT,
        content TEXT, published_at TIMESTAMP, rubric TEXT)''')
    conn.commit()
    conn.close()
init_db()

# ----- API HANDLER (AI-кластер) -----
class API:
    def __init__(self):
        self.s = requests.Session()
        self.s.mount('http://', requests.adapters.HTTPAdapter(max_retries=3))
        self.s.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
        self.or_models = ["openai/gpt-4-turbo", "anthropic/claude-3-sonnet", "google/gemini-pro",
                          "meta-llama/llama-3-70b-instruct", "mistralai/mistral-7b-instruct", "deepseek/deepseek-chat"]
        self.hf_models = ["microsoft/DialoGPT-medium", "google/flan-t5-large", "EleutherAI/gpt-neo-1.3B"]
        self.cache = {}

    async def smart_chat(self, prompt, context="", style="business"):
        system = f"Ты — Аура Квинси, бизнес-аналитик. Отвечай глубоко, структурированно, с цифрами. Стиль: {style}."
        user_msg = f"Контекст: {context}\n\n{prompt}"
        # OpenRouter (6 моделей параллельно)
        tasks = [self._or_req(m, system, user_msg) for m in self.or_models]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid = [r for r in results if isinstance(r, str) and len(r) > 30]
        if valid:
            return max(valid, key=lambda x: (len(x), x.count('.'), sum(c.isdigit() for c in x)))
        # DeepSeek напрямую
        try:
            r = await self._ds_req(system, user_msg)
            if r and len(r) > 30: return r
        except: pass
        # HuggingFace
        for m in self.hf_models:
            try:
                r = await self._hf_req(m, prompt)
                if r and len(r) > 30: return r
            except: pass
        return "Извините, все AI каналы перегружены. Попробуйте позже."

    async def _or_req(self, model, system, user_msg):
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {CONFIG['OPENROUTER_API_KEY']}", "Content-Type": "application/json"}
        data = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
                "temperature": 0.85, "max_tokens": 2000}
        r = self.s.post(url, headers=headers, json=data, timeout=25)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()

    async def _ds_req(self, system, user_msg):
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {CONFIG['DEEPSEEK_API_KEY']}", "Content-Type": "application/json"}
        data = {"model": "deepseek-chat", "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
                "temperature": 0.85, "max_tokens": 2000}
        r = self.s.post(url, headers=headers, json=data, timeout=20)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()

    async def _hf_req(self, model, prompt):
        url = f"https://api-inference.huggingface.co/models/{model}"
        r = self.s.post(url, json={"inputs": prompt, "parameters": {"max_length": 600}}, timeout=15)
        if r.status_code == 200:
            res = r.json()
            if isinstance(res, list) and res:
                return res[0].get("generated_text", "").strip()
        return ""

    # ----- Другие API -----
    async def get_weather(self, city):
        try:
            r = self.s.get("https://api.openweathermap.org/data/2.5/weather",
                           params={"q": city, "appid": CONFIG["OPENWEATHERMAP_API_KEY"], "units": "metric", "lang": "ru"}, timeout=10)
            r.raise_for_status()
            d = r.json()
            return f"🌤 {city}: {d['weather'][0]['description']}, {d['main']['temp']:.1f}°C, ветер {d['wind']['speed']} м/с."
        except:
            return f"Не удалось получить погоду для {city}."

    async def get_crypto(self, coin="bitcoin"):
        try:
            r = self.s.get(f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd,eur,gbp", timeout=10)
            r.raise_for_status()
            p = r.json().get(coin, {})
            return f"💰 {coin.capitalize()}:\nUSD: ${p.get('usd','N/A')}\nEUR: €{p.get('eur','N/A')}\nGBP: £{p.get('gbp','N/A')}"
        except:
            return "Ошибка курса."

    async def tts(self, text):
        try:
            r = self.s.post("https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM",
                            headers={"xi-api-key": CONFIG["ELEVENLABS_API_KEY"]},
                            json={"text": text, "model_id": "eleven_monolingual_v1", "voice_settings": {"stability":0.5,"similarity_boost":0.75}}, timeout=30)
            r.raise_for_status()
            return r.content
        except:
            return None

    async def pexels(self, query):
        try:
            r = self.s.get("https://api.pexels.com/v1/search", headers={"Authorization": CONFIG["PEXELS_API_KEY"]},
                           params={"query": query, "per_page": 5}, timeout=15)
            r.raise_for_status()
            return [p["src"]["original"] for p in r.json().get("photos", [])]
        except:
            return []

    async def translate(self, text, target="RU"):
        try:
            r = self.s.post("https://api-free.deepl.com/v2/translate",
                            data={"auth_key": CONFIG["DEEPL_API_KEY"], "text": text, "target_lang": target}, timeout=10)
            r.raise_for_status()
            return r.json()["translations"][0]["text"]
        except:
            return "Ошибка перевода."

    async def news(self, query=""):
        news = []
        try:
            r = self.s.get("https://gnews.io/api/v4/search", params={"q": query or "business", "token": CONFIG["GNEWS_API_KEY"], "lang": "ru", "max": 5}, timeout=10)
            if r.status_code == 200:
                for a in r.json().get("articles", []):
                    news.append({"title": a["title"], "description": a["description"], "url": a["url"]})
        except: pass
        try:
            r = self.s.get("https://newsapi.org/v2/top-headlines", params={"q": query or "business", "apiKey": CONFIG["NEWSAPI_API_KEY"], "language": "ru", "pageSize": 5}, timeout=10)
            if r.status_code == 200:
                for a in r.json().get("articles", []):
                    news.append({"title": a["title"], "description": a["description"], "url": a["url"]})
        except: pass
        seen = set()
        unique = []
        for item in news:
            if item["title"] not in seen:
                seen.add(item["title"])
                unique.append(item)
        return unique[:10]

    async def qr(self, data):
        try:
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            return buf.getvalue()
        except:
            return None

    async def joke(self):
        try:
            r = self.s.get("https://v2.jokeapi.dev/joke/Any?lang=ru", timeout=10)
            r.raise_for_status()
            d = r.json()
            return d["joke"] if d["type"] == "single" else f"{d['setup']}\n{d['delivery']}"
        except:
            return "Почему программисты путают Хэллоуин и Рождество? Потому что 31 Oct = 25 Dec."

# ----- ОСНОВНОЙ БОТ -----
class AuraBot:
    def __init__(self):
        self.api = API()
        self.app = None
        self.running = True
        self.quiet_until = {}
        self.last_msg = {}
        self.keyboard = ReplyKeyboardMarkup([
            ["🌤 Погода", "💰 Криптовалюта", "📰 Новости"],
            ["🖼 Картинка", "🎤 Озвучить", "🔤 Перевод"],
            ["📊 Бизнес", "🏭 Промышленность", "📈 Стратегия"],
            ["💵 Финансы", "💻 Код", "📝 План"],
            ["🎭 Шутка", "📱 QR-код", "🔕 Тишина"],
            ["❓ Помощь"]
        ], resize_keyboard=True)

    async def start(self, update, context):
        await update.message.reply_text("🏢 Привет! Я Аура Квинси — бизнес-консультант. Задавай вопросы.", reply_markup=self.keyboard)

    async def help(self, update, context):
        await update.message.reply_text("Команды: /start, /help, /weather, /crypto, /tts, /translate, /pic, /news, /qr, /joke, /quiet, /plan, /code, /business, /industry, /strategy, /finance")

    async def handle_text(self, update, context):
        user_id = update.effective_user.id
        text = update.message.text
        now = datetime.now()
        self.last_msg[user_id] = now

        if "НИНА" in text.upper():
            await update.message.reply_text("💖 Нина — душа проекта. Спасибо, что помните!")
            return

        lower = text.lower()
        if "погода" in lower:
            city = re.search(r'в\s+([А-Яа-я\- ]+)', text)
            city = city.group(1).strip() if city else "Москва"
            await update.message.reply_text(await self.api.get_weather(city))
            return
        if "биткоин" in lower or "крипт" in lower:
            coin = "bitcoin" if "биткоин" in lower else "ethereum" if "эфир" in lower else "toncoin"
            await update.message.reply_text(await self.api.get_crypto(coin))
            return
        if "новости" in lower:
            news = await self.api.news()
            if news:
                response = "📰 Новости:\n" + "\n".join([f"• [{n['title']}]({n['url']})" for n in news[:5]])
                await update.message.reply_text(response, parse_mode="Markdown", disable_web_page_preview=True)
            else:
                await update.message.reply_text("Новости не найдены.")
            return
        if "шутк" in lower or "анекдот" in lower:
            await update.message.reply_text(f"🎭 {await self.api.joke()}")
            return
        if "qr" in lower:
            await update.message.reply_text("Используйте /qr текст")
            return

        await update.message.reply_text("🧠 Анализирую...")
        response = await self.api.smart_chat(text, style="business")
        await self._send_long(update, response)

    # Команды (короткие)
    async def weather_cmd(self, update, context):
        city = " ".join(context.args) if context.args else "Москва"
        await update.message.reply_text(await self.api.get_weather(city))

    async def crypto_cmd(self, update, context):
        coin = context.args[0] if context.args else "bitcoin"
        await update.message.reply_text(await self.api.get_crypto(coin))

    async def tts_cmd(self, update, context):
        if not context.args:
            await update.message.reply_text("Напишите текст: /tts Привет")
            return
        text = " ".join(context.args)
        await update.message.reply_text("🎧 Озвучиваю...")
        audio = await self.api.tts(text)
        if audio:
            await update.message.reply_audio(audio=BytesIO(audio), filename="voice.mp3")
        else:
            await update.message.reply_text("Ошибка озвучивания.")

    async def translate_cmd(self, update, context):
        args = context.args
        if not args:
            await update.message.reply_text("Пример: /translate Hello world RU")
            return
        lang = "RU"
        if len(args) > 1 and args[-1].upper() in ["RU","EN","DE","FR","ES","IT","PT","NL","PL","SV","DA","FI","EL","CS","RO","HU","SK","BG"]:
            lang = args[-1].upper()
            text = " ".join(args[:-1])
        else:
            text = " ".join(args)
        translated = await self.api.translate(text, lang)
        await update.message.reply_text(f"🔤 Перевод ({lang}):\n{translated}")

    async def pic_cmd(self, update, context):
        if not context.args:
            await update.message.reply_text("Запрос: /pic космос")
            return
        query = " ".join(context.args)
        urls = await self.api.pexels(query)
        if urls:
            media = [InputMediaPhoto(url) for url in urls[:5]]
            await update.message.reply_media_group(media)
        else:
            await update.message.reply_text("Ничего не найдено.")

    async def news_cmd(self, update, context):
        query = " ".join(context.args) if context.args else "business"
        news = await self.api.news(query)
        if news:
            response = "📰 Новости:\n" + "\n".join([f"• [{n['title']}]({n['url']})" for n in news[:5]])
            await update.message.reply_text(response, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            await update.message.reply_text("Новости не найдены.")

    async def qr_cmd(self, update, context):
        if not context.args:
            await update.message.reply_text("Введите данные: /qr https://example.com")
            return
        data = " ".join(context.args)
        qr_bytes = await self.api.qr(data)
        if qr_bytes:
            await update.message.reply_photo(photo=BytesIO(qr_bytes), caption="Ваш QR-код")
        else:
            await update.message.reply_text("Ошибка QR.")

    async def joke_cmd(self, update, context):
        await update.message.reply_text(f"🎭 {await self.api.joke()}")

    async def quiet_cmd(self, update, context):
        user_id = update.effective_user.id
        self.quiet_until[user_id] = datetime.now() + timedelta(hours=2)
        await update.message.reply_text("🔕 Тишина на 2 часа.")

    async def plan_cmd(self, update, context):
        await update.message.reply_text("📝 Генерирую бизнес-план...")
        response = await self.api.smart_chat("Составь бизнес-план для IT-стартапа.")
        await update.message.reply_text(response)

    async def code_cmd(self, update, context):
        await update.message.reply_text("💻 Генерирую код...")
        response = await self.api.smart_chat("Напиши код Python для веб-скрапинга с BeautifulSoup.")
        await update.message.reply_text(response)

    async def business_cmd(self, update, context):
        await update.message.reply_text("📊 Провожу бизнес-анализ...")
        response = await self.api.smart_chat("Проведи всесторонний бизнес-анализ рынка.")
        await update.message.reply_text(response)

    async def industry_cmd(self, update, context):
        await update.message.reply_text("🏭 Анализирую отрасль...")
        response = await self.api.smart_chat("Сделай обзор промышленной отрасли.")
        await update.message.reply_text(response)

    async def strategy_cmd(self, update, context):
        await update.message.reply_text("📈 Разрабатываю стратегию...")
        response = await self.api.smart_chat("Разработай стратегию развития компании.")
        await update.message.reply_text(response)

    async def finance_cmd(self, update, context):
        await update.message.reply_text("💵 Провожу финансовый анализ...")
        response = await self.api.smart_chat("Проведи финансовый анализ компании.")
        await update.message.reply_text(response)

    async def _send_long(self, update, text):
        if len(text) > 4000:
            for i in range(0, len(text), 4000):
                await update.message.reply_text(text[i:i+4000])
        else:
            await update.message.reply_text(text)

    # ----- Фоновые задачи -----
    async def publish_posts(self, context):
        now = datetime.now()
        rubrics = ["Экономика дня", "Мысль на сегодня", "Техно-обзор", "Мнение Ауры"]
        day = now.timetuple().tm_yday
        hour = now.hour
        if hour == 9:
            idx = day % 4
        elif hour == 21:
            idx = (day + 2) % 4
        else:
            return
        rubric = rubrics[idx]
        prompts = {
            "Экономика дня": "Сделай обзор главных мировых экономических событий за сутки.",
            "Мысль на сегодня": "Напиши вдохновляющую мысль о лидерстве.",
            "Техно-обзор": "Опиши ключевые технологические прорывы.",
            "Мнение Ауры": "Выскажи экспертное мнение о будущем бизнеса."
        }
        content = await self.api.smart_chat(prompts.get(rubric, "Расскажи что-то полезное для бизнеса."))
        if not content:
            content = "Пост временно недоступен."
        try:
            await context.bot.send_message(chat_id=CONFIG["CHANNEL_ID"], text=f"📌 *{rubric}*\n\n{content}", parse_mode="Markdown")
            logger.info(f"Post published: {rubric}")
        except Exception as e:
            logger.error(f"Publish error: {e}")

    async def check_interest(self, context):
        now = datetime.now()
        for user_id, last in list(self.last_msg.items()):
            if user_id in self.quiet_until and self.quiet_until[user_id] > now:
                continue
            if (now - last).total_seconds() > 5400:
                try:
                    await context.bot.send_message(chat_id=user_id, text="😊 Привет! Давно не общались. Как дела?")
                    self.last_msg[user_id] = now
                except:
                    pass

    async def health_check(self):
        while self.running:
            await asyncio.sleep(30)
            try:
                await self.app.bot.get_me()
            except Exception as e:
                logger.critical(f"Health check failed: {e}. Restarting...")
                await self.restart()
                break

    async def restart(self):
        self.running = False
        if self.app and self.app.running:
            await self.app.stop()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    async def check_updates(self):
        while self.running:
            await asyncio.sleep(3600)
            try:
                repo = CONFIG["GITHUB_REPO"]
                url = f"https://api.github.com/repos/{repo}/commits/main"
                headers = {"Authorization": f"token {CONFIG['GITHUB_TOKEN']}"}
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            latest_sha = data["sha"]
                            version_file = "version.txt"
                            local_sha = open(version_file).read().strip() if os.path.exists(version_file) else ""
                            if latest_sha != local_sha:
                                logger.info("New version, updating...")
                                subprocess.run(["git", "pull"], check=True)
                                with open(version_file, "w") as f:
                                    f.write(latest_sha)
                                await self.restart()
                                break
            except Exception as e:
                logger.error(f"Update error: {e}")

    async def run(self):
        self.app = Application.builder().token(CONFIG["TELEGRAM_BOT_TOKEN"]).build()
        for cmd, handler in [("start", self.start), ("help", self.help), ("weather", self.weather_cmd),
                             ("crypto", self.crypto_cmd), ("tts", self.tts_cmd), ("translate", self.translate_cmd),
                             ("pic", self.pic_cmd), ("news", self.news_cmd), ("qr", self.qr_cmd),
                             ("joke", self.joke_cmd), ("quiet", self.quiet_cmd), ("plan", self.plan_cmd),
                             ("code", self.code_cmd), ("business", self.business_cmd),
                             ("industry", self.industry_cmd), ("strategy", self.strategy_cmd),
                             ("finance", self.finance_cmd)]:
            self.app.add_handler(CommandHandler(cmd, handler))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        self.app.add_error_handler(lambda u,c: logger.error(f"Error: {c.error}"))

        jq = self.app.job_queue
        if jq:
            jq.run_daily(self.publish_posts, time=datetime.strptime("09:00","%H:%M").time(), days=tuple(range(7)))
            jq.run_daily(self.publish_posts, time=datetime.strptime("21:00","%H:%M").time(), days=tuple(range(7)))
            jq.run_repeating(self.check_interest, interval=300, first=10)

        asyncio.create_task(self.health_check())
        asyncio.create_task(self.check_updates())

        logger.info("🚀 Бот запущен!")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        while self.running:
            await asyncio.sleep(1)

if __name__ == "__main__":
    bot = AuraBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Остановлен.")
    except Exception as e:
        logger.critical(f"Critical error: {e}")
        time.sleep(5)
        os.execv(sys.executable, [sys.executable] + sys.argv)
