# 02 — Mimari

## Dizin yapısı
```
gt1-tone-matcher/
├── CLAUDE.md, README.md, pyproject.toml, uv.lock
├── tonematch.ps1 / tonematch.cmd     # başlatıcı: venv'i OneDrive dışında tutar (%LOCALAPPDATA%\tonematch\venv)
├── src/tonematch/
│   ├── cli.py                # typer: run, analyze, gt1 {info,list,show,backup,restore}
│   ├── config.py             # yollar (DATA_DIR = %LOCALAPPDATA%\tonematch\data), ayırma modelleri
│   ├── pipeline.py           # uçtan uca akış + analiz önbelleği (ANALYSIS_VERSION)
│   ├── ingest.py             # yt-dlp/ffmpeg, önbellek, YouTube bot-kontrolünde tarayıcı çerezi denemesi
│   ├── separate.py           # audio-separator (BS-Roformer-SW → htdemucs_6s fallback)
│   ├── analysis.py           # pencereler, özellikler, kümeleme, grup profilleri, delay/reverb
│   ├── catalog.py            # GT-1 model isim listeleri (testlerde spec ile doğrulanır)
│   ├── kb.py                 # 411 pro patch (BTS preset + liveset): model başına knob medyanları, şablonlar
│   ├── match.py              # ton motoru: ses imzası → model, knob'lar, efekt kuralları (deterministik)
│   ├── practice/             # pratik sistemi (docs/14): theory, exercises, listen, score, session, progress, quiz, solo, cli
│   └── device/gt1/
│       ├── data/gt1_spec.json  # ÜRETİLMİŞ tek kaynak (tools/build_gt1_spec.py)
│       ├── spec.py             # spec yükleme, ekran↔ham değer dönüşümü
│       ├── sysex.py            # DT1/RQ1, checksum
│       ├── patch.py            # Patch (alan → ham byte), .tsl okuma/yazma
│       ├── client.py           # MIDI oturumu, okuma/yazma/kaydet/seç, doğrulama
│       └── backup.py           # slot yedekleri → backups/*.tsl
├── tools/
│   ├── build_gt1_spec.py     # BTS → gt1_spec.json
│   ├── calib.py              # analiz kalibrasyonu (pencere dökümü)
│   ├── temp_roundtrip.py     # .tsl → edit buffer → geri oku → karşılaştır (slota yazmaz)
│   └── select_patch.py       # cihazda patch seç
├── tests/                    # pytest (donanımsız)
├── backups/                  # slot yedekleri (.tsl) — küçük, OneDrive'da kalması istenir
└── output/                   # üretilen patch'ler (.tsl)
```
Büyük veri (`%LOCALAPPDATA%\tonematch\data`): `tracks/<video_id>/` → `source.wav`, `meta.json`,
`stems/*.wav`, `analysis.json`, `report.json`; `models/` (ayırma model ağırlıkları).

## Akış
```
ingest ──► separate ──► analyze ──► match (imza eşleştirme + KB medyanları + kurallar) ──► Patch
                                                                                    ├─► output/*.tsl
                                                                                    └─► GT-1: yedek → yaz → kaydet → doğrula → seç
```

## Katman kuralları
- `analysis.py` saf DSP; cihaz bilgisi içermez.
- `device/gt1/` analizden habersiz; sadece "alan adı → değer".
- `match.py` iki dünyayı birleştirir; tüm cihaz değerleri `Patch.set()` (ekran birimi) üzerinden, spec'e göre
  sınırlanarak yazılır. Ham byte yalnızca 14-bit değerlerde (`set_raw`) kullanılır.
- Önbellek: indirme/stem/analiz video ID bazında; analiz kodu değişince `pipeline.ANALYSIS_VERSION` artırılır.
