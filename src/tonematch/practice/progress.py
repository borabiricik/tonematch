"""Practice memory: every take, the working tempo per skill, the speed ladder and the daily routine.

Files (DATA_DIR/practice): history.jsonl (one line per take), state.json (per-skill tempo + settings).

The ladder, the way a teacher runs it:
  * a take is *clean* at accuracy >= threshold (default 95 %) with most notes on the beat;
  * two clean takes in a row at the working tempo -> ask to go up ~4 % (the player decides: "Sor, sonra geç");
  * under 80 % -> suggest backing off one step (practising mistakes at speed is practising mistakes);
  * the best clean tempo is the record; the next day starts a little under the working tempo (warm-up).
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from ..config import DATA_DIR
from .exercises import build, key_of_day, spider_of_day

PRACTICE_DIR = DATA_DIR / "practice"
DEFAULTS = {"minutes": 30, "threshold": 0.95, "latency_ms": 0.0, "click_level": 0.7, "count_in": 4}
ON_TIME_CLEAN = 0.6       # share of notes inside the tight window for a clean take
BACK_OFF_BELOW = 0.80
CLEAN_IN_A_ROW = 2


def _dir() -> Path:
    PRACTICE_DIR.mkdir(parents=True, exist_ok=True)
    return PRACTICE_DIR


def load_state() -> dict:
    p = _dir() / "state.json"
    st = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    st.setdefault("skills", {})
    st["settings"] = {**DEFAULTS, **st.get("settings", {})}
    return st


def save_state(st: dict) -> None:
    p = _dir() / "state.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def history() -> list[dict]:
    p = _dir() / "history.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def quiz_history() -> list[dict]:
    p = _dir() / "quiz.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def log_quiz(summary: dict) -> None:
    line = {"at": datetime.now().isoformat(timespec="seconds"), **{k: v for k, v in summary.items() if k != "items"}}
    with (_dir() / "quiz.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def step(bpm: int) -> int:
    return max(2, round(bpm * 0.04))


def working_bpm(skill: str, default: int, st: dict | None = None) -> int:
    st = st or load_state()
    return int(st["skills"].get(skill, {}).get("bpm", default))


def record_take(ex_id: str, bpm: int, summary: dict, seconds: float, mode: str = "play") -> dict:
    """Log a take, update the skill and return the ladder's decision for the UI."""
    ex = build(ex_id)
    st = load_state()
    thr = float(st["settings"]["threshold"])
    sk = st["skills"].setdefault(ex.skill, {"bpm": ex.bpm, "best": 0, "clean_streak": 0, "takes": 0})
    if bpm != sk["bpm"]:  # the player chose another tempo: that is the working tempo now
        sk["bpm"], sk["clean_streak"] = bpm, 0
    acc = summary.get("accuracy", 0.0)
    clean = acc >= thr and summary.get("on_time", 0.0) >= ON_TIME_CLEAN and summary.get("notes", 0) > 0
    sk["takes"] += 1
    sk["last"] = datetime.now().isoformat(timespec="seconds")
    sk["clean_streak"] = sk["clean_streak"] + 1 if clean else 0
    if clean:
        sk["best"] = max(sk["best"], bpm)
    decision = decide(bpm, acc, clean, sk["clean_streak"], ex.goal_bpm, thr)
    save_state(st)
    line = {"at": sk["last"], "id": ex_id, "skill": ex.skill, "bpm": bpm, "mode": mode, "seconds": round(seconds, 1),
            "clean": clean, **{k: summary.get(k) for k in ("accuracy", "on_time", "mean_ms", "spread_ms", "notes",
                                                              "correct", "extras")}}
    with (_dir() / "history.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return {**decision, "clean": clean, "best": sk["best"], "streak": sk["clean_streak"]}


def decide(bpm: int, acc: float, clean: bool, streak: int, goal: int, thr: float) -> dict:
    """What to suggest after a take (Turkish message for the player)."""
    up = bpm + step(bpm)
    if clean and streak >= CLEAN_IN_A_ROW:
        msg = (f"Üst üste {streak} temiz tur. {up} BPM'e geçelim mi?" if bpm < goal
               else f"Hedef tempoyu ({goal}) geçtin ve temiz. {up} BPM'i dene ya da sonraki egzersize geç.")
        return {"suggest": "faster", "to_bpm": up, "message": msg}
    if clean:
        return {"suggest": "again", "to_bpm": bpm,
                "message": f"Temiz tur (%{acc * 100:.0f}). Bir tur daha temiz çalarsan tempoyu artıralım."}
    if acc < BACK_OFF_BELOW:
        down = max(30, bpm - step(bpm))
        return {"suggest": "slower", "to_bpm": down,
                "message": f"%{acc * 100:.0f} doğruluk. {down} BPM'e inip temiz çalalım; yanlışı hızlı çalmak yanlışı "
                           "ezberletir."}
    return {"suggest": "again", "to_bpm": bpm,
            "message": f"%{acc * 100:.0f}, temize az kaldı (%{thr * 100:.0f}). Aynı tempoda bir tur daha."}


def set_bpm(skill: str, bpm: int) -> dict:
    st = load_state()
    sk = st["skills"].setdefault(skill, {"bpm": bpm, "best": 0, "clean_streak": 0, "takes": 0})
    sk["bpm"], sk["clean_streak"] = int(bpm), 0
    save_state(st)
    return sk


def set_settings(**kw) -> dict:
    st = load_state()
    st["settings"].update({k: v for k, v in kw.items() if v is not None})
    save_state(st)
    return st["settings"]


# ------------------------------------------------------------------------------------------------ routine
def day_index(d: date | None = None) -> int:
    return ((d or date.today()) - date(2026, 1, 5)).days  # a Monday


# technique focus by day (6-day cycle; the 7th day repeats the first lightly)
FOCUS = [
    ("Alternate picking", ["seq/{k}/natural_minor/4/0", "tremolo/4"]),
    ("Legato", ["trill/{trill}", "legato3nps/{k}/natural_minor/0"]),
    ("Arpej", ["sweep/{k}/min/3", "arp7/{k}/min7"]),
    ("Alternate picking", ["seq/{k}/natural_minor/3/0", "skip/{k}/min"]),
    ("Pentatonik hız", ["pent6/{k}/1", "pent/{k}/{box}"]),
    ("Ritim ve sweep", ["subdiv", "sweep/{k}/min/5"]),
]
QUIZ_OF_DAY = ["fretboard", "interval", "degree", "echo"]


def routine(minutes: int | None = None, d: date | None = None, solo_item: dict | None = None) -> dict:
    """Today's plan: warm-up, technique, speed bursts, scales, theory/ear, solo. Minutes split like a lesson."""
    st = load_state()
    minutes = int(minutes or st["settings"]["minutes"])
    i = day_index(d)
    k = key_of_day(i)
    box = i % 5 + 1
    trill = ["12", "13", "14", "34"][i % 4]
    focus_name, focus_ids = FOCUS[i % len(FOCUS)]
    fill = lambda s: s.format(k=k, box=box, trill=trill)
    share = {"warmup": 0.10, "technique": 0.30, "burst": 0.15, "scales": 0.20, "theory": 0.10, "solo": 0.15}
    m = {b: max(2, round(minutes * f)) for b, f in share.items()}
    tech = [fill(x) for x in focus_ids]
    blocks = [
        {"id": "warmup", "title": "Isınma", "minutes": m["warmup"],
         "why": "Eller ısınmadan hız denenmez. Kromatik ve günün permütasyonu: parmak bağımsızlığı.",
         "items": [f"chromatic/1234/1", f"chromatic/{spider_of_day(i)}/5"]},
        {"id": "technique", "title": f"Teknik · {focus_name}", "minutes": m["technique"],
         "why": "Bugünün odağı. Önce temiz, sonra hız: iki temiz turdan sonra tempo artar.", "items": tech},
        {"id": "burst", "title": "Hız patlaması", "minutes": m["burst"],
         "why": "Rahat temponun üstünde kısa patlamalar: el hızlı hareketi böyle öğrenir, dinlenmede gevşe.",
         "items": [f"burst/{tech[0]}"]},
        {"id": "scales", "title": f"Gam ve pozisyon · {k}", "minutes": m["scales"],
         "why": f"Bu haftanın tonu {k} (beşliler çemberinde her hafta bir ton). Pentatonik kutu {box} ve 3 nota/tel "
                "şekli: klavyeyi parça parça değil ağ gibi öğren.",
         "items": [f"pent/{k}/{box}", f"3nps/{k}/natural_minor/{(i % 3) * 2}"]},
        {"id": "theory", "title": "Teori ve kulak", "minutes": m["theory"],
         "why": "Klavyeyi bilmek ve duyduğunu çalabilmek: zor solo, kulağın önden gittiği solodur.",
         "quiz": QUIZ_OF_DAY[i % len(QUIZ_OF_DAY)], "items": []},
        {"id": "solo", "title": "Solo / lick", "minutes": m["solo"],
         "why": "Teknik müziğe dönüşsün: şarkıdan bir pasaj, yavaştan hedef tempoya.",
         "items": [solo_item["id"]] if solo_item else [f"pent6/{k}/1"], "solo": solo_item},
    ]
    for b in blocks:
        b["exercises"] = []
        for ex_id in b["items"]:
            try:
                ex = build(ex_id)
            except Exception:  # a solo that is gone, etc.
                continue
            target = working_bpm(ex.skill, ex.bpm, st)
            sk = st["skills"].get(ex.skill, {})
            b["exercises"].append({"id": ex_id, "title": ex.title, "subtitle": ex.subtitle, "group": ex.group,
                                   "bpm": target, "best": sk.get("best", 0), "goal": ex.goal_bpm,
                                   "warm": max(30, round(target * 0.9)) if b["id"] == "warmup" else target})
    done = _today_done(d)
    return {"date": (d or date.today()).isoformat(), "minutes": minutes, "key": k, "focus": focus_name,
            "blocks": blocks, "done_ids": sorted(done), "streak": streak_days(), "settings": st["settings"]}


def _today_done(d: date | None = None) -> set[str]:
    day = (d or date.today()).isoformat()
    return ({h["id"] for h in history() if h.get("at", "").startswith(day)}
            | {f"quiz:{q['quiz']}" for q in quiz_history() if q.get("at", "").startswith(day)})


def streak_days(today: date | None = None) -> int:
    days = {h["at"][:10] for h in history() + quiz_history() if h.get("at")}
    d = today or date.today()
    if d.isoformat() not in days:
        d -= timedelta(days=1)  # today not played yet: the streak still counts until midnight
    n = 0
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return n


def stats() -> dict:
    """Per-skill tempo over time (best clean tempo per day) and minutes per day, for the progress screen."""
    h = history()
    st = load_state()
    per_skill: dict[str, dict] = {}
    minutes: dict[str, float] = {}
    for t in h:
        day = t["at"][:10]
        minutes[day] = minutes.get(day, 0.0) + t.get("seconds", 0) / 60
        s = per_skill.setdefault(t["skill"], {"skill": t["skill"], "title": _title(t["id"]), "days": {}, "takes": 0})
        s["takes"] += 1
        dd = s["days"].setdefault(day, {"day": day, "best_clean": 0, "best_acc": 0.0, "bpm": 0})
        dd["bpm"] = max(dd["bpm"], t["bpm"])
        dd["best_acc"] = max(dd["best_acc"], t.get("accuracy") or 0.0)
        if t.get("clean"):
            dd["best_clean"] = max(dd["best_clean"], t["bpm"])
    skills = []
    for s in per_skill.values():
        sk = st["skills"].get(s["skill"], {})
        skills.append({**s, "days": sorted(s["days"].values(), key=lambda x: x["day"]),
                       "working": sk.get("bpm"), "best": sk.get("best", 0)})
    skills.sort(key=lambda s: -s["takes"])
    quizzes: dict[str, dict] = {}
    for q in quiz_history():
        e = quizzes.setdefault(q["quiz"], {"quiz": q["quiz"], "sessions": 0, "asked": 0, "right": 0, "days": {}})
        e["sessions"] += 1
        e["asked"] += q.get("asked", 0)
        e["right"] += q.get("right", 0)
        dd = e["days"].setdefault(q["at"][:10], {"day": q["at"][:10], "asked": 0, "right": 0, "mean_ms": None})
        dd["asked"] += q.get("asked", 0)
        dd["right"] += q.get("right", 0)
        dd["mean_ms"] = q.get("mean_ms") or dd["mean_ms"]
    quiz = [{**e, "days": sorted(e["days"].values(), key=lambda x: x["day"])} for e in quizzes.values()]
    return {"skills": skills, "quiz": quiz,
            "minutes": [{"day": k, "minutes": round(v, 1)} for k, v in sorted(minutes.items())],
            "streak": streak_days(), "takes": len(h), "total_minutes": round(sum(minutes.values()), 1),
            "generated": int(time.time())}


def _title(ex_id: str) -> str:
    try:
        return build(ex_id).title
    except Exception:
        return ex_id
