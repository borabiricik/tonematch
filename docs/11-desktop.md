# 11 — Masaüstü Arayüzü (Tauri, Windows + macOS)

Durum: React arayüz + tasarım sistemi (2026-10-17).

## Yapı
```
desktop/
  design/tokens.json                       # TEK kaynak: renk/tip/boşluk/radius/gölge (tasarım sistemi formatı)
  design/README.md, index.d.ts, cover.html # tasarım sistemi kitabı, tipler, kapak
  scripts/build-tokens.mjs                 # tokens.json -> src/styles/tokens.css (npm run tokens; dev/build öncesi otomatik)
  scripts/stage-design-system.py           # tasarım sistemi artifact'ının project/ dosyalarını hazırlar (npm run ds sonrası)
  src/ds/                                  # tasarım sistemi React bileşenleri (Button, Field, Segmented, SlotPicker, Tabs,
                                           #   Panel, Status/Led, Steps, Notice, Dialog, Console, Knob/KnobRow, Timeline,
                                           #   Chip, PatchCard, SlotGrid) — stil: src/styles/components.css (tm- sınıfları)
  src/app/                                 # uygulama: App (header, sekmeler, çıktı çekmecesi), RunView, DeviceView, TunerView
  src/cli.ts, src/tuning.ts                # CLI köprüsü (tek iş), akort önizlemesi
  src-tauri/                               # Tauri 2 (Rust)
    src/lib.rs                             # komutlar: environment, run_cli, cancel_job, stop_job, cached_slots
    tauri.conf.json, capabilities/default.json, icons/
  dev.ps1 / dev.sh                         # geliştirme başlatıcıları
  app-icon.png                             # ikon kaynağı (`npx tauri icon app-icon.png -o src-tauri/icons`)
```

## Nasıl çalışıyor
Arayüz **sadece CLI argümanı üretir**. Rust tarafı `uv run --project <repo> tonematch <argümanlar>` çalıştırır
(venv: `tonematch.ps1` / `tonematch.sh` ile aynı yer) ve her çıktı satırını `cli-line` olayı, bitişi
`cli-exit` olayı olarak gönderir. Böylece terminal ve uygulama her zaman aynı kodu çalıştırır; ton motoru,
yedekleme, doğrulama, BTS koruması Python'da kalır.

- Slot yazma onayı arayüzde sorulur, CLI'ye `--yes` geçilir (alt süreçte stdin yok).
- **Uzun süren işler** (`gt1 tuner --json`): `cli.run(args, onLine, interactive=true)` → stdin açık kalır.
  `cli.stop()` → `stop_job` bir satır yazıp stdin'i kapatır; CLI temizliğini yapar (cihaz çalma moduna döner) ve
  normal biter. `cancel_job` süreci öldürür, temizlik yapılmaz: tuner için kullanma. `@@TUNER {...}` gibi `@@`
  akış satırları sadece işin `onLine`'ına gider, çıktı çekmecesine düşmez.
- `PYTHONUTF8=1`: Windows'ta konsol kod sayfası (cp1254) yüzünden `→` gibi karakterlerde çökmesin.
- GUI'ler kısa PATH ile açılır: `~/.local/bin`, `~/.cargo/bin`, WinGet Links, `/opt/homebrew/bin` eklenir.
- Repo yolu: derlendiği repo (`CARGO_MANIFEST_DIR/../..`); `TONEMATCH_PROJECT` / `TONEMATCH_VENV` ile değişir.

## Geliştirme
Gerekenler: Node LTS, Rust (rustup), Windows'ta Visual Studio Build Tools (C++), macOS'ta Xcode CLT.
```powershell
desktop\dev.ps1            # Windows: npm install (ilk sefer) + tauri dev
desktop\dev.ps1 build      # kurulum paketi (msi/nsis)
```
```sh
desktop/dev.sh             # macOS
desktop/dev.sh build       # .app / .dmg
```
Rust derleme çıktısı OneDrive/iCloud dışında: `%LOCALAPPDATA%\tonematch\desktop-target`,
`~/Library/Caches/tonematch/desktop-target`.

## macOS notları (Mac'te henüz denenmedi)
- Python: torch PyPI'dan (MPS/CPU), `audio-separator[cpu]` (CUDA yok → ayrıştırma GPU'suz, daha yavaş).
- BTS yolları (`config.py`) AIR düzenine göre tahmin: `/Applications/BOSS TONE STUDIO for GT-1.app/Contents/Resources`,
  `~/Library/Preferences/BOSS-TONE-STUDIO-for-GT-1/Local Store`. Yanlışsa `BTS_INSTALL` / `BTS_APPDATA`.
  KB (BOSS preset'leri) buradan okunur; BTS kurulu olmalı.
- BTS açık mı kontrolü `ps` ile; GT-1 MIDI (CoreMIDI) python-rtmidi ile.

## Sonraki adımlar
- Patch listesi / yedekten geri yükleme ekranları.
- Dağıtım: Python ortamını uygulamayla paketlemek (şimdilik repo + uv gerekiyor).

## Tasarım sistemi
- Yayınlanan referans: https://claude.ai/artifact/TeMiKKRsm2hh4XtfvFSuW7 (renkler, tipler, her bileşenin canlı önizlemesi).
- Değişiklik akışı: `design/tokens.json` veya `src/ds` değişir → `npm run ds` → `python scripts/stage-design-system.py <klasör>`
  → artifact'a yayınla. Uygulama aynı dosyaları doğrudan kullanır.
- React 18, klasik JSX (`import * as React`), bileşenler `window.ToneMatch` olarak da paketlenir (vite.ds.config.ts).
- CLI'nin `--json` çıktısı (`@@RESULT` / `@@ERROR`, `src/tonematch/report.py`): `run`, `gt1 info`, `gt1 list`.
- **Kalibrasyon** (`app/CalibrateView.tsx`, 2026-10-19): sonuç kartında her tonun "Kalibre et" butonu
  (`PatchCard onCalibrate`) → `calibrate <youtube-id url> --role R --json [--slot Uxx]`. CLI `@@CALIB` satırları
  gönderir: `phase: ready` (patch, amp, çalınacak yerler, CTL durumu), `countdown`, `record`, `measure`, ve ~10/sn
  `kind: level` (dBFS, canlı gösterge); sonunda `@@RESULT` (eksen tablosu, ipuçları, spektral mesafe). `--slot`
  sadece ilk turda geçer: sonraki turlar cihazda çevrilen knob'ları korur. İkinci ton (CTL açık) için geri sayım 5 sn.
  Kaynak olarak önbellekteki YouTube id'si verilir (arama tekrar YouTube'a gitmesin). "Dosyaya" hedefinde buton yok.
  İlk turdan sonra "Slota kaydet…" (onay penceresi) → `gt1 save Uxx --expect-name <patch> --yes --json`: edit buffer
  okunur, cihazda başka patch seçiliyse reddedilir, slot yedeklenir, `store_patch` ile yazılıp doğrulanır, seçilir;
  sonuçta değişen knob'lar (`cli._changed_knobs`) gösterilir. "Sadece dinle" sonucunda hedef slot pencerede seçilir.

## Cihaz bilgisinin hızı (2026-10-17)
- Slot listesi için tam patch (24 blok, ~1.5–2 s/slot) değil, tek küçük okuma: isim 00,00–0F + PREAMP tip/gain
  00,51–52 (`GT1Client.patch_summary`, ~25 ms/slot). Okuma isteklerinden sonra yazma aralığı (30 ms) beklenmez.
- `gt1 status` = bağlantı + 99 slot tek bağlantıda (~4 s); `gt1 info --json` ~1 s.
- Son bilinen liste `DATA_DIR/gt1_slots.json` (`device/gt1/slots.py`): her okumada ve tonematch her slota yazdığında
  güncellenir. Uygulama açılışta bu dosyayı Rust'tan doğrudan okur (`cached_slots`, Python başlatmadan, anında),
  cihazı arka planda okur. Cihazda/BTS'te elle yapılan değişiklikler "Yenile" ya da sonraki açılışta gelir.
- CLI işleri kuyrukta sırayla çalışır (MIDI portunun tek sahibi olur); arka plan okuması bir çalıştırmayı engellemez,
  sadece öne geçer.
- Uygulama Python'u venv'in kendi `tonematch` başlatıcısıyla açar (uv'nin proje kontrolü atlanır).
