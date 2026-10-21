# 13 — Arayüz ve Tasarım Sistemi (UI/UX v2, "Signal Path")

Durum: masaüstü arayüzü sıfırdan yeniden yazıldı (2026-10-21). Tasarım sisteminin kuralları
`desktop/design/README.md` (İngilizce, tasarım sistemi kitabı), değerleri `desktop/design/tokens.json` (tek kaynak).
Tauri / CLI köprüsü için `11-desktop.md`.

## Kullanıcının istekleri (2026-10-21)
- UI/UX tarafı **sıfırdan** yeniden düzenlensin; önce güzel bir tasarım sistemi kurulsun.
- Uygulamaya **ne gerekiyorsa eklensin** (bakış açısı: 15+ yıllık UI/UX tasarımcısı ve sahnede çalan bir gitarist).
- Yapılan her şey `docs/` altına yazılsın.
- Tasarım skill'i / knowledge base kurulu değilse bulunup kurulsun.
- GT-1 şu an bağlı değil: canlı test yapılamıyor → arayüz cihazsız denenebilmeli (**demo modu**).

## Kurulan skill'ler (proje kapsamı, `.claude/settings.json`)
| Plugin | Kaynak | Ne için |
|---|---|---|
| `frontend-design` | `claude-plugins-official` (Anthropic) | özgün görsel yön, tipografi, "şablon gibi görünme" kontrolü |
| `ui-ux-pro-max` | `nextlevelbuilder/ui-ux-pro-max-skill` (marketplace eklendi) | yerel arama yapılabilen veritabanı: stiller, paletler, font eşleşmeleri, 119 UX kuralı, teslim öncesi kontrol listesi |

`ui-ux-pro-max`'in önerileri bu ürüne genel kaldı (festival fontları, OLED siyahı). Kontrol listesi olarak
kullanıldı (kontrast, odak, dokunma alanı, reduced-motion, ilerleme göstergesi, onay pencereleri); görsel yön
`frontend-design` sürecine göre ürünün kendi dünyasından (pedal board, amfi paneli, GT-1 ekranı) çıkarıldı.
Arama: `python3 ~/.claude/plugins/cache/ui-ux-pro-max-skill/ui-ux-pro-max/<sürüm>/.claude/skills/ui-ux-pro-max/scripts/search.py "<sorgu>" --domain ux`.

## Tasarım kararları
1. **Konsept "Signal Path".** Arayüz gitar sinyalinin yolunu izler: şarkı → analiz → patch zinciri → cihaz.
   Kabuk sakin (grafit / gündüz grisi); tek sıcak vurgu amfi düğmesinin kremi. Gerçek renk sadece efekt
   zincirinde: her GT-1 bloğu gitarcının tanıdığı pedal rengiyle çizilir (OD/DS turuncu, FX1 sarı, FX2 mor,
   DELAY turkuaz, REVERB mavi, PREAMP krem panel). Renk hiçbir zaman tek ipucu değildir: blok adı hep üstünde.
2. **İki mesafe.** *Masa modu* (ton çıkarma, slotlar) kol mesafesinden okunur. *Sahne modu* (tuner,
   çalarak karşılaştırma) iki metreden, gitar elindeyken okunur: dev rakamlar (`stage` stili, 168px), tek
   belirgin eylem, **Space** ile başlat/durdur.
3. **Tipografi.** Saira (genişliği değişebilen, Eurostile'e yakın panel baskısı: başlıklar, parametre adları,
   bütün sayılar, LCD), Atkinson Hyperlegible Next (okunan her şey; uzaktan okunurluk ve Il1/0O ayrımı için),
   Martian Mono (sadece konsol ve dosya yolları). Hepsi değişken, Latin + Türkçe alt kümesi, repoda
   (`desktop/src/assets/fonts`, OFL), internet gerekmez.
4. **Büyük harf kuralı.** Cihazın yazdığı (GAIN, OD/DS, CTL, amfi ve patch adları) büyük harf; bizim
   yazdığımız her şey cümle düzeninde.
5. **Temalar.** *Sahne* (koyu, varsayılan) ve *Gündüz* (açık); sistem ayarını izler, Ayarlar'dan seçilir.
   Bütün metin çiftleri her iki temada ≥ 4.5:1, kontrol kenarları ve göstergeler ≥ 3:1 (script ile ölçüldü).
6. **Yazma her zaman açıklanır.** Slota yazan her eylemden önce onay penceresi: slotta şu an ne var, onu ne
   koruyor (yedek + geri okuma doğrulaması). Durdurma da onaylanır.

## Bilgi mimarisi
```
┌ Rail ───────┬──────────────────────────────────────────────┐
│ ToneMatch   │  sayfa                                        │
│ Ton çıkar ⌘1│                                               │
│ Kütüphane ⌘2│                                               │
│ Cihaz     ⌘3│                                               │
│ Tuner     ⌘4│                                               │
│             │                                               │
│ Demo modu   │                                               │
│ [● GT-1 …]  │                                               │
│ Ayarlar   ⌘,├─ Çıktı (konsol çekmecesi, ⌘J) ───────────────┤
└─────────────┴──────────────────────────────────────────────┘
```
Rail 1100px altında 64px ikon şeridine iner. Kalibrasyon tam pencere bir **sheet** olarak açılır.

## Ekranlar
- **Ton çıkar** (`app/MatchView.tsx`). Sayfanın tek sorusu "Hangi şarkının tonu?" ve büyük şarkı alanı (`/` ile
  odak). Yazılan şeyin ne olarak yorumlanacağı canlı söylenir: YouTube videosu (küçük resimle) / YouTube araması /
  yerel dosya. Ayarlar tek bir "rack" kartında: Nereye (slot / sadece dinle / dosya) + hedef slot ve içindeki
  patch, şarkının akordu (gitarın hangi akortta kalacağı ve pitch shifter canlı önizlemesi), Analiz
  (Algoritma / Claude ile), iki tonlu şarkılar (tek patch CTL ile / ayrı slotlar). Ana buton ne olacağını söyler:
  "Tonu çıkar ve U20'ye yaz" (⌘↵). Altta son 4 ton.
  Çalışırken: şarkı başlığı, **Pipeline** (dört gerçek aşama, kablo dolar), canlı satır, "Durdur" (onaylı),
  ve **"Bu arada gitarını akort et"** kartı (ayrıştırma dakikalar sürerken tuner'a geçiş). İş arka planda
  sürer; başka sayfaya geçince rail'de LED yanar.
- **Sonuç** (`app/ResultView.tsx`). Şarkı başlığı (küçük resim, BPM, süre), **akort şeridi** ("Şarkı Eb
  standart. Gitarını EADGBE akortla; FX1 pitch shifter −1"), Claude notu, her patch için **PatchCard**: slot,
  LCD'de patch adı, durum, iki tonlu patch'te **CTL anahtarı** (zincir değişir, CTL'nin değiştirdiği bloklar ve
  knob'lar işaretlenir), **pedal zinciri** (FX1 → OD/DS → PREAMP ve 6 knob → FX2 → DELAY → REVERB; kapalı
  bloklar kesikli), şarkı haritası (her ton nerede çalıyor), CTL ile değişen ayarlar. Dosyalar: .tsl ve yedek
  yolu, kopyala ve "Klasörde göster". Zincir sırası GT-1'in alışılmış sırasıdır: hangi blok açık ve nasıl
  ayarlı onu gösterir, patch'teki gerçek routing'i değil.
- **Çalarak karşılaştır** (`app/CalibrateSheet.tsx`, sahne modu). Adımlar, kayıt uzunluğu, "Kaydı başlat"
  (Space). Sağda "Nereden çalacaksın" (sonuçtan bilindiği için baştan görünür) ve turlar. Geri sayım dev
  rakamla, kayıt sırasında kalan süre + LED merdiveni seviye göstergesi + ne yapılacağını söyleyen cümle.
  Rapor: spektral mesafe (dev), önceki tura göre fark, **Ne yapmalı** kartları (hangi knob, hangi yöne),
  **Eksen eksen** (şarkı ve sen aynı ölçekte), **Frekans frekans** (1/3 oktav fark grafiği; CLI'nin
  `third_oct_diff` verisi artık gösteriliyor; bas sızıntısı bantları taralı), "Slota kaydet…" (onaylı).
  Kaydedilmemiş turla kapatırken uyarır. Sheet açılınca odak kapatma butonuna değil sheet'e gider (Space
  kapatmasın diye).
- **Kütüphane** (`app/LibraryView.tsx`). Çıkarılan tonlar bu bilgisayarda saklanır (localStorage, en çok 40):
  arama, sonucu tekrar açma (kalibrasyon dahil), "Tekrar çıkar…" (form aynı ayarlarla dolar), listeden kaldırma
  (cihaza ve dosyalara dokunmaz).
- **Cihaz** (`app/DeviceView.tsx`). Cihaz kartı (bağlantı, seçili patch, edit buffer; PREAMP = SYSTEM uyarısı),
  99 slot ızgarası (ad / amfi / slot ile filtre; hedef, cihazda seçili, seçili işaretleri), sağda **inceleme
  paneli**: LCD adı, amfi, gain knob'u, CTL; "Cihazda seç ve dinle" (**yeni CLI komutu `gt1 select`**, hiçbir
  şey yazmaz) ve "Sonraki tonu buraya yaz". "Tümünü yedekle" ilerlemeyi n/99 gösterir.
- **Tuner** (`app/TunerView.tsx`, sahne modu). Dev nota, cent ibresi (±3 cent penceresi), yön cümlesi
  ("Pes: teli sıkıştır" / "Tiz: teli gevşet" / "Akortta"); çoklu modda 6 dikey gösterge. Altta gitarın akordu
  (E standart / Drop D) ve tellerin hedef notaları. Space aç/kapat; sayfadan çıkınca cihaz çalma moduna döner.
- **Ayarlar** (`app/SettingsView.tsx`). Tema, demo modu, motorun yeri (proje, venv, uv, platform), kütüphaneyi
  temizle, klavye kısayolları.

## Klavye
| Kısayol | İş |
|---|---|
| ⌘1 … ⌘4, ⌘, | sayfalar, Ayarlar |
| ⌘K | Ton çıkar → şarkı alanı |
| `/` | (Ton çıkar'da) şarkı alanı |
| ⌘↵ | tonu çıkar |
| ⌘J | çıktı çekmecesi |
| Space | tuner aç/kapat · kalibrasyonda kaydı başlat / tekrar çal |
| Esc | pencereyi kapat (kayıt sırasında değil) |

Windows'ta ⌘ yerine Ctrl. Sayfa değişince odak sayfaya taşınır (ekran okuyucu duyurur, Space rail'e gitmez).

## Demo modu (cihazsız deneme)
`src/demo/mock.ts` Tauri tarafının yerine geçer (`run_cli`, `cancel_job`, `stop_job`, `environment`,
`cached_slots`, `reveal_path`) ve her CLI komutunun **gerçek çıktı biçimini** gerçekçi zamanlamayla üretir:
`gt1 status/info/list/select/save/backup`, `run` (1/4…4/4 satırları, ayrıştırma yüzdesi, `--tuning`,
`--separate`, `--claude`, `--no-device`, `--slot` kurallarıyla), `gt1 tuner --json` (tek ve çoklu), `calibrate
--json` (geri sayım, ~10/sn seviye, her turda biraz daha yakın sonuç). Veriler `src/demo/fixtures.ts`.
- Açmak: Ayarlar → Demo modu (uygulama yeniden yüklenir). Tarayıcıda (`npm run dev`, Tauri yok) hep açık.
- Demo açıkken hiçbir gerçek komut çalışmaz; rail'de "Demo modu", cihaz kartında "Demo verisi" yazar.
- Akort kuralı CLI ile aynı (`tuning.ts`): akort verilmezse E standart, pitch shifter yok.

## Tasarım sistemi
- Kaynak: `desktop/design/tokens.json` → `npm run tokens` → `src/styles/tokens.css`. Bileşenler `src/ds/`
  (`controls`, `feedback`, `gear`, `meters`, `results`, `icons`, `format`), stiller `src/styles/components.css`
  (`tm-` sınıfları), uygulama yerleşimi `src/styles/app.css`, temel `src/styles/base.css`.
- Yayınlanan referans (canlı önizlemeler, kurallar): https://claude.ai/artifact/TeMiKKRsm2hh4XtfvFSuW7 (v2).
  Güncelleme: `npm run ds && python scripts/stage-design-system.py <klasör>` → `<klasör>/project/` artifact'a
  yayınlanır (index `design-system.json` en son; `.d.ts` `text/plain` olarak gider). Artifact sayfası
  `unicode-range` ve motion token'larını okumaz: script motion değişkenlerini ve `.t-*` tip sınıflarını
  `bundle.css`'e ekler; fontlar bu yüzden tek dosya.
- Bileşen envanteri: Button, IconButton, Kbd · Field, TextInput, Select, Segmented, Switch, SlotPicker ·
  Led, Chip, Status, Card, SectionHead, Notice, Dialog, Sheet, Toaster/toast, EmptyState, Skeleton, Console ·
  Knob, KnobRow, Lcd, Pedal, SignalChain, SlotGrid · Pipeline, SongMap, LevelMeter, CentsMeter, StringMeter,
  AxisCompare, BandDiff, Sparkline · PatchCard.

## Yeni arka uç parçaları
- CLI `tonematch gt1 select U21 [--json]`: slotu cihazda seçer (edit buffer'a yükler), patch verisi yazmaz
  (`GT1Client.select_patch`). Test: `tests/test_cli_select.py` (donanımsız).
- Tauri `reveal_path`: CLI'nin verdiği dosyayı Finder / Explorer'da gösterir (göreli yollar repoya göre).
- Pencere 1280×840 (en az 900×600).

## Doğrulama (2026-10-21)
- `tsc --noEmit` temiz (`noUnusedLocals`), `cargo check` temiz, `tests/test_cli_select.py` geçti.
- Tarayıcıda demo moduyla uçtan uca: ton çıkar (onay → pipeline → sonuç), CTL geçişi, çalarak karşılaştırma
  (Space, geri sayım, kayıt, rapor), kütüphane, cihaz (seç, hedef), tuner (tek / çoklu), ayarlar, iki tema.
- **Cihazla denenmedi** (GT-1 bağlı değildi). İlk cihaz denemesinde bakılacaklar: `gt1 select` gerçekten slota
  geçiyor mu; tuner / kalibrasyon akışları yeni arayüzde; "Klasörde göster" Windows'ta.

## Sıradaki işler (arayüz)
1. `tweak` komutu gelince (07-roadmap #1) PatchCard'a kulak geri bildirimi: "fazla bas", "gain az" gibi hızlı
   düzeltmeler, knob'lar canlı değişir, onaylı yazma.
2. Kalibrasyonda otomatik düzeltme (07-roadmap #0 adım 2) gelince rapora "Uygula" (edit buffer'a).
3. Yedekten geri yükleme ekranı (`gt1 restore` var; yedek listesi için `gt1 backups --json` gerekir).
4. Kütüphaneyi CLI'nin önbelleğinden (`tracks/<id>/report.json`) doldurmak: başka bilgisayarda çıkarılan
   tonlar da görünsün.
5. Uzun işlerde bitince sistem bildirimi (Tauri notification plugin).
