# CLAUDE.md — gt1-tone-matcher

YouTube'daki bir şarkının gitar tonlarını (rhythm / lead / clean / crunch) analiz edip **BOSS GT-1**
patch'leri üreten ve cihaza yazan araç. Çalışır durumda (v0.1, 2026-10-17). Önce bunu, sonra ilgili `docs/` dosyasını oku.

## Kullanıcı ve kurulum
- Kullanıcı Türkçe konuşuyor; yanıtlar Türkçe, kod/identifier'lar İngilizce.
- GT-1 USB ile bağlı → amfinin ön girişi, amfi düz (sadece yükseltiyor). **Reamp yok** → sistem open-loop.
- Kullanıcı çalıştırırken test istemiyor: `run` tek komutla sonuç vermeli; patch'leri kulakla dinleyip geri bildirim verir.
- Windows 11, PowerShell (macOS da hedef: `tonematch.sh`, docs/11). Her komut `tonematch.ps1` üzerinden (venv `%LOCALAPPDATA%\tonematch\venv`, OneDrive dışı).
  Doğrudan `uv run` kullanacaksan önce `$env:UV_PROJECT_ENVIRONMENT="$env:LOCALAPPDATA\tonematch\venv"`.
- BOSS TONE STUDIO açıkken MIDI portu meşgul olur.

## Dokümanlar
| Dosya | Ne zaman |
|---|---|
| `docs/00-overview.md` | yöntem ve neden |
| `docs/01-hardware-gt1.md` | cihazda **doğrulanmış** gerçekler (olmayan bloklar!) |
| `docs/02-architecture.md` | modüller, veri yerleri |
| `docs/03-separation.md` / `04-tone-analysis.md` | ayırma, rol ayrımı, kalibrasyon sayıları |
| `docs/05-tone-matching.md` | ton motoru: imza tablosu, knob/efekt kuralları |
| `docs/06-gt1-protocol.md` (+ `-extracted.md`) | SysEx, spec üretimi, BTS kanıtları |
| `docs/07-roadmap.md` | sıradaki işler |
| `docs/09-setup.md` | komutlar, sorun giderme |
| `docs/10-tuning.md` | akort tespiti, pitch shifter kuralları, kalibrasyon |
| `docs/12-claude-mode.md` | isteğe bağlı Claude modu: akış, şema, arka uçlar |
| `docs/11-desktop.md` | Tauri masaüstü arayüzü (Windows + macOS), CLI'yi alt süreç olarak çalıştırır |

## Altın kurallar
1. **Cihaz parametreleri tek kaynaktan:** `src/tonematch/device/gt1/data/gt1_spec.json` (üretilmiş;
   `tools/build_gt1_spec.py`). Adres/aralık/enum'u kodda tekrar yazma, elle düzenleme.
2. **GT-1'de EQ / COMP / CHORUS / ACCEL blokları yok** (adresler BTS ortak haritasında var ama cihaz yazmaları
   yok sayıyor ya da hiç kullanılmıyor). EQ → MASTER EQ, kompresör → FX1 COMPRESSOR, modülasyon → FX2.
3. **Slot güvenliği:** slota yazmadan önce yedek (`backups/`), sonra geri okuma doğrulaması — `pipeline.run` ve
   `gt1 restore` bunu yapıyor; yeni yazma yolları da aynısını yapmalı. Kullanıcının istemediği slota yazma.
   Geliştirmede cihazı denemek için `tools/temp_roundtrip.py` (sadece edit buffer, sonra geri yükler).
4. **SYSTEM alanına yazma** (output select, preamp preference vb.). Sadece okunur ve kullanıcı uyarılır.
5. Patch seçimi Program Change ile değil `GT1Client.select_patch` (editör modunda PC yok sayılıyor).
   CTL/ASSIGN: şablondan gelen CTL/assign'lar her patch'te sıfırlanır (CTL1 = PREAMP SOLO); iki tonlu
   şarkıda CTL1 → ASSIGN 1..8 ile ikinci tona geçer (`match.build_dual`, docs/05 §4). NS1 GT-1'de hep açık.
   Slota kaydetmeden önce edit buffer geri okunup doğrulanır (`store_patch`). BTS açıkken bağlanma (koruma var).
6. **Varsayılan: algoritma, LLM yok.** Analiz deterministik koddan çalışır; model ve efektleri ölçülen sesten
   `match.py` seçer. **Claude modu** (kullanıcı kararı 2026-10-17, `run --claude`, arayüzde "Analiz" anahtarı)
   isteğe bağlıdır: motorun önerisini Claude kayıt/ekipman bilgisiyle gözden geçirir (`claude_mode.py`, docs/12).
   Claude modu kapalıyken hiçbir dış model/servis çağrılmaz; açıkken de motorun garantileri (blok kuralları,
   pitch shifter, seviye eşitleme, CTL) korunur ve hata olursa motor sonucu kullanılır. İnternet araması yok.
7. `analysis.py` değişirse `pipeline.ANALYSIS_VERSION` artır (önbellek). Kalibrasyonu `tools/calib.py` ile 5
   referans şarkıda kontrol et (ID'ler: `docs/03-separation.md`), sayıları `docs/04` içinde güncelle.
8. **Akort:** otomatik tespit KAPALI; kullanıcı `--tuning` ile verir (`tuning.parse_tuning`), verilmezse E standart.
   Kullanıcının gitarı EADGBE/DADGBE; bu iki akortta pitch shifter ASLA eklenmez. Diğerlerinde FX1 PITCH SHIFTER
   (`match.apply_pitch_shift`). Tespit kodu (`detect_tuning`) sadece dev araçlarında.
9. **Masaüstü arayüzü (`desktop/`) ince kabuk:** iş mantığı Python'da kalır, arayüz CLI argümanı üretir ve
   `run_cli` ile çalıştırır (`--json` → `@@RESULT`). Yeni özellik önce CLI'ye, sonra arayüze. Arayüz React 18;
   görsel kurallar tasarım sisteminde: `desktop/design/` (tokens.json tek kaynak) + `desktop/src/ds/`, docs/11.
10. Büyük/ telifli veri repoya girmez: ses, stem, model → `%LOCALAPPDATA%\tonematch\data`.

## Kod konvansiyonları
- Python 3.11, `src/tonematch`, typer CLI, `rich` çıktı (kullanıcıya dönük mesajlar Türkçe), tip ipuçları.
- DSP saf fonksiyonlar (`analysis.py`); I/O kenarlarda (`ingest`, `separate`, `device/gt1/client.py`).
- Testler `tests/` (donanımsız, `uv run pytest`). Donanım testleri `@pytest.mark.hardware`.
- Değerleri `Patch.set(alan, ekran_değeri)` ile yaz; ham byte sadece 14-bit alanlarda (`set_raw`).

## Sık komutlar
```powershell
.\tonematch.ps1 run "<youtube-url>" --slot U20      # tam akış, gruplar U20, U21, ... (önce yedek)
.\tonematch.ps1 run "<url>" --slot U20 --tuning D#G#C#F#A#D#   # şarkının akordu (yoksa E standart)
.\tonematch.ps1 run "<url>" --no-device             # sadece analiz + output\*.tsl
.\tonematch.ps1 analyze "<url>"                     # grupları/ölçümleri göster
.\tonematch.ps1 gt1 info | list | show U20 | backup | restore <tsl> --index N --slot U20
uv run pytest
uv run python tools/calib.py <video_id> -v --from 3:20 --to 5:50
uv run python tools/temp_roundtrip.py output\<dosya>.tsl
```

## Durum
Çalışan akış: indirme → BS-Roformer-SW → rol ayrımı → profil → ses imzası → GT-1 modeli + pro patch medyanları + kurallar →
doğrulanmış GT-1 patch → yedek + slot yazma + doğrulama + seçme. Sıradaki iş: `docs/07-roadmap.md`
(kullanıcı kulak geri bildirimiyle `tweak` komutu).
