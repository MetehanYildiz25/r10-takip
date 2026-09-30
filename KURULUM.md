# R10 Takip Botu — Kurulum

Her 10 dakikada bir R10'daki iş kategorilerini tarar ve yeni açılan ilanları Telegram'dan gönderir.
Windows Görev Zamanlayıcı'daki **"R10 Takip"** görevi ile çalışır (bilgisayar açık ve oturumun açıkken).

## 1. Telegram botu oluştur (2 dk)
1. Telegram'da **@BotFather**'ı aç ve `/newbot` yaz.
2. Bota bir isim ve `_bot` ile biten bir kullanıcı adı ver.
3. BotFather'ın verdiği **token**'ı kopyala (`123456:ABC...` gibi).
4. Yeni botunu aç ve **Start**'a bas (bu şart, yoksa bot sana yazamaz).

Eski botun varsa: @BotFather → `/mybots` → botunu seç → **API Token**.

## 2. Botuna mesaj at
Telegram'da botunu aç ve ona herhangi bir mesaj yaz (örn. "merhaba").
Chat ID'yi script bu mesajdan kendisi bulur.

## 3. config.json'a token'ı yaz
`config.json` dosyasında sadece `telegram_token` alanını doldur, `chat_id`'ye dokunma:
```json
{
  "telegram_token": "123456:ABC...",
  "chat_id": "BURAYA_CHAT_ID"
}
```

## 4. Test et
```
python r10_takip.py --test
```
Telegram'a "bağlantı testi başarılı" mesajı gelmeli.

## Kullanım
- İlk çalıştırmada "R10 takip başladı" mesajı gelir, sonra sadece yeni ilanlar gelir.
- Kayıtlar: `r10_takip.log`
- Kategori veya yasaklı kelime eklemek için: `r10_takip.py` içindeki `CATEGORIES` ve `BLACKLIST`.
- Durdurmak için: `schtasks /change /tn "R10 Takip" /disable`
- Silmek için: `schtasks /delete /tn "R10 Takip" /f`

## GitHub Actions (7/24, bilgisayar kapalıyken de çalışır) — AKTİF
- Depo: https://github.com/MetehanYildiz25/r10-takip
- Token ve chat ID, depo ayarlarında **Secrets** olarak saklanıyor (`TELEGRAM_TOKEN`, `CHAT_ID`); kodda yok.
- Çalışma geçmişi: depo → **Actions** sekmesi.
- Elle çalıştırmak / test: Actions → R10 Takip → **Run workflow** (test kutusunu işaretlersen sadece Telegram testi yapar).
- Durdurmak: Actions → R10 Takip → **⋯** → **Disable workflow**.
- Token yenilenirse: `gh secret set TELEGRAM_TOKEN` (veya Settings → Secrets and variables → Actions).
- Bilgisayardaki "R10 Takip" zamanlanmış görevi, çift bildirim olmasın diye **devre dışı**.
