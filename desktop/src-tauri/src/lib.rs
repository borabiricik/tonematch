//! Thin desktop shell around the Python `tonematch` CLI.
//!
//! The UI never talks to the GT-1 or does audio work itself: it builds a CLI argument list, this side
//! runs `uv run --project <repo> tonematch <args>` and streams every output line back as events.
//! Same code path as the terminal, so the app and `tonematch.ps1` always behave identically.

use std::collections::HashMap;
use std::io::{BufRead, BufReader, Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager, State};

#[derive(Default)]
struct Jobs {
    next: u32,
    running: HashMap<u32, Arc<Mutex<Child>>>,
    /// stdin of `interactive` jobs: stop_job writes a line and closes it so the CLI can clean up
    stdins: HashMap<u32, ChildStdin>,
}

#[derive(Clone, Serialize)]
struct LineEvent {
    job: u32,
    stream: &'static str,
    line: String,
}

#[derive(Clone, Serialize)]
struct ExitEvent {
    job: u32,
    code: Option<i32>,
}

#[derive(Serialize)]
struct EnvInfo {
    project: String,
    venv: String,
    uv: Option<String>,
    /// the engine can be started (venv launcher or uv present)
    ready: bool,
    platform: &'static str,
}

fn home() -> PathBuf {
    std::env::var_os(if cfg!(windows) { "USERPROFILE" } else { "HOME" })
        .map(PathBuf::from)
        .unwrap_or_default()
}

/// Repo root (holds pyproject.toml). TONEMATCH_PROJECT overrides; default = the repo this app was built in.
fn project_root() -> PathBuf {
    if let Some(p) = std::env::var_os("TONEMATCH_PROJECT") {
        return PathBuf::from(p);
    }
    let p = Path::new(env!("CARGO_MANIFEST_DIR")).join("..").join("..");
    p.canonicalize().map(strip_unc).unwrap_or(p)
}

/// canonicalize() on Windows returns \\?\C:\..., which Python and uv do not like.
fn strip_unc(p: PathBuf) -> PathBuf {
    let s = p.to_string_lossy();
    match s.strip_prefix(r"\\?\") {
        Some(rest) => PathBuf::from(rest),
        None => p,
    }
}

/// Same venv location as tonematch.ps1 (kept out of OneDrive / iCloud).
fn venv_dir() -> PathBuf {
    if let Some(p) = std::env::var_os("TONEMATCH_VENV") {
        return PathBuf::from(p);
    }
    if cfg!(windows) {
        let base = std::env::var_os("LOCALAPPDATA").map(PathBuf::from).unwrap_or_else(|| home().join("AppData/Local"));
        base.join("tonematch").join("venv")
    } else if cfg!(target_os = "macos") {
        home().join("Library/Application Support/tonematch/venv")
    } else {
        home().join(".local/share/tonematch/venv")
    }
}

/// Where the Python side keeps its data (config.DATA_DIR): TONEMATCH_DATA or <local app data>/tonematch/data.
fn data_dir() -> PathBuf {
    if let Some(p) = std::env::var_os("TONEMATCH_DATA") {
        return PathBuf::from(p);
    }
    venv_dir().parent().map(|p| p.join("data")).unwrap_or_default()
}

/// The venv's own `tonematch` launcher: skips uv's project check (~0.3 s per command).
fn venv_exe() -> Option<PathBuf> {
    let p = if cfg!(windows) { venv_dir().join("Scripts").join("tonematch.exe") } else { venv_dir().join("bin").join("tonematch") };
    p.is_file().then_some(p)
}

/// GUI apps (Finder on macOS, a fresh winget install on Windows) often get a short PATH:
/// add the usual tool folders so uv, ffmpeg and yt-dlp's helpers are found.
fn extra_path_dirs() -> Vec<PathBuf> {
    let h = home();
    let mut v = vec![h.join(".local/bin"), h.join(".cargo/bin")];
    if cfg!(windows) {
        if let Some(l) = std::env::var_os("LOCALAPPDATA") {
            v.push(PathBuf::from(l).join("Microsoft/WinGet/Links"));
        }
    } else {
        v.push("/opt/homebrew/bin".into());
        v.push("/usr/local/bin".into());
    }
    v
}

fn search_path() -> Vec<PathBuf> {
    let mut dirs: Vec<PathBuf> = std::env::var_os("PATH").map(|p| std::env::split_paths(&p).collect()).unwrap_or_default();
    dirs.extend(extra_path_dirs());
    dirs
}

fn find_uv() -> Option<PathBuf> {
    let exe = if cfg!(windows) { "uv.exe" } else { "uv" };
    search_path().into_iter().map(|d| d.join(exe)).find(|p| p.is_file())
}

/// Read a pipe line by line; progress bars redraw with '\r', so only the last redraw of a line is kept.
fn pump<R: Read + Send + 'static>(app: AppHandle, job: u32, stream: &'static str, r: R) {
    thread::spawn(move || {
        let mut reader = BufReader::new(r);
        let mut buf = Vec::new();
        while reader.read_until(b'\n', &mut buf).map(|n| n > 0).unwrap_or(false) {
            let text = String::from_utf8_lossy(&buf);
            let line = text.trim_end_matches(['\n', '\r']).rsplit('\r').next().unwrap_or("").to_string();
            let _ = app.emit("cli-line", LineEvent { job, stream, line });
            buf.clear();
        }
    });
}

#[tauri::command]
fn environment() -> EnvInfo {
    EnvInfo {
        project: project_root().display().to_string(),
        venv: venv_dir().display().to_string(),
        uv: find_uv().map(|p| p.display().to_string()),
        ready: venv_exe().is_some() || find_uv().is_some(),
        platform: std::env::consts::OS,
    }
}

/// Start `tonematch <args>`; returns a job id. Output arrives as `cli-line`, the end as `cli-exit`.
/// interactive: keep stdin open so stop_job can ask the CLI to finish (e.g. `gt1 tuner` restores play mode).
#[tauri::command]
fn run_cli(app: AppHandle, jobs: State<'_, Mutex<Jobs>>, args: Vec<String>, interactive: Option<bool>) -> Result<u32, String> {
    let path = std::env::join_paths(search_path()).map_err(|e| e.to_string())?;
    let mut cmd = match venv_exe() {
        Some(exe) => Command::new(exe),
        None => {
            let uv = find_uv().ok_or("uv bulunamadı (kurulum: https://docs.astral.sh/uv/)")?;
            let mut c = Command::new(uv);
            c.arg("run").arg("--project").arg(project_root()).arg("tonematch");
            c
        }
    };
    cmd.args(&args)
        .current_dir(project_root())
        .env("UV_PROJECT_ENVIRONMENT", venv_dir())
        .env("PATH", path)
        // the CLI prints Turkish text and box drawing: never fall back to a legacy code page (cp1254 crash)
        .env("PYTHONUTF8", "1")
        .env("PYTHONIOENCODING", "utf-8")
        .env("COLUMNS", "110")
        .stdin(if interactive.unwrap_or(false) { Stdio::piped() } else { Stdio::null() })
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    let mut child = cmd.spawn().map_err(|e| format!("tonematch başlatılamadı: {e}"))?;

    let job = {
        let mut j = jobs.lock().unwrap();
        j.next += 1;
        j.next
    };
    pump(app.clone(), job, "stdout", child.stdout.take().unwrap());
    pump(app.clone(), job, "stderr", child.stderr.take().unwrap());
    let stdin = child.stdin.take();
    let child = Arc::new(Mutex::new(child));
    {
        let mut j = jobs.lock().unwrap();
        j.running.insert(job, child.clone());
        if let Some(s) = stdin {
            j.stdins.insert(job, s);
        }
    }

    // poll instead of wait() so cancel_job can still lock the child and kill it
    thread::spawn(move || {
        let code = loop {
            let status = child.lock().unwrap().try_wait();
            match status {
                Ok(Some(s)) => break s.code(),
                Ok(None) => thread::sleep(Duration::from_millis(150)),
                Err(_) => break None,
            }
        };
        {
            let state = app.state::<Mutex<Jobs>>();
            let mut j = state.lock().unwrap();
            j.running.remove(&job);
            j.stdins.remove(&job);
        }
        let _ = app.emit("cli-exit", ExitEvent { job, code });
    });
    Ok(job)
}

#[tauri::command]
fn cancel_job(jobs: State<'_, Mutex<Jobs>>, job: u32) -> Result<(), String> {
    let child = {
        let mut j = jobs.lock().unwrap();
        j.stdins.remove(&job);
        j.running.remove(&job)
    };
    match child {
        Some(c) => c.lock().unwrap().kill().map_err(|e| e.to_string()),
        None => Ok(()),
    }
}

/// Ask an interactive job to finish on its own: one "stop" line, then EOF. Unlike cancel_job the CLI
/// runs its cleanup (the GT-1 leaves tuner / editor mode); cli-exit follows as usual.
#[tauri::command]
fn stop_job(jobs: State<'_, Mutex<Jobs>>, job: u32) -> Result<(), String> {
    let stdin = jobs.lock().unwrap().stdins.remove(&job);
    match stdin {
        Some(mut s) => {
            let _ = s.write_all(b"stop
");
            Ok(()) // dropping s closes the pipe
        }
        None => Err("bu iş durdurma isteğini desteklemiyor".into()),
    }
}

/// Last known slot list (written by `tonematch gt1 list/status` and after every slot write): instant,
/// no Python start, no MIDI. Empty when the device was never read.
#[tauri::command]
fn cached_slots() -> serde_json::Value {
    std::fs::read_to_string(data_dir().join("gt1_slots.json"))
        .ok()
        .and_then(|t| serde_json::from_str(&t).ok())
        .unwrap_or_else(|| serde_json::json!({ "updated": null, "slots": [] }))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(Mutex::new(Jobs::default()))
        .invoke_handler(tauri::generate_handler![environment, run_cli, cancel_job, stop_job, cached_slots])
        .run(tauri::generate_context!())
        .expect("error while running ToneMatch");
}
