# 14 — Pratik sistemi ("Antrenör")

Kullanıcı isteği (2026-10-22): her gün hızlanmak, teoriyi güçlendirmek, zor soloları daha kolay çalmak. Tab akar,
metronomu ayarlar, çaldığı her nota doğru/yanlış görünür; yüksek doğrulukta "sonraki tempoya/bölüme geçelim mi?"
diye sorulur. Kararlar (aynı gün): v1'de teknik + hız, günlük rutin + ilerleme, şarkıdan solo, teori + kulak;
ilerleme **sor, sonra geç**; metronom **GT-1 → amfi**; varsayılan **30 dk**.

Kod: `src/tonematch/practice/`, CLI `tonematch practice ...`, arayüz `desktop/src/app/practice/` ("Pratik", ⌘5).

## Akış
```
egzersiz (id) ──► Take: tık planı + NoteDetector + Scorer ──► @@PRACTICE olayları ──► arayüz (tab, renkler)
                     ▲ GT-1 duplex USB ses (tık çıkışı = MIX → amfi; giriş = zincir sonu)
sonuç ──► progress.record_take ──► merdiven kararı ("X BPM'e geçelim mi?") ──► practice set-bpm
```

## Modüller
| Dosya | Ne yapar |
|---|---|
| `theory.py` | notalar, gamlar/modlar, akorlar, aralıklar; `scale_position` gamın üstünden tel başına n nota yürüyerek pentatonik kutuları (2/tel) ve 3 nota/tel şekillerini üretir |
| `exercises.py` | id'den egzersiz (`aile/param/...`): kromatik + 23 permütasyon, tremolo, sekanslar (3'lü/4'lü), 3nps (penalı/legato), tril, pentatonik kutu 1–5 ve 6'lık iniş, sweep (3/5 tel, standart şekiller), 7'li arpejler, tel atlama, bölüm merdiveni, hız patlaması, solo cümlesi. Her egzersizde hoca notları (`tips`) ve odak cümlesi. İlerleme **skill** başına (id'nin tonsuz hali): tonu değiştirmek rekoru silmez |
| `listen.py` | gerçek zamanlı tek-nota tespiti: spektral akı başlangıcı (1024/256), uyarlamalı eşik, gürültü kapısı (en fazla −40 dBFS), YIN perde, legato = çalan nota içinde kararlı ≥0.6 yarım ses değişimi |
| `score.py` | her beklenen nota için hit / early / late / wrong / miss; eşleşmeyen nota extra (önceki notanın tekrarı = tel çınlaması, sayılmaz); oktav farkı doğru sayılır |
| `session.py` | `Take` (saat + dedektör + puan, G/Ç yok, testler ses besler); `Duplex` (GT-1 duplex akış, tık planı); `play`, `measure_latency`, `play_sound` |
| `progress.py` | `history.jsonl`, `quiz.jsonl`, `state.json` (skill başına çalışma temposu, rekor, ayarlar); merdiven; rutin; istatistik |
| `quiz.py` | klavye / aralık / derece / akor tonu / kulaktan tekrar; gitarda çalarak cevap; ağırlıklı tekrar (kaçan ve yavaş cevaplanan daha sık) |
| `solo.py` | lead stem → pYIN → notalar (legato, bend) → vuruş ızgarası (beat tracking, 16'lık/triplet'e yapıştırma) → el pozisyonu Viterbi'si (tel/perde) → cümleler |
| `cli.py` | `catalog`, `exercise`, `today`, `play`, `set-bpm`, `settings`, `stats`, `quiz`, `latency`, `solo`, `solos`, `reference` |

## Zamanlama
Tık ve gitar tek akışta (aynı örnek sayacı). Çıkış çerçevesi F'deki tıka çalınan nota giriş çerçevesi
F + gidiş-dönüş'te görünür; gidiş-dönüş akışın kendi raporundan (`outputBufferDacTime − inputBufferAdcTime`,
ön sayım sırasında ölçülür, sonra sabit). Üstüne oyuncunun kendi farkı: `practice latency` (80 BPM'de 16 tık,
medyan) → `settings.latency_ms`. Tüm zamanlar "take time": ilk notanın vuruşu, oyuncunun duyduğu an = 0.
Pencereler: vuruşta ±25 ms (nota aralığının ¼'ünden büyük olmamak üzere), eşleşme ±110 ms (aralığın yarısı).

## Hız merdiveni (`progress.decide`)
- Temiz tur: doğruluk ≥ eşik (varsayılan %95) ve notaların ≥%60'ı vuruşta.
- Üst üste 2 temiz tur → "+%4 (en az 2) BPM'e geçelim mi?" (arayüzde onay penceresi; evet = `set-bpm` + hemen başlar).
- %80 altı → bir basamak aşağı öner. Rekor = en yüksek temiz tempo. Kullanıcı başka tempo seçerse o tempo çalışma temposu olur.

## Günlük rutin (`progress.routine`)
Süre payları: ısınma %10, teknik %30, hız patlaması %15, gam/pozisyon %20, teori/kulak %10, solo %15.
6 günlük odak döngüsü (alternate picking, legato, arpej, alternate picking 2, pentatonik hız, ritim + sweep);
haftanın tonu beşliler çemberinde (`key_of_week`), pentatonik kutusu ve 3nps şekli günlere göre döner,
spider permütasyonu her gün başka. Solo bloğu, çıkarılmış solo varsa sıradaki cümleyi alır.

## Doğrulama
- Sentetik (Karplus-Strong + tanh distorsiyon): 16'lık 100–160 BPM, 6'lık 140 BPM, legato → tüm notalar
  bulundu, başlangıç hatası ±2 ms (sd), CPU ~25 ms / sn. Testler: `tests/test_practice.py`.
- Arayüz demo modunda uçtan uca denendi (rutin, oynatıcı, sonuç + merdiven, quiz, solo listesi, ilerleme).
- **Cihazda gerçek çalımla denenmedi.** 2026-10-22 gecesi Mac'te ses girişi açılırken akış bekledi: macOS
  mikrofon izni (TCC). Akış açılışı artık 6 sn'de anlaşılır bir hatayla vazgeçiyor; Tauri paketine
  `NSMicrophoneUsageDescription` eklendi (`desktop/src-tauri/Info.plist`). İzin verildikten sonra bakılacaklar:
  gerçek gitarda (özellikle high-gain) fazla nota oranı, gecikme testi değeri, tık amfiden duyuluyor mu
  (USB MIX LEVEL > 0), LOOP BACK kapalı mı.

## Sıradaki
- Gerçek çalımla eşikleri ayarlama (gürültü kapısı, akı eşiği, legato), gerekirse dedektör için temiz pratik
  tonu (edit buffer'a, slota değil).
- Akor/ritim egzersizleri (polifonik: kroma şablonu), bend hedefinin doğrulanması, solo transkripsiyonunu
  kulakla düzeltme (notaya tıklayıp perde/tel değiştirme).
