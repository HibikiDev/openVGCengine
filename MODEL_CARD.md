# Model card

The models openVGCengine ships. Exact files and hashes for a build are in `models/manifest.json` and `bundle.json`.

## The three models

| File | What it does | Trained on |
|---|---|---|
| `ckpt_<update>.pt` | **The policy.** Picks the four to bring, the leads, and every turn's moves and switches, and estimates who is winning. About 5.6M parameters, plus a 0.8M preview network. | Self-play only: reinforcement learning (PPO) on the engine, against a league of its own earlier versions and fixed opponents, over more than 1.5 billion games. No human games. |
| `reply_policy.pt` | **The reply model.** Predicts what a human would click, so the search plans against people. Same network, fine-tuned. | About 2.2 million decisions from public Showdown replays of Reg M formats. |
| `preview_head.pt` | **The preview model.** Predicts which four a human opponent brings. | Team previews from the same public replays. |

## Formats

Every VGC format Showdown offers from VGC 2013 on, except Champions Reg M-A and M-B. Reg M-C has had the most training. The older formats and Scarlet / Violet were added later and have had less.

## What it's for

Practice and study: testing teams, reviewing games, and playing against it on your own computer. It isn't for playing on Showdown's ladder or servers, which breaks Showdown's rules. See Fair play in the README.

## Limits

- **Win rates are the model playing both sides.** They're a strong signal for how teams match up when both sides play well, not a promise of how a game against a person goes. A team the model pilots well can look better than it would in your hands, and vice versa.
- **Win estimates are for spotting swings.** They aren't calibrated probabilities.
- **It has blind spots.** It learned by playing itself, so it can underrate lines that it rarely sees. Treat a surprising verdict as a question to look into.
- **The reply model was fit on Reg M games.** It's also used in older formats' open-sheet search. In a test on Reg I, a model fit on that format's games predicted people better but didn't play better.
- **Closed team sheets rest on a guess.** There the search plays against the likeliest sets given what has been revealed, and a real opponent's set can differ.
- **Replays without team sheets are approximate.** The Analyzer fills in the sets, and says so on the page.

## Data and privacy

The replays used were public. Player names, chat and teams aren't in the models or the set data, which holds counts only. The usage statistics in `data/smogon-usage/` are Smogon's; see THIRD_PARTY_NOTICES.

## Licence

The code and the model weights are MIT-licensed. See LICENSE.
