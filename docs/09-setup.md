# 09 — Kurulum ve Kullanım

## Bu makinede kurulu (2026-10-17)
- `uv` (winget astral-sh.uv), `ffmpeg` (winget Gyan.FFmpeg), Python 3.11 (uv), OpenJDK 21 (sadece spec üretimi için)
- venv: `%LOCALAPPDATA%\tonematch\venv` (OneDrive dışında; torch cu128, CUDA çalışıyor — RTX 3070 Ti)
- Veri: `%LOCALAPPDATA%\tonematch\data` (şarkılar, stem'ler, model ağırlıkları)
- Dış servis yok: indirme dışında her şey yerelde çalışır (LLM/Claude kullanılmaz).

## Sıfırdan kurulum (başka makine)
```powershell
winget install --id=astral-sh.uv -e
winget install --id=Gyan.FFmpeg -e
cd $HOME\OneDrive\Desktop\gt1-tone-matcher
$env:UV_PROJECT_ENVIRONMENT = "$env:LOCALAPPDATA\tonematch\venv"
uv python install 3.11
uv sync
```

## Kullanım
BOSS TONE STUDIO **kapalı** olmalı (MIDI portunu tutuyor).
```powershell
cd $HOME\OneDrive\Desktop\gt1-tone-matcher

# Tam akış: iki tonlu şarkıda TEK patch -> U20 (CTL kapalı = ana ton, CTL açık = ikinci ton)
.\tonematch.ps1 run "https://www.youtube.com/watch?v=XXXX" --slot U20

# Akort: şarkının akordunu sen ver (kalın telden inceye). Verilmezse E standart, pitch shifter yok.
# EADGBE / DADGBE -> shifter yok; diğerleri -> FX1 pitch shifter (gitar EADGBE ya da DADGBE kalır)
.	onematch.ps1 run "<url>" --slot U20 --tuning D#G#C#F#A#D#    # Eb standart: EADGBE çal, -1
.	onematch.ps1 run "<url>" --slot U20 --tuning CGCFAD          # Drop C: DADGBE çal, -2

# Her ton ayrı slota (rhythm U20, clean U21, ...)
.\tonematch.ps1 run "<url>" --slot U20 --separate

# Sadece belirli gruplar
.\tonematch.ps1 run "<url>" --slot U20 --only lead

# Cihaza dokunmadan: analiz + output\*.tsl
.\tonematch.ps1 run "<url>" --no-device

# Slot vermeden: ilk grubu sadece edit buffer'a yükle (kaydetmez, dinlemek için)
.\tonematch.ps1 run "<url>"

# Arama ile
.\tonematch.ps1 run "ytsearch1:Metallica Enter Sandman"

# Cihaz
.\tonematch.ps1 gt1 info          # bağlantı, seçili patch, output select
.\tonematch.ps1 gt1 list          # 99 slotun isimleri
.\tonematch.ps1 gt1 show U20      # patch özeti
.\tonematch.ps1 gt1 backup        # tüm slotları yedekle
.\tonematch.ps1 gt1 restore backups\<dosya>.tsl --index 20 --slot U20   # yedekten geri yükle
```
`--yes` onay sorusunu atlar. Geliştirme: `uv run pytest`, `uv run python tools/calib.py <video_id> -v`.

## Sorun giderme
| Belirti | Çözüm |
|---|---|
| `GT-1 MIDI port not found` / `cannot open` | USB kablosu, BTS'i kapat |
| YouTube "confirm you're not a bot" | Firefox'ta YouTube'a giriş yap veya Chrome/Edge'i kapatıp tekrar dene; ya da `TONEMATCH_COOKIES` |
| Patch sesi çok yüksek/alçak | `gt1 show` ile seviyelere bak; amfiyi kısık başlat |
