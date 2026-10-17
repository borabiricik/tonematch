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
1. **Kulak geri bildirimi döngüsü**: kullanıcı yorumlarına göre (ör. "fazla bas", "gain az") hızlı düzeltme
   komutu: `tonematch tweak U20 --gain +10 --bass -5`; tekrarlayan geri bildirimlerle imza tablosunu kalibre et.
2. MoP tipi şarkılarda temiz ara/solo ayrımını iyileştir (daha kısa pencereler, merkez özellikleri için ayrı küme).
3. Modülasyon tespiti (chorus/phaser: stereo dekorelasyon + spektral çentik hareketi).
4. `--only` ve grup birleştirme/bölme için etkileşimli onay (isteğe bağlı; varsayılan otomatik kalsın).
5. Analiz raporu (HTML): grupların zaman çizelgesi, spektrum grafikleri, dinleme klipleri.

## Faz 7 — Ar-Ge (donanım gerektirir)
- Reamp kutusu ile closed-loop optimizasyon (DI → GT-1 → USB kayıt → mesafe → Optuna), planı eski
  sürüm `05`'teydi: aşamalı arama (amp tipi → gain → ton → efektler), ~60–200 deneme.
- GT-1 surrogate modeli (toplanan ölçümlerle).
