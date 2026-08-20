#!/usr/bin/env python3
"""
Auto-distribute honeypots to threat actors
Correctly pairs videos with payloads:
  - op_israel → IL database video (27) + zip (28)
  - malware groups → RAT video+exe (29)

Runs via cron every 6 hours
"""
import asyncio
import json
import random
import os
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError, PeerFloodError

# Scanner account (has trust)
API_ID = 35473324
API_HASH = 'd6b1b6d25c05a8326cb3e798fcae1f16'
SESSION = '/root/telegram-osint/scanner_session'

SENT_LOG = '/root/telegram-osint/sent_users.txt'
TARGETS_FILE = '/root/telegram-osint/threat_actors.json'
CHANNEL = "justicedev2027"

# Message IDs for each campaign
HONEYPOTS = {
    # Anti-Israel hacktivists → IL database
    "op_israel": {
        "name": "IL_DATABASE",
        "messages": [27, 28],  # Video first, then zip
        "desc": "Israeli database honeypot"
    },
    # Malware buyers → RAT
    "hrmchat": {
        "name": "RAT_HONEYPOT",
        "messages": [29],  # Video + exe combined
        "desc": "RAT builder honeypot"
    },
    # Default for other malware groups
    "default_malware": {
        "name": "RAT_HONEYPOT",
        "messages": [29],
        "desc": "RAT builder honeypot"
    }
}

def load_sent():
    try:
        with open(SENT_LOG, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()

def log_sent(username):
    with open(SENT_LOG, 'a') as f:
        f.write(f"{username}\n")

def get_honeypot(group):
    """Get correct honeypot for target group"""
    if group in HONEYPOTS:
        return HONEYPOTS[group]
    # Default: malware groups get RAT
    return HONEYPOTS["default_malware"]

async def main():
    log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{log_time}] === AUTO-DISTRIBUTE START ===")

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        print("[!] Session expired - need to re-auth")
        return

    me = await client.get_me()
    print(f"[*] Using: @{me.username}")

    # Load targets
    try:
        with open(TARGETS_FILE, 'r') as f:
            all_targets = json.load(f)
    except FileNotFoundError:
        print("[!] No targets file found")
        return

    sent = load_sent()
    targets = [t for t in all_targets if t['username'] not in sent]

    print(f"[*] {len(targets)} remaining ({len(sent)} already sent)")

    if not targets:
        print("[*] All targets hit!")
        await client.disconnect()
        return

    # Group targets by campaign
    by_group = {}
    for t in targets:
        g = t['group']
        if g not in by_group:
            by_group[g] = []
        by_group[g].append(t)

    print(f"[*] Target breakdown:")
    for g, members in by_group.items():
        hp = get_honeypot(g)
        print(f"    {g}: {len(members)} targets → {hp['name']} (msgs {hp['messages']})")

    success = 0
    total_attempted = 0

    for t in targets:
        if total_attempted >= 25:  # Max per session to avoid flood
            print(f"\n[*] Reached session limit (25) - will continue next run")
            break

        username = t['username']
        group = t['group']
        honeypot = get_honeypot(group)

        try:
            # Forward all messages for this honeypot (video + payload)
            for msg_id in honeypot['messages']:
                await client.forward_messages(username, msg_id, CHANNEL)
                await asyncio.sleep(2)  # Small delay between messages

            log_sent(username)
            success += 1
            total_attempted += 1
            print(f"  [+] @{username} ← {honeypot['name']} (msgs {honeypot['messages']})")

            # Safe pacing: 2-4 min between targets
            delay = random.randint(120, 240)
            print(f"      waiting {delay}s...")
            await asyncio.sleep(delay)

        except FloodWaitError as e:
            print(f"\n[!] Flood wait {e.seconds}s - stopping session")
            break
        except PeerFloodError:
            print(f"\n[!] Peer flood - stopping session")
            break
        except UserPrivacyRestrictedError:
            log_sent(username)  # Don't retry privacy-blocked users
            print(f"  [-] @{username} - privacy blocked")
            total_attempted += 1
        except Exception as e:
            print(f"  [-] @{username} - {str(e)[:50]}")
            total_attempted += 1

    remaining = len(targets) - total_attempted
    print(f"\n[*] Session complete:")
    print(f"    Sent: {success}")
    print(f"    Total sent all time: {len(load_sent())}")
    print(f"    Remaining: {remaining}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] === AUTO-DISTRIBUTE END ===\n")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
