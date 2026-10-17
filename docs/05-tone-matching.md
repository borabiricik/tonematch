# 05 — Ton Motoru (ölçüm → GT-1 patch)

Tamamen deterministik kod (`src/tonematch/match.py`). Dış servis, LLM, internet araması **yok**;
kayıtta hangi ekipmanın kullanıldığı bilinmez/aranmaz. Aynı girdi → her zaman aynı patch.

## 1. Model seçimi (ses imzası eşleştirme)
Ölçülen grup profili şu eksenlere indirgenir (referans stem medyanlarına göre sapma, dB):
| Eksen | Ölçüm | Anlamı |
|---|---|---|
| D (0..1) | `drive_index(drive_flatness(g))` — log ölçek, 0.05→0, 0.45→1 | distorsiyon miktarı |
| M | `mid_scoop_db` (400–1200 Hz vs 150–350 & 1.8–4 kHz) | <0 V/oyuk, >0 orta öne |
| P | `presence_db` (2–4.5 kHz vs 0.7–1.6 kHz) | ısırık / parlaklık |
| B | `body_db` (200–450 Hz vs 0.7–1.6 kHz) | alt-orta gövde |
| L | `low_depth_db` (60–110 vs 110–220 Hz) | sadece metal ↔ pedal ayrımında (bas sızıntısı gürültülü) |

Her GT-1 modelinin beklenen imzası `PREAMP_SIGNATURES` / `CLEAN_SIGNATURES` tablosunda (GT-1 COSM
modellerinin voicing'ine göre elle tanımlı). Skor = ağırlıklı kare mesafe; en düşük skor kazanır.
Lead rolünde lead'e uygun modellere (BG LEAD, SLDN, EXTREME LEAD...) küçük bir bonus.
Çok doymuş ama alt ucu ince sesler için "amfi|pedal" kombinasyonları: `STACK CRUNCH|DISTORTION`,
`MS1959 I|MUFF FUZZ` (grunge/punk/fuzz).

Referans (`REF`, 7 kalibrasyon şarkısının medyanı): driven `M +0.4, P -3.7, B +7, L -6.5, fizz -16`;
clean `M 0, P -6, B +9, L -9.5, fizz -19`.

## 2. Knob'lar
- Başlangıç: o modelin 411 pro patch'teki **medyan** gain/bass/middle/treble/presence ve seviyeleri
  (`kb.type_stats`; <5 örnekli modellerde makul varsayılanlar).
- Gain: `medyan + (D − model_D) × 120` (+6 lead; pedal kombinasyonunda amfi −10).
- Middle: `+ M × 3`; Treble: `+ P × 2`; Presence: `+ P × 1.5 + fizz/3 (±4)`.
- Bass: medyandan **sadece azaltılır** (alt uç fazlası veya şişkin gövde varsa) — bas sızıntısı yüzünden asla artmaz.
- Sınırlar: gain 5–110, bass 25–75, middle 15–85, treble 25–80, presence 0–60.
- MASTER EQ: orta sapma 4 dB'yi aşarsa 630 Hz'de ±4 dB; alt uç fazlasında low-shelf kesimi; fizz'e göre
  high-shelf −3..+2. (GT-1'de ayrı EQ bloğu yok.)

## 3. Efektler (kurallar)
| Efekt | Kural |
|---|---|
| OD/DS | pedal kombinasyonu seçildiyse o pedal; driven lead → T-SCREAM (yüksek gain) veya MID BOOST; sıkı high-gain ritim (D>0.75) → T-SCREAM drive 10 |
| Noise gate | driven gruplarda açık, eşik D'ye göre 15–50 |
| Kompresör | clean gruplarda FX1 COMPRESSOR (hafif) |
| Delay | sadece ölçülürse: `detected` → her rol; `possible` → lead/clean/crunch (ağır ritimde değil). Süre = ölçülen ms, feedback ölçümden (10–45) |
| Reverb | ölçülen miktar (small/medium/large → room/plate/hall); bilinmiyorsa clean plate 1.8 s, lead room 1.2 s, ritim room 0.8 s (hafif) |
| Modülasyon | şu an ölçülmüyor → kapalı |
| BPM | şarkı temposu |
| İsim | şarkı adından ≤11 karakter + `RHY/LEAD/CLN/CRN` |

Şablon: seçilen modeli kullanan bir BOSS preset (rota/assign/seviye). FX1/FX2/pedal/OD kapatılıp yukarıdaki
kurallarla yeniden kurulur.

## 4. Çift tonlu patch (varsayılan, `--separate` ile kapatılır)
Şarkıda ≥2 ton grubu varsa tek patch üretilir (`build_dual`):
- **CTL kapalı** = ana ton (en uzun grup), **CTL açık (toggle)** = ikinci ton (clean varsa clean, yoksa lead).
- CTL1 kaynağı → ASSIGN 1..8 (`source=CTL1`, `mode=TOGGLE`, `target_min` = ana ton, `target_max` = ikinci ton).
  Öncelik: PREAMP TYPE, GAIN, OD/DS on/off, DELAY on/off, FX1 on/off (kompresör), MIDDLE, TREBLE, BASS,
  REVERB E.LEVEL, PRESENCE, LEVEL — sadece farklı olanlar, en fazla 8.
- Sadece ikinci tonun kullandığı bloklar (delay süresi, kompresör, OD ayarları) patch'e kopyalanır, aç/kapa ASSIGN'la.
- CTL1'in kendi işlevi OFF (sadece assign'ları sürer). NS eşiği atanamadığı için ≤22 tutulur.
- Hedef kodları BTS `CTLAssignTargetDefinitionGT.as`'tan `gt1_spec.json`'a (`assign_targets`) üretilir
  (ör. PREAMP: TYPE = 131, DELAY: ON/OFF = 263). Cihazda edit buffer üzerinden doğrulandı (2026-10-17).
- Üçüncü bir grup varsa ayrı patch olarak sonraki slota yazılır.

## Kalibrasyon sonuçları (2026-10-17, `tools/engine_table.py`)
| Şarkı / grup | Seçilen |
|---|---|
| Master of Puppets ritim | CORE METAL (orta −8.5 dB), T-SCREAM |
| Come As You Are nakarat | STACK CRUNCH + DISTORTION |
| Running Away | POWER DRIVE + T-SCREAM |
| Sweet Child ritim | MS1959 I (+240 ms hafif delay) |
| Back in Black ritim / lead | BG DRIVE / MS1959 I+II + MID BOOST |
| Run Like Hell delay riff | PRO CRUNCH + 389 ms delay |
| Temiz bölümler | NATURAL CLEAN / JC-120 + kompresör + plate |

İmza tablosu veya `REF` değişirse bu tabloyu yeniden üret ve testleri çalıştır.

## Tek nota düzeltmesi (`drive_flatness`, 2026-10-17)
Spektral düzlük akorlarda distorsiyonun intermodülasyonuyla dolar; tek notalı riff (fuzz riff, arpej) ne kadar
sürülürse sürülsün temiz bir harmonik çizgi spektrumu bırakır ve olduğundan **temiz** okunur. Ölçüm: Do I Wanna
Know periodicity 0.84, flatness 0.09 → DELUXE CRUNCH G70, kulakla "daha crunchy olmalı". Sürülen gruplarda
periodicity 0.6'nın üstündeki her birim için flatness `exp(1.75·Δ)` ile büyütülür (akor ağırlıklı parçalar ≤0.6,
değişmez; temiz gruplar hiç etkilenmez). Denenen ve reddedilen: eğim (tilt) arındırılmış düzlük — temiz gitarın
dik eğimi de distorsiyon ipucu, arındırınca temiz/sürülen ayrımı bozuluyor (Gitaroo clean 0.26 > rhythm 0.17).

## Ses seviyesi eşitleme (`kb.matched_preamp_level`, 2026-10-17)
Kullanıcı: "Running Away volume çok yüksek; clean de distortion da tüm tonlar aynı seviyede olsun". Eskiden
PREAMP LEVEL / PATCH LEVEL tipin 411 patch'teki medyanıydı (seviyelenmemiş, gain ve boost'a bakmıyordu →
POWER DRIVE G83 + T-SCREAM, L50). Şimdi: PATCH LEVEL her zaman 100; PREAMP LEVEL, BOSS'un **kendi seviyelediği**
fabrika preset'lerinden (hepsi PATCH LEVEL 100) öğrenilen modelden: `taban + tip ofseti + a·(gain−50) +
b·max(0, 45−gain) + OD açık/level/drive terimleri` (ridge, tip ofsetleri 0'a büzülür; hata ≈5 adım). Yüksek
gain ve boost seviyeyi düşürür, düşük gain'li temiz tonlar yükseltir. İki tonlu patch'te PREAMP: LEVEL assign'ı
GAIN'den hemen sonra gelir (her zaman 8 assign'a girer), böylece CTL ile iki ton da aynı seviyede kalır.
Sınır: açık döngü (cihaz çıkışı ölçülmüyor); BOSS preset'lerinin eşit seviyede olduğu varsayımına dayanır.
