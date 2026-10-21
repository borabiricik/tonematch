# 01 — Donanım: BOSS GT-1 (doğrulanmış bilgiler)

Bu dosyadaki her şey **2026-10-17'de kullanıcının cihazında** doğrulandı (aksi belirtilmedikçe).

## Bağlantı
| Öğe | Değer |
|---|---|
| USB | `GT-1`, `USB\VID_0582&PID_01D6`, sürücü yüklü |
| MIDI portları (mido) | giriş `GT-1 0`, çıkış `GT-1 1` (isimde "GT-1" aranır) |
| Ses uç noktaları | `IN (GT-1)`, `OUT (GT-1)` — şu an kullanılmıyor |
| BOSS TONE STUDIO | `C:\Program Files (x86)\BOSS TONE STUDIO for GT-1\` (Adobe AIR) — **çalışırken MIDI portunu tutar, kapatılmalı** |
| BTS kullanıcı verisi | `%APPDATA%\BOSS-TONE-STUDIO-for-GT-1\Local Store\` (25 liveset `.tsl`, `liveset.db`) |

## Kullanıcının kurulumu
- GT-1 → amfinin **ön girişi**, amfi EQ'su sıfırda ("amfi sadece yükseltiyor"). Tüm ton patch içinde üretilir.
- `PREFERENCE: OUTPUT SELECT = SYSTEM`, sistem `OUTPUT SELECT = COMBO RETURN` → patch içindeki output select
  **yok sayılıyor**. (Not: ön girişe bağlıyken BOSS'un önerisi amfi tipine göre JC-120 / COMBO AMP / STACK AMP;
  RETURN seçenekleri effect-return girişi içindir. Kullanıcıya bildirildi; sistem ayarına program dokunmaz.)
- `PREFERENCE: PREAMP = PATCH` → yazdığımız preamp ayarları geçerli. SYSTEM olursa program uyarır.

## Kimlik / protokol (doğrulandı)
- Identity reply: `F0 7E 00 06 02 41 30 03 00 00 00 00 00 00 F7` → **device id 0x00**.
- Model id `00 00 00 30`. DT1/RQ1, Roland checksum. Ayrıntı: `06-gt1-protocol.md`.
- Edit buffer (temporary patch) `60 00 xx xx`, user patch i (0-tabanlı) `10 ii xx xx`.
- Patch = 24 blok. **Son blok (`.. 11 00`) cihazda 64 değil 26 byte** — okuma kısa yanıtı kabul eder.
- Patch okuma ~2.5 s, yaz+kaydet+doğrula ~3 s.
- Edit buffer'a **tek alan** yazılabilir (2026-10-22, Mac): tek byte DT1 blok ortasında da geçerli, okuma da öyle
  (3 alan yaz + geri oku 0.26 s, `GT1Client.write_fields`). İki istisna: 14-bit değerin (`_h`/`_l`) sadece `_l`
  byte'ından başlayan yazma **ve okuma yok sayılır** → çift tek mesajda `_h`'den yazılır; parametrenin aralığı
  dışındaki değer yazılmaz (ör. ON/OFF hedefli assign'ın max'ına 2).

## GT-1'de OLMAYAN bloklar (önemli)
BTS'in adres haritası GT-100/GT-001 ile ortak; bazı bloklar haritada var ama GT-1'de yok:
| Blok | Kanıt | Yerine |
|---|---|---|
| **EQ** (`60 00 01 30-3B`) | Cihaz tüm yazmaları yok sayıyor (tek byte dahil) ; 411 pro patch'in hiçbirinde açık değil | **MASTER EQ** (low / parametrik mid / high, patch sonu) veya FX tipi PEQ/GEQ |
| **COMP** | 0/411 patch'te açık | FX1 tipi `COMPRESSOR` (`fx1_adv_comp_*`) |
| **CHORUS** | 0/411 | FX2 tipi `CHORUS` (`fx2_chorus_*`, 73 pro patch böyle) |
| ACCEL FX | 0/411 | — |
| PREAMP B / DIVIDER DUAL | 411/411 `divider_mode = SINGLE` | yalnızca PREAMP A kullanılır |

## Patch seçimi
- MIDI Program Change **editör modu açıkken yok sayılıyor**.
- BTS yöntemi çalışıyor: setup `current_patch_no` (`00 01 00 00`) = `[n // 128, n % 128]` → cihaz o patch'e geçer
  ve edit buffer'a yükler (`GT1Client.select_patch`).

## Ses ile ilgili (reamp)
- BTS kodunda USB'den gelen sesi efekt zincirine sokan bir mod **yok** (USB sadece kayıt / monitor / loopback).
- Kullanıcıda reamp kutusu yok → sistem **open-loop** çalışır (cihazı ölçüm döngüsüne sokmaz). Bkz. `05-tone-matching.md`.

## Güvenlik kuralları (kodda uygulanıyor)
- Slot yazmadan önce o slot `backups/` altına `.tsl` olarak yedeklenir; yazma sonrası slot geri okunup doğrulanır.
- İlk kurulumda tüm 99 user patch yedeklendi: `backups/20261017-015136_all_U01-U99.tsl` (BTS ile içe aktarılabilir).
- SYSTEM alanına program yazmaz.
