# 03 — İndirme, Ayırma ve Rol Ayrımı

## İndirme (`ingest.py`)
- `yt-dlp` en iyi ses → `ffmpeg` → 44.1 kHz, stereo, float32 WAV. Metadata (`title`, `artist`, `album`, yıl,
  açıklama) `meta.json`'a (sadece patch adı için kullanılır).
- Girdi: YouTube URL, `ytsearch1:sanatçı şarkı` ya da yerel ses dosyası.
- Önbellek: URL'deki video ID işlenmişse ağa hiç çıkılmaz.
- YouTube "bot olmadığını doğrula" derse otomatik olarak Firefox/Chrome/Edge/Brave çerezleriyle tekrar dener;
  olmazsa `TONEMATCH_COOKIES=<cookies.txt>` ortam değişkeni. (Kısa sürede çok indirme bu kontrolü tetikler.)

## Ayırma (`separate.py`)
- `audio-separator` + **BS-Roformer-SW** (6 stem: guitar, bass, drums, vocals, piano, other). Yedek: `htdemucs_6s`.
- RTX 3070 Ti'de 4 dk şarkı ≈ 90 s (ilk kullanımda model indirme +2-3 dk). Stem'ler önbelleklenir.
- Bilinen artefaktlar: otokorelasyonda ~86 ms ve ~223 ms'de küçük tepeler (delay dedektörü bunları eşikle eler);
  alçak bantlarda bas sızıntısı (EQ kurallarında dikkate alınır); 10 kHz üstü güvenilmez.

## Rol ayrımı (`analysis.py`)
1. Beat tracking → ~2.6 s'lik, vuruşa hizalı pencereler.
2. Pencere özellikleri: seviye, L/R genişlik ve korelasyon, pan, 0.8–5 kHz spektral düzlük (distorsiyon),
   sustain, crest, merkez-kanal enerji oranı / periyodiklik / f0 (STFT tabanlı merkez çıkarımı, 30 s parçalar).
3. Aktif pencereler: gitar kendi yüksek seviyesine yakın ve mikste gömülü değil.
4. GMM (diag, k=1..4, BIC) + 3 pencerelik median filtre. Küçük kümeler (<%8) en yakına katılır; **ancak**
   gain'i diğerlerinden çok farklıysa (ör. ağır şarkı içindeki kısa temiz ara) korunur.
5. Etiketleme:
   - `clean`: medyan gain < 0.42 (tüm temiz kümeler birleşir)
   - `lead`: merkezde (rhythm geniş), merkez f0 > 220 Hz, merkez periyodiklik > 0.6, skor farkı > 0.2
   - `rhythm`: en uzun distorted küme; çok daha düşük gain'li distorted küme → `crunch`
6. Grup ≥ 6 s ise profil çıkarılır. Lead, rhythm geniş ise merkez-çıkarılmış sinyalden analiz edilir.

### Referans şarkılarda sonuç (2026-10-17)
| Şarkı | Bulunan | Doğru mu |
|---|---|---|
| AC/DC – Back in Black | rhythm (0:06–1:48, 2:31–3:28), lead (1:48–2:31, 3:28–4:01) | ✅ iki solo da |
| Metallica – Nothing Else Matters | clean (arpejler), rhythm (distorted nakaratlar) | ✅ (solo ayrı bulunmadı) |
| Metallica – Master of Puppets | rhythm | ⚠️ temiz ara ve sololar ayrılmadı |
| Pink Floyd – Run Like Hell | rhythm + crunch (delay riff, 389 ms) | ✅ |
| Nirvana – Come As You Are | clean (chorus'lu riff) + rhythm (nakarat) | ✅ |
