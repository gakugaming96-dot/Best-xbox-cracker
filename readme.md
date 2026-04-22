# GG's Xbox Cracker Pro – Ultimate Edition
# Made by Killarua (Discord)
# Features: Dashboard, Discord bot + 
```markdown
# 🎮 GG's Xbox Cracker Pro – Ultimate Dashboard

> **WARNING**  
> This tool is for educational purposes only. You alone are responsible for how you use this software.

---

## 🔐 Safety & Policy

- **No logs** – The dashboard does not store your IP or personal data.
- **Proxy only** – All requests go through rotating proxies. Your real IP is never exposed to target servers.
- **Local storage** – Valid accounts are saved only on your server (`result.txt`). We do not collect them.
- **Rate limiting** – Built‑in delays and concurrency controls prevent abuse of target services.
- **Use at your own risk** – The authors assume no liability for account bans, legal consequences, or anything else.

---

## 👑 Made by Killarua (Discord)

Special thanks to **Killarua** for the architecture, async optimization, and dashboard design.  
Contact on Discord for support or custom builds.

---

## 💰 Support the Project (Crypto)

If you want to support continued development:

**Ethereum (ETH) address:**  
`0x3dEF0419BE1c1248f78ed9e751EF547883a56277`

Any amount is appreciated. Funds go toward hosting, proxy sources, and API access.

---

## 🚀 Features

- **Async cracker** – 100x faster than sync scripts  
- **Live dashboard** – WebSocket real‑time updates, live chart, particle background, theme toggle (dark/light), copy‑to‑clipboard, sound notification on new valid account  
- **Proxy scraper & checker** – Auto‑rotate from multiple sources  
- **Discord bot** – Full command set: `!start`, `!stop`, `!reset`, `!stats`, `!status`, `!total`, `!recent`, `!help`  
- **Discord webhook** – Sends each valid account to your channel  
- **Total stats** – Checked, valid, GamePass hits, success rate, uptime  
- **24/7 free deployment** on Render  

---

## 📦 Installation & Deployment

```bash
git clone https://github.com/yourname/xbox-cracker.git
cd xbox-cracker
pip install -r requirements.txt
```

Set environment variables (optional – for Discord):

· DISCORD_BOT_TOKEN – your Discord bot token
· DISCORD_WEBHOOK_URL – your Discord webhook URL

Then run:

```bash
python app.py
```

Open http://localhost:10000

Deploy on Render – connect your GitHub repo, add the same env vars, and Render will run it 24/7 for free.

---

🤖 Discord Bot Commands

Command Description
!start Start the account cracker
!stop Stop the cracker
!reset Reset all statistics
!stats Detailed statistics embed
!status Short status line
!total Total accounts checked
!recent Last 5 valid accounts
!help Show all commands

---

📜 License

Contact me for © Copyright
© 2025 Killarua (Discord)

---

Cool tools? Please click star ⭐

```

---

## ✅ How to Use

1. Create a folder `xbox-cracker`.
2. Inside, create `app.py`, `requirements.txt`, and a folder `templates` with `dashboard.html` inside it.
3. Paste the respective code into each file.
4. Run `pip install -r requirements.txt`
5. Run `python app.py`
6. Open `http://localhost:10000`
