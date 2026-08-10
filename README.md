# Telegram OSINT Scanner

Telegram OSINT Scanner — a Telethon-based, read-only tool that scans public Telegram channels and groups for keywords and hashtags, classifies hits as broadcast channels or supergroups, and exports structured results and member lists to local files. Supports full/quick scans, channel recon and group scraping; for authorized threat intelligence use only—run with local API credentials on a throwaway account to avoid rate limits and OPSEC risk.


<img width="1665" height="867" alt="image" src="https://github.com/user-attachments/assets/06a53bae-77a9-4cb6-bbb3-b78a3155940c" />

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

The default wordlist targets malware market infrastructure. Swap `CORE_TERMS` and `ALL_TERMS` in the script to redirect the scanner at different threat surfaces. Save your output files before switching (rename `osint_channels.txt` etc.) — each scan overwrites them.

---

### Wordlist Variations

**Malware market** (`telegram_osint_malware.py` — preserved backup)

Targets: RAT sellers, stealer builders, crypter services, C2 infrastructure, malware-as-a-service operators.
```
Core:     #RAT #RemoteTool #HackerTools #LifetimeAccess #Stealer #Crypter
          #Bypass #CyberTools #Logger #Keylogger
Extended: #Malware #Spyware #Botnet #FUD #Undetected #C2 #Payload #Dropper
          #InfoStealer #PrivateTools #Exploit #Shell #Backdoor #Ransomware
          #Phishing #Grabber #Cracker #Brute #Combo #Checker
Families: AsyncRAT DCRat RedLine Raccoon Vidar LummaC2 EagleSpy NjRAT
          QuasarRAT XWorm Remcos AgentTesla FormBook SnakeKeylogger
```

---

**Scammer / stalker / fraud** (`telegram_osint.py` — current default)

Targets: romance scammers, stalkerware buyers/sellers, carding operations, SIM swappers, doxxers, social engineering kit sellers, identity theft services.
```
Core:     #RomanceScam #PigButchering #Stalkerware #PhoneSpy #Carding
          #Fullz #OTPBypass #SIMSwap #Doxx #ScamPage
Extended: #CryptoScam #InvestmentScam #BankLogs #AccountTakeover
          #FakeID #FakePassport #IdentityTheft #PersonalData
          #Smishing #Vishing #SEKit #SocialEngineering
          #LocationTracker #GPSTracker #SpyApp #HiddenApp
          #DataBreach #Doxing #Lure #CVV #CashOutMethod
Apps:     FlexiSPY mSpy Cerberus AhMyth Pegasus
```

---

**Threat intel / defensive research** (build your own)

Targets: legitimate security researchers, vulnerability feeds, IOC sharing channels, breach notifications, red team tooling. These channels post actionable intel rather than selling access.
```
Core:     #ThreatIntel #IOC #CVE #Vulnerability #MalwareAnalysis
          #DataLeak #Breach #RedTeam #BugBounty #PenTest
Extended: #0day #Exploit #APT #Ransomware #ThreatHunting
          #DFIR #IncidentResponse #Indicators #YARA #Sigma
          #CyberThreat #InfoSec #BlueTeam #SOC #SIEM
Tools:    Cobalt Strike Metasploit Sliver Havoc Brute Ratel
          Nuclei BurpSuite Nmap Mimikatz
Groups:   #CTF #HackTheBox #TryHackMe #WriteUp #Reversing
```

What you find here is different in character — researchers sharing samples, IOC lists, YARA rules, leaked tool drops, breach databases being discussed before they hit the news. High signal-to-noise compared to the malware market channels.

---

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
