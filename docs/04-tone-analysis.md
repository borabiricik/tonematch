# 04 — Ton Analizi (GroupProfile)

Her grup için `analysis.GroupProfile` (önbellek: `tracks/<id>/analysis.json`).

| Alan | Yöntem | Not |
|---|---|---|
| `gain` 0..1 | log(0.8–5 kHz spektral düzlük) ağırlıklı sigmoid, sustain/crest küçük katkı | clean/driven ayrımı güvenilir |
| `gain_class` | clean (<0.42) / crunch (düzlük < 0.22) / high_gain | crunch↔high-gain **kaba ipucu** |
| `flatness` | medyan spektral düzlük | |
| `bands_db` | Welch PSD, L/R güç ortalaması, oktav bantları 80 Hz–10 kHz, 320 Hz–2.5 kHz ortalamasına göre | 10 kHz güvenilmez |
| `tilt_db_per_oct` | 160 Hz–5 kHz eğim | |
| `stereo` | genişlik + korelasyon → mono/centre, stereo, wide/double-tracked | |
| `periodicity`, `f0_median` | normalize otokorelasyon tepe değeri | monofonik/lead ipucu |
| `delay` | aşağıda | |
| `reverb` | aşağıda | çoğu stemde "unknown" |

## Kalibrasyon verisi (5 referans şarkı)
Spektral düzlük (0.8–5 kHz, pencere medyanı):
- Temiz: 0.002–0.04 (NEM intro, MoP ara 3:35–3:51, Run Like Hell, CAYA verse)
- Driven: 0.07–0.45 (Back in Black ~0.2, MoP 0.3–0.44, NEM nakarat 0.06–0.5)
- Grup medyanlarında: crunch kayıtlar 0.13–0.21 (AC/DC, GnR, NEM, Gitaroo, RLH), high-gain/fuzz 0.29–0.37
  (MoP, Running Away, CAYA) → `match.drive_index` bu aralığa göre ölçeklenir.

Dinleme tanımlayıcıları (`descriptors`): low_depth, mid_scoop, presence, fizz, body (dB) ve 1/3 oktav
spektrum (`third_oct_db`); motorun referansları `match.REF`. Eski oktav medyanları:
- distorted: `80:+3 160:+7 320:+5 640:+2 1.28k:-4 2.56k:-3 5.12k:-12`
- clean: `80:+3 160:+12 320:+8 640:+3 1.28k:-5 2.56k:-6 5.12k:-18`

## Delay tespiti
Koherent eko → dalga formu otokorelasyonunda **izole, keskin** tepe; insanın tekrar çalması koherent değildir.
- 300–3000 Hz bant, spektral beyazlatma, L, R ve L+R (ping-pong için) otokorelasyonu, 8 s'lik parçaların ortalaması.
- Tepe yüksekliği (yerel medyana göre) ve izolasyon (±30 ms komşulara göre oranı).
- `detected`: izolasyon > 1.8 ve yükseklik > 0.012; `possible`: > 1.5 ve > 0.006.
- Kalibrasyon: Run Like Hell 388.7 ms (gerçek, Gilmour ~380 ms) yükseklik 0.009–0.016; kuru şarkılarda ayırma
  artefaktları (86/223 ms) ≤ 0.003. CAYA nakaratta 0.009'luk şüpheli tepe → bu yüzden "possible" kademesi var;
  motor bunu sadece daha az distorsiyonlu bölümlerde (lead/clean/crunch) kullanır.
- Feedback: 2τ'daki tepe / τ'daki tepe. Tempo bölümü (1/4, dotted 1/8 ...) bilgi amaçlı.

## Reverb / ambiyans
Nota bırakma olayları: 50 ms'de ≥10 dB düşüş **ve** sonraki 300 ms'de yeni nota yok (≤3 dB yükselme).
Bırakmadan 80–250 ms sonraki enerji (dB, nota seviyesine göre) → dry/small/medium/large. Yoğun çalımda yeterli
olay yoksa `unknown` (çoğu rock stem'i) → motor hafif varsayılan kullanır.

## Bilinen zayıflıklar
- Modülasyon (chorus/phaser) ölçülmüyor → patch'lerde kapalı.
- Lead, rhythm ile aynı konumdaysa (mono kayıt) ayrılamayabilir.
- Mastering ve ayırma tizi azaltır, bas sızıntısı alçakları şişirir → düzeltmeler yarı oranda, bas artışı sınırlı.
