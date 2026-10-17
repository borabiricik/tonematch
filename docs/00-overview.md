# 00 — Genel Bakış

## Ne yapar
```powershell
.\tonematch.ps1 run "https://www.youtube.com/watch?v=..." --slot U20
```
1. Şarkıyı indirir (yt-dlp, 44.1 kHz stereo).
2. Gitarı ayırır (BS-Roformer-SW, 6 stem; GPU ~1.5 dk).
3. Gitar stem'ini baştan sona pencerelere böler, **ton gruplarını** bulur: `rhythm`, `lead`, `clean`, `crunch`
   (zaman aralıklarıyla).
4. Her grubun tonunu ölçer: distorsiyon (clean/driven), spektrum (oktav bantları), stereo, delay (süre),
   ambiyans, tempo.
5. **Ton motoru** (tamamen kod, dış servis yok): ölçülen ses imzasına en yakın GT-1 amfi modelini seçer,
   knob'ları o modelin profesyonel patch'lerdeki medyanından başlatıp ölçülen sapmalara göre kaydırır,
   boost/gate/kompresör/delay/reverb'i ölçüm ve kurallarla ekler.
6. Değerler cihaz aralıklarına ve güvenli sınırlara oturtulur → GT-1 patch'i.
7. Belirtilen slot(lar)ın yedeğini alır, patch'leri **ardışık slotlara** yazar (rhythm → U20, lead → U21 ...),
   geri okuyup doğrular, cihazı ilk yeni patch'e geçirir. Ayrıca `output/<şarkı>.tsl` yazar.

## Yöntem ilkeleri (kullanıcı kararı, 2026-10-17)
- **Sadece dinlediğine göre karar verir.** Kayıtta kullanılan ekipman bilinmez/aranmaz; LLM veya internet yok.
  Ekipmanı (GT-1 modeli, pedal, efekt) sistem kendisi ölçümden seçer.
- **Deterministik:** aynı şarkı → aynı patch; CLI'dan çalıştırmak yeterli.
- Reamp yok → cihaz ölçüm döngüsüne sokulmaz (open-loop).

| Bilgi | Kaynak | Güvenilirlik |
|---|---|---|
| Clean mi driven mı, distorsiyon miktarı | spektral düzlük | yüksek |
| Amfi modeli | ses imzası eşleştirme (drive, orta, presence, gövde, alt uç) | orta |
| Knob ayarları | model medyanı (pro patch'ler) + ölçülen sapma | orta |
| Delay süresi | koherent eko ölçümü (ms) | yüksek (tespit edilirse) |
| Seviye, NS, rota | profesyonel patch şablonları | yüksek |
| Bölümler (rhythm/lead/clean) | stereo konum, merkez perde, kümeleme | orta-yüksek |

## Kapsam dışı
- Birebir aynı ekipman (GT-1 kataloğundaki en yakın model kullanılır).
- Amfi ayarı (amfi sadece yükseltiyor).
- Çalım tekniği, gitar/manyetik farkı.

## Doküman haritası
| Dosya | İçerik |
|---|---|
| `01-hardware-gt1.md` | GT-1'de doğrulanmış bilgiler, kullanıcı kurulumu, olmayan bloklar |
| `02-architecture.md` | Modüller, veri akışı, dosyalar |
| `03-separation.md` | İndirme, stem ayırma, rol ayrımı |
| `04-tone-analysis.md` | Özellikler ve referans şarkılarla kalibrasyon |
| `05-tone-matching.md` | Ton motoru: model seçimi, knob ve efekt kuralları |
| `06-gt1-protocol.md` | SysEx protokolü, spec üretimi |
| `07-roadmap.md` | Durum ve sonraki işler |
| `08-risks.md` | Riskler / sınırlamalar |
| `09-setup.md` | Kurulum ve komutlar |
| `10-tuning.md` | Akort tespiti ve pitch shifter |
