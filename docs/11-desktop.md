# 11 — Masaüstü Arayüzü (Tauri, Windows + macOS)

Durum: React arayüz + tasarım sistemi (2026-10-17); arayüz v2 "Signal Path" (2026-10-21, ekranlar ve tasarım kararları: `13-ui-ux.md`).

## Yapı
```
desktop/
  design/tokens.json                       # TEK kaynak: renk/tip/boşluk/radius/gölge/motion (tasarım sistemi formatı)
  design/README.md, index.d.ts, cover.html # tasarım sistemi kitabı (İngilizce), tipler, kapak
  scripts/build-tokens.mjs                 # tokens.json -> src/styles/tokens.css (npm run tokens; dev/build öncesi otomatik)
  scripts/stage-design-system.py           # tasarım sistemi artifact'ının project/ dosyalarını hazırlar (npm run ds sonrası)
  src/ds/                                  # tasarım sistemi bileşenleri: controls, feedback, gear (Knob, Pedal, SignalChain,
                                           #   SlotGrid, Lcd), meters (Pipeline, SongMap, LevelMeter, CentsMeter, AxisCompare,
                                           #   BandDiff), results (PatchCard), icons, format — stil: styles/components.css (tm-)
  src/app/                                 # App (rail, cihaz durumu, konsol, kısayollar), MatchView, ResultView, CalibrateSheet,
                                           #   LibraryView, DeviceView, TunerView, SettingsView, state.ts, parts.tsx
  src/demo/                                # demo modu: mock.ts (Tauri tarafının yerine), fixtures.ts (CLI çıktı biçiminde veri)
  src/cli.ts, src/tuning.ts                # CLI köprüsü (tek iş, demo seçimi), akort önizlemesi
  src/styles/                              # tokens.css (üretilir), base.css, components.css, app.css
  src/assets/fonts/                        # Saira, Atkinson Hyperlegible Next, Martian Mono (OFL, Latin + Türkçe)
  src-tauri/                               # Tauri 2 (Rust)
    src/lib.rs                             # komutlar: environment, run_cli, cancel_job, stop_job, cached_slots, reveal_path
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

## macOS notları (2026-10-21: dev modda açıldı, demo moduyla denendi; 2026-10-22: GT-1 bağlı, okuma komutları çalışıyor)
- Python: torch PyPI'dan (MPS/CPU), `audio-separator[cpu]` (CUDA yok → ayrıştırma GPU'suz, daha yavaş).
- BTS yolları (`config.py`, 2026-10-22 Mac'te doğrulandı): `/Applications/BOSS_TONE_STUDIO_for_GT1.app/Contents/Resources`,
  `~/Library/Application Support/BOSS-TONE-STUDIO-for-GT-1/Local Store` (eski tahmin yanlıştı: KB boş geliyor,
  11 test düşüyordu). Farklıysa `BTS_INSTALL` / `BTS_APPDATA`. KB (BOSS preset'leri) buradan okunur; BTS kurulu olmalı.
- BTS açık mı kontrolü `ps` ile; GT-1 MIDI (CoreMIDI) python-rtmidi ile.
- `src/tonematch/device/gt1/data/gt1_spec.json` `.gitignore`'daki `data/` kuralı yüzünden repoda yok: yeni bir
  bilgisayarda diğerinden kopyala ya da `tools/build_gt1_spec.py` ile üret; yoksa cihaz komutları ve bazı testler
  açılmaz (arayüz "GT-1 parametre tablosu yok" der).
  Mac'te üretim (2026-10-22, Java 17 + JPEXS FFDec 26.3.0, sadece gereken 4 sınıf, ~2 sn):
  `java -jar ffdec-cli.jar -selectclass tonecentral.parametors.TemporaryParams,tonecentral.common.define.ParameterDefinitionGT,tonecentral.common.define.CTLAssignTargetDefinitionGT,tonecentral.common.define.CTLDefinitionGT -export script <out> "/Applications/BOSS_TONE_STUDIO_for_GT1.app/Contents/Resources/BOSS_TONE_STUDIO_for_GT1.swf"`
  sonra `uv run python tools/build_gt1_spec.py <out>/scripts --bts "/Applications/BOSS_TONE_STUDIO_for_GT1.app/Contents/Resources"`
  (995 alan, 468 tanım). Cihazla doğrulandı: `gt1 status` 99 slotu doğru adlarla okudu; 40 test geçiyor.
- `tonematch.sh` ve `desktop/dev.sh` repoda çalıştırılabilir olarak işaretli değil (Windows'tan geldi): `chmod +x`.

## Sonraki adımlar
- Arayüz işleri: `13-ui-ux.md` → Sıradaki işler.
- Dağıtım: Python ortamını uygulamayla paketlemek (şimdilik repo + uv gerekiyor).

## Tasarım sistemi
- Kurallar ve kararlar: `13-ui-ux.md` ve `desktop/design/README.md`; yayınlanan referans (canlı önizlemeler):
  https://claude.ai/artifact/TeMiKKRsm2hh4XtfvFSuW7 (v2, 2026-10-21).
- Değişiklik akışı: `design/tokens.json` veya `src/ds` değişir → `npm run ds` → `python scripts/stage-design-system.py <klasör>`
  → artifact'a yayınla. Uygulama aynı dosyaları doğrudan kullanır.
- React 18, klasik JSX (`import * as React`), bileşenler `window.ToneMatch` olarak da paketlenir (vite.ds.config.ts).
- CLI'nin `--json` çıktısı (`@@RESULT` / `@@ERROR`, `src/tonematch/report.py`): `run`, `gt1 info`, `gt1 status`, `gt1 list`,
  `gt1 select`, `gt1 save`, `calibrate`, `gt1 tuner`.
- **Demo modu** (Ayarlar'dan; tarayıcıda hep açık): `src/demo/mock.ts` aynı komutların aynı çıktısını üretir, cihaz ve
  Python gerekmez. Ayrıntı: `13-ui-ux.md`.
- **Kalibrasyon** (`app/CalibrateSheet.tsx`, 2026-10-19; v2'de tam pencere "sahne modu"): sonuç kartında her tonun
  "Çalarak karşılaştır" butonu (`PatchCard onCalibrate`) → `calibrate <youtube-id url> --role R --json [--slot Uxx]`.
  CLI `@@CALIB` satırları gönderir: `phase: ready` (patch, amp, çalınacak yerler, CTL durumu), `countdown`, `record`, `measure`,
  ve ~10/sn `kind: level` (dBFS, canlı gösterge); sonunda `@@RESULT` (eksen tablosu, ipuçları, spektral mesafe, 1/3 oktav
  fark `third_oct_diff`). `--slot` sadece ilk turda geçer: sonraki turlar cihazda çevrilen knob'ları korur. İkinci ton
  (CTL açık) için geri sayım 5 sn. Kaynak olarak önbellekteki YouTube id'si verilir (arama tekrar YouTube'a gitmesin).
  "Dosyaya" hedefinde buton yok. İlk turdan sonra "Slota kaydet…" (onay penceresi) → `gt1 save Uxx --expect-name <patch>
  --yes --json`: edit buffer okunur, cihazda başka patch seçiliyse reddedilir, slot yedeklenir, `store_patch` ile yazılıp
  doğrulanır, seçilir; değişen knob'lar (`cli._changed_knobs`) bildirimde gösterilir.

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
