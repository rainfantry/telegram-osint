"""
Telegram OSINT Scanner
Searches public Telegram channels/groups by hashtag keyword.
Two methods per term: message content search + channel name search.

Menu:
  1. Full scan    — all terms, both methods, paginated
  2. Quick scan   — core 10 tags only, 1 page each
  3. Channel recon — read osint_channels.txt, get linked group + subscriber count
  4. Group scrape  — read osint_groups.txt, dump all members to txt

Setup:
  1. pip install telethon
  2. Go to my.telegram.org → log in → API Development Tools → Create App
  3. Paste your API_ID and API_HASH below
  4. python telegram_osint.py
  5. First run: enter phone (hidden) + verification code (hidden)
"""

import asyncio
import json
import getpass
from telethon import TelegramClient
from telethon.tl.functions.messages import SearchGlobalRequest
from telethon.tl.functions.contacts import SearchRequest as ContactsSearch
from telethon.tl.functions.channels import GetFullChannelRequest, GetParticipantsRequest
from telethon.tl.types import InputMessagesFilterEmpty, InputPeerEmpty, ChannelParticipantsSearch

# ── CONFIG ────────────────────────────────────────────────────────────────────
API_ID   = 0    # ← my.telegram.org
API_HASH = ""   # ← my.telegram.org

CORE_TERMS = [
    "#RAT", "#RemoteTool", "#HackerTools", "#LifetimeAccess",
    "#Stealer", "#Crypter", "#Bypass", "#CyberTools", "#Logger", "#Keylogger",
]

ALL_TERMS = CORE_TERMS + [
    "#Malware", "#Spyware", "#Botnet", "#FUD", "#Undetected",
    "#C2", "#Payload", "#Dropper", "#InfoStealer", "#PrivateTools",
    "#Exploit", "#Shell", "#Backdoor", "#Ransomware", "#Phishing",
    "#Grabber", "#Cracker", "#Brute", "#Combo", "#Checker",
    "AsyncRAT", "DCRat", "RedLine", "Raccoon", "Vidar", "LummaC2",
    "EagleSpy", "Eclipse C2", "NjRAT", "QuasarRAT", "XWorm",
    "Remcos", "AgentTesla", "FormBook", "SnakeKeylogger",
]

OUTPUT_JSON     = "osint_results.json"
OUTPUT_CHANNELS = "osint_channels.txt"
OUTPUT_GROUPS   = "osint_groups.txt"
OUTPUT_MEMBERS  = "osint_members.txt"


# ── HELPERS ───────────────────────────────────────────────────────────────────

def chat_type(chat):
    if getattr(chat, 'megagroup', False):
        return "group"
    if getattr(chat, 'broadcast', False):
        return "channel"
    return "group"  # plain Chat objects are groups


def save_outputs(all_hits, seen_channels, seen_groups):
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_hits, f, indent=2, ensure_ascii=False)

    with open(OUTPUT_CHANNELS, "w", encoding="utf-8") as f:
        f.write(f"# CHANNELS (broadcast, read-only) — {len(seen_channels)} found\n")
        for link in sorted(seen_channels):
            f.write(link + "\n")

    with open(OUTPUT_GROUPS, "w", encoding="utf-8") as f:
        f.write(f"# GROUPS (supergroups, scrapable) — {len(seen_groups)} found\n")
        for link in sorted(seen_groups):
            f.write(link + "\n")

    print("\n" + "=" * 60)
    print("  DONE")
    print(f"  Total hits:      {len(all_hits)}")
    print(f"  Channels found:  {len(seen_channels)}  → {OUTPUT_CHANNELS}")
    print(f"  Groups found:    {len(seen_groups)}  → {OUTPUT_GROUPS}")
    print(f"  Full data:       {OUTPUT_JSON}")
    print("=" * 60)
    print("\n  CHANNELS:")
    for link in sorted(seen_channels):
        print(f"  {link}")
    if seen_groups:
        print("\n  GROUPS:")
        for link in sorted(seen_groups):
            print(f"  {link}")


def load_links(filepath):
    links = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    links.append(line)
    except FileNotFoundError:
        print(f"[!] {filepath} not found — run a scan first (option 1 or 2)")
    return links


# ── METHOD 1: message content search (paginated) ──────────────────────────────

async def search_term(client, term, max_pages=10):
    print(f"\n[*] Searching: {term}")
    hits        = []
    offset_rate = 0
    offset_peer = InputPeerEmpty()
    offset_id   = 0
    page        = 0

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
            print(f"  [!] Error (page {page}): {e}")
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
                    "term": term, "source": "message_search",
                    "type": chat_type(chat) if chat else "unknown",
                    "message_id": msg.id, "date": str(msg.date),
                    "text": (msg.message or "")[:300],
                    "channel_id": None, "channel_name": None,
                    "channel_username": None, "channel_link": None,
                }
                if chat:
                    hit["channel_id"]       = chat.id
                    hit["channel_name"]     = getattr(chat, "title", None)
                    hit["channel_username"] = getattr(chat, "username", None)
                    if hit["channel_username"]:
                        hit["channel_link"] = f"https://t.me/{hit['channel_username']}"

                hits.append(hit)
                link = hit["channel_link"] or hit["channel_name"] or str(hit["channel_id"])
                print(f"  HIT [{hit['type'][:4]}] → {link}")
                if hit["text"]:
                    print(f"       {hit['text'][:100]}")
            except Exception:
                pass

        next_rate = getattr(results, 'next_rate', None)
        if not next_rate:
            break
        offset_rate = next_rate
        page += 1
        await asyncio.sleep(1)

    print(f"  [{len(hits)} results across {page+1} page(s)]")
    return hits


# ── METHOD 2: channel name search (unbiased) ──────────────────────────────────

async def search_channels_by_name(client, term):
    found = []
    try:
        q = term.lstrip("#")
        results = await client(ContactsSearch(q=q, limit=100))
        for chat in results.chats:
            username = getattr(chat, "username", None)
            title    = getattr(chat, "title", None)
            link     = f"https://t.me/{username}" if username else None
            if link:
                ctype = chat_type(chat)
                found.append({
                    "term": term, "source": "channel_name_search",
                    "type": ctype,
                    "channel_id": chat.id, "channel_name": title,
                    "channel_username": username, "channel_link": link,
                    "text": "", "message_id": None, "date": None,
                })
                print(f"  CHAN [{ctype[:4]}] → {link}  [{title}]")
    except Exception as e:
        print(f"  [!] Name search error: {e}")
    print(f"  [{len(found)} channels by name]")
    return found


# ── SCAN RUNNER ───────────────────────────────────────────────────────────────

async def run_scan(client, terms, max_pages=10):
    all_hits      = []
    seen_channels = set()
    seen_groups   = set()

    for term in terms:
        hits = await search_term(client, term, max_pages=max_pages)
        all_hits.extend(hits)
        for h in hits:
            if h["channel_link"]:
                (seen_groups if h["type"] == "group" else seen_channels).add(h["channel_link"])
        await asyncio.sleep(3)

        chan_hits = await search_channels_by_name(client, term)
        all_hits.extend(chan_hits)
        for h in chan_hits:
            if h["channel_link"]:
                (seen_groups if h["type"] == "group" else seen_channels).add(h["channel_link"])
        await asyncio.sleep(2)

    save_outputs(all_hits, seen_channels, seen_groups)


# ── OPTION 3: channel recon ───────────────────────────────────────────────────

async def run_channel_recon(client):
    links = load_links(OUTPUT_CHANNELS)
    if not links:
        return
    print(f"\n[*] Reconning {len(links)} channels from {OUTPUT_CHANNELS}\n")
    results = []
    for link in links:
        username = link.rstrip("/").split("/")[-1]
        try:
            full = await client(GetFullChannelRequest(username))
            subs       = full.full_chat.participants_count
            linked_id  = full.full_chat.linked_chat_id
            linked_url = f"https://t.me/c/{linked_id}" if linked_id else None
            print(f"  {link}")
            print(f"    subscribers:  {subs}")
            print(f"    linked group: {linked_url or 'none'}")
            results.append({
                "channel": link,
                "subscribers": subs,
                "linked_group": linked_url,
            })
        except Exception as e:
            print(f"  {link}  [!] {e}")
        await asyncio.sleep(2)

    out = "osint_recon.txt"
    with open(out, "w", encoding="utf-8") as f:
        for r in results:
            f.write(f"{r['channel']}\n")
            f.write(f"  subs:         {r['subscribers']}\n")
            f.write(f"  linked group: {r['linked_group'] or 'none'}\n\n")
    print(f"\n[*] Recon saved → {out}")


# ── OPTION 4: group member scrape ─────────────────────────────────────────────

async def run_group_scrape(client):
    links = load_links(OUTPUT_GROUPS)
    if not links:
        return
    print(f"\n[*] Scraping members from {len(links)} groups in {OUTPUT_GROUPS}\n")
    all_members = []

    for link in links:
        username = link.rstrip("/").split("/")[-1]
        print(f"  Scraping: {link}")
        offset = 0
        limit  = 200
        count  = 0
        while True:
            try:
                participants = await client(GetParticipantsRequest(
                    channel=username,
                    filter=ChannelParticipantsSearch(''),
                    offset=offset,
                    limit=limit,
                    hash=0
                ))
                if not participants.users:
                    break
                for u in participants.users:
                    all_members.append({
                        "group":      link,
                        "user_id":    u.id,
                        "username":   getattr(u, "username", None),
                        "first_name": getattr(u, "first_name", None),
                        "last_name":  getattr(u, "last_name", None),
                        "phone":      getattr(u, "phone", None),
                        "bot":        getattr(u, "bot", False),
                    })
                count  += len(participants.users)
                offset += len(participants.users)
                await asyncio.sleep(1)
            except Exception as e:
                print(f"    [!] {e}")
                break
        print(f"    {count} members")
        await asyncio.sleep(3)

    with open(OUTPUT_MEMBERS, "w", encoding="utf-8") as f:
        f.write(f"# GROUP MEMBERS — {len(all_members)} total\n\n")
        for m in all_members:
            uname = f"@{m['username']}" if m['username'] else "no_username"
            name  = " ".join(filter(None, [m['first_name'], m['last_name']])) or "?"
            phone = m['phone'] or ""
            bot   = " [BOT]" if m['bot'] else ""
            f.write(f"{m['group']}  |  {uname}  |  {name}  |  {phone}{bot}\n")

    print(f"\n[*] {len(all_members)} members saved → {OUTPUT_MEMBERS}")


# ── MAIN ──────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("  TELEGRAM OSINT SCANNER")
    print("=" * 60)
    print("  1. Full scan     — 45 terms, both methods, paginated")
    print("  2. Quick scan    — 10 core tags, 1 page each")
    print("  3. Channel recon — recon osint_channels.txt (subs + linked group)")
    print("  4. Group scrape  — scrape members from osint_groups.txt")
    print("=" * 60)

    choice = input("Select [1-4]: ").strip()
    if choice not in ("1", "2", "3", "4"):
        print("[!] Invalid choice")
        return

    client = TelegramClient("osint_session", API_ID, API_HASH)
    await client.start(
        phone=lambda: getpass.getpass("Phone: "),
        code_callback=lambda: getpass.getpass("Code:  "),
        password=lambda: getpass.getpass("2FA:   "),
    )

    async with client:
        me = await client.get_me()
        print(f"\n[*] Logged in as: {me.first_name} (@{me.username})\n")

        if choice == "1":
            await run_scan(client, ALL_TERMS, max_pages=10)
        elif choice == "2":
            await run_scan(client, CORE_TERMS, max_pages=1)
        elif choice == "3":
            await run_channel_recon(client)
        elif choice == "4":
            await run_group_scrape(client)


if __name__ == "__main__":
    asyncio.run(main())
