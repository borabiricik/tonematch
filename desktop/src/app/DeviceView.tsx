import * as React from "react";
import * as cli from "../cli";
import { Button, Chip, Card, EmptyState, Knob, Lcd, Led, Notice, SlotGrid, TextInput, ago, toast } from "../ds";
import { friendly, type Device } from "./state";

// The unit's 99 user slots (last known list, refreshed in the background), one slot's details,
// selecting a slot on the unit (`gt1 select`, also by double-clicking it), making it the next run's target, and a full backup.

type Props = {
  device: Device;
  busy: boolean;
  target: string;
  refresh: () => Promise<string | null>;
  select: (slot: string) => Promise<void>;
  onTarget: (slot: string) => void;
};

export function DeviceView({ device, busy, target, refresh, select, onTarget }: Props) {
  const [picked, setPicked] = React.useState<string | null>(device.current || null);
  const [filter, setFilter] = React.useState("");
  const [backup, setBackup] = React.useState<{ n: number; path?: string } | null>(null);
  const [selecting, setSelecting] = React.useState(false);

  React.useEffect(() => { if (!picked && device.current) setPicked(device.current); }, [device.current]);

  async function read() {
    const err = await refresh();
    if (err) { const f = friendly(err); toast({ tone: f.kind === "warn" ? "warn" : "danger", title: f.title, text: f.text }); }
  }

  async function backupAll() {
    let path = "";
    setBackup({ n: 0 });
    const r = await cli.run(["gt1", "backup"], (l) => {
      const m = /backup written:\s*(.+)$/.exec(l.text);
      if (m) path = m[1].trim();
      else if (/^\s+U\d\d\s/.test(l.text)) setBackup((b) => ({ n: (b?.n ?? 0) + 1 }));
    });
    setBackup(null);
    if (r.code === 0) toast({ tone: "ok", title: "99 slotun hepsi yedeklendi", text: path });
    else toast({ tone: "danger", title: "Yedek alınamadı", text: "Ayrıntı çıktıda." });
  }

  // selecting only loads the slot into the unit's edit buffer; nothing is written
  const canSelect = (s: string) => device.connected && !busy && !selecting && s !== device.current;
  async function selectOn(s: string) {
    if (!canSelect(s)) return;
    setPicked(s);
    setSelecting(true);
    await select(s);
    setSelecting(false);
  }

  const has = device.slots.length > 0;
  const slot = device.slots.find((s) => s.slot === picked);

  return (
    <section className="page device">
      <header className="page__head">
        <div>
          <h1 className="t-title">Cihaz</h1>
          <p className="t-small page__sub">
            {device.refreshing ? <><Led state="busy" /> Cihazdan okunuyor…</> : device.updated ? `Liste ${ago(device.updated * 1000)} okundu.` : "Liste henüz okunmadı."}
            {" "}Cihazda ya da BTS'te elle yaptığın değişiklikler Yenile ile gelir.
          </p>
        </div>
        <div className="page__actions">
          <Button icon="refresh" onClick={read} loading={device.refreshing} disabled={busy && !device.refreshing}>Yenile</Button>
          <Button icon="backup" onClick={backupAll} disabled={busy || !device.connected} loading={!!backup}>
            {backup ? `Yedekleniyor ${backup.n}/99` : "Tümünü yedekle"}
          </Button>
        </div>
      </header>

      <div className="device__summary">
        <DeviceCard device={device} />
        {device.preampFromSystem && (
          <Notice tone="warn" title="PREFERENCE: PREAMP = SYSTEM">
            Cihaz patch'lerin amfi ayarlarını yok sayıyor; yazdığımız ton duyulmaz. Cihazın SYSTEM menüsünden PATCH yap (program sistem ayarına dokunmaz).
          </Notice>
        )}
      </div>

      {backup && (
        <div className="backup-bar" role="progressbar" aria-valuemin={0} aria-valuemax={99} aria-valuenow={backup.n} aria-label="Yedekleme">
          <span style={{ width: `${(backup.n / 99) * 100}%` }} />
        </div>
      )}

      {!has && !device.refreshing ? (
        <EmptyState icon="device" title="Slot listesi henüz okunmadı"
          action={<Button variant="primary" icon="refresh" onClick={read}>Cihazdan oku</Button>}>
          GT-1 USB ile bağlıyken oku. Liste bir kez okununca sonraki açılışlarda anında görünür.
        </EmptyState>
      ) : (
        <div className="device__body">
          <div className="device__grid">
            <div className="device__tools">
              <TextInput icon="search" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Patch adı, amfi ya da U20" aria-label="Slotlarda ara" />
              <span className="device__legend t-small">
                <span><span className="legend-target" /> Hedef</span>
                <span><Led state="on" /> Cihazda seçili</span>
                <span>Çift tık: cihazda seç</span>
              </span>
            </div>
            <SlotGrid slots={has ? device.slots : null} target={target} current={device.current} selected={picked ?? undefined} filter={filter}
              onPick={setPicked} onActivate={selectOn} />
          </div>

          <aside className="inspector" aria-label="Seçili slot">
            {slot ? (
              <Card className="inspector__card">
                <div className="inspector__top">
                  <span className="t-readout-lg">{slot.slot}</span>
                  <span className="inspector__flags">
                    {slot.slot === device.current && <Chip led="on" tone="ok">Cihazda seçili</Chip>}
                    {slot.slot === target && <Chip tone="info">Hedef</Chip>}
                  </span>
                </div>
                <Lcd size="lg">{slot.name.trimEnd() || " "}</Lcd>
                <dl className="inspector__facts">
                  <div><dt className="t-param">PREAMP</dt><dd>{slot.amp}</dd></div>
                  <div><dt className="t-param">CTL</dt><dd>{slot.dual ? "İki ton (CTL ile geçiş)" : "Tek ton"}</dd></div>
                </dl>
                <Knob label="Gain" value={slot.gain} />
                <div className="inspector__actions">
                  <Button block icon="play" disabled={!device.connected || busy || slot.slot === device.current} loading={selecting}
                    onClick={() => selectOn(slot.slot)}>
                    {slot.slot === device.current ? "Cihazda zaten seçili" : "Cihazda seç ve dinle"}
                  </Button>
                  <Button block variant={slot.slot === target ? "secondary" : "primary"} icon="wave" disabled={slot.slot === target}
                    onClick={() => onTarget(slot.slot)}>
                    {slot.slot === target ? "Bu slot zaten hedef" : "Sonraki tonu buraya yaz"}
                  </Button>
                </div>
                <p className="t-small inspector__note">Seçmek hiçbir şey yazmaz. Yazmadan önce slot her zaman yedeklenir.</p>
              </Card>
            ) : (
              <EmptyState icon="grid" title="Bir slot seç">Ayrıntılarını görmek, cihazda seçmek ya da hedef yapmak için soldan bir slota tıkla.</EmptyState>
            )}
          </aside>
        </div>
      )}
    </section>
  );
}

function DeviceCard({ device }: { device: Device }) {
  return (
    <Card className="devcard">
      <div className="devcard__unit" aria-hidden="true">
        <span className="devcard__screen"><span className="t-readout">{device.connected ? device.current || "—" : "----"}</span></span>
        <span className="devcard__switches"><i /><i /><i /></span>
      </div>
      <div className="devcard__text">
        <span className="devcard__state"><Led state={device.state} /> <strong>{device.label}</strong></span>
        <span className="t-small devcard__sub">
          {device.connected ? <>Seçili patch <strong>{device.current}</strong> · edit buffer <strong>{device.editBuffer || "—"}</strong></>
            : device.refreshing ? "Bağlanılıyor…" : "USB kablosunu ve cihazın açık olduğunu kontrol et. BOSS TONE STUDIO açıksa kapat."}
        </span>
      </div>
      {cli.DEMO && <Chip led="warn" tone="warn">Demo verisi</Chip>}
    </Card>
  );
}
