import * as React from "react";
import * as cli from "../../cli";
import { Button, Card, Chip, EmptyState, Icon, Notice, Segmented, Select, Skeleton, Sparkline, TextInput, cx, toast } from "../../ds";
import { friendly, useStored } from "../state";
import { PlayerSheet } from "./PlayerSheet";
import { LatencySheet, QuizSheet } from "./QuizSheet";
import { QUIZ_HINTS, QUIZ_NAMES, type Exercise, type QuizKind, type Routine, type Solo, type Stats } from "./types";

// The practice system (`tonematch practice ...`): today's routine, the exercise menu, theory / ear drills,
// solos from songs, progress. Everything is computed by the CLI (routine, ladder, scoring); this page lists it
// and opens the stage sheets (PlayerSheet, QuizSheet).

type Tab = "today" | "exercises" | "theory" | "solo" | "progress";
const TABS: { value: Tab; label: string }[] = [
  { value: "today", label: "Bugün" }, { value: "exercises", label: "Egzersizler" }, { value: "theory", label: "Teori ve kulak" },
  { value: "solo", label: "Solo" }, { value: "progress", label: "İlerleme" },
];
const MINUTES = [{ value: "15", label: "15 dk" }, { value: "30", label: "30 dk" }, { value: "45", label: "45 dk" }, { value: "60", label: "60 dk" }];
const KEYS = ["C", "G", "D", "A", "E", "B", "F#", "Db", "Ab", "Eb", "Bb", "F"];
const BLOCK_ICON = { warmup: "sun", technique: "sparkle", burst: "clock", scales: "grid", theory: "ear", solo: "wave" } as const;

type Open = { id: string; next: { id: string; title: string } | null } | null;

export function PracticeView({ active }: { active: boolean }) {
  const [tab, setTab] = useStored<Tab>("practice-tab", "today");
  const [today, setToday] = React.useState<Routine | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [open, setOpen] = React.useState<Open>(null);
  const [quiz, setQuiz] = React.useState<QuizKind | null>(null);
  const [latency, setLatency] = React.useState(false);

  const loadToday = React.useCallback(async (minutes?: string) => {
    if (minutes) await cli.run(["practice", "settings", "--minutes", minutes, "--json"]);
    const r = await cli.run<Routine>(["practice", "today", "--json"]);
    if (r.result) { setToday(r.result); setError(null); } else setError(friendly(r.error?.message ?? "").text);
  }, []);
  React.useEffect(() => { if (active && !today) loadToday(); }, [active]);

  // the routine as one list: "next exercise" after each one
  const flat = today ? today.blocks.flatMap((b) => b.exercises.map((e) => ({ id: e.id, title: e.title }))) : [];
  const openEx = (id: string) => {
    const i = flat.findIndex((e) => e.id === id);
    setOpen({ id, next: i >= 0 && i + 1 < flat.length ? flat[i + 1] : null });
  };

  return (
    <section className="page practice">
      <header className="page__head">
        <div>
          <h1 className="t-title">Pratik</h1>
          <p className="t-small page__sub">Metronom GT-1'den amfiye çalar, çaldığın her nota dinlenir: doğru, erken, geç ya da yanlış. Temiz turlardan sonra tempo artar.</p>
        </div>
        <div className="page__actions">
          <Segmented<Tab> name="practice-tab" value={tab} onChange={setTab} options={TABS} />
        </div>
      </header>

      {error && <Notice tone="danger" title="Pratik verisi okunamadı">{error}</Notice>}
      {tab === "today" && <TodayTab today={today} reload={loadToday} onPlay={openEx} onQuiz={setQuiz} onLatency={() => setLatency(true)} />}
      {tab === "exercises" && <ExercisesTab active={active} onPlay={(id) => setOpen({ id, next: null })} />}
      {tab === "theory" && <TheoryTab onQuiz={setQuiz} onLatency={() => setLatency(true)} />}
      {tab === "solo" && <SoloTab onPlay={(id, next) => setOpen({ id, next })} />}
      {tab === "progress" && <ProgressTab active={active && tab === "progress"} />}

      <PlayerSheet id={open?.id ?? null} onClose={() => { setOpen(null); loadToday(); }}
        next={open?.next ? { title: open.next.title, go: () => openEx(open.next!.id) } : null} />
      <QuizSheet kind={quiz} onClose={() => setQuiz(null)} onDone={() => loadToday()} />
      <LatencySheet open={latency} onClose={() => setLatency(false)}
        onSaved={(ms) => { toast({ tone: "ok", title: "Gecikme kaydedildi", text: `${ms.toFixed(0)} ms: zamanlama artık buna göre ölçülüyor.` }); loadToday(); }} />
    </section>
  );
}

// ------------------------------------------------------------------------------------------------ today
function TodayTab({ today, reload, onPlay, onQuiz, onLatency }: {
  today: Routine | null; reload: (minutes?: string) => void; onPlay: (id: string) => void; onQuiz: (k: QuizKind) => void; onLatency: () => void;
}) {
  if (!today) return <div className="prac-list"><Skeleton h={90} /><Skeleton h={90} /><Skeleton h={90} /></div>;
  const done = new Set(today.done_ids);
  const all = today.blocks.flatMap((b) => b.exercises);
  const nextUp = all.find((e) => !done.has(e.id));
  const total = all.length + today.blocks.filter((b) => b.quiz).length;
  const finished = all.filter((e) => done.has(e.id)).length + today.blocks.filter((b) => b.quiz && done.has(`quiz:${b.quiz}`)).length;
  return (
    <div className="today">
      <Card className="today__head">
        <div className="today__summary">
          <div>
            <span className="t-label">{new Date(today.date).toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long" })}</span>
            <p className="t-title">Bugünün odağı: {today.focus} · ton {today.key}</p>
            <p className="t-small today__muted">{finished}/{total} bölüm · seri {today.streak} gün{today.settings.latency_ms ? ` · gecikme ${today.settings.latency_ms.toFixed(0)} ms` : ""}</p>
          </div>
          <div className="today__actions">
            <Segmented name="minutes" label="Süre" value={String(today.minutes)} onChange={(m) => reload(m)} options={MINUTES} size="sm" />
            {nextUp ? <Button variant="primary" size="lg" icon="play" onClick={() => onPlay(nextUp.id)}>{finished ? "Devam et" : "Rutini başlat"}</Button>
              : <Chip tone="ok" icon="check">Bugünkü rutin tamam</Chip>}
          </div>
        </div>
        <div className="today__bar" aria-hidden="true">{today.blocks.map((b) => <span key={b.id} style={{ flexGrow: b.minutes }} className={`is-${b.id}`} />)}</div>
        {!today.settings.latency_ms && (
          <p className="t-small today__muted"><Icon name="info" /> İlk kez mi? Önce <button type="button" className="linkish" onClick={onLatency}>gecikme testini</button> yap: zamanlama senin kulağına göre ölçülsün.</p>
        )}
      </Card>

      <ol className="plan">
        {today.blocks.map((b) => (
          <li key={b.id} className="plan__block">
            <div className="plan__rail"><span className="plan__icon"><Icon name={BLOCK_ICON[b.id]} /></span></div>
            <div className="plan__body">
              <div className="plan__head">
                <h3 className="t-heading">{b.title}</h3>
                <span className="t-readout plan__min">{b.minutes} dk</span>
              </div>
              <p className="t-small plan__why">{b.why}</p>
              <ul className="plan__items">
                {b.exercises.map((e) => (
                  <li key={e.id} className={cx("plan__item", done.has(e.id) && "is-done")}>
                    <span className="plan__check">{done.has(e.id) ? <Icon name="check" /> : null}</span>
                    <span className="plan__title"><span className="t-body-strong">{e.title}</span><span className="t-small plan__sub">{e.subtitle}</span></span>
                    <span className="t-readout plan__bpm">{e.bpm} BPM{e.best ? <span className="plan__best"> · rekor {e.best}</span> : null}</span>
                    <Button size="sm" icon="play" onClick={() => onPlay(e.id)}>Çal</Button>
                  </li>
                ))}
                {b.quiz && (
                  <li className={cx("plan__item", done.has(`quiz:${b.quiz}`) && "is-done")}>
                    <span className="plan__check">{done.has(`quiz:${b.quiz}`) ? <Icon name="check" /> : null}</span>
                    <span className="plan__title"><span className="t-body-strong">{QUIZ_NAMES[b.quiz]}</span><span className="t-small plan__sub">{QUIZ_HINTS[b.quiz]}</span></span>
                    <span />
                    <Button size="sm" icon="ear" onClick={() => onQuiz(b.quiz!)}>Başla</Button>
                  </li>
                )}
              </ul>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

// -------------------------------------------------------------------------------------------- exercises
function ExercisesTab({ active, onPlay }: { active: boolean; onPlay: (id: string) => void }) {
  const [key, setKey] = useStored<string>("practice-key", "");
  const [list, setList] = React.useState<{ key: string; exercises: Exercise[] } | null>(null);
  React.useEffect(() => {
    if (!active) return;
    cli.run<{ key: string; exercises: Exercise[] }>(["practice", "catalog", "--json", ...(key ? ["--key", key] : [])]).then((r) => r.result && setList(r.result));
  }, [active, key]);
  if (!list) return <div className="prac-list"><Skeleton h={60} /><Skeleton h={60} /><Skeleton h={60} /></div>;
  const groups = [...new Set(list.exercises.map((e) => e.group))];
  return (
    <div className="exlist">
      <div className="exlist__tools">
        <label className="t-label" htmlFor="ex-key">Ton (gam egzersizleri)</label>
        <Select id="ex-key" value={key || list.key} onChange={setKey} options={KEYS.map((k) => ({ value: k, label: k }))} />
      </div>
      {groups.map((g) => (
        <section key={g} className="exlist__group">
          <h2 className="t-heading">{g}</h2>
          <div className="exlist__grid">
            {list.exercises.filter((e) => e.group === g).map((e) => (
              <button key={e.id} type="button" className="excard" onClick={() => onPlay(e.id)}>
                <span className="excard__level" aria-label={`Seviye ${e.level}`}>{"●".repeat(e.level)}<span>{"●".repeat(5 - e.level)}</span></span>
                <span className="t-body-strong">{e.title}</span>
                <span className="t-small excard__sub">{e.subtitle}</span>
                <span className="excard__foot t-readout"><span>{e.working} BPM</span><span>{e.best ? `rekor ${e.best}` : `hedef ${e.goal_bpm}`}</span></span>
              </button>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------- theory
function TheoryTab({ onQuiz, onLatency }: { onQuiz: (k: QuizKind) => void; onLatency: () => void }) {
  const kinds: QuizKind[] = ["fretboard", "interval", "degree", "chord", "echo", "mix"];
  return (
    <div className="exlist">
      <div className="exlist__grid">
        {kinds.map((k) => (
          <button key={k} type="button" className="excard" onClick={() => onQuiz(k)}>
            <span className="excard__icon"><Icon name={k === "echo" ? "ear" : "grid"} /></span>
            <span className="t-body-strong">{QUIZ_NAMES[k]}</span>
            <span className="t-small excard__sub">{QUIZ_HINTS[k]}</span>
          </button>
        ))}
        <button type="button" className="excard" onClick={onLatency}>
          <span className="excard__icon"><Icon name="clock" /></span>
          <span className="t-body-strong">Gecikme testi</span>
          <span className="t-small excard__sub">16 tıka eşlik et; zamanlama ölçümü senin duyduğun vuruşa göre ayarlanır.</span>
        </button>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------- solo
function SoloTab({ onPlay }: { onPlay: (id: string, next: { id: string; title: string } | null) => void }) {
  const [solos, setSolos] = React.useState<Solo[] | null>(null);
  const [source, setSource] = React.useState("");
  const [busy, setBusy] = React.useState<string | null>(null);
  const load = () => cli.run<{ solos: Solo[] }>(["practice", "solos", "--json"]).then((r) => setSolos(r.result?.solos ?? []));
  React.useEffect(() => { load(); }, []);

  async function transcribe() {
    if (!source.trim()) return;
    setBusy("Hazırlanıyor…");
    const r = await cli.run<Solo>(["practice", "solo", source.trim(), "--json"], (l) => {
      if (l.text.startsWith("@@PRACTICE ")) { const ev = JSON.parse(l.text.slice(11)); if (ev.kind === "info") setBusy(ev.message); }
    });
    setBusy(null);
    if (r.result) { toast({ tone: "ok", title: "Solo çıkarıldı", text: `${r.result.phrases.length} cümle. Birini seçip yavaştan başla.` }); setSource(""); load(); }
    else { const f = friendly(r.error?.message ?? ""); toast({ tone: "danger", title: f.title, text: f.text }); }
  }

  return (
    <div className="exlist">
      <Card className="solo__new">
        <h2 className="t-heading">Şarkıdan solo çıkar</h2>
        <p className="t-small today__muted">Şarkının lead gitarı ayrılır, notalara ve tab'a çevrilir, döngüye alınabilecek cümlelere bölünür. İlk sefer ton çıkarmadaki gibi indirme ve ayırma sürer; daha önce çıkardığın şarkılar hızlıdır.</p>
        <div className="solo__form">
          <TextInput value={source} onChange={(e) => setSource(e.target.value)} placeholder="YouTube bağlantısı veya 'sanatçı şarkı'" disabled={!!busy}
            onKeyDown={(e) => { if (e.key === "Enter") transcribe(); }} />
          <Button variant="primary" icon="wave" onClick={transcribe} loading={!!busy} disabled={!source.trim()}>Çıkar</Button>
        </div>
        {busy && <p className="t-small today__muted">{busy}</p>}
      </Card>
      {solos === null ? <Skeleton h={80} /> : solos.length === 0 ? (
        <EmptyState icon="wave" title="Henüz solo yok">Bir şarkı çıkar; her cümle kendi tempo merdiveniyle çalışılır (%60'tan kayıt hızına).</EmptyState>
      ) : solos.map((s) => (
        <section key={s.track_id} className="exlist__group">
          <h2 className="t-heading">{[s.artist, s.title].filter(Boolean).join(" - ")} <span className="t-small today__muted">· {s.tempo.toFixed(0)} BPM</span></h2>
          <div className="exlist__grid">
            {s.phrases.map((p, i) => {
              const id = `solo/${s.track_id}/${p.index}`;
              const nx = s.phrases[i + 1];
              return (
                <button key={id} type="button" className="excard" onClick={() => onPlay(id, nx ? { id: `solo/${s.track_id}/${nx.index}`, title: `Cümle ${nx.index + 1}` } : null)}>
                  <span className="t-body-strong">Cümle {p.index + 1}</span>
                  <span className="t-small excard__sub">{Math.floor(p.start_s / 60)}:{String(Math.floor(p.start_s % 60)).padStart(2, "0")} · {p.count} nota · {p.beats} vuruş</span>
                </button>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}

// --------------------------------------------------------------------------------------------- progress
function ProgressTab({ active }: { active: boolean }) {
  const [s, setS] = React.useState<Stats | null>(null);
  React.useEffect(() => { if (active) cli.run<Stats>(["practice", "stats", "--json"]).then((r) => r.result && setS(r.result)); }, [active]);
  if (!s) return <div className="prac-list"><Skeleton h={80} /><Skeleton h={80} /></div>;
  if (!s.takes && !s.quiz.length) return <EmptyState icon="history" title="Henüz kayıt yok">İlk turdan sonra her egzersizin temposu burada gün gün görünür.</EmptyState>;
  const lastWeek = s.minutes.slice(-14);
  return (
    <div className="progress">
      <div className="progress__tiles">
        <Card className="tile"><span className="t-label">Seri</span><span className="t-stage">{s.streak}</span><span className="t-small">gün üst üste</span></Card>
        <Card className="tile"><span className="t-label">Toplam</span><span className="t-stage">{Math.round(s.total_minutes)}</span><span className="t-small">dakika çalım</span></Card>
        <Card className="tile"><span className="t-label">Tur</span><span className="t-stage">{s.takes}</span><span className="t-small">ölçülen tur</span></Card>
        <Card className="tile tile--wide"><span className="t-label">Son 14 gün (dk)</span>
          {lastWeek.length > 1 ? <Sparkline rising values={lastWeek.map((d) => d.minutes)} width={280} height={56} label={lastWeek.map((d) => `${d.day}: ${d.minutes} dk`).join(", ")} /> : <span className="t-small">Bir gün daha çal, grafik başlasın.</span>}
        </Card>
      </div>
      <section className="exlist__group">
        <h2 className="t-heading">Tempo, egzersiz egzersiz</h2>
        <table className="progress__table">
          <thead><tr><th>Egzersiz</th><th>Çalışma</th><th>Rekor (temiz)</th><th>Gün gün</th><th>Tur</th></tr></thead>
          <tbody>
            {s.skills.map((k) => {
              const vals = k.days.map((d) => d.best_clean || d.bpm);
              return (
                <tr key={k.skill}>
                  <td className="t-body-strong">{k.title}</td>
                  <td className="t-readout">{k.working ?? "—"} BPM</td>
                  <td className="t-readout">{k.best || "—"}</td>
                  <td>{vals.length > 1 ? <Sparkline rising values={vals} width={140} height={28} label={k.days.map((d) => `${d.day}: ${d.best_clean || d.bpm}`).join(", ")} /> : <span className="t-small">—</span>}</td>
                  <td className="t-readout">{k.takes}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
      {s.quiz.length > 0 && (
        <section className="exlist__group">
          <h2 className="t-heading">Teori ve kulak</h2>
          <div className="exlist__grid">
            {s.quiz.map((q) => (
              <Card key={q.quiz} className="tile">
                <span className="t-label">{QUIZ_NAMES[q.quiz]}</span>
                <span className="t-stage">%{q.asked ? Math.round((q.right / q.asked) * 100) : 0}</span>
                <span className="t-small">{q.asked} soru, {q.sessions} oturum</span>
              </Card>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
