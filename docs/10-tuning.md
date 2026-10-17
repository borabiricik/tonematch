# 10 — Akort Tespiti ve Pitch Shifter

Kod: `src/tonematch/tuning.py`, entegrasyon `match.apply_pitch_shift`, önbellek `tracks/<id>/tuning.json`
(`pipeline.TUNING_VERSION`).

## Kullanım (2026-10-17 itibarıyla)
**Otomatik tespit kapalı (kullanıcı kararı).** Şarkının akordunu kullanıcı verir: `run ... --tuning <6 nota>`
(kalın telden inceye; `#`/`b`, boşluklu ya da bitişik: `D#G#C#F#A#D#`, `Eb Ab Db Gb Bb Eb`, `CGCFAD`).
Verilmezse **E standart**, pitch shifter yok. `tuning.parse_tuning` akordu EADGBE ya da DADGBE'nin tamamen
k yarım ses kaydırılmış hali olarak çözer (k = −9..+2); olmuyorsa (açık akortlar, `DGDGBD`) hata verir.
FINE her zaman 0. Aşağıdaki tespit yöntemi kodda duruyor, sadece `tools/tuning_evidence.py` kullanıyor.

## Kural (kullanıcı)
Kullanıcının gitarı her zaman **EADGBE** veya **DADGBE**. Şarkı bu iki akorttan birindeyse **pitch shifter
kullanılmaz**. Diğer akortlarda gitar GT-1'de FX1 PITCH SHIFTER ile şarkının akorduna kaydırılır.

| Şarkı akordu | Gitar | GT-1 |
|---|---|---|
| E standart / Drop D | EADGBE / DADGBE | shifter yok |
| Eb std / D std / C# std / C std / B std | EADGBE | −1 / −2 / −3 / −4 / −5 |
| Drop C# / Drop C / Drop B / Drop A# / Drop A | DADGBE | −1 / −2 / −3 / −4 / −5 |

## Yöntem
Özellikler (`extract_features`, gitar stem + bas stem + miks):
- 440 Hz'e göre sapma (cent): `librosa.estimate_tuning` (harmonik kısım).
- CQT (A1'den, yarım ses başına 3 bin, **merkezli**), harmonik 1–4'ün **geometrik ortalaması** = nota gücü.
  Geometrik ortalama, bas gitar sızıntısını (çıplak temel frekans) eler.
- Her karede **en pes nota** (frame max'ının ≥%45'i olan en alttaki tepe). Bas stem'inde o an güçlü ama gitarda
  zayıf olan notalar sayılmaz (sızıntı).
- Ton (Krumhansl profili, miks chroma'sı).

Skor (`score_tunings`) iki aşamalı:
1. **Aile** k (0, −1 … −5): üst 4 telin (A D G B + k) nota gücü (2. tel ağırlıklı), aile kalın telinin
   (std 40+k veya drop 38+k) en pes nota olarak görülme oranı, tonalitenin gitar-dostu olması, kalın telin 1–3
   yarım ses altında kalın teli **baskın** geçen notalar (daha alçak aile işareti) cezası, yaygınlık önseli.
2. **Standart / drop**: sadece kalın tel kanıtı (38+k ve 39+k vs 40+k); kanıt yoksa standart.
   Aile içinde 2–6. teller aynı olduğundan kalın tel hiç çalınmıyorsa bu seçim nota olarak fark yaratmaz.

Güvenlik: kayıt yarım sesler arasındaysa (|sapma| ≥ 40 cent) veya en iyi iki aile arasındaki fark çok küçükse
(güven < 0.2) kaydırma **uygulanmaz**; E standart (D2 baskınsa Drop D) varsayılır, CLI uyarır (`uncertain`).

## Pitch shifter ayarı (`apply_pitch_shift`)
GT-1 arayüzünde PITCH, FINE, EFFECT LEVEL, DIRECT LEVEL, PRE DELAY, FEEDBACK var (voice/mode gizli, BOSS'un
tune-down preset'i "METAL DELAY" ile aynı: 1 voice, MEDIUM). Kurulum: FX1 (amfiden önce) = PITCHSHIFTER,
PITCH = yarım ses, FINE = kaydın sapması (±40 ile sınırlı, sadece kaydırma varken), EFFECT 100, DIRECT 0,
PRE DELAY 0, FEEDBACK 0. Kaydırma varken temiz tonun kompresörü FX2'ye taşınır; iki tonlu patch'te shifter
her iki tonda açık kalır (FX1 için assign yok, FX2 aç/kapa assign'la).

## Kalibrasyon (2026-10-17, `tools/tuning_evidence.py`)
Akordu bilinen 10 kayıt, **10/10** (Smoke on the Water güvenlik kuralıyla: kayıt −48 cent, belirsiz → E std):
Master of Puppets, Nothing Else Matters, Back in Black, Enter Sandman, Smoke on the Water (E std);
Pride and Joy, Sweet Child O' Mine (Eb std); Killing in the Name (Drop D); Chop Suey (Drop C); Duality (Drop B).
Doğrusu bilinmeyenler: Come As You Are → Drop D, Run Like Hell → Drop D, Running Away → D standard,
Gitaroo → E std.

Sınırlar: test seti küçük; kalın teli hiç kullanılmayan ve tonalitesi belirsiz kayıtlar, çok yoğun miksler ve
yarım ses arası kayıtlar zayıf noktalar. Yeni şarkı eklemek: `tools/fetch.py` ile indir, `TRUTH`'a ekle,
`tools/tuning_evidence.py --extract`.
