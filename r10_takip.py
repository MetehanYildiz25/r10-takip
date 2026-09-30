"""R10 yeni iş ilanı takipçisi.

İş verenlerin ilan açtığı kategorileri tarar; yeni açılan ilanları
Telegram botu üzerinden mesaj olarak gönderir. Görev Zamanlayıcı ile
her 10 dakikada bir çalıştırılır.

Kullanım:
    python r10_takip.py          # normal tarama
    python r10_takip.py --test   # Telegram bağlantısını test eder
"""
import json
import os
import re
import sys
import time
from datetime import datetime
from html import escape
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parent
CONFIG_FILE = BASE / "config.json"
STATE_FILE = BASE / "seen.json"
LOG_FILE = BASE / "r10_takip.log"

CATEGORIES = {
    "is-verenler": "İş Verenler",
    "yazilim-kodlama-is-verenler": "Yazılım İş Verenler",
    "makale-icerik-siparisleri": "Makale Siparişleri",
    "editor-ariyorum": "Editör Arıyorum",
    "tasarim-isleri": "Tasarım İşleri",
    "video-kurgu-produksiyon-ve-seslendirme": "Video Kurgu",
    "ui-ux-tasarim": "UI/UX Tasarım",
    "ucretli-wordpress-isleri": "Ücretli WordPress",
    "bot-program-istek": "Bot & Program İstek",
}

# Başlıkta bunlardan biri geçen ilanlar atlanır (yasal risk / platform kuralı / satıcı ilanı).
BLACKLIST = [
    "hesap aç", "hesap acma", "hesap açma", "stripe", "paypal", "onay işi", "onay isi",
    "hit bot", "hit botu", "cookie", "takipçi", "takipci", "beğeni", "begeni",
    "kilit açıcı", "kilit acici", "toplu mesaj", "dm bot", "bahis", "casino",
    "kripto", "coin", "yatırım yap", "satış başına", "referans kod",
    # satıcı ilanları (iş veren değil, hizmet satan)
    "satış:", "yaparım", "yapariz", "yaparız", "hizmeti", "hizmetleri", "sunuyorum",
    "geliştiriyorum", "faturalı", "indirim", "ücretsiz web",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
}
THREAD_ID_RE = re.compile(r"/(\d{6,})-")


def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    # Log dosyası 1 MB'ı geçerse son yarısını tut
    if LOG_FILE.stat().st_size > 1_000_000:
        text = LOG_FILE.read_text(encoding="utf-8")
        LOG_FILE.write_text(text[len(text) // 2:], encoding="utf-8")


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def send_telegram(cfg, text):
    r = requests.post(
        f"https://api.telegram.org/bot{cfg['telegram_token']}/sendMessage",
        data={
            "chat_id": cfg["chat_id"],
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        },
        timeout=20,
    )
    if not r.ok:
        log(f"Telegram hatası {r.status_code}: {r.text[:200]}")
    return r.ok


def fetch_threads(session, slug):
    r = session.get(f"https://www.r10.net/{slug}/", timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.content, "html.parser")
    threads = []
    for a in soup.select('a[id^="thread_title_"]'):
        m = THREAD_ID_RE.search(a.get("href", ""))
        if not m:
            continue
        tid = int(m.group(1))
        row = a.find_parent("li", class_="thread")
        author = ""
        replies = ""
        if row:
            u = row.select_one(".user .desktop a")
            author = u.get_text(strip=True) if u else ""
            c = row.find("span", attrs={"title": re.compile("Cevap")})
            replies = c.get_text(strip=True) if c else ""
            prefix = row.select_one(".prefix")
            if prefix and "sabit" in prefix.get_text(strip=True).lower():
                continue
        threads.append({
            "id": tid,
            "title": a.get_text(" ", strip=True),
            "url": a["href"],
            "author": author,
            "replies": replies,
        })
    return threads


def fetch_first_post(session, url):
    try:
        r = session.get(url, timeout=30)
        soup = BeautifulSoup(r.content, "html.parser")
        m = soup.select_one(".postContent, [id^=post_message]")
        text = m.get_text(" ", strip=True) if m else ""
        return text[:350] + ("…" if len(text) > 350 else "")
    except requests.RequestException:
        return ""


def is_blacklisted(title):
    t = title.lower()
    return any(w in t for w in BLACKLIST)


def detect_chat_id(cfg):
    """Bota en son mesaj atan sohbetin ID'sini bulup config.json'a yazar."""
    r = requests.get(f"https://api.telegram.org/bot{cfg['telegram_token']}/getUpdates", timeout=20)
    if not r.ok:
        print("Token hatalı görünüyor:", r.status_code)
        return False
    chats = [u["message"]["chat"]["id"] for u in r.json().get("result", []) if "message" in u]
    if not chats:
        print("Bota henüz mesaj gelmemiş. Telegram'da botuna 'merhaba' yaz ve tekrar dene.")
        return False
    cfg["chat_id"] = str(chats[-1])
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Chat ID bulundu ve config.json'a kaydedildi.")
    return True


def main():
    if os.environ.get("TELEGRAM_TOKEN"):  # GitHub Actions: token Secrets'tan gelir
        cfg = {"telegram_token": os.environ["TELEGRAM_TOKEN"], "chat_id": os.environ["CHAT_ID"]}
    else:
        cfg = load_json(CONFIG_FILE, None)
    if not cfg or "BURAYA" in cfg.get("telegram_token", "BURAYA"):
        log("config.json doldurulmamış, çıkılıyor.")
        sys.exit(1)
    if "BURAYA" in str(cfg.get("chat_id", "BURAYA")) and not detect_chat_id(cfg):
        log("chat_id bulunamadı, çıkılıyor.")
        sys.exit(1)

    if "--test" in sys.argv:
        ok = send_telegram(cfg, "✅ R10 takip botu bağlantı testi başarılı.")
        print("Telegram testi:", "BAŞARILI" if ok else "BAŞARISIZ (log dosyasına bak)")
        return

    state = load_json(STATE_FILE, {"baseline": 0, "seen": []})
    seen = set(state["seen"])
    first_run = state["baseline"] == 0

    session = requests.Session()
    session.headers.update(HEADERS)

    all_threads = []
    for slug, name in CATEGORIES.items():
        try:
            for t in fetch_threads(session, slug):
                t["category"] = name
                all_threads.append(t)
        except requests.RequestException as e:
            log(f"{slug} okunamadı: {e}")
        time.sleep(1.5)

    if not all_threads:
        log("Hiç ilan okunamadı (site erişimi?).")
        return

    if first_run:
        # İlk çalıştırmada mevcut ilanları "görüldü" say; sadece bundan sonra açılanları bildir.
        state["baseline"] = max(t["id"] for t in all_threads)
        state["seen"] = sorted({t["id"] for t in all_threads})
        STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
        send_telegram(cfg, f"🚀 R10 takip başladı. {len(CATEGORIES)} kategori izleniyor; "
                           f"bundan sonra açılan yeni ilanlar buraya gelecek.")
        log(f"İlk çalıştırma: baseline={state['baseline']}")
        return

    # Yeni ilan = daha önce görülmemiş VE baseline'dan büyük ID
    # (eski konular yeni cevapla üste çıkınca bildirim gelmesin diye).
    new = [t for t in all_threads if t["id"] not in seen and t["id"] > state["baseline"]]
    new = list({t["id"]: t for t in new}.values())
    new.sort(key=lambda t: t["id"])

    sent = skipped = 0
    for t in new:
        seen.add(t["id"])
        if is_blacklisted(t["title"]):
            skipped += 1
            continue
        snippet = fetch_first_post(session, t["url"])
        time.sleep(1)
        msg = (
            f"🆕 <b>{escape(t['title'])}</b>\n"
            f"📂 {escape(t['category'])} · 👤 {escape(t['author'])} · 💬 {escape(t['replies'])} cevap\n\n"
            f"{escape(snippet)}\n\n"
            f"🔗 {t['url']}"
        )
        if send_telegram(cfg, msg):
            sent += 1
        time.sleep(0.5)

    state["seen"] = sorted(seen)[-5000:]
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    log(f"Tarama bitti: {len(all_threads)} ilan okundu, {sent} bildirim, {skipped} elendi.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # zamanlanmış görevde sessizce çökmesin
        log(f"HATA: {e!r}")
        raise
