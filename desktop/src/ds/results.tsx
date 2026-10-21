import * as React from "react";
import { Button, Segmented } from "./controls";
import { Chip } from "./feedback";
import { cx, driveName, roleName } from "./format";
import { Lcd, SignalChain, type PatchResult, type Tone } from "./gear";
import { Icon } from "./icons";
import { SongMap } from "./meters";

const CONF: Record<string, string> = { high: "emin", medium: "kısmen emin", low: "tahmin" };

export type PatchCardProps = {
  patch: PatchResult;
  duration: number;
  /** shows "Kalibre et" for the tone on screen (the patch must be on the unit or in the edit buffer) */
  onCalibrate?: (tone: Tone, ctl: "off" | "on" | undefined) => void;
  calibrateDisabled?: boolean;
};
/** One patch the engine built: slot, LCD name, the tone as a pedal chain, where it plays. Dual patches flip with CTL. */
export function PatchCard({ patch: p, duration, onCalibrate, calibrateDisabled }: PatchCardProps) {
  const [ctl, setCtl] = React.useState<"off" | "on">("off");
  const onDevice = !!p.slot?.startsWith("U");
  const [a, b] = p.tones;
  const tone = p.dual && ctl === "on" ? b : a;
  const other = p.dual ? (ctl === "on" ? a : b) : undefined;
  const id = React.useId();
  return (
    <article className="tm-patch">
      <header className="tm-patch__head">
        <span className={cx("tm-patch__slot t-readout-lg", !onDevice && "is-none")} title={onDevice ? "Yazıldığı slot" : undefined}>
          {onDevice ? p.slot : p.slot ? "TEMP" : "—"}
        </span>
        <div className="tm-patch__name">
          <Lcd>{p.name}</Lcd>
          <span className="t-small tm-patch__sub">
            {p.dual ? `${roleName(a.role)} + ${roleName(b.role)} · CTL ile geçiş` : `${roleName(a.role)} tonu`}
          </span>
        </div>
        <div className="tm-patch__state">
          {onDevice ? <Chip tone="ok" led="ok">Cihaza yazıldı</Chip>
            : p.slot ? <Chip tone="warn" led="warn">Edit buffer'da</Chip>
              : <Chip icon="file">Sadece dosya</Chip>}
        </div>
      </header>

      <div className="tm-patch__bar">
        {p.dual ? (
          <Segmented<"off" | "on"> name={`ctl-${id}`} value={ctl} onChange={setCtl} size="sm"
            options={[{ value: "off", label: `CTL kapalı · ${roleName(a.role)}` }, { value: "on", label: `CTL açık · ${roleName(b.role)}` }]} />
        ) : <span />}
        <div className="tm-patch__facts t-small">
          <span><Icon name="wave" /> {driveName(tone.drive)}</span>
          <span>{tone.stereo}</span>
        </div>
        {onCalibrate && (
          <Button size="sm" icon="ear" onClick={() => onCalibrate(tone, p.dual ? ctl : undefined)} disabled={calibrateDisabled}
            title="Bu tonu GT-1'den çal; USB kaydı şarkıdaki gitarla karşılaştırılır">
            Çalarak karşılaştır
          </Button>
        )}
      </div>

      <SignalChain tone={tone} compareTo={other} />

      {tone.claude && (
        <div className="tm-patch__claude">
          <Chip icon="sparkle" tone="info">Claude · {CONF[tone.claude.confidence]}</Chip>
          <p className="t-small">{tone.claude.why}</p>
        </div>
      )}

      <div className="tm-patch__map">
        <SongMap duration={duration}
          lanes={p.dual
            ? [{ label: roleName(a.role), segments: a.segments, tone: "song" }, { label: roleName(b.role), segments: b.segments, tone: "you" }]
            : [{ label: roleName(a.role), segments: a.segments, tone: "song" }]} />
        {p.dual && p.assigns.length > 0 && (
          <details className="tm-patch__assigns">
            <summary className="t-small">CTL ile değişen {p.assigns.length} ayar</summary>
            <ul className="t-small">{p.assigns.map((s) => <li key={s}>{s}</li>)}</ul>
          </details>
        )}
      </div>
    </article>
  );
}
