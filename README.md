# openVGCengine

A VGC battle engine, a neural network that learned to play VGC on it by playing itself, and a desktop toolkit built around
the two: test a team against a field, study matchups and brings, review replays, and practise against the bot on your own computer.

> **Early version.** Expect rough edges, and tell me about them (see [Bugs and feedback](#bugs-feedback-and-updates)).

- [What's inside](#whats-inside)
- [The model](#the-model)
- [The tools](#the-tools)
- [The training buddy](#the-training-buddy)
- [Fair play](#fair-play)
- [Installing the release package](#installing-the-release-package)
- [Building from source](#building-from-source)
- [Pokémon icons (optional)](#pokémon-icons-optional)
- [What it connects to](#what-it-connects-to)
- [Bugs, feedback and updates](#bugs-feedback-and-updates)
- [Supporting the project](#supporting-the-project)
- [Credits and licence](#credits-and-licence)

## What's inside

| Part | What it is |
|---|---|
| **Engine** (`crates/`) | A battle simulator in Rust: a port of [Showdown](https://github.com/smogon/pokemon-showdown)'s, checked against Showdown battle by battle (same random rolls, same result at every step). It plays thousands of games a second. |
| **Model** (`trainer/`; the weights are on the [Releases page](https://github.com/HibikiDev/openVGCengine/releases)) | The neural network that plays: picks the four to bring, the leads, and every turn's moves and switches. |
| **Tools** (`suite/`) | A desktop app on top of the model: team testing, matchup and bring analysis, replay review. |
| **Training buddy** | The bot as a practice partner on a Showdown server running on your own computer. |

**Formats.** Every VGC format Showdown offers from VGC 2013 on - Gens 5 to 8, the Scarlet / Violet regulations and Champions -
except Champions Reg M-A and M-B, which aren't supported yet. Every tool and the training buddy play them all (pick one in the
Format box; the current regulation, **Champions VGC 2026 Reg M-C**, is the default). Formats with closed team sheets (VGC
2013-2022) have a Team sheets switch: closed, as played, or open, with OTS information.

## The model

**How it learned.** By playing: a great many games on the engine, improving with reinforcement learning (PPO) against a league of
its own earlier versions and fixed opponents, so it doesn't overfit to one style. This network, the one that chooses the moves, was never trained to copy human play: its
choices are its own. Two smaller models that help it are trained on public Showdown replays, to predict what humans do: see below.

**What it sees.** Everything a player at the table could know: both team sheets (open team sheets where the format has them; in
closed-sheet formats, its best guess of the opponent's sets from usage statistics), the field, both sides' active and benched
mons, and the recent turns. A transformer network reads that and scores every legal action: moves with their targets, switches,
and the format's gimmick (Mega Evolution, Z-Moves, Dynamax, Terastallization). The second slot's choice is made knowing the first's,
so the two coordinate.

**How it decides a turn.** It doesn't just take the network's favourite. It searches one turn ahead: its best few candidate plays
against the replies a human would likely make, each played out a little further on the engine, and picks the play that holds up best.
The replies come from a second model trained on public Showdown replays to predict what human players do - so the bot plans against
people, not against itself. A third model predicts which four a human opponent brings.

**What its numbers mean.** A win rate in these tools is the model playing *both* sides: a strong signal for how teams and brings
match up when both sides play well, not a guarantee of how a game against a person goes. A team the model pilots well can look
better than it would in your hands, and vice versa.

For what the models are, how they were trained and where they fall short, see the [model card](MODEL_CARD.md).

## The tools

Open the app and pick a tab. Every tool takes teams as a pasted Showdown export, a [pokepast.es](https://pokepast.es) link, or a
**bucket** (below).

**Open team sheets work as they are.** A team needs no EVs: the tools, the buckets and the training buddy all take a paste with just
the moves, items and abilities. A set without a spread gets its species' most used one from the usage stats, under its nature if the
paste shows one, and a set with its own spread keeps it. So you can drop in a team from a public team sheet and test against it straight
away. Real spreads are more exact when you know them.

| Tool | What it does | Use it for |
|---|---|---|
| **Team Lab → Team Deep Dive** | Your team against a field of teams, many games each: your score per opponent, and per opponent the brings that work (which four, which two lead, what they bring back). | "Is this team ready for the event?", finding your weak matchups and what to bring into them. A brings sheet to print for your own study (Print / Save as PDF) - homework before an event, not something to use during play. |
| **Team Lab → Change a slot** | Tries replacements for one team member - your own candidates or the most used ones - and ranks them by how the team does. | Fixing a weak slot, finding a sixth. |
| **Battle Lab → Head-to-head** | Two teams against each other: who wins, which brings and leads work, turn-1 plans. | Preparing one specific matchup. |
| **Battle Lab → Play-out** | Two teams with the brings and leads you choose; the bot plays turn 1 or whole games, a few times. | "What happens if I lead this into that?" |
| **Battle Lab → Series vs a field** | Best-of-three series against every team of a field, as real games to replay. | Studying games, not just numbers. |
| **Battle Lab → Preview Advisor** | Two teams in, a bring-and-lead plan out: what to bring, what they'll likely bring, how it plays. | Team preview decisions. |
| **Battle Lab → Line Crawler** | One game, turn by turn: you pick both sides' moves with the bot's view of each, and keep every branch. | Exploring a line; "what if they had switched?" |
| **Replays → Analyzer** | A replay turn by turn, with where the model would have played differently and how likely it thought each option was. Takes a replay link, a downloaded replay, or anything you drop into the install's `replays` folder. | Reviewing your own games. |
| **Buckets** | Named, saved sets of teams - say, the field you expect at an event - each weighted by how often you expect it. Open team sheets are enough: no EVs needed. | The "against" field for the Deep Dive, Series, the buddy. |
| **Buddy** | The training buddy's control panel (below). | Practice. |

**Quick and searched modes.** Most tools have a fast mode (the network's instinct, thousands of games in seconds) and a searched
mode (every game played the way the bot plays for real, with its search - slower, and more trustworthy for close matchups).
Searched modes want a GPU: without one the app says so, and they start switched off.

## The training buddy

The bot as a practice partner, on a Showdown server that runs on your own computer - nobody else can see or join it. It plays every
buddy format with its full search (on a GPU or the CPU), with the standard VGC timer.

Reg M-C works straight away: until you pick a team, the bot plays one from the **Default** bucket, three regional-winning teams
that come with the app. You can edit or delete that bucket like any other.

1. **Set it up** - in the app, **Buddy -> Your practice settings**: the name you'll use on the local server, the team the bot plays
   and the format it's for (one team per format: a pasted Showdown export, with or without EVs, a pokepast.es link, or `bucket:<name>`
   for a bucket of that format's teams drawn by weight each game), and open or closed team sheets. Optional, per format: the **lead drill**: the bot
   always leads two mons you pick (and brings the back two you pick), to practise one matchup.
2. **Start practice bot** - the local server and the bot start.
3. **Play** - **Open Showdown** on the Buddy page opens the local Showdown in its own window (Showdown's own client page; it needs
   the internet), use the same name, and challenge **PracticeBot** in one of the "... buddy" formats, e.g. "[Gen 9 Champions] VGC 2026 Reg M-C buddy" (Bo1 or Bo3).
4. **Review** - every game is listed under **Recent practice games** with a link to its page: the whole game, turn by turn, and
   **Open in the Replay Analyzer** for where the model would have played differently and how likely it thought each option was.

If you use your regular Showdown name, it asks for your password: Showdown's client checks registered names against the real Showdown servers, even on the local server. You can always use a name that isn't registered instead.

**Practice sessions.** Group a block of games: **Start a session** on the Buddy page (your name, a name for the session), play,
**end** it. The session page shows your record, the leads and mons on both sides, and every game with its link. Games can be added
to or taken out of a session afterwards, and an ended session resumed.

## Fair play

openVGCengine is for practice and study, on your own machine. This release has **no** way to play on Showdown's servers or ladder:

- the buddy's client connects only to a server on your own computer (it refuses any other address), and only in the "... buddy"
  formats, which exist only on the bundled server;
- it identifies itself, so a modified copy pointed at a public server is easy to
  tell apart.

Letting a bot play rated games for you breaks Showdown's rules - please don't.

## Installing the release package

### Windows

**You need:** Windows 10 or 11 (64-bit), ~4 GB of disk, and an internet connection during setup. A GPU makes the searched tools much
faster:

| GPU | What setup installs |
|---|---|
| NVIDIA (GTX 16xx / RTX 20xx and newer) | the CUDA build - driver 580 or newer needed for RTX 50-series cards |
| Intel Arc / Core Ultra graphics | the Intel GPU build (experimental) |
| AMD Radeon | the CPU build. RX 7000 / 9000 series and Ryzen AI graphics can try AMD's own GPU build (experimental: about 4 GB to download, 9 GB on disk): see below |
| none | the CPU build: every tool works, searched modes are much slower |

**Steps:**

1. Download `openVGCengine-<version>-win64.zip` from the [Releases](https://github.com/HibikiDev/openVGCengine/releases) page and
   extract it to a folder of its own (e.g. `Documents\openVGCengine`).
2. Double-click **`setup.cmd`**. It installs a private copy of Python and everything the app needs inside that folder - nothing
   system-wide - then checks the result and adds **openVGCengine** to the Start menu. With an NVIDIA GPU it downloads ~2 GB.
   Windows may warn that the app is from an unknown publisher (it isn't code-signed): *More info → Run anyway*.
3. Start **openVGCengine** from the Start menu.

**If something doesn't start:** run `openVGCengine (console).cmd` in the folder - it does the same with a window that shows the error.
To force the small CPU build (or another build), set `OPENVGC_TORCH_BUILD=cpu` (`cu130`, `cu126`, `xpu`, `rocm`) before running setup; updates keep your choice. For AMD's GPU build, open a Command Prompt
in the folder and run `set OPENVGC_TORCH_BUILD=rocm`, then `setup.cmd`. If the build can't run on your card, setup falls back to the CPU build.

**Updating:** *About & updates* (bottom of every page) → *Check for updates*. If a new version is out: *Download update*, then *Restart and update*. The app closes, updates itself and
reopens, usually in about a minute. Your buckets, runs and practice games stay, and if anything goes wrong it goes back to the version you had.

To update by hand: download the new zip, extract it over the old folder (your buckets and runs are kept), then run `setup.cmd` again.

**Uninstalling:** double-click **`uninstall.cmd`** in the folder. It asks first, then stops the app, removes the Start-menu entry and
deletes the folder, including your buckets, saved runs and practice games, plus the small `.openvgcengine` folder in your user folder
where the app window keeps its settings. Nothing else on your PC is changed.

### macOS

**You need:** a Mac with Apple silicon (M1 or newer) and an internet connection during setup (about 150 MB). Intel Macs aren't
supported: PyTorch has no Intel-Mac build of the version the app needs. The searched tools use the Mac's GPU.

**Steps:**

1. Download `openVGCengine-<version>-macos-arm64.zip` from the [Releases](https://github.com/HibikiDev/openVGCengine/releases)
   page, extract it and put the folder where it will stay (e.g. Documents). Moving it after setup breaks the installed Python; if
   you do move it, run the setup again.
2. Run the setup once. It installs everything inside that folder, nothing system-wide. The app isn't signed by Apple yet, so macOS
   blocks the first start. The easiest way on every macOS version: open Terminal (Applications → Utilities), type `bash` and a
   space, drag **`setup.command`** from the folder into the Terminal window and press Return.
   Or double-click it, then on macOS 15 and later go to *System Settings → Privacy & Security → Open Anyway*; on macOS 14 and earlier
   right-click it → *Open*.
3. Double-click **`openVGCengine.command`** to start the app. A Terminal window shows the app's log: keep it open while you use the
   app, closing it quits the app. Tip: drag the file to the Dock.

The folder's `START HERE (Mac).txt` has the same steps.

**If something doesn't start:** the text in the Terminal window is what helps, so copy it into your bug report.

**Updating:** *About & updates* (bottom of every page) → *Check for updates*. If a new version is out: *Download update*, then *Restart and update*. The app closes, updates itself and
reopens, usually in about a minute. Your buckets, runs and practice games stay, and if anything goes wrong it goes back to the version you had.

To update by hand: extract the new zip somewhere else, then merge it over the old folder in Terminal with `ditto`, followed by the new folder and the old one (type `ditto` and a
space, drag in each folder, press Return). Don't replace the folder in Finder: that deletes your buckets and runs. Then run `setup.command` again.

**Uninstalling:** drag the folder to the Bin. That includes your buckets, saved runs and practice games. The app window also keeps its
settings in a small hidden `.openvgcengine` folder in your home folder, which you can delete too. Nothing else on your Mac is changed.

### Linux

Build from source for now (below); a package is planned.

## Building from source

**Prerequisites:** git, Python 3.13, Rust (the version in `rust-toolchain.toml`; [rustup](https://rustup.rs) picks it up),
Node.js 22.18 or newer (the engine's data generation, team validation and the buddy server use it), and bash (Git Bash on Windows).

```sh
git clone https://github.com/HibikiDev/openVGCengine
cd openVGCengine

# 1. Showdown at the version the engine ports (vendor/ - not part of this repo)
git clone https://github.com/smogon/pokemon-showdown vendor/pokemon-showdown
git -C vendor/pokemon-showdown checkout 3661ce40bf9001d185ce078b8920e12304204609     # SHOWDOWN_PIN.md
(cd vendor/pokemon-showdown && npm ci --omit=dev && node build)

# 2. Python: PyTorch first, in the build for your GPU (the table below - here CUDA 13.0), then the rest
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install torch==2.14.0 --index-url https://download.pytorch.org/whl/cu130
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"   # e.g. 2.14.0+cu130 True
pip install -r requirements/app.txt                      # numpy, jinja2, websockets, pywebview (torch already there)
pip install -r requirements/dev.txt                      # maturin, pytest

# 3. The engine (a Python extension, built with maturin)
(cd crates/engine-py && maturin build --release -o ../../target/wheels)
pip install target/wheels/vgc_engine-*.whl

# 4. The models: the models zip from the Releases page, unzipped here (it fills models/ - suite/pins.json points there - and the
#    closed-sheet set data; without that data the bot plays closed-sheet formats, VGC 2013-2022, on its network alone)

# 5. The buddy's local Showdown server (only the buddy formats, 127.0.0.1 only)
bash tools/buddy/make_server.sh vendor/pokemon-showdown trainer/runs/buddy_server

# 6. Run it
python suite/web/app.py            # the desktop window
python suite/web/server.py         # or the same in your browser at http://127.0.0.1:8765
```

**Which PyTorch build** (the `--index-url` in step 2; the Windows package's setup picks it the same way):

| Your GPU | Index | Notes |
|---|---|---|
| NVIDIA, driver 580 or newer (`nvidia-smi` shows it) | `.../whl/cu130` | RTX 20xx through 50xx |
| NVIDIA, older driver | `.../whl/cu126` | no RTX 50-series - update the driver instead |
| Intel Arc / Core Ultra graphics | `.../whl/xpu` | experimental (fp32) |
| AMD Radeon on Linux | `.../whl/rocm7.2` | experimental; shows as `cuda` |
| AMD on Windows (RX 7000 / 9000, Ryzen AI) | AMD's own index: `pip install "torch[device-all]==2.14.0+rocm10.1.0" --index-url https://stable.repo.amd.com/rocm/whl-next/` | experimental, not yet run on a Radeon; shows as `cuda` |
| Other AMD on Windows, or no GPU | `.../whl/cpu` | every tool works; searched modes are much slower |
| macOS | none: `pip install torch==2.14.0` | Apple GPUs via MPS |

The check line should print `True` for an NVIDIA or AMD build (Intel: `torch.xpu.is_available()`). The app picks the device itself
(CUDA, then Intel, then Apple, then the CPU) and says on the page when it runs on the CPU.

On Linux the desktop window needs a GUI backend for pywebview (`pip install "pywebview[qt]"`); without one, use `server.py`.

**Checking the engine against Showdown:** `bash tools/diff/scripts/verify.sh <tag>` replays a regression corpus and 1,000 random
battles in both simulators and compares every step (the same check every engine change passes).

## Pokémon icons (optional)

The pages can show a small icon next to each Pokémon's name. None are included, so you bring your own images.
Put them in the **`sprites`** folder of the install (from source: `sprites/` at the repo root, which git ignores), each
file named after the Pokémon it shows - `charizard.png`, `Charizard-Mega-X.png`, Showdown's sprite names like `charizard-megax.png`,
or a dex number with forme words like `0006-Mega_X.png`. The folder's `README.txt` has the details. Without images the pages show names only. The icons
never leave your computer.

## What it connects to

Only when you ask:

| When | Where |
|---|---|
| Setup | python-build-standalone (via uv), PyPI and PyTorch's package index |
| You import a replay by URL | replay.pokemonshowdown.com |
| You save a bucket with pokepast.es links | pokepast.es |
| "Check for updates" | api.github.com |
| You open Showdown from the Buddy page | play.pokemonshowdown.com |
| You pick a registered name there | Showdown's login server, as any Showdown client does |

Nothing is sent about you or your teams; there is no telemetry.

## Bugs, feedback and updates

- **Report a bug:** *Report a bug* (bottom of every page) shows my address - **openvgcengine@gmail.com** - and a block of
  technical details (versions, your GPU, the last error) you can copy into your report after reading it. Or open a
  [GitHub issue](https://github.com/HibikiDev/openVGCengine/issues).
- **Updates:** *About & updates → Check for updates*.

## Supporting the project

openVGCengine is entirely free to use. The [Patreon](https://www.patreon.com/cw/openVGCengine) is there to support its ongoing
development, and it is entirely optional.

## Credits and licence

- **[Pokémon Showdown](https://github.com/smogon/pokemon-showdown)** (MIT) - the engine is a port of its simulator, and the buddy
  runs a copy of its server.
- **[Smogon](https://www.smogon.com/stats/)** - the usage statistics that ship in `data/smogon-usage/` are theirs, from Showdown's ladder
  games, shipped so each user needn't download them.
- **Fonts:** Fredoka and Nunito (SIL Open Font License).

openVGCengine's code and model weights are MIT-licensed ([LICENSE](LICENSE)); third-party terms are in
[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES). Pokémon and all related names are trademarks of Nintendo, Game Freak and Creatures Inc. /
The Pokémon Company; this is an unofficial fan project, not affiliated with or endorsed by them.
