import * as React from "react";
import * as cli from "../cli";
import { Button, Led, Notice, SlotGrid } from "../ds";
import type { Device } from "./App";
import { friendly } from "./store";

type Props = {
  device: Device;
  busy: boolean;
  target: string;
  refresh: () => Promise<string | null>;
  onPick: (slot: string) => void;
};

type Msg = { tone: "ok" | "warn" | "danger" | "busy"; title: string; text?: React.ReactNode } | null;

function ago(updated: number | null) {
  if (!updated) return "henüz okunmadı";
  const min = Math.round((Date.now() / 1000 - updated) / 60);
  return min < 1 ? "az önce okundu" : min < 60 ? `${min} dk önce okundu` : `${Math.round(min / 60)} sa önce okundu`;
}

export function DeviceView({ device, busy, target, refresh, onPick }: Props) {
  const [msg, setMsg] = React.useState<Msg>(null);

  async function read() {
    setMsg(null);
    const err = await refresh();
    if (err) { const f = friendly(err); setMsg({ tone: f.kind, title: f.title, text: f.text }); }
  }

  async function backup() {
    let path = "";
    setMsg({ tone: "busy", title: "Yedekleniyor", text: "99 slot tam olarak okunuyor, yaklaşık 2 dakika sürer…" });
    const r = await cli.run(["gt1", "backup"], (l) => { const m = /backup written:\s*(.+)$/.exec(l.text); if (m) path = m[1].trim(); });
    setMsg(r.code === 0
      ? { tone: "ok", title: "Tüm slotlar yedeklendi", text: <span className="tm-readout">{path}</span> }
      : { tone: "danger", title: "Yedek alınamadı", text: "Ayrıntı çıktıda." });
  }

  const has = device.slots.length > 0;
  return (
    <main className="view view-device">
      <div className="device">
        <div className="device__head">
          <div>
            <h1>Cihazdaki patch'ler</h1>
            <p className="device__sub">
              {device.refreshing ? <><Led state="busy" /> Cihazdan güncelleniyor…</> : `U01–U99 · ${ago(device.updated)}`}
              {has && ` · Bir slota tıklayınca hedef olur (şu an ${target}).`}
            </p>
          </div>
          <div className="device__tools">
            <Button onClick={read} disabled={busy || device.refreshing}>Yenile</Button>
            <Button onClick={backup} disabled={busy || !device.connected}>Tümünü yedekle</Button>
          </div>
        </div>
        {msg && <Notice tone={msg.tone} title={msg.title}>{msg.text}</Notice>}
        {has || device.refreshing
          ? <SlotGrid slots={has ? device.slots : null} target={target} current={device.current} onPick={onPick} />
          : <Notice title="Slot listesi henüz okunmadı">GT-1 bağlıyken Yenile'ye bas; liste bir kez okununca sonraki açılışlarda anında görünür.</Notice>}
      </div>
    </main>
  );
}
