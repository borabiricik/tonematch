# 07 — Yol Haritası / Durum

## Tamamlanan (2026-10-17)
- [x] Faz 0 — Planlama, dokümanlar
- [x] Faz 1 — GT-1 iletişimi: BTS'ten adres haritası + parametre tanımları + protokol çıkarıldı (`gt1_spec.json`),
      okuma/yazma/kaydet/seç/doğrula cihazda çalışıyor, 99 slot yedeği alındı
- [x] Faz 2 — İndirme (önbellek, bot-kontrol fallback'i), BS-Roformer-SW ayırma
- [x] Faz 3 — Rol ayrımı (rhythm/lead/clean/crunch), 5 referans şarkıyla kalibre
- [x] Faz 4 — Ton profili + deterministik ton motoru (LLM yok) + KB şablonları → GT-1 patch, `.tsl` export
- [x] `tonematch run <url> --slot Uxx` uçtan uca; 10 birim testi
- [x] Üretilen patch'ler cihazın edit buffer'ında birebir doğrulandı (slot yazma yolu U99 ile doğrulandı)

## Sıradaki işler (öncelik sırasıyla)
0. **Çalarak kalibrasyon** (kullanıcı kararı 2026-10-18): reamp'siz kapalı döngü. Kullanıcı riff'i/soloyu çalar,
   `IN (GT-1)` USB kaydı (BTS'e göre kayıt noktası zincirin sonunda) stem'le aynı ölçümlerle karşılaştırılır
   (drive, M/P/B, fizz, 1/3 oktav LTAS, seviye eşitlenmiş) → GAIN/MIDDLE/TREBLE/PRESENCE + MASTER EQ düzeltmesi
   edit buffer'a; 2–3 tur, sonra yedek + kaydet + doğrula. İki tonlu patch'te CTL kapalı/açık ayrı ayrı (assign
   min/max güncellenir). Model değişimi sadece öneri. LOOP BACK açıksa uyarı (SYSTEM'e yazılmaz). Farklar
   kaydedilir → tekrarlayan sapmalar `match.py`'ye geri beslenir. Sıra: CLI `calibrate` (önce sadece ölçüm/rapor,
   cihaz kaydını doğrula, `sounddevice`) → düzeltme döngüsü + testler → masaüstü "Kalibre et" butonu → öğrenme.
   - [x] Adım 1 (2026-10-19): `tonematch calibrate <url> --role R [--slot Uxx]` — `calibrate.py` (kayıt, ölçüm =
     `analysis.build_profile`, karşılaştırma + yön ipuçları), LOOP BACK / PREAMP=SYSTEM uyarısı, kayıt + sonuç
     `tracks/<id>/calib/` altında (patch özeti dahil, öğrenme için). Cihazda doğrulandı: `IN (GT-1)` WASAPI
     44.1 kHz stereo. Açık soru: ilk gerçek kayıtlarda stem (ayrılmış + master) ile direkt kayıt arasındaki
     sistematik farkı ölç (özellikle drive, bkz. `drive_index(for_gain)` notu); düzeltme katsayıları buna göre.
   - [x] Adım 3 (öne alındı, 2026-10-19): masaüstünde "Kalibre et" (geri sayım, canlı seviye, fark tablosu, tur
     tur spektral mesafe). Sadece ölçüm; otomatik düzeltme (adım 2) gelince aynı panele "Uygula" eklenecek.
1. **Kulak geri bildirimi döngüsü**: kullanıcı yorumlarına göre (ör. "fazla bas", "gain az") hızlı düzeltme
   komutu: `tonematch tweak U20 --gain +10 --bass -5`; tekrarlayan geri bildirimlerle imza tablosunu kalibre et.
2. **Eksik ölçümler** (kullanıcı onayı 2026-10-18):
   - MoP tipi şarkılarda temiz ara/solo ayrımını iyileştir (daha kısa pencereler, merkez özellikleri için ayrı küme).
   - Kabin/mikrofon karakteri: 4–8 kHz rezonans ve üst kesim noktasını ölç → MASTER EQ high-shelf'e daha ince yansıt.
3. Modülasyon tespiti (chorus/phaser/flanger: stereo dekorelasyon + spektral çentik hareketi) → FX2.
4. `--only` ve grup birleştirme/bölme için etkileşimli onay (isteğe bağlı; varsayılan otomatik kalsın).
5. Analiz raporu (HTML): grupların zaman çizelgesi, spektrum grafikleri, dinleme klipleri.

## Masaüstü arayüzü
- [x] Arayüz v2 "Signal Path" + tasarım sistemi v2 + demo modu + `gt1 select` (2026-10-21, `13-ui-ux.md`).
- Sıradaki arayüz işleri `13-ui-ux.md` sonunda (tweak geri bildirimi, kalibrasyonda "Uygula", yedekten geri yükleme).

## Faz 7 — Ar-Ge (donanım gerektirir)
- Reamp kutusu ile closed-loop optimizasyon (DI → GT-1 → USB kayıt → mesafe → Optuna), planı eski
  sürüm `05`'teydi: aşamalı arama (amp tipi → gain → ton → efektler), ~60–200 deneme.
- GT-1 surrogate modeli (toplanan ölçümlerle).
