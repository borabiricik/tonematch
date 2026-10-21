import * as React from "react";
import { Button, Dialog, EmptyState, IconButton, TextInput, ago, roleName, youtubeId } from "../ds";
import { Cover, RequestFacts } from "./parts";
import { ResultView } from "./ResultView";
import { useLibrary, type RunRequest } from "./state";

// Past results, kept on this computer (localStorage): reopen a result, calibrate it again, or run it again.

type Props = { slot: number; onRerun: (req: RunRequest) => void; onSaved: () => void };

export function LibraryView({ slot, onRerun, onSaved }: Props) {
  const [items, remove] = useLibrary();
  const [open, setOpen] = React.useState<string | null>(null);
  const [q, setQ] = React.useState("");
  const [del, setDel] = React.useState<string | null>(null);
  const entry = items.find((e) => e.id === open);

  if (entry) {
    return (
      <ResultView entry={entry} slot={slot} onSaved={onSaved}
        back={<div className="page__back"><Button variant="ghost" size="sm" icon="chevron-left" onClick={() => setOpen(null)}>Kütüphane</Button></div>}
        actions={<Button variant="primary" icon="refresh" onClick={() => onRerun(entry.request)}>Tekrar çıkar…</Button>} />
    );
  }

  const needle = q.trim().toLowerCase();
  const shown = items.filter((e) => !needle || e.result.title.toLowerCase().includes(needle)
    || e.result.patches.some((p) => p.name.toLowerCase().includes(needle) || (p.slot ?? "").toLowerCase() === needle));

  return (
    <section className="page library">
      <header className="page__head">
        <div>
          <h1 className="t-title">Kütüphane</h1>
          <p className="t-small page__sub">Çıkardığın tonlar bu bilgisayarda saklanır. Birini açıp çalarak karşılaştırabilir ya da ayarlarını değiştirip tekrar çıkarabilirsin.</p>
        </div>
        {items.length > 0 && (
          <TextInput icon="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Şarkı, patch ya da slot ara" aria-label="Kütüphanede ara" className="library__search" />
        )}
      </header>

      {items.length === 0 ? (
        <EmptyState icon="library" title="Henüz bir ton çıkarmadın">
          Ton çıkar sayfasında bir şarkı verdiğinde sonucu burada tekrar açabilirsin.
        </EmptyState>
      ) : shown.length === 0 ? (
        <EmptyState icon="search" title="Eşleşen ton yok">"{q}" için sonuç bulunamadı.</EmptyState>
      ) : (
        <ul className="lib-list">
          {shown.map((e) => {
            const r = e.result;
            return (
              <li key={e.id} className="lib-row">
                <button type="button" className="lib-row__main" onClick={() => setOpen(e.id)}>
                  <Cover id={youtubeId(r.track_id)} title={r.title} size="sm" />
                  <span className="lib-row__text">
                    <span className="lib-row__title">{r.title}</span>
                    <RequestFacts req={e.request} />
                  </span>
                  <span className="lib-row__patches">
                    {r.patches.map((p) => (
                      <span key={p.group} className="lib-patch">
                        <span className="t-readout lib-patch__slot">{p.slot?.startsWith("U") ? p.slot : p.slot ? "TEMP" : "—"}</span>
                        <span className="lib-patch__name">{p.name.trim()}</span>
                        <span className="t-small lib-patch__roles">{p.tones.map((t) => roleName(t.role)).join(" + ")}</span>
                      </span>
                    ))}
                  </span>
                  <span className="t-small lib-row__when">{ago(e.when)}</span>
                </button>
                <IconButton icon="x" label="Kütüphaneden kaldır" size="sm" onClick={() => setDel(e.id)} />
              </li>
            );
          })}
        </ul>
      )}

      <Dialog open={!!del} title="Kütüphaneden kaldırılsın mı?" confirmLabel="Kaldır" tone="danger"
        onCancel={() => setDel(null)} onConfirm={() => { if (del) remove(del); setDel(null); }}>
        <p>Sadece bu listeden kalkar. Cihazdaki patch, .tsl dosyası ve yedekler olduğu gibi kalır.</p>
      </Dialog>
    </section>
  );
}
