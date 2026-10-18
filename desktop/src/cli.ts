import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

// One tonematch CLI process at a time (the GT-1's MIDI port can only have one owner); later calls queue.
// `--json` commands end with one "@@RESULT {...}" or "@@ERROR {...}" line; everything else is log, except
// "@@<KIND> {...}" stream lines (e.g. @@TUNER readings): they go to the job's onLine only, not to the console.

type LineEvent = { job: number; stream: "stdout" | "stderr"; line: string };
type ExitEvent = { job: number; code: number | null };

export type Line = { text: string; stream: "stdout" | "stderr" };
export type Outcome<T> = { code: number | null; result?: T; error?: { message: string; kind: string }; cancelled: boolean };
export type EnvInfo = { project: string; venv: string; uv: string | null; ready: boolean; platform: string };

type Job = { onLine: (l: Line) => void; done: (code: number | null) => void; result?: unknown; error?: Outcome<unknown>["error"] };

const jobs = new Map<number, Job>();
const early = new Map<number, (LineEvent | ExitEvent)[]>(); // events that beat run_cli's reply
let current: number | null = null;
let cancelled = false;
const busyListeners = new Set<(busy: boolean) => void>();
const logListeners = new Set<(l: Line | { cmd: string }) => void>();

const ANSI = /\x1b\[[0-9;]*[A-Za-z]/g;

function handle(ev: LineEvent | ExitEvent) {
  const job = jobs.get(ev.job);
  if (!job) {
    early.set(ev.job, [...(early.get(ev.job) ?? []), ev]);
    return;
  }
  if ("line" in ev) {
    const text = ev.line.replace(ANSI, "");
    if (text.startsWith("@@RESULT ")) job.result = JSON.parse(text.slice(9));
    else if (text.startsWith("@@ERROR ")) job.error = JSON.parse(text.slice(8));
    else if (text.startsWith("@@")) job.onLine({ text, stream: ev.stream });
    else {
      const l = { text, stream: ev.stream };
      job.onLine(l);
      logListeners.forEach((f) => f(l));
    }
  } else {
    jobs.delete(ev.job);
    job.done(ev.code);
  }
}

export async function initCli() {
  await listen<LineEvent>("cli-line", (e) => handle(e.payload));
  await listen<ExitEvent>("cli-exit", (e) => handle(e.payload));
}

export const isBusy = () => current !== null;
export const onBusy = (f: (busy: boolean) => void) => busyListeners.add(f);
export const onLog = (f: (l: Line | { cmd: string }) => void) => logListeners.add(f);

// Jobs run one after another: a run started while the device list is being read simply waits for it.
let queue: Promise<unknown> = Promise.resolve();
let waiting = 0;
export const pending = () => waiting + (current !== null ? 1 : 0);

/** interactive: the job can be asked to finish cleanly with stop() (its stdin stays open). */
export function run<T>(args: string[], onLine: (l: Line) => void = () => {}, interactive = false): Promise<Outcome<T>> {
  waiting++;
  const job = queue.then(() => { waiting--; return start<T>(args, onLine, interactive); });
  queue = job.catch(() => undefined);
  return job;
}

function start<T>(args: string[], onLine: (l: Line) => void, interactive: boolean): Promise<Outcome<T>> {
  logListeners.forEach((f) => f({ cmd: `tonematch ${args.join(" ")}` }));
  cancelled = false;
  return new Promise<Outcome<T>>((resolve, reject) => {
    const finish = (code: number | null, job: Job) => {
      current = null;
      busyListeners.forEach((f) => f(false));
      resolve({ code, result: job.result as T, error: job.error, cancelled });
    };
    invoke<number>("run_cli", { args, interactive })
      .then((id) => {
        current = id;
        busyListeners.forEach((f) => f(true));
        const job: Job = { onLine, done: (code) => finish(code, job) };
        jobs.set(id, job);
        for (const ev of early.get(id) ?? []) handle(ev);
        early.delete(id);
      })
      .catch((e) => reject(new Error(String(e))));
  });
}

export async function cancel() {
  if (current === null) return;
  cancelled = true;
  await invoke("cancel_job", { job: current });
}

/** Ask the running interactive job to finish on its own (it cleans up, then exits as usual). */
export async function stop() {
  if (current === null) return;
  await invoke("stop_job", { job: current });
}

export const environment = () => invoke<EnvInfo>("environment");
export const cachedSlots = <T>() => invoke<{ updated: number | null; slots: T[] }>("cached_slots");
