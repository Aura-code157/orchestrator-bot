#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AURA KVINSI v22.1 — Безопасная версия для промышленности
Все ключи вынесены в переменные окружения (.env)
"""

import os
import sys
import asyncio
import logging
import json
import time
import random
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta
from io import BytesIO
from typing import Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import qrcode
from PIL import Image
from dotenv import load_dotenv

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, InputMediaPhoto
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# Загружаем переменные из .env
load_dotenv()

# ========== ЛОГИРОВАНИЕ ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.FileHandler("aura_bot.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ========== КОНФИГ (из переменных окружения) ==========
def get_config():
    """Загружает конфигурацию из переменных окружения."""
    required = [
        "TELEGRAM_BOT_TOKEN",
        "OPENROUTER_API_KEY",
        "DEEPSEEK_API_KEY",
        "ELEVENLABS_API_KEY",
        "OPENWEATHERMAP_API_KEY",
        "PEXELS_API_KEY",
        "DEEPL_API_KEY",
        "GNEWS_API_KEY",
        "NEWSAPI_KEY",
        "GITHUB_TOKEN"
    ]
    config = {}
    missing = []
    for key in required:
        value = os.getenv(key)
        if not value:
            missing.append(key)
        config[key] = value

    # Необязательные, но с значениями по умолчанию
    config["GITHUB_REPO"] = os.getenv("GITHUB_REPO", "AuraKvinsi/AuraBot")
    config["CHANNEL_ID"] = os.getenv("CHANNEL_ID", "@AuraKvinsi")
    config["DB_FILE"] = os.getenv("DB_FILE", "aura_bot.db")

    if missing:
        logger.critical(f"Отсутствуют обязательные переменные: {', '.join(missing)}")
        print(f"❌ Ошибка: не заданы переменные: {', '.join(missing)}")
        print("Создайте файл .env и укажите их.")
        sys.exit(1)

    return config

CONFIG = get_config()

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect(CONFIG["DB_FILE"])
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        joined_at TIMESTAMP,
        last_interaction TIMESTAMP,
        quiet_until TIMESTAMP,
        preferences TEXT,
        style TEXT,
        history TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel TEXT,
        content TEXT,
        published_at TIMESTAMP,
        rubric TEXT
    )''')
    conn.commit()
    conn.close()
init_db()

# ========== API HANDLER ==========
class APIHandler:
    def __init__(self):
        self.session = None
        self._init_session()
        self.hf_models = [
            "microsoft/DialoGPT-medium",
            "google/flan-t5-large",
            "EleutherAI/gpt-neo-1.3B"
        ]
        self.or_models = [
            "openai/gpt-4-turbo",
            "anthropic/claude-3-sonnet",
            "google/gemini-pro",
            "meta-llama/llama-3-70b-instruct",
            "mistralai/mistral-7b-instruct",
            "deepseek/deepseek-chat"
        ]

    def _init_session(self):
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500,502,503,504])
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    async def smart_chat(self, prompt: str, context: str = "", style: str = "business") -> str:
        system_prompt = (
            "Ты — Аура Квинси, ведущий бизнес-аналитик и стратег. "
            "Твои ответы должны быть глубокими, структурированными, с цифрами, фактами и рекомендациями. "
            "Ты помогаешь руководителям принимать решения в области управления, финансов, производства, инноваций. "
            "Говори уверенно, профессионально, но доступно. "
            f"Стиль: {style}."
        )
        user_message = f"Контекст предыдущих обсуждений:\n{context}\n\nЗапрос пользователя:\n{prompt}"

        tasks = [self._openrouter_request(model, system_prompt, user_message) for model in self.or_models]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid = [r for r in results if isinstance(r, str) and len(r) > 30]

        if valid:
            best = max(valid, key=lambda x: (
                len(x),
                x.count('.') + x.count('!') + x.count('?'),
                sum(c.isdigit() for c in x)
            ))
            return best

        logger.warning("OpenRouter не ответил, пробуем DeepSeek напрямую.")
        try:
            ds_resp = await self._deepseek_direct(system_prompt, user_message)
            if ds_resp and len(ds_resp) > 30:
                return ds_resp
        except Exception as e:
            logger.error(f"DeepSeek error: {e}")

        logger.warning("DeepSeek не ответил, пробуем HuggingFace.")
        for hf_model in self.hf_models:
            try:
                hf_resp = await self._huggingface_request(hf_model, prompt)
                if hf_resp and len(hf_resp) > 30:
                    return hf_resp
            except Exception as e:
                logger.error(f"HuggingFace {hf_model} error: {e}")
                continue

        return (
            "Уважаемый руководитель! В данный момент я не могу получить доступ к своим аналитическим модулям, "
            "но хочу поделиться ключевой мыслью: в любой бизнес-ситуации важно сохранять стратегический взгляд. "
            "Оцените текущие риски, пересмотрите операционные процессы и не бойтесь внедрять инновации. "
            "Попробуйте задать вопрос более конкретно, и мы проведём детальный анализ."
        )

    async def _openrouter_request(self, model: str, system: str, user_msg: str) -> str:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {CONFIG['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg}
            ],
            "temperature": 0.85,
            "max_tokens": 2000,
            "top_p": 0.95
        }
        try:
            resp = self.session.post(url, headers=headers, json=data, timeout=25)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"OpenRouter {model} error: {e}")
            return ""

    async def _deepseek_direct(self, system: str, user_msg: str) -> str:
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {CONFIG['DEEPSEEK_API_KEY']}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg}
            ],
            "temperature": 0.85,
            "max_tokens": 2000
        }
        try:
            resp = self.session.post(url, headers=headers, json=data, timeout=20)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"DeepSeek direct error: {e}")
            return ""

    async def _huggingface_request(self, model: str, prompt: str) -> str:
        url = f"https://api-inference.huggingface.co/models/{model}"
        headers = {"Content-Type": "application/json"}
        payload = {"inputs": prompt, "parameters": {"max_length": 600, "temperature": 0.8}}
        try:
            resp = self.session.post(url, headers=headers, json=payload, timeout=15)
            if resp.status_code == 200:
                result = resp.json()
                if isinstance(result, list) and len(result) > 0:
                    return result[0].get("generated_text", "").strip()
                elif isinstance(result, dict) and "generated_text" in result:
                    return result["generated_text"].strip()
            return ""
        except Exception as e:
            logger.error(f"HF {model} error: {e}")
            return ""

    # ---------- Остальные методы без изменений (используют CONFIG) ----------
    async def get_weather(self, city: str) -> str:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"q": city, "appid": CONFIG["OPENWEATHERMAP_API_KEY"], "units": "metric", "lang": "ru"}
        try:
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return f"🌤 {city}: {data['weather'][0]['description']}, {data['main']['temp']:.1f}°C, ветер {data['wind']['speed']} м/с."
        except:
            return f"Не удалось получить погоду для {city}."

    async def get_crypto(self, coin: str = "bitcoin") -> str:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd,eur,gbp"
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if coin in data:
                p = data[coin]
                return f"💰 {coin.capitalize()}:\nUSD: ${p.get('usd','N/A')}\nEUR: €{p.get('eur','N/A')}\nGBP: £{p.get('gbp','N/A')}"
            return f"Монета {coin} не найдена."
        except:
            return "Ошибка получения курса."

    async def elevenlabs_tts(self, text: str) -> Optional[bytes]:
        url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
        headers = {"xi-api-key": CONFIG["ELEVENLABS_API_KEY"], "Content-Type": "application/json"}
        data = {"text": text, "model_id": "eleven_monolingual_v1", "voice_settings": {"stability":0.5,"similarity_boost":0.5}}
        try:
            resp = self.session.post(url, headers=headers, json=data, timeout=30)
            resp.raise_for_status()
            return resp.content
        except:
            return None

    async def pexels_search(self, query: str) -> List[str]:
        url = "https://api.pexels.com/v1/search"
        headers = {"Authorization": CONFIG["PEXELS_API_KEY"]}
        params = {"query": query, "per_page": 5}
        try:
            resp = self.session.get(url, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            return [p["src"]["original"] for p in resp.json().get("photos", [])]
        except:
            return []

    async def deepl_translate(self, text: str, target_lang: str = "RU") -> str:
        url = "https://api-free.deepl.com/v2/translate"
        params = {"auth_key": CONFIG["DEEPL_API_KEY"], "text": text, "target_lang": target_lang}
        try:
            resp = self.session.post(url, data=params, timeout=10)
            resp.raise_for_status()
            return resp.json()["translations"][0]["text"]
        except:
            return "Ошибка перевода."

    async def get_news(self, query: str = "") -> List[Dict]:
        news = []
        try:
            g_url = "https://gnews.io/api/v4/search"
            g_params = {"q": query or "business", "token": CONFIG["GNEWS_API_KEY"], "lang": "ru", "max": 5}
            resp = self.session.get(g_url, params=g_params, timeout=10)
            if resp.status_code == 200:
                for a in resp.json().get("articles", []):
                    news.append({"title": a["title"], "description": a["description"], "url": a["url"], "source": "GNews"})
        except: pass
        try:
            n_url = "https://newsapi.org/v2/top-headlines"
            n_params = {"q": query or "business", "apiKey": CONFIG["NEWSAPI_KEY"], "language": "ru", "pageSize": 5}
            resp = self.session.get(n_url, params=n_params, timeout=10)
            if resp.status_code == 200:
                for a in resp.json().get("articles", []):
                    news.append({"title": a["title"], "description": a["description"], "url": a["url"], "source": "NewsAPI"})
        except: pass
        seen = set()
        unique = []
        for item in news:
            if item["title"] not in seen:
                seen.add(item["title"])
                unique.append(item)
        return unique[:10]

    async def generate_qr(self, data: str) -> Optional[bytes]:
        try:
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
            qr.add_data(data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            return buf.getvalue()
        except:
            return None

    async def get_joke(self) -> str:
        url = "https://v2.jokeapi.dev/joke/Any?lang=ru"
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data["type"] == "single":
                return data["joke"]
            return f"{data['setup']}\n{data['delivery']}"
        except:
            return "Почему программисты путают Хэллоуин и Рождество? Потому что 31 Oct = 25 Dec."

# ========== ОСНОВНОЙ БОТ ==========
class AuraBot:
    def __init__(self):
        self.api = APIHandler()
        self.application = None
        self.running = True
        self.quiet_until = {}
        self.last_user_message = {}
        self.user_history = {}

        self.main_keyboard = ReplyKeyboardMarkup([
            ["🌤 Погода", "💰 Криптовалюта"],
            ["📰 Новости", "🖼 Картинка"],
            ["🎤 Озвучить", "🔤 Перевод"],
            ["📊 Бизнес", "🏭 Промышленность"],
            ["📈 Стратегия", "💵 Финансы"],
            ["💻 Код", "📝 План"],
            ["🎭 Шутка", "📱 QR-код"],
            ["🔕 Тишина", "❓ Помощь"]
        ], resize_keyboard=True)

    # ---------- Команды (все, как в v22.0) ----------
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        now = datetime.now()
        conn = sqlite3.connect(CONFIG["DB_FILE"])
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, joined_at, last_interaction) VALUES (?,?,?,?,?,?)",
                  (user.id, user.username, user.first_name, user.last_name, now, now))
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"🏢 Привет, {user.first_name}!\n\n"
            "Я **Аура Квинси** — ваш цифровой бизнес-консультант.\n"
            "Помогаю принимать стратегические решения, анализировать рынки, оптимизировать процессы.\n"
            "Используйте кнопки меню или задавайте любые вопросы — я дам глубокий анализ.\n"
            "Доступны команды: /business, /industry, /strategy, /finance.",
            parse_mode="Markdown", reply_markup=self.main_keyboard
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 **Помощь**\n\n"
            "Основные команды:\n"
            "/business – общий бизнес-анализ\n"
            "/industry – отраслевой обзор\n"
            "/strategy – разработка стратегии\n"
            "/finance – финансовый анализ\n"
            "/plan – бизнес-план\n"
            "/code – генерация кода\n\n"
            "Также работают:\n"
            "/weather, /crypto, /tts, /translate, /pic, /news, /qr, /joke, /quiet",
            parse_mode="Markdown", reply_markup=self.main_keyboard
        )

    async def business_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("📊 Провожу бизнес-анализ...")
        prompt = "Проведи всесторонний бизнес-анализ текущей ситуации: оцени рыночные тренды, конкурентную среду, внутренние риски и возможности для роста. Дай конкретные рекомендации."
        response = await self.api.smart_chat(prompt, style="business")
        await self._send_long(update, response)

    async def industry_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🏭 Анализирую отрасль...")
        prompt = "Сделай глубокий обзор промышленной отрасли: ключевые игроки, технологии, инновации, перспективы развития, влияние макроэкономических факторов."
        response = await self.api.smart_chat(prompt, style="business")
        await self._send_long(update, response)

    async def strategy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("📈 Разрабатываю стратегию...")
        prompt = "Разработай детальную стратегию развития компании на 3-5 лет: цели, этапы, необходимые ресурсы, KPI, методы контроля и адаптации к изменениям рынка."
        response = await self.api.smart_chat(prompt, style="business")
        await self._send_long(update, response)

    async def finance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("💵 Провожу финансовый анализ...")
        prompt = "Проведи финансовый анализ: оцени текущую ликвидность, рентабельность, структуру капитала, денежные потоки. Предложи меры по оптимизации затрат и увеличению прибыли."
        response = await self.api.smart_chat(prompt, style="business")
        await self._send_long(update, response)

    async def plan_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("📝 Генерирую бизнес-план...")
        prompt = "Составь полный бизнес-план для промышленного стартапа: описание продукта, анализ рынка, маркетинговая стратегия, производственный план, финансовые прогнозы, оценка рисков."
        response = await self.api.smart_chat(prompt, style="business")
        await self._send_long(update, response)

    async def code_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("💻 Генерирую код...")
        prompt = "Напиши пример кода на Python для автоматизации бизнес-процесса (например, сбор данных, анализ отчётов). Добавь пояснения для каждого шага."
        response = await self.api.smart_chat(prompt, style="technical")
        await self._send_long(update, response)

    # Стандартные команды
    async def weather_command(self, update, context):
        city = " ".join(context.args) if context.args else "Москва"
        await update.message.reply_text(await self.api.get_weather(city))

    async def crypto_command(self, update, context):
        coin = context.args[0] if context.args else "bitcoin"
        await update.message.reply_text(await self.api.get_crypto(coin))

    async def tts_command(self, update, context):
        if not context.args:
            await update.message.reply_text("Напишите текст: /tts Привет")
            return
        text = " ".join(context.args)
        await update.message.reply_text("🎧 Озвучиваю...")
        audio = await self.api.elevenlabs_tts(text)
        if audio:
            await update.message.reply_audio(audio=BytesIO(audio), filename="aura_voice.mp3")
        else:
            await update.message.reply_text("Ошибка озвучивания.")

    async def translate_command(self, update, context):
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
        translated = await self.api.deepl_translate(text, lang)
        await update.message.reply_text(f"🔤 Перевод ({lang}):\n{translated}")

    async def pic_command(self, update, context):
        if not context.args:
            await update.message.reply_text("Запрос: /pic космос")
            return
        query = " ".join(context.args)
        urls = await self.api.pexels_search(query)
        if urls:
            media = [InputMediaPhoto(url) for url in urls[:5]]
            await update.message.reply_media_group(media)
        else:
            await update.message.reply_text("Ничего не найдено.")

    async def news_command(self, update, context):
        query = " ".join(context.args) if context.args else "business"
        news = await self.api.get_news(query)
        if news:
            response = "📰 **Новости**:\n\n" + "\n".join([f"• [{n['title']}]({n['url']})" for n in news[:5]])
            await update.message.reply_text(response, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            await update.message.reply_text("Новости не найдены.")

    async def qr_command(self, update, context):
        if not context.args:
            await update.message.reply_text("Введите данные: /qr https://example.com")
            return
        data = " ".join(context.args)
        qr_bytes = await self.api.generate_qr(data)
        if qr_bytes:
            await update.message.reply_photo(photo=BytesIO(qr_bytes), caption="Ваш QR-код")
        else:
            await update.message.reply_text("Ошибка генерации QR.")

    async def joke_command(self, update, context):
        await update.message.reply_text(f"🎭 {await self.api.get_joke()}")

    async def quiet_command(self, update, context):
        user_id = update.effective_user.id
        self.quiet_until[user_id] = datetime.now() + timedelta(hours=2)
        await update.message.reply_text("🔕 Режим «Не беспокоить» включён на 2 часа.")

    # ---------- Обработчик текста ----------
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text
        now = datetime.now()
        self.last_user_message[user_id] = now

        if user_id not in self.user_history:
            self.user_history[user_id] = []
        self.user_history[user_id].append(text)
        if len(self.user_history[user_id]) > 5:
            self.user_history[user_id].pop(0)
        history = "\n".join(self.user_history[user_id])

        if "НИНА" in text.upper():
            await update.message.reply_text(
                "💖 Нина — душа и наставница проекта. Без неё Аура Квинси не была бы такой. Спасибо, что помните о ней! 🙏"
            )
            return

        lower = text.lower()
        if "погода" in lower:
            city_match = re.search(r'в\s+([А-Яа-я\- ]+)', text)
            city = city_match.group(1).strip() if city_match else "Москва"
            await update.message.reply_text(await self.api.get_weather(city))
            return
        if "биткоин" in lower or "крипт" in lower:
            coin = "bitcoin"
            if "эфир" in lower: coin = "ethereum"
            elif "тон" in lower: coin = "toncoin"
            await update.message.reply_text(await self.api.get_crypto(coin))
            return
        if "новости" in lower:
            news = await self.api.get_news()
            if news:
                response = "📰 **Новости**:\n" + "\n".join([f"• [{n['title']}]({n['url']})" for n in news[:5]])
                await update.message.reply_text(response, parse_mode="Markdown", disable_web_page_preview=True)
            else:
                await update.message.reply_text("Новости не найдены.")
            return
        if "шутк" in lower or "анекдот" in lower:
            await update.message.reply_text(f"🎭 {await self.api.get_joke()}")
            return

        await update.message.reply_text("🧠 Анализирую ситуацию, подождите...")
        response = await self.api.smart_chat(text, context=history, style="business")
        await self._send_long(update, response)

    async def _send_long(self, update, text):
        if len(text) > 4000:
            for i in range(0, len(text), 4000):
                await update.message.reply_text(text[i:i+4000])
        else:
            await update.message.reply_text(text)

    # ---------- Фоновые задачи ----------
    async def publish_daily_posts(self, context: ContextTypes.DEFAULT_TYPE):
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
            "Экономика дня": "Сделай обзор главных мировых экономических событий за сутки с акцентом на промышленность.",
            "Мысль на сегодня": "Напиши вдохновляющую мысль о лидерстве и инновациях.",
            "Техно-обзор": "Опиши ключевые технологические прорывы, которые повлияют на промышленность.",
            "Мнение Ауры": "Выскажи своё экспертное мнение о будущем бизнеса и промышленности."
        }
        prompt = prompts.get(rubric, "Расскажи что-то полезное для бизнеса.")
        content = await self.api.smart_chat(prompt, style="business")
        if not content:
            content = "Сегодняшний пост временно недоступен. Загляните позже!"
        try:
            await context.bot.send_message(
                chat_id=CONFIG["CHANNEL_ID"],
                text=f"📌 *{rubric}*\n\n{content}",
                parse_mode="Markdown"
            )
            logger.info(f"Post published: {rubric}")
            conn = sqlite3.connect(CONFIG["DB_FILE"])
            c = conn.cursor()
            c.execute("INSERT INTO posts (channel, content, published_at, rubric) VALUES (?,?,?,?)",
                      (CONFIG["CHANNEL_ID"], content, now, rubric))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Publish error: {e}")

    async def check_interest(self, context: ContextTypes.DEFAULT_TYPE):
        now = datetime.now()
        for user_id, last_time in list(self.last_user_message.items()):
            if user_id in self.quiet_until and self.quiet_until[user_id] > now:
                continue
            if (now - last_time).total_seconds() > 5400:
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="😊 Привет! Давно не общались. Как идут дела в бизнесе? Может, нужен совет?"
                    )
                    self.last_user_message[user_id] = now
                except:
                    pass

    async def health_check(self):
        while self.running:
            await asyncio.sleep(30)
            try:
                await self.application.bot.get_me()
                logger.debug("Health OK")
            except Exception as e:
                logger.critical(f"Health check failed: {e}. Restarting...")
                await self.restart_bot()
                break

    async def restart_bot(self):
        logger.info("Restarting bot...")
        self.running = False
        if self.application and self.application.running:
            await self.application.stop()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    async def check_for_updates(self):
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
                                logger.info("New version detected, updating...")
                                subprocess.run(["git", "pull"], check=True)
                                with open(version_file, "w") as f:
                                    f.write(latest_sha)
                                await self.restart_bot()
                                break
            except Exception as e:
                logger.error(f"Update error: {e}")

    async def run(self):
        self.application = Application.builder().token(CONFIG["TELEGRAM_BOT_TOKEN"]).build()
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("weather", self.weather_command))
        self.application.add_handler(CommandHandler("crypto", self.crypto_command))
        self.application.add_handler(CommandHandler("tts", self.tts_command))
        self.application.add_handler(CommandHandler("translate", self.translate_command))
        self.application.add_handler(CommandHandler("pic", self.pic_command))
        self.application.add_handler(CommandHandler("news", self.news_command))
        self.application.add_handler(CommandHandler("qr", self.qr_command))
        self.application.add_handler(CommandHandler("joke", self.joke_command))
        self.application.add_handler(CommandHandler("quiet", self.quiet_command))
        self.application.add_handler(CommandHandler("plan", self.plan_command))
        self.application.add_handler(CommandHandler("code", self.code_command))
        self.application.add_handler(CommandHandler("business", self.business_command))
        self.application.add_handler(CommandHandler("industry", self.industry_command))
        self.application.add_handler(CommandHandler("strategy", self.strategy_command))
        self.application.add_handler(CommandHandler("finance", self.finance_command))

        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        self.application.add_error_handler(lambda u,c: logger.error(f"Error: {c.error}"))

        job_queue = self.application.job_queue
        if job_queue:
            job_queue.run_daily(self.publish_daily_posts, time=datetime.strptime("09:00","%H:%M").time(), days=tuple(range(7)))
            job_queue.run_daily(self.publish_daily_posts, time=datetime.strptime("21:00","%H:%M").time(), days=tuple(range(7)))
            job_queue.run_repeating(self.check_interest, interval=300, first=10)

        asyncio.create_task(self.health_check())
        asyncio.create_task(self.check_for_updates())

        logger.info("🚀 Бот запущен в режиме 'Промышленный интеллект'")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        while self.running:
            await asyncio.sleep(1)

if __name__ == "__main__":
    bot = AuraBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Остановлен пользователем.")
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}")
        time.sleep(5)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    
