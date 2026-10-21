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
| 16 × `threejs-*` | `OpenAEC-Foundation/Three.js-Claude-Skill-Package` (MIT, commit `6c190f0`), `.claude/skills/` içine kopyalandı | 3D tuner (2026-10-22): renderer, geometri, materyal, ışık, kontroller, raycaster, animasyon, performans/dispose, render hataları; R3F/drei de var (kullanılmadı) |

Three.js paketinden IFC, XR, fizik, WebGPU, ses ve agent skill'leri alınmadı (bu işe yaramıyor). Paket sadece
markdown; kurmadan önce script/hook olmadığı kontrol edildi. Lisans: `.claude/skills/THREEJS-SKILLS-LICENSE`.

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
  **Önerilen düzeltme** (2026-10-22): knob başına önceki → yeni değer; "Uygula" (`gt1 apply <kayıt> --json`, sadece
  edit buffer) sonrası buton "Geri al" olur (`--undo`), cihazda çevrilmiş olduğu için atlanan knob soluk gösterilir,
  CTL açık tarafta "CTL'yi kapatıp tekrar aç" notu. Yeni tur başlayınca uygulama durumu sıfırlanır (yeni öneri).
  Kaydedilmemiş turla kapatırken uyarır. Sheet açılınca odak kapatma butonuna değil sheet'e gider (Space
  kapatmasın diye).
- **Kütüphane** (`app/LibraryView.tsx`). Çıkarılan tonlar bu bilgisayarda saklanır (localStorage, en çok 40):
  arama, sonucu tekrar açma (kalibrasyon dahil), "Tekrar çıkar…" (form aynı ayarlarla dolar), listeden kaldırma
  (cihaza ve dosyalara dokunmaz).
- **Cihaz** (`app/DeviceView.tsx`). Cihaz kartı (bağlantı, seçili patch, edit buffer; PREAMP = SYSTEM uyarısı),
  99 slot ızgarası (ad / amfi / slot ile filtre; hedef, cihazda seçili, seçili işaretleri), sağda **inceleme
  paneli**: LCD adı, amfi, gain knob'u, CTL; "Cihazda seç ve dinle" (**yeni CLI komutu `gt1 select`**, hiçbir
  şey yazmaz; ızgarada slota **çift tık** da aynısını yapar, 2026-10-22) ve "Sonraki tonu buraya yaz". "Tümünü yedekle" ilerlemeyi n/99 gösterir.
- **Tuner** (`app/TunerView.tsx`, sahne modu). Varsayılan görünüm **3D** (aşağıda "3D tuner"); "Klasik" anahtarı eski
  düz görünüme döner (tercih saklanır). Dev nota, cent ibresi (±3 cent penceresi), yön cümlesi
  ("Pes: teli sıkıştır" / "Tiz: teli gevşet" / "Akortta"); çoklu modda 6 dikey gösterge. Altta gitarın akordu
  (E standart / Drop D) ve tellerin hedef notaları. Space aç/kapat; sayfadan çıkınca cihaz çalma moduna döner.
- **Ayarlar** (`app/SettingsView.tsx`). Tema, demo modu, motorun yeri (proje, venv, uv, platform), kütüphaneyi
  temizle, klavye kısayolları.

## 3D tuner (2026-10-22)
Kullanıcının isteği: tuner için kendi gitarının (Epiphone Les Paul, Cardinal Red) birebir 3D modeli; fareyle
sürükleyince 360° dönsün; tuner açılınca kafaya (headstock) zoom; çalınan telin mandalının hangi yöne döneceği
3D ve animasyonlu gösterilsin.

- **Model** (`app/guitar/lesPaul.ts`): dosya yok, kodla kuruluyor (prosedürel). Cardinal Red'in tek üretildiği model
  **Les Paul Standard '50s** (2020+ "Inspired by Gibson") olarak alındı. Gerçek ölçüler: 24.75" menzil, 43.8 cm
  gövde, 13" alt bölüm, 1.69" eşik, köprüde 2 1/16" tel aralığı, 22 perde, 17° kafa açısı, kemerli akçaağaç kapak.
  Görünüş: parlak Cardinal Red (gövde, sap, kafa arkası), tek kat krem bağlama (kapak ve klavye), defne klavye,
  trapez inlay, Kalamazoo "open book" kafa, siyah kafa yüzü + Epiphone logosu, nikel kapaklı iki humbucker + krem
  çerçeve, krem pickguard, Tune-o-matic + stopbar, altın top-hat düğmeler, krem seçici başı, Keystone mandallar.
  **Gövde silüeti (2026-10-22, kullanıcı geri bildirimi: bel/boğum yanlış, sap kısa):** artık gerçek bir Les Paul
  şablonundan: [cho2/guitar-shape](https://github.com/cho2/guitar-shape) `les-paul.svg` (**CC BY-SA 4.0**; türetilen
  nokta listesi `lesPaul.ts` içinde, kaynak ve lisans yorumda). 43.8 cm boya ölçeklenince eni 33.06 cm (13") çıkıyor,
  yani oranlar gerçek gövdeyle aynı. Sap gövdeden 16. perdede çıkar (eskiden ~13. perde: sap ~3.5 cm kısaydı);
  kuyruk köprünün 18.9 cm gerisinde, toplam boy ~100 cm (gerçek: 39.5"). İki tarafta bel y≈10'da (tiz taraftaki,
  oturunca bacağa gelen boğum), cutaway tabanı 22. perde hizasında. Kemerli kapak artık kenara uzaklıktan
  hesaplanıyor (üçgenleme + 4 kat alt bölme, normaller yükseklik alanından: parlak boyada pürüzsüz yansıma);
  pickguard, düğmeler, seçici ve askı pimi yeni silüete göre yerleşti.
  **Kafa ve detaylar (2026-10-22, geri bildirim: seçicide kesilme, rondela yazısız, kafa şekli tutmuyor):** resmi
  spesifikasyona (gibson.com, Les Paul Standard '50s Cardinal Red) göre: kafa silüeti Wikimedia Commons
  "Gibson-headstock-LP.svg" (GreyCat, **CC BY-SA 3.0**; Epiphone "60s Kalamazoo" aynı open-book): eşikten sonra
  açılan boğaz, düz kenarlar, üstte iki tümsek + V çentik; 17.9 cm boy, çizim dar olduğu için enine %10 açıldı
  (ölçülen 73 mm orta genişlik). Logo sedef (iridescence), "Les Paul Model" altın serigrafi, truss rod kapağı
  2 katlı siyah çan + "Standard" + 3 vida. Seçici rondelası krem + altın RHYTHM / TREBLE, artık kemerli kapağa
  oturuyor (düzdü, eğime gömülüp "kesik" görünüyordu); kol ve krem başlık yüzey normaline dik. Top-hat düğmelerde
  gösterge ve VOLUME / TONE kapakları, eğime göre oturuyor. Yeni parçalar: krem kare jak plakası (tiz yan),
  üst bölüm askı pimi, arkada siyah kontrol kapakları. Tekerlek artık imlecin gösterdiği yere yakınlaşır. Fotoğraf taraması değil; gerçek bir model
  dosyası (GLB) ileride eklenirse aynı arayüzle (`pegAnchor`, `update`) değiştirilebilir.
- **Etkileşim** (`app/guitar/GuitarStage.tsx`, three.js r186, OrbitControls): sürükle = her yöne döndür (pan yok),
  tekerlek = yakınlaş, çift tık = görünümü sıfırla, mandala / tele tıkla = o teli sabitle (tek tel modu).
  Tuner açılınca kamera 1.1 sn'de kafaya uçar; kapanınca bütün gitara döner. Yakın plan, çalınan telin tarafına
  yatar (bas teller üstten, tiz teller alttan) ki düğme uçtan görünsün; oyuncu kamerayı tuttuysa otomatik hareket
  durur (çift tık geri verir). `prefers-reduced-motion`: uçuş anında, oklar ve tel titreşimi durağan.
- **Gösterim:** aktif telin mandalında iki ok: direğin etrafında (kafa yüzünde) ve düğmenin etrafında (mili
  çevresinde); ikisi de dönme yönünde döner, sapma büyüdükçe hızlanır; direk ve düğme de o yönde döner. Renk
  tuner'ın renkleri: uzak (>15 cent) `--danger`, yakın `--warning`, akortta `--success` (direkte halka, ok yok).
  Tel parlar ve titrer. Etiket düğmenin yanında: "5. tel · A / sıkıştır". Çoklu modda altı mandal birden.
- **Hangi yöne:** 3+3 kafada tel direğin iç tarafından çıkar → sıkıştırmak için bas direkler (6-5-4) kafa
  yüzünden bakınca saat yönünün tersine, tiz direkler (3-2-1) saat yönünde döner (geometriden). Düğmeler için
  yaygın kural kullanıldı: uçtan bakınca bas tarafı saat yönünün tersine, tiz tarafı saat yönünde. Bu ikincisi
  dişli yönüne bağlı; kullanıcı gitarında ters görürse `lesPaul.ts` içindeki `BUTTON_TIGHTEN` işaretini çevirmek
  yeter (direk okları değişmez). **Cihazla / gerçek gitarla doğrulanmadı.**
- **Tel tespiti** (`src/tunerStrings.ts`, saf mantık): GT-1 tek tel modunda sadece en yakın nota + cent veriyor
  (oktav yok, tel numarası yok). Tel = hedef notası en yakın olan; iki E (Drop D'de iki D) son çalınan tele göre
  ayrılır, eşitse sıradaki ince tel. Sapma hedefe göre hesaplanır, yani tel yarım ton pesken cihaz D# gösterse
  de "6. tel · sıkıştır" der (eski sürüm sadece cent'e bakıyordu). Otomatik tespit yanılırsa alttaki tel
  düğmelerinden ya da modelden tıklayarak tel sabitlenir; tekrar tıklayınca otomatiğe döner.
- **Performans:** three.js ayrı ve tembel yüklenen parça (~610 kB, sadece Tuner sayfasında), ~150 çizim çağrısı,
  piksel oranı ≤ 2, sayfadan çıkınca her şey `dispose`. WebGL yoksa ya da bağlam kaybolursa uyarı + klasik tuner.
- **Demo:** tek tel modunda demo sırayla 6→1 telleri akort ediyormuş gibi okuma üretir (biri yarım ton pes başlar,
  ikisi tiz); cihazsız bütün akış görülebilir.
- **Doğrulama (2026-10-22, tarayıcı + demo):** genel görünüm, 360° sürükleme (arka yüz), tuner açılınca kafaya zoom,
  bas/tiz tarafına yatma, sıkıştır/gevşet/akortta, çoklu mod, iki tema. `tsc` temiz, `npm run build` geçti, tel
  tespiti için hızlı kontrol betiği geçti (projede JS test altyapısı yok). Tauri penceresinde ve GT-1 ile denenmedi.

## Klavye
| Kısayol | İş |
|---|---|
| ⌘1 … ⌘4, ⌘, | sayfalar, Ayarlar |
| ⌘K | Ton çıkar → şarkı alanı |
| `/` | (Ton çıkar'da) şarkı alanı |
| ⌘↵ | tonu çıkar |
| ⌘J | çıktı çekmecesi |
| Space | tuner aç/kapat · kalibrasyonda kaydı başlat / tekrar çal |
| Çift tık (3D) | tuner'da görünümü sıfırla |
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

## Pratik (2026-10-22, `app/practice/`, docs/14)
- Rail'de "Pratik" (⌘5). Sekmeler: **Bugün** (ders planı gibi dikey zaman çizelgesi: blok, süre, neden, egzersizler,
  tamamlananlar işaretli, "Rutini başlat / Devam et", süre seçimi, ilk kullanımda gecikme testi önerisi),
  **Egzersizler** (gruplu kartlar, seviye noktaları, çalışma temposu / rekor, ton seçimi), **Teori ve kulak**,
  **Solo** (şarkıdan çıkar + cümle kartları), **İlerleme** (seri, dakika, egzersiz başına tempo eğrisi, quiz yüzdeleri).
- **Oynatıcı** (`PlayerSheet`, sahne modu): büyük BPM (←/→, Shift ±5), uzunluk, Space başlat/durdur; tab şeridi
  (SVG, imleç rAF ile akar, notalar yeşil / sarı / kırmızı, önceki tur soluk, birden fazla turda kaçan nota kırmızı
  çerçeveli), ön sayım dev rakamla, canlı doğruluk / tur / fazla nota, zamanlama şeridi (−60..+60 ms, vuruş bölgesi
  yeşil), seviye. Yan panel: odak, klavye şeması (kökler dolu, çalınan nota vurgulu), hoca notları. Sonuç: doğruluk,
  vuruşta %, acele/geride, sayımlar, tur tur eğri, merdiven kararı; "faster" kararında onay penceresi
  ("Evet, X BPM" / "Hayır, kal" / "Sonraki egzersize geç").
- **Quiz** (`QuizSheet`): büyük soru, gerekirse tel vurgulu klavye, duyulan notalar, doğru/yanlış çerçevesi, cevap
  geçmişi noktaları. **Gecikme testi** (`LatencySheet`).
- Tasarım sistemi: `Sparkline`'a `rising` (büyük değer yukarıda) eklendi; yeni ikon `metronome`.
- Demo: `src/demo/practice.ts` + `practice.json` (Python'un ürettiği katalog ve rutin), simüle oyuncu her turda
  biraz daha iyi çalar.

## Sıradaki işler (arayüz)
1. `tweak` komutu gelince (07-roadmap #1) PatchCard'a kulak geri bildirimi: "fazla bas", "gain az" gibi hızlı
   düzeltmeler, knob'lar canlı değişir, onaylı yazma.
2. Yedekten geri yükleme ekranı (`gt1 restore` var; yedek listesi için `gt1 backups --json` gerekir).
3. Kütüphaneyi CLI'nin önbelleğinden (`tracks/<id>/report.json`) doldurmak: başka bilgisayarda çıkarılan
   tonlar da görünsün.
4. Uzun işlerde bitince sistem bildirimi (Tauri notification plugin).
