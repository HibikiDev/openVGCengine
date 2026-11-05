



































from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from vgc_trainer.winproc import NO_WINDOW

from vgc_trainer.showdown.tracker import to_id
from vgc_trainer.amp import pick_device
from vgc_trainer.showdown.teams import UnknownTeam

from .core.teams import lookup_team


HELP = ("Commands: .team <id | pokepast.es link> | .team <format> <id | link> (formats: mc, vgc13 ... vgc19, regc, regd, regg, regi; e.g. "
        ".team gen5vgc13 https://pokepast.es/...) | .team bucket:<name> (a team from a saved bucket, drawn by weight each game) | .team default | .formats | .reset | .sheets on/off | .timer on/off | .lead <mon>, <mon> | .back <mon>, <mon> | "
        ".session start [name] / .session end / .session resume (groups your games on the dashboard) | .status. Your team for a format is played in that format's challenges (Bo1 or Bo3).")
USER_AGENT = "Mozilla/5.0 (openVGCengine buddy)"
PREFIX = "."
MC = "gen9championsvgc2026regmc"

YEAR_FORMATS = {"13": "gen5vgc2013", "14": "gen6vgc2014", "15": "gen6vgc2015", "16": "gen6vgc2016", "17": "gen7vgc2017",
                "18": "gen7vgc2018", "19": "gen7vgc2019", "20": "gen8vgc2020", "21": "gen8vgc2021", "22": "gen8vgc2022"}

SV_REGS = {"c": "gen9vgc2023regc", "d": "gen9vgc2023regd", "g": "gen9vgc2024regg", "i": "gen9vgc2025regi"}
FORMAT_NAMES = {MC: "Reg M-C", **{f: f"VGC 20{y}" for y, f in YEAR_FORMATS.items()}, **{f: f"SV Reg {r.upper()}" for r, f in SV_REGS.items()}}

SHOWDOWN_NAMES = {MC: "[Gen 9 Champions] VGC 2026 Reg M-C", MC + "bo3": "[Gen 9 Champions] VGC 2026 Reg M-C (Bo3)",
                  "gen5vgc2013": "[Gen 5] VGC 2013", "gen6vgc2014": "[Gen 6] VGC 2014", "gen6vgc2015": "[Gen 6] VGC 2015",
                  "gen6vgc2016": "[Gen 6] VGC 2016", "gen7vgc2017": "[Gen 7] VGC 2017", "gen7vgc2018": "[Gen 7] VGC 2018",
                  "gen7vgc2019": "[Gen 7] VGC 2019", "gen8vgc2020": "[Gen 8] VGC 2020",
                  "gen8vgc2021": "[Gen 8] VGC 2021", "gen8vgc2022": "[Gen 8] VGC 2022", "gen9vgc2023regc": "[Gen 9] VGC 2023 Reg C",
                  "gen9vgc2023regd": "[Gen 9] VGC 2023 Reg D", "gen9vgc2024regg": "[Gen 9] VGC 2024 Reg G", "gen9vgc2025regi": "[Gen 9] VGC 2025 Reg I"}
TEAM_PREFIX = {MC: "mc", **{f: f"vgc{y}" for y, f in YEAR_FORMATS.items()}, **{f: f"reg{r}" for r, f in SV_REGS.items()}}


def formats_text(accepted: tuple[str, ...]) -> str:

    parts = []
    for f in accepted:
        group = MC if f.startswith(MC) else f
        bo3 = "" if f.startswith(MC) else f" (Bo3: /challenge <bot>, {f}@@@Best Of = 3)"
        parts.append(f"{SHOWDOWN_NAMES.get(f, f)} = {f}{bo3}, team: .team {TEAM_PREFIX.get(group, f)} <id | link>")
    return "Formats I play: " + " | ".join(parts) + "."


def parse_format(token: str) -> str | None:


    t = to_id(token)
    if t in ("mc", "regmc", "champions", "championsmc") or t.startswith(MC):
        return MC
    m = re.fullmatch(r"(?:gen[5-8])?vgc(?:20)?(1[3-9]|2[0-2])", t)
    if m:
        return YEAR_FORMATS.get(m.group(1))
    sv = re.fullmatch(r"(?:gen9)?(?:sv)?(?:vgc(?:20)?2[345])?reg([cdgi])", t)
    return SV_REGS[sv.group(1)] if sv else None


def _library_format(team_id: str) -> str | None:

    from vgc_trainer.showdown.teams import TEAM_FILES
    for f in (f for f in TEAM_FILES if f.exists()):
        doc = json.loads(f.read_text(encoding="utf8"))
        if doc.get("format") and any(t["id"] == team_id for t in doc["teams"]):
            return doc["format"]
    return None


def _validated_sets(text: str, fmt: str) -> list[dict]:

    from .core.teams import validated_sets
    return validated_sets(text, fmt)


@dataclass
class Profile:
    team_spec: str | None = None
    team_label: str = "my rotation"
    sheets: bool = True
    timer: bool = True
    games: int = 0

    format_teams: dict[str, dict] = field(default_factory=dict)
    lead: list[str] = field(default_factory=list)
    back: list[str] = field(default_factory=list)

    drills: dict[str, dict] = field(default_factory=dict)


def _fetch_paste(paste_id: str) -> str:
    req = urllib.request.Request(f"https://pokepast.es/{paste_id}/raw", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf8")


@dataclass
class Buddy:
    path: Path | None = None
    profiles: dict[str, Profile] = field(default_factory=dict)
    formats: tuple[str, ...] | None = None
    accepted: tuple[str, ...] = ()
    _teams: dict[str, list[dict]] = field(default_factory=dict)

    _mtime: float = 0.0

    def __post_init__(self):
        self._reload()

    def _reload(self) -> None:


        if not self.path or not Path(self.path).exists():
            return
        m = Path(self.path).stat().st_mtime
        if m > self._mtime:
            self.profiles = {user: Profile(**p) for user, p in json.loads(Path(self.path).read_text(encoding="utf8")).items()}
            self._mtime = m

    def save(self) -> None:
        if self.path:
            tmp = Path(self.path).with_suffix(".part")
            tmp.write_text(json.dumps({u: asdict(p) for u, p in self.profiles.items()}, indent=1), encoding="utf8")
            tmp.replace(self.path)
            self._mtime = Path(self.path).stat().st_mtime

    def profile(self, user: str) -> Profile:
        self._reload()
        return self.profiles.setdefault(to_id(user), Profile())

    def resolve(self, spec: str, fmt: str = MC) -> list[dict]:


        key = spec if fmt == MC else f"{fmt}|{spec}"
        if key not in self._teams:
            m = re.fullmatch(r"paste:([0-9a-fA-F]+)", spec)
            text = _fetch_paste(m.group(1)) if m else spec[5:] if spec.startswith("text:") else None
            if fmt == MC:
                sets = lookup_team(text if text is not None else spec)
            else:
                if text is None:
                    own = _library_format(spec)
                    if own is not None and own != fmt:
                        raise ValueError(f"{spec} is a {FORMAT_NAMES.get(own, own)} team")


                from .core.teams import read_team
                sets = read_team(text if text is not None else spec, fmt)
            self._teams[key] = sets
        return self._teams[key]

    def team_for(self, user: str, fmt: str = MC) -> list[dict] | None:


        spec = self.spec_for(user, fmt)
        if not spec:
            return None
        if spec.startswith("bucket:"):
            from .core.buckets import draw
            return self.resolve(draw(spec[7:])[1], fmt)
        return self.resolve(spec, fmt)

    def spec_for(self, user: str, fmt: str = MC) -> str | None:


        from .core.buckets import default_spec
        p = self.profile(user)
        return (p.team_spec if fmt == MC else (p.format_teams.get(fmt) or {}).get("spec")) or default_spec(fmt)

    def drill_for(self, user: str, fmt: str = MC) -> tuple[list[str], list[str]]:

        p = self.profile(user)
        if fmt == MC:
            return list(p.lead), list(p.back)
        d = p.drills.get(fmt) or {}
        return list(d.get("lead", [])), list(d.get("back", []))

    def _set_drill(self, p: Profile, fmt: str, lead: list[str], back: list[str]) -> None:
        if fmt == MC:
            p.lead, p.back = lead, back
        elif lead:
            p.drills[fmt] = {"lead": lead, "back": back}
        else:
            p.drills.pop(fmt, None)

    def label_for(self, user: str, fmt: str = MC) -> str:
        from .core.buckets import DEFAULT, default_spec
        p = self.profile(user)
        label = p.team_label if fmt == MC else p.format_teams.get(fmt, {}).get("label", "my rotation")
        return f"the {DEFAULT} bucket" if label == "my rotation" and default_spec(fmt) else label

    def game_started(self, user: str) -> None:
        self.profile(user).games += 1
        self.save()

    def handle(self, user: str, text: str) -> str | None:

        text = text.strip()
        if not text.startswith(PREFIX):
            return None
        cmd, _, arg = text[1:].partition(" ")
        cmd, arg = cmd.lower(), arg.strip()
        p = self.profile(user)
        if cmd == "help":
            return HELP
        if cmd == "status":
            drill = (f" Drill: leads {' + '.join(p.lead)}" + (f", back {' + '.join(p.back)}" if p.back else "") + ".") if p.lead else ""
            others = "".join(f" {FORMAT_NAMES.get(f, f)}: {t['label']}." for f, t in sorted(p.format_teams.items()))
            return (f"Team (Reg M-C): {self.label_for(user)}.{others} Open team sheets: {'on' if p.sheets else 'off'}. Timer: {'on' if p.timer else 'off'}.{drill} "
                    f"Games played: {p.games}.")
        if cmd == "formats":
            return formats_text(self.accepted or self.formats or (MC,))
        if cmd == "session":
            from . import buddy_sessions as bs
            if not self.path:
                return "Sessions need a saved profile file - not available on this bot."
            where = bs.path_for(self.path)
            sub, _, name = arg.partition(" ")
            if sub.lower() == "start":
                new, closed = bs.start(where, user, name)
                return (f"Session \"{new['name']}\" started: every game you play me from now on is grouped on the dashboard's Buddy "
                        f"page until .session end." + (f" (Closed your open session \"{closed['name']}\" first.)" if closed else ""))
            if sub.lower() == "resume":
                s, folded = bs.resume(where, user)
                if s is None:
                    return "No ended session to resume - .session start [name] begins one."
                return (f"Session \"{s['name']}\" (since {s['start'][5:16]}) is running again." +
                        (f" Folded in the {len(folded)} session(s) you started after it." if folded else ""))
            if sub.lower() in ("end", "stop"):
                s = bs.end(where, user)
                if s is None:
                    return "No session running - .session start [name] begins one."
                return f"Session \"{s['name']}\" ended ({s['start'][11:16]}-{s['end'][11:16]}). It's on the dashboard's Buddy page."
            s = bs.active(where, user)
            return (f"Session \"{s['name']}\" running since {s['start'][11:16]} - .session end closes it." if s
                    else "No session running - .session start [name] begins one, .session end closes it.")
        if cmd == "reset":
            self.profiles[to_id(user)] = Profile(games=p.games)
            self.save()
            return "Back to the defaults: my own rotation in every format, open team sheets on, no drill."
        if cmd in ("lead", "back"):

            first, _, rest = arg.partition(" ")
            dfmt = None if "," in first else parse_format(first)
            if dfmt is not None:
                arg = rest.strip()
            dfmt = dfmt or MC
            lead_now, back_now = self.drill_for(user, dfmt)
            if arg.lower() in ("off", "", "none"):
                self._set_drill(p, dfmt, [] if cmd == "lead" else lead_now, [])
                self.save()
                return "Drill off: the model picks its own leads." if cmd == "lead" else "The model picks its own back two."
            spec = self.spec_for(user, dfmt)
            if not spec:
                return f"Pick the team I play in {FORMAT_NAMES.get(dfmt, dfmt)} first (.team ...): the drill needs to know my six."
            if spec.startswith("bucket:"):
                return "The drill needs one team, not a bucket: pick a single team first (.team <id | link | paste>)."
            names = [x.strip() for x in arg.split(",") if x.strip()]
            six = [s_["species"] for s_ in self.resolve(spec, dfmt)]
            ids = {to_id(x): x for x in six}
            picked = [ids.get(to_id(x)) for x in names]
            if len(names) != 2 or None in picked or len(set(picked)) != 2:
                return f"Name two different mons from my team: {', '.join(six)}."
            if cmd == "back":
                if not lead_now:
                    return "Set the leads first (.lead ...)."
                if set(picked) & set(lead_now):
                    return "The back two can't be the leads."
                self._set_drill(p, dfmt, lead_now, picked)
            else:
                self._set_drill(p, dfmt, picked, [] if set(back_now) & set(picked) else back_now)
            self.save()
            lead_now, back_now = self.drill_for(user, dfmt)
            where = "" if dfmt == MC else f" in {FORMAT_NAMES.get(dfmt, dfmt)}"
            return (f"Drill{where}: I'll lead {' + '.join(lead_now)}" + (f" with {' + '.join(back_now)} in the back." if back_now
                    else ", the model picks the back two."))
        if cmd == "timer":
            if arg.lower() not in ("on", "off"):
                return "Use .timer on or .timer off."
            p.timer = arg.lower() == "on"
            self.save()
            return f"Battle timer {'on: I turn it on in every game' if p.timer else 'off: I leave it off (you can still turn it on in the game)'}."
        if cmd == "sheets":
            if arg.lower() not in ("on", "off"):
                return "Use .sheets on or .sheets off."
            p.sheets = arg.lower() == "on"
            self.save()
            return f"Open team sheets {'on: I will accept them' if p.sheets else 'off: I will decline them (closed sheets)'}."
        if cmd == "team":
            if not arg or arg.lower() == "default":
                p.team_spec, p.team_label = None, "my rotation"
                p.format_teams = {}
                p.lead, p.back = [], []
                self.save()
                return "I'll use my own rotation in every format."

            first, _, rest = arg.partition(" ")
            fmt = None if "\n" in first else parse_format(first)
            if fmt is not None:
                arg = rest.strip()
                if not arg:
                    return f"Name the team for {FORMAT_NAMES.get(fmt, fmt)}: .team {first} <id | pokepast.es link> (or default)."
                if self.formats is not None and fmt not in self.formats:
                    return (f"I don't play {FORMAT_NAMES.get(fmt, fmt)} here. Formats: "
                            f"{', '.join(FORMAT_NAMES.get(f, f) for f in self.formats)}.")
                if arg.lower() == "default":
                    if fmt == MC:
                        p.team_spec, p.team_label = None, "my rotation"
                        p.lead, p.back = [], []
                    else:
                        p.format_teams.pop(fmt, None)
                    self.save()
                    return f"I'll use my own rotation in {FORMAT_NAMES.get(fmt, fmt)}."
            if arg.lower().startswith("bucket:"):
                from .core import buckets
                name = arg[7:].strip()
                name = next((b for b in buckets.names() if b.lower() == name.lower()), name)
                if name not in buckets.names():
                    return f"I don't have a team bucket called {name}."
                own = buckets.format_of(name)
                if fmt is not None and fmt != own:
                    return f"Bucket {name} holds {FORMAT_NAMES.get(own, own)} teams, not {FORMAT_NAMES.get(fmt, fmt)} ones."
                if self.formats is not None and own not in self.formats:
                    return f"Bucket {name} holds {FORMAT_NAMES.get(own, own)} teams, and I don't play that format here."
                n = len(buckets.get(name)["teams"])
                spec, label = f"bucket:{name}", f"bucket {name} ({n} teams, one drawn by weight per game)"
                if own == MC:
                    p.team_spec, p.team_label = spec, label
                else:
                    p.format_teams[own] = {"spec": spec, "label": label}
                self._set_drill(p, own, [], [])
                self.save()
                return (f"Next {FORMAT_NAMES.get(own, own)} games I'll play a team from bucket {name}: one of its {n} teams per game, "
                        "by their weights.")
            if "\n" in arg:
                spec, label = "text:" + arg.strip() + "\n", "your pasted team"
            elif "pokepast.es" in arg:
                m = re.search(r"pokepast\.es/([0-9a-fA-F]+)", arg)
                if not m:
                    return "That doesn't look like a pokepast.es link."
                spec, label = f"paste:{m.group(1)}", f"your paste ({m.group(1)})"
            else:
                spec, label = arg, arg
                if fmt is None:
                    try:
                        fmt = _library_format(arg)
                    except Exception:
                        fmt = None
            fmt = fmt or MC
            if self.formats is not None and fmt not in self.formats:
                return f"{arg} is a {FORMAT_NAMES.get(fmt, fmt)} team, and I don't play that format here."
            try:
                sets = self.resolve(spec, fmt)
            except UnknownTeam:
                return f"I don't know a team called {arg}."
            except Exception as e:
                return f"Couldn't load that team for {FORMAT_NAMES.get(fmt, fmt)} ({type(e).__name__}): {str(e)[:200]}"
            if fmt == MC:
                p.team_spec, p.team_label = spec, label
            else:
                p.format_teams[fmt] = {"spec": spec, "label": label}
            self._set_drill(p, fmt, [], [])
            self.save()
            return f"Next {FORMAT_NAMES.get(fmt, fmt)} games I'll play {label}: {', '.join(s['species'] for s in sets)}."
        return f"Unknown command .{cmd}. {HELP}"


def log_notes(path: Path, room: str, user: str, lines: list[str]) -> None:

    with open(path, "a", encoding="utf8") as f:
        f.write(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "room": room, "user": to_id(user), "notes": lines}) + "\n")



PRACTICE = {"url": "ws://127.0.0.1:8000/showdown/websocket", "username": "PracticeBot",
            "rotation": "LO-25,BR-30,handmade_teams/LO-14b.txt,FR-25,LO-33",
            "logs": "trainer/runs/buddy_logs", "results": "trainer/runs/buddy_results.jsonl", "notes": "trainer/runs/buddy_notes.jsonl",
            "profiles": "trainer/runs/buddy_profiles.json", "out": "trainer/runs/buddy_host.out", "pid": "trainer/runs/buddy_host.pid",
            "drain": "trainer/runs/BUDDY_DRAIN"}


def practice_command(root: Path) -> list[str]:



    import sys
    from .core.bundle import _pins, path as pinned
    from .core.models import newest_checkpoint
    ckpt = Path(newest_checkpoint())
    head = pinned("opp_head")
    P = PRACTICE


    cmd = [sys.executable, "-u", str(root / "trainer/scripts/buddy_host.py"), "--port", "8000", "--username", P["username"],
           "--checkpoint", str(ckpt), "--team", _rotation(), "--buddy-profiles", str(root / P["profiles"]),
           "--buddy-notes", str(root / P["notes"]),
           "--logs", str(root / P["logs"]), "--results", str(root / P["results"]), "--drain-file", str(root / P["drain"]),
           "--search-arms", _pins()["search_arm"]["name"], "--reply-temps", "1", "--lead-arms", "v3", "--device", pick_device().type, "--max-battles", "2", "--join-rooms", "lobby",
           "--reply-policy", str(pinned("reply_policy")), "--foe-preview", str(pinned("preview_head"))]


    from vgc_trainer.showdown.live_search import SEARCH_ARMS
    if head.exists() and SEARCH_ARMS.get(_pins()["search_arm"]["name"], {}).get("opp_head"):
        cmd += ["--opp-head", str(head)]
    return cmd


def _rotation() -> str:


    from vgc_trainer.showdown.teams import load_team
    try:
        for t in PRACTICE["rotation"].split(","):
            load_team(t)
    except ValueError:
        return ""
    return PRACTICE["rotation"]


def practice_env() -> dict:
    return dict(os.environ, PYTHONIOENCODING="utf-8")


def disagreements(agent, log_lines: list[str], user: str, k: int = 3) -> list[str]:


    from .core.analysis import policy_view
    from .core.positions import walk
    from .core.replay import load_replay
    log = load_replay("\n".join(log_lines))
    side = log.side_of(user)
    if side is None:
        return []
    found = []
    for d in walk(log, side):
        view = policy_view(agent, d)
        for s in view["slots"]:
            if not s or "played_p" not in s or not s["top"]:
                continue
            top_label, top_p = s["top"][0]
            ratio = s["played_p"] / max(top_p, 1e-9)
            if ratio < 0.35:
                found.append((ratio, f"T{d.turn} {s['mon']}: you played {s['played']} ({s['played_p']:.0%}); "
                                     f"model preferred {top_label} ({top_p:.0%})"))
    found.sort()
    return [line for _, line in found[:k]]




def _server_up(port: int = 8000) -> bool:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False





SERVER = {"dir": "trainer/runs/buddy_server", "pid": "trainer/runs/buddy_server.pid", "out": "trainer/runs/local_showdown.out"}


def _detached() -> dict:




    import subprocess
    return ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == "nt"
            else {"start_new_session": True})


def _kill_tree(pid: int) -> None:
    import subprocess
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, **NO_WINDOW)
    else:
        import signal
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except OSError:
            pass


def _pid_from(f: Path) -> int | None:
    try:
        pid = int(f.read_text().strip())
    except (OSError, ValueError):
        return None
    return pid if _pid_alive(pid) else None


def server_pid(root: Path) -> int | None:

    return _pid_from(root / SERVER["pid"])


def start_server(root: Path, wait: float = 45) -> str | None:

    import shutil
    import subprocess
    if _server_up():
        return None
    d = root / SERVER["dir"]
    if not (d / "dist/config/formats-showdown.js").exists():
        return "The local buddy server isn't built yet: run `bash tools/buddy/make_server.sh` once (it needs Node.js)."
    node = shutil.which("node")
    if not node:
        return "The local buddy server needs Node.js (nodejs.org), and `node` isn't on this PC's PATH."


    for sub in ("logs/repl", "logs/chat", "logs/modlog", "config/chat-plugins", "config/ladders", "config/avatars"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    out = open(root / SERVER["out"], "a", encoding="utf8")
    out.write(f"=== started from the Buddy page {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    out.flush()
    p = subprocess.Popen([node, "pokemon-showdown", "start", "--skip-build", "8000"], cwd=d, stdout=out, stderr=subprocess.STDOUT,
                         **_detached())
    (root / SERVER["pid"]).write_text(str(p.pid))
    t0 = time.monotonic()
    while time.monotonic() - t0 < wait:
        if _server_up():
            return None
        if p.poll() is not None:
            break
        time.sleep(0.5)
    return f"The local buddy server didn't come up (see {SERVER['out']})."


def stop_server(root: Path) -> str:
    pid = server_pid(root)
    if not pid:
        return "No local buddy server started from here is running."
    _kill_tree(pid)
    (root / SERVER["pid"]).unlink(missing_ok=True)
    return "Local buddy server stopped."


def _pid_alive(pid: int) -> bool:
    import subprocess
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, **NO_WINDOW).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def practice_pid(root: Path) -> int | None:

    return _pid_from(root / PRACTICE["pid"])


def start_practice(root: Path) -> str:
    import subprocess
    if practice_pid(root):
        return "The practice bot is already running."
    missing = start_server(root)
    if missing:
        return missing
    (root / PRACTICE["drain"]).unlink(missing_ok=True)
    (root / PRACTICE["logs"]).mkdir(parents=True, exist_ok=True)
    out = open(root / PRACTICE["out"], "a", encoding="utf8")
    out.write(f"=== started from the Buddy page {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    out.flush()

    p = subprocess.Popen(practice_command(root), cwd=root, stdout=out, stderr=subprocess.STDOUT, env=practice_env(), **_detached())
    (root / PRACTICE["pid"]).write_text(str(p.pid))
    return f"Practice bot starting as {PRACTICE['username']} (it takes ~20 s to load and log in)."


def stop_practice(root: Path) -> str:
    pid = practice_pid(root)
    if not pid:
        return "The practice bot isn't running."
    _kill_tree(pid)
    (root / PRACTICE["pid"]).unlink(missing_ok=True)
    with open(root / PRACTICE["out"], "a", encoding="utf8") as f:
        f.write(f"=== stopped from the Buddy page {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    return "Practice bot stopped."


def save_settings(root: Path, user: str, team: str, rotation: bool, sheets: bool, lead: list[str] | None = None,
                  back: list[str] | None = None, fmt: str = MC, drills: dict[str, tuple[list[str], list[str]]] | None = None) -> list[str]:



    user = user.strip()
    if not to_id(user):
        return ["Enter the name you use on the local Showdown server."]
    b = Buddy(root / PRACTICE["profiles"])
    msgs = []
    if rotation:
        msgs.append(b.handle(user, ".team default"))
    elif team.strip():
        msgs.append(b.handle(user, ".team " + ("" if fmt == MC else fmt + " ") + team.strip()))
    msgs.append(b.handle(user, ".sheets " + ("on" if sheets else "off")))
    if drills is None and lead is not None:
        drills = {MC: (lead, back or [])}
    for dfmt, (dlead, dback) in (drills or {}).items():
        if rotation or (team.strip() and dfmt == fmt):
            continue
        dlead = [x for x in dlead if x]
        dback = [x for x in (dback or []) if x]
        now_lead, now_back = b.drill_for(user, dfmt)
        pre = "" if dfmt == MC else dfmt + " "
        if not dlead:
            if now_lead:
                msgs.append(b.handle(user, f".lead {pre}off"))
        elif dlead != now_lead or dback != now_back:
            msgs.append(b.handle(user, f".lead {pre}" + ", ".join(dlead)))
            if len(dlead) == 2:
                msgs.append(b.handle(user, f".back {pre}" + ", ".join(dback)) if dback else b.handle(user, f".back {pre}off"))
    return [m for m in msgs if m]


def _jsonl(path: Path, last: int) -> list[dict]:
    try:
        rows = [json.loads(ln) for ln in path.read_text(encoding="utf8").splitlines() if ln.strip()]
    except OSError:
        return []
    return rows[-last:]


def page_data(root: Path, who: str = "") -> dict:


    P = PRACTICE
    pid = practice_pid(root)
    try:
        tail = (root / P["out"]).read_text(encoding="utf8", errors="replace").splitlines()[-8:]
    except OSError:
        tail = []
    b = Buddy(root / P["profiles"])
    profiles = []
    for u, p in sorted(b.profiles.items()):
        try:
            six = [s_["species"] for s_ in b.resolve(p.team_spec)] if p.team_spec and not p.team_spec.startswith("bucket:") else []
        except Exception:
            six = []

        drill_rows = []
        for f in [MC, *sorted(p.format_teams)]:
            spec = b.spec_for(u, f)
            if not spec or spec.startswith("bucket:"):
                continue
            try:
                six_f = six if f == MC else [s_["species"] for s_ in b.resolve(spec, f)]
            except Exception:
                continue
            if six_f:
                dl, db = b.drill_for(u, f)
                drill_rows.append({"fmt": f, "name": FORMAT_NAMES.get(f, f), "six": six_f, "lead": dl, "back": db})
        profiles.append({"user": u, "team": b.label_for(u), "pasted": (p.team_spec or "").startswith("text:"), "sheets": p.sheets,
                         "games": p.games, "six": six, "lead": p.lead, "back": p.back, "drill_rows": drill_rows,
                         "others": [(FORMAT_NAMES.get(f, f), t["label"]) for f, t in sorted(p.format_teams.items())]})
    notes = {r["room"]: r["notes"] for r in _jsonl(root / P["notes"], 500)}
    try:
        cmd = " ".join(f'"{c}"' if " " in c else c for c in practice_command(root))
    except Exception as e:
        cmd = f"(can't build the command: {type(e).__name__}: {e})"
    from . import buddy_sessions
    from .core.buckets import default_spec
    users = sorted({u for cfg in buddy_sessions.BOTS.values() for u in Buddy(root / cfg["profiles"]).profiles})
    games = []
    for r in buddy_sessions.recent_games(root, 30, who):
        games.append({"time": r["time"][5:16], "room": r["room"], "opponent": r["opponent"], "bot": r["bot"], "bot_label": r["bot_label"],
                      "team": r.get("team") if r.get("team") not in (None, "?") else "their pick",
                      "result": "-" if r["won"] is None else (f"{r['opponent']} won" if r["won"] else "bot won"),
                      "turns": r.get("turns"), "notes": notes.get(r["room"], None), "series": r.get("series"), "game": r.get("game"),
                      "sessions": r["sessions"], "other_sessions": r["other_sessions"]})
    return {"sessions": buddy_sessions.listing(root), "session_bots": buddy_sessions.BOTS, "session_users": users,
            "who": who, "players": buddy_sessions.players(root),
            "server_up": _server_up(), "running": pid is not None, "pid": pid, "tail": tail, "profiles": profiles,
            "games": games, "bot": P["username"], "command": cmd, "rotation": _rotation(), "default_bucket": bool(default_spec()),
            "formats": [(MC, "Reg M-C")] + [(f, SHOWDOWN_NAMES.get(f, f)) for f in [*YEAR_FORMATS.values(), *SV_REGS.values()]]}
