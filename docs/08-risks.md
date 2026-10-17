# 08 — Riskler ve Sınırlamalar

| Risk | Durum / azaltma |
|---|---|
| Slotlardaki patch'lerin kaybı | Her yazmadan önce slot yedeği (`backups/`), yazma sonrası geri okuma doğrulaması; ilk tam yedek alındı |
| YouTube bot kontrolü | Önbellek + tarayıcı çerezi ile yeniden deneme + `TONEMATCH_COOKIES`; yerel dosya da kabul edilir |
| Model seçimi ses imzasından yanılabilir | İmza tablosu + kalibrasyon şarkıları (`tools/engine_table.py`); kulak geri bildirimiyle ayar |
| Stem kalitesi (yoğun miks) | Sadece en temiz/yüksek pencereler; düzeltmeler yarı oranda |
| crunch ↔ high-gain sınırı | Düzlük 0.13–0.21 crunch, 0.29–0.37 high-gain; arada kalanlar belirsiz |
| Rhythm+lead aynı anda, aynı konumda | Ayrılamayabilir → tek grup çıkar |
| BTS açıkken MIDI portu meşgul | Açık hata mesajı: "BTS'i kapat" |
| Output select / amfi ön giriş | Sistem COMBO RETURN'de; ön giriş için BOSS'un önerisi amp tipi seçenekleri — kullanıcıya bırakıldı |
| Ses seviyesi sıçramaları | Seviyeler pro patch medyanlarından; ilk denemede amfiyi kısık başlat |

## Yasal not
YouTube içeriği yalnızca kişisel ton analizi için işlenir; ses/stem dosyaları `%LOCALAPPDATA%\tonematch\data`
altında kalır, repoya/paylaşıma girmez. BTS dosyaları (adres haritası, pro patch'ler) kullanıcının kendi
kurulumundan okunur; `gt1_spec.json` bunlardan türetilmiş, kişisel kullanım içindir.
