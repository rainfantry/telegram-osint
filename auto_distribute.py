#!/usr/bin/env python3
"""
Auto-distribute honeypots to remaining targets
Run via cron or manually when flood clears
"""
import asyncio
import json
import random
import os
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError, PeerFloodError

API_ID = 35473324
API_HASH = 'd6b1b6d25c05a8326cb3e798fcae1f16'
SESSION = '/root/telegram-osint/scanner_session'

SENT_LOG = '/root/telegram-osint/sent_users.txt'

def load_sent():
    try:
        with open(SENT_LOG, 'r') as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()

def log_sent(username):
    with open(SENT_LOG, 'a') as f:
        f.write(f"{username}\n")

async def main():
    print(f"\n[{datetime.now()}] Starting auto-distribute...")

    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        print("[!] Session expired - need to re-auth")
        return

    me = await client.get_me()
    print(f"[*] Using: @{me.username}")

    # Load targets
    with open('/root/telegram-osint/threat_actors.json', 'r') as f:
        all_targets = json.load(f)

    sent = load_sent()
    targets = [t for t in all_targets if t['username'] not in sent]

    print(f"[*] {len(targets)} remaining targets ({len(sent)} already sent)")

    if not targets:
        print("[*] All targets hit!")
        return

    success = 0

    for t in targets:
        username = t['username']
        group = t['group']

        # Choose honeypot based on group
        if group == 'op_israel':
            msg_id = 28  # IL database
        else:
            msg_id = 29  # RAT

        try:
            await client.forward_messages(username, msg_id, "justicedev2027")
            log_sent(username)
            success += 1
            print(f"  [+] @{username} ({group})")

            # Slow and steady - 2-4 min between sends
            delay = random.randint(120, 240)
            await asyncio.sleep(delay)

        except FloodWaitError as e:
            print(f"\n[!] Flood wait {e.seconds}s - stopping for now")
            break
        except PeerFloodError:
            print(f"\n[!] Peer flood - stopping for now")
            break
        except UserPrivacyRestrictedError:
            log_sent(username)  # Don't retry
            print(f"  [-] @{username} - privacy blocked")
        except Exception as e:
            print(f"  [-] @{username} - {str(e)[:40]}")

    print(f"\n[*] Session complete: {success} sent")
    print(f"[*] Total sent so far: {len(load_sent())}")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
