# tonematch

YouTube'daki bir şarkının gitar tonlarını (ritim, solo, temiz…) ayırıp analiz eden ve **BOSS GT-1** için
en yakın patch'leri üretip cihaza yazan araç. CLI ve Tauri masaüstü uygulaması (Windows + macOS).

*Turns the guitar tones of a song on YouTube into BOSS GT-1 patches: source separation, tone analysis,
a deterministic tone engine (optionally reviewed by Claude), and direct SysEx writes to the unit.*

```powershell
# BOSS TONE STUDIO kapalıyken:
.\tonematch.ps1 run "https://www.youtube.com/watch?v=XXXX" --slot U20
.\tonematch.ps1 run "<url>" --slot U20 --tuning D#G#C#F#A#D#   # şarkı Eb akortluysa
.\tonematch.ps1 run "<url>" --slot U20 --claude                # Claude modu (isteğe bağlı)
```

Ne yapar:
1. Sesi indirir (yt-dlp), gitarı diğer enstrümanlardan ayırır (BS-Roformer, CUDA varsa GPU'da).
2. Gitar bölümlerini ton gruplarına ayırır, her grubun gain, EQ, delay ve reverb'ini ölçer.
3. Ölçümden GT-1 amfi modelini, knob'ları ve efektleri seçer. İki tonlu şarkılarda tek patch'e koyar,
   CTL ile geçilir. Akort verilirse pitch shifter ekler. Tüm patch'ler aynı ses seviyesine ayarlanır.
4. Hedef slotu yedekler, patch'i yazar, geri okuyup doğrular ve cihazı o slota geçirir. Ayrıca
   BOSS TONE STUDIO'ya aktarılabilen bir `.tsl` dosyası yazar.

Varsayılan analiz tamamen algoritmadır. `--claude` ile Claude, motorun önerisini kayıtta kullanılan
ekipman bilgisiyle gözden geçirir (API anahtarı ya da giriş yapılmış `claude` CLI gerekir).

## Masaüstü uygulaması
`desktop/` — Tauri 2 + React 18, kendi tasarım sistemiyle (`desktop/design/`). Ayrıntı:
[`docs/11-desktop.md`](docs/11-desktop.md).

```powershell
desktop\dev.ps1          # Windows (Node, Rust, VS C++ Build Tools gerekir)
desktop/dev.sh           # macOS
```

## Kurulum ve belgeler
- Kurulum, komutlar, sorun giderme: [`docs/09-setup.md`](docs/09-setup.md)
- Yöntem ve mimari: [`docs/00-overview.md`](docs/00-overview.md), [`docs/02-architecture.md`](docs/02-architecture.md)
- GT-1 hakkında doğrulanmış bilgiler ve protokol: [`docs/01-hardware-gt1.md`](docs/01-hardware-gt1.md),
  [`docs/06-gt1-protocol.md`](docs/06-gt1-protocol.md)
- Claude Code ile çalışıyorsan önce [`CLAUDE.md`](CLAUDE.md).

Gereksinimler: BOSS GT-1 (USB), Python 3.11 (uv), ffmpeg. Amfi modellerinin başlangıç ayarları için
bilgisayarda BOSS TONE STUDIO for GT-1 kurulu olmalı; preset dosyaları oradan okunur, repoda yoktur.

BOSS, GT-1 ve BOSS TONE STUDIO, Roland Corporation'ın ticari markalarıdır. Bu proje Roland/BOSS ile
bağlantılı değildir ve onlar tarafından desteklenmez.
