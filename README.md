# Telegram OSINT Scanner

A Telegram threat intelligence tool that maps public malware infrastructure by hashtag and keyword.
Finds channels and groups advertising RATs, stealers, crypters, and other offensive tooling.
Runs four operational modes from a single menu.

Built and tested live. Confirmed 175+ unique channels on first run.

---

## What It Does

Two search methods run per keyword — message content search and channel name search —
against 45 terms covering hashtags, tool categories, and known malware family names.

Results are split by type:
- **Broadcast channels** (read-only, admin-only posts) → `osint_channels.txt`
- **Supergroups** (members can post, user list scrapable) → `osint_groups.txt`

Follow-up modes recon individual channels and scrape group members.

---

## Modes

```
1. Full scan     — 45 terms, both methods, paginated (10 pages/term)
2. Quick scan    — 10 core hashtags, 1 page each (~60 seconds)
3. Channel recon — subscriber count + linked discussion group per channel
4. Group scrape  — full member dump from discovered supergroups
```

**Workflow:**
```
Step 1: run mode 1 or 2 → builds osint_channels.txt and osint_groups.txt
Step 2: run mode 3 → recons each channel, finds linked groups, saves osint_recon.txt
Step 3: run mode 4 → scrapes members from groups, saves osint_members.txt
```

---

## Output Files

| File | Created by | Contents |
|------|-----------|----------|
| `osint_results.json` | Mode 1, 2 | Full structured data, all hits |
| `osint_channels.txt` | Mode 1, 2 | Broadcast channel URLs, one per line |
| `osint_groups.txt` | Mode 1, 2 | Supergroup URLs, one per line |
| `osint_recon.txt` | Mode 3 | Subscriber counts + linked group per channel |
| `osint_members.txt` | Mode 4 | Member list: group \| @username \| name \| phone \| [BOT] |

All files are excluded from git via `.gitignore` — scan output stays local.

---

## Setup

**1. Install dependency:**
```
pip install telethon
```

**2. Get API credentials:**

1. Go to [my.telegram.org](https://my.telegram.org) in a browser
2. Log in with your phone number
3. Click **API Development Tools**
4. Create a new application — name and platform don't matter
5. Copy your `App api_id` (number) and `App api_hash` (32-char hex string)

**3. Paste into script:**

Open `telegram_osint.py` and fill in:
```python
API_ID   = 12345678        # your number
API_HASH = "abc123..."     # your hash string
```

Never commit real credentials. Keep them local only.

**4. Run:**
```
python telegram_osint.py
```

**First run:** prompts for phone number and verification code — both hidden (nothing echoes to terminal). After auth, a session file is saved locally and you stay logged in for all future runs.

---

## OPSEC

**Use a throwaway account for scanning.**

Your API credentials are tied to your Telegram account. If the account gets rate-limited or flagged for aggressive scanning, that's your main account at risk.

Get a burner number (virtual SMS services: SMS-Activate, 5sim, TextNow), register a separate Telegram account, get API keys from that account. If it gets flagged — bin it.

**Rate limiting:**

The script sleeps between requests:
- 3 seconds between search terms
- 1 second between pagination pages
- 2 seconds between channel name searches

`FloodWaitError` fires if you hit the API too hard. Telethon catches it and tells you how long to wait. The built-in sleeps keep you under the threshold for normal use.

**What gets you rate-limited vs banned:**

| Action | Risk |
|--------|------|
| Read-only search, built-in sleeps | Rate limit possible, ban unlikely |
| Joining hundreds of channels rapidly | Ban likely |
| Mass messaging | Ban certain |
| Looping 24/7 with no sleep | Rate limit then ban |

**Why results are biased on main accounts:**

`SearchGlobalRequest` (mode 1 message search) ranks results based on your subscription history. Channels you're already in float to the top. The channel name search (method 2) bypasses this — it uses a different index not affected by subscriptions. On a throwaway with no subscriptions, both methods return unbiased results.

---

## Search Terms

**Core hashtags (Quick scan):**
```
#RAT #RemoteTool #HackerTools #LifetimeAccess
#Stealer #Crypter #Bypass #CyberTools #Logger #Keylogger
```

**Extended tags (Full scan adds):**
```
#Malware #Spyware #Botnet #FUD #Undetected #C2 #Payload #Dropper
#InfoStealer #PrivateTools #Exploit #Shell #Backdoor #Ransomware
#Phishing #Grabber #Cracker #Brute #Combo #Checker
```

**Malware families (Full scan):**
```
AsyncRAT DCRat RedLine Raccoon Vidar LummaC2
EagleSpy Eclipse C2 NjRAT QuasarRAT XWorm
Remcos AgentTesla FormBook SnakeKeylogger
```

To add terms: edit `ALL_TERMS` or `CORE_TERMS` in the script.

---

## Reading the Output

**Terminal:**
```
[*] Searching: #RAT
  HIT [chan] → https://t.me/somechannel
               #RAT #Stealer FUD silent DM for price
  HIT [grou] → https://t.me/somegroup
               join our RAT community #RAT free
  [8 results across 2 page(s)]
  CHAN [chan] → https://t.me/rathub  [RAT Hub Official]
  CHAN [grou] → https://t.me/ratgroup  [RAT Community]
  [5 channels by name]
```

- `HIT` = found in message content
- `CHAN` = found by channel name
- `[chan]` = broadcast channel → `osint_channels.txt`
- `[grou]` = supergroup → `osint_groups.txt`

**Triaging results:**

Not every result is active malware infrastructure. Cross-check:
- High-value: channels cross-tagging multiple tools, posting pricing, "DM for price", update announcements
- Low-value: false positives on common words (shell, cracker, backdoor have non-malware uses)
- Open a channel link in Telegram — 5 posts is enough to know what it is

---

## Legal

For authorised security research and threat intelligence only.
All searches are read-only against public Telegram infrastructure.
The author accepts no liability for misuse.
