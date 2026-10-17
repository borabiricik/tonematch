# 12 — Claude Modu (isteğe bağlı)

Kod: `src/tonematch/claude_mode.py`, bağlantı `match.match_groups(claude=True)`. Varsayılan **kapalı**.

```powershell
.\tonematch.ps1 run "<url>" --slot U20 --claude     # Claude modu
.\tonematch.ps1 run "<url>" --slot U20              # sadece algoritma (varsayılan)
```
Arayüzde: "Analiz" → Algoritma / Claude modu (seçim hatırlanır).

## Akış
1. Motor her grup için patch'ini kurar (algoritma modundakiyle birebir aynı).
2. Claude'a gider: şarkı kimliği (başlık, kanal), tempo, kullanıcının verdiği akort, her grubun ölçümleri
   (gain sınıfı, drive, sapma dB'leri, bant spektrumu, delay/reverb ölçümü, bölümler) ve motorun önerisi.
   Kullanıcının kulak geri bildirimleri (crunch hep yumuşak kaldı, clean steril olmasın) ve cihaz kuralları
   prompt'ta.
3. Claude yapılandırılmış JSON döner (şema `claude_mode.schema`): şarkı + kayıtta kullanılan ekipman notu, ve her
   grup için preamp tipi/knob'ları/kabin, OD/DS, delay, reverb, FX2 modülasyon, MASTER EQ, güven, gerekçe.
4. `apply_recipe` tarifi motor patch'inin üstüne uygular. **Korunanlar:** FX1 pitch shifter (akort), temiz
   tonun kompresörü (FX2'de ise modülasyon atlanır), NS, CTL/assign kurulumu, ölçülen delay (ölçülen sürede
   kalır), seviye eşitleme (`matched_preamp_level` Claude'un amfi/gain/boost seçimine göre yeniden), patch
   level 100. Sınırlar: gain ≤100, MASTER EQ ±6 dB, alçak bant en fazla +2 dB (bas sızıntısı).
5. İki tonlu şarkıda CTL patch'i Claude'un düzelttiği iki tondan kurulur.
6. Herhangi bir hata (bağlantı, ret, zaman aşımı, bozuk cevap) → motorun patch'leri, CLI/arayüz uyarır.

## Arka uçlar (`claude_mode.backend`)
- **API:** `ANTHROPIC_API_KEY` veya `ANTHROPIC_AUTH_TOKEN` varsa. `client.beta.messages.create`, model
  `claude-opus-5-5`, effort high, `output_config.format` JSON şeması, `fallbacks: "default"`
  (`server-side-fallback-2026-07-01`), ret kontrolü.
- **claude CLI:** aksi halde (Claude Code girişi). `claude -p --output-format json --json-schema … --tools ""
  --no-session-persistence --effort high`, nötr geçici klasörde (proje CLAUDE.md'si okunmaz). Sonuç
  `structured_output`.
- Zorlamak için `TONEMATCH_CLAUDE_BACKEND=api|cli`; model `TONEMATCH_CLAUDE_MODEL`.
- Araç yok, web araması yok: Claude kayıt hakkında bildiğinden cevaplar, emin değilse `confidence: low` ve
  motorun önerisine yakın kalır.

## Çıktı
`report.json` / `--json`: `claude` (ok, model, backend, song, rig_notes, error) ve her tonda
`claude: {confidence, why}`. CLI ekipman notunu basar; arayüz sonuçta Notice + tonun altında gerekçe gösterir.

İlk deneme (2026-10-17, Sweet Child, cihazsız): ~28 sn. Claude JCM800 → MS1959 I+II + hafif T-SCREAM,
temiz partiler için düşük gain MS1959 I önerdi.
