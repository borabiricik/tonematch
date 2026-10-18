# 06 — GT-1 İletişim Protokolü (uygulanan ve doğrulanan)

Kaynak: BOSS TONE STUDIO for GT-1'in kendi dosyaları + decompile edilmiş AS3 kodu. Ayrıntılı kanıtlar
(dosya:satır) `06-gt1-protocol-extracted.md` içinde. Kod: `src/tonematch/device/gt1/`.

## Tek doğruluk kaynağı: `gt1_spec.json`
`src/tonematch/device/gt1/data/gt1_spec.json`, `tools/build_gt1_spec.py` ile **üretilir** (elle düzenlenmez):
| Girdi | Ne verir |
|---|---|
| `_assets/data/addressmap_gt.json` (BTS) | model id, bölgeler, komut adresleri, sistem adresleri |
| `TemporaryParams.as` (decompile) | 995 alan adı ↔ patch içi adres (`setData` alıcı yolu) |
| `ParameterDefinitionGT.as` (decompile) | 468 parametre için min/max/step, enum seçenek listeleri |
| BTS `SystemExclusive.as` | 24 yazma bloğu (adres, boyut) |

Yeniden üretmek için (BTS güncellenirse):
```powershell
winget install Microsoft.OpenJDK.21
# JPEXS FFDec indir (github.com/jindrapetrik/jpexs-decompiler/releases), sonra:
java -jar ffdec-cli.jar -export script <out> "C:\Program Files (x86)\BOSS TONE STUDIO for GT-1\BOSS_TONE_STUDIO_for_GT1.swf"
uv run python tools/build_gt1_spec.py <out>/scripts
```

## Mesajlar
```
DT1: F0 41 00 00 00 00 30 12 a1 a2 a3 a4 data… cs F7
RQ1: F0 41 00 00 00 00 30 11 a1 a2 a3 a4 s1 s2 s3 s4 cs F7
cs  = (128 - sum(adres + veri) % 128) % 128
```
- Mesajlar arası 30 ms (BTS ile aynı). Okumada 3 s timeout, 3 deneme.
- Adresler 7-bit: `.. 7F` sonrası bir üst byte artar.

## Oturum
| Adım | Mesaj |
|---|---|
| Bağlan | `F0 7E 7F 06 01 F7` → yanıtın [2]. byte'ı = device id (GT-1: 00) |
| Editör modu aç | DT1 `7F 00 00 01` = `01`, 100 ms bekle |
| Kapat | DT1 `7F 00 06 00` = `01` (USB direct monitor), DT1 `7F 00 00 01` = `00` |

## Patch işlemleri
| İşlem | Nasıl |
|---|---|
| Edit buffer oku/yaz | 24 blok, taban `60 00` |
| User slot oku | 24 blok, taban `10 <slot>` (slot 0-98 = U01-U99) |
| Edit buffer'ı slota kaydet | DT1 `7F 00 01 04` = `[slot//128, slot%128]` (BTS "WRITE"), ~0.5 s flash |
| Patch seç | DT1 `00 01 00 00` = `[n//128, n%128]` |
| Değer kodlaması | ham byte; ekran değeri = `ham*step + (min<0 ? min : 0)` (ör. EQ gain ham 20 = 0 dB, patch level ham 50 = 100) |
| 14-bit değerler | `<ad>_h`, `<ad>_l` byte çifti (delay time, BPM, pre-delay): `değer = h*128 + l` |

## Tuner (`tuner.py`, `gt1 tuner`)
Kaynak: BTS `Tuner.as`, `SystemExclusive.as:1210-1240`, `PlayMenuLogic.as:133`.
| İşlem | Nasıl |
|---|---|
| Aç / kapat | DT1 `running_mode` `7F 00 00 02` = `01` tek tel, `02` çoklu (polifonik), `00` çalma modu |
| Okuma | cihaz kendisi DT1 gönderir (editör modu açıkken; BTS sorgulamaz): tek tel `7F 00 05 00`, çoklu tel N `7F 00 02 2(N-1)` |
| Veri | `[nota, cent+50]`, nota 0..11 = C..B, `0C` = sinyal yok; BTS ±3 cent'te "akortlu", çoklu metrede ±5 merkeze yapışır |
| Cihazdan çıkış | oyuncu tuner'ı cihazda kapatırsa cihaz `running_mode = 00` gönderir → komut biter |
Referans pitch (`sys_tuner_pitch`, A=435+değer) ve tuner çıkışı (MUTE/BYPASS/THRU) SYSTEM ayarı → yazılmaz.
`[VERIFY ON DEVICE]` push'ların gerçekten geldiği ve çoklu tel numarasının (1 = ince E) yönü.

## `.tsl` dosyaları
BTS JSON formatı: `{"device":"GT-1","patchList":[{"params":{alan: ham değer}, "name", "note", ...}], "liveSetData":{...}}`.
`params` anahtarları spec alan adlarıyla aynıdır. Program hem yedekleri hem üretilen patch'leri bu formatta yazar
(`output/*.tsl`, `backups/*.tsl`) → BTS'te "Import" ile açılabilir.

## Cihazda gözlenen tuhaflıklar
- EQ bloğu adresleri yazılamıyor (GT-1'de blok yok) → MASTER EQ kullanılır; doğrulamada `eq_*` alanları atlanır.
- Son patch bloğu 26 byte döner.
- Slot kaydından hemen sonraki ilk okuma bazen zaman aşımına uğrar (flash yazımı) → yeniden deneme yeterli.
