import * as React from "react";
import * as cli from "../cli";
import { Button, Chip, Icon, IconButton, Notice, PatchCard, mmss, toast, youtubeId, type RunResult } from "../ds";
import { CalibrateSheet, type CalTarget } from "./CalibrateSheet";
import { Cover, RequestFacts } from "./parts";
import type { LibraryEntry } from "./state";

/** What `calibrate` gets as the song: the cached YouTube id keeps it offline (a search would hit YouTube again). */
const calSource = (r: RunResult, source: string) => (r.track_id.startsWith("file_") ? source : `https://www.youtube.com/watch?v=${r.track_id}`);

type Props = { entry: LibraryEntry; slot: number; onSaved: () => void; actions?: React.ReactNode; back?: React.ReactNode };

/** A finished run: the song, how to tune, one card per patch (pedal chain + where it plays), the files. */
export function ResultView({ entry, slot, onSaved, actions, back }: Props) {
  const { result: r, request } = entry;
  const [cal, setCal] = React.useState<CalTarget | null>(null);
  const [calKey, setCalKey] = React.useState(0);
  const tu = r.tuning;
  const written = r.patches.filter((p) => p.slot?.startsWith("U")).map((p) => p.slot);
  const toFile = request.target === "file";
  const heading = written.length ? `${written.join(", ")} cihaza yazıldı ve doğrulandı`
    : request.target === "listen" ? "Edit buffer'a yüklendi, hiçbir slot değişmedi" : "Dosyaya yazıldı";

  return (
    <section className="page result">
      {back}
      <header className="song-head">
        <Cover id={youtubeId(r.track_id)} title={r.title} />
        <div className="song-head__text">
          <span className="song-head__eyebrow t-small">
            <Icon name={written.length ? "check" : toFile ? "file" : "ear"} /> {heading}
          </span>
          <h1 className="t-display song-head__title">{r.title}</h1>
          <ul className="facts t-small">
            <li><span className="t-readout">{Math.round(r.tempo)}</span> BPM</li>
            <li><span className="t-readout">{mmss(r.duration)}</span></li>
            <li>{r.patches.length} patch</li>
          </ul>
        </div>
        {actions && <div className="song-head__actions">{actions}</div>}
      </header>

      {tu && (
        <div className="tuning-strip" role="note">
          <span className="tuning-strip__icon"><Icon name="tuner" /></span>
          <div>
            <div className="tuning-strip__title">
              Şarkı <strong>{tu.name}</strong>{tu.evidence?.source === "default" ? " (akort belirtilmedi)" : ""}. Gitarını <strong className="t-readout">{tu.user_tuning}</strong> akortla.
            </div>
            <div className="t-small tuning-strip__sub">
              {tu.semitones
                ? <>Patch'te FX1 pitch shifter <strong>{tu.semitones > 0 ? "+" : "−"}{Math.abs(tu.semitones)}</strong> yarım ses: sen normal akortla çalarsın, çıkan ses şarkıdaki akortta olur.</>
                : "Pitch shifter yok."}
            </div>
          </div>
        </div>
      )}

      {r.claude?.ok && (
        <Notice tone="info" title={`Claude'un notu · ${r.claude.song || r.title}`}>{r.claude.rig_notes}</Notice>
      )}
      {r.claude && !r.claude.ok && (
        <Notice tone="warn" title="Claude modu çalışmadı, algoritmanın sonucu yazıldı">{r.claude.error}</Notice>
      )}

      <div className="result__patches">
        {r.patches.map((p) => (
          <PatchCard key={p.group} patch={p} duration={r.duration}
            onCalibrate={toFile || !p.slot ? undefined : (tone, ctl) => {
              setCal({ source: calSource(r, request.source), role: tone.role, ctl, patch: p.name.trim(),
                slot: p.slot?.startsWith("U") ? p.slot : null, amp: tone.amp, title: r.title,
                segments: tone.segments, duration: r.duration });
              setCalKey((k) => k + 1);
            }} />
        ))}
      </div>

      <section className="files" aria-label="Dosyalar">
        <FileRow icon="file" label="Patch dosyası (.tsl)" hint="BOSS TONE STUDIO'da içe aktarılabilir" path={r.tsl} />
        {r.backup && <FileRow icon="backup" label="Slotun önceki hali" hint="Geri yüklemek için BTS'te aç" path={r.backup} />}
      </section>

      <details className="result__request">
        <summary className="t-small">Bu sonuç hangi ayarlarla çıktı</summary>
        <RequestFacts req={request} />
      </details>

      <CalibrateSheet key={calKey} target={cal} fallbackSlot={slot} onClose={() => setCal(null)} onSaved={onSaved} />
    </section>
  );
}

function FileRow({ icon, label, hint, path }: { icon: "file" | "backup"; label: string; hint: string; path: string }) {
  return (
    <div className="file-row">
      <Icon name={icon} />
      <div className="file-row__text">
        <span className="file-row__label">{label} <Chip>{hint}</Chip></span>
        <span className="t-console file-row__path">{path}</span>
      </div>
      <IconButton icon="copy" label="Yolu kopyala" size="sm" onClick={() => { navigator.clipboard?.writeText(path); toast({ tone: "ok", title: "Yol kopyalandı" }); }} />
      {cli.IN_TAURI && !cli.DEMO && (
        <Button size="sm" icon="folder" onClick={() => cli.reveal(path).catch((e) => toast({ tone: "danger", title: "Açılamadı", text: String(e) }))}>
          Klasörde göster
        </Button>
      )}
    </div>
  );
}
