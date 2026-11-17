# gta6-twitch-ccu-forecast-01

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/asenamapr/gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/asenamapr/gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Hour-by-hour forecast of GTA VI's launch-day Twitch viewers: a log-space quantile model fitted at run time from past big launches' release-day shapes, anchored on the pre-midnight level.

## How it works

Past big launches show one robust shape: the UTC release day's first hour (00:00–01:00Z) usually sits below the previous evening's level — New Zealand, Australia and Japan are already playing, Europe is about to unlock, the US has not — then viewership climbs as the US unlocks (05:00Z east coast, 08:00Z west coast) and peaks in the US afternoon. So the level is anchored on the pre-midnight median (the median hourly count of the six hours before midnight), not on the hour-1 print alone, and the shape is the median log-ratio to that anchor across comparable launches, with the spread from the same comparables' dispersion (IQR / 1.349). Two guards keep the anchor honest: if hour 1 is already at or above the pre-midnight level (no midnight dip), hour 1 itself is the anchor; and comparables are filtered to the same launch structure as GTA VI — a paid, console, rolling-midnight-local launch, excluding early-access-contaminated launches, weak analogues, single simultaneous global unlocks, pre-release network-test days, multiplayer-beta launches, and categories whose hour-1 count is under 5,000.

## Validation

Walk-forward on the kit's four practice cases (Marvel's Wolverine, Red Dead Redemption 2, God of War Ragnarök, Marvel's Spider-Man 2 — none of them in the fit set, answers from SullyGnome's published hourly averages): mean pinball loss **0.197** against the house persistence baseline's **0.387**. Leave-one-out over the filtered comparables: **0.272** vs a **0.417** baseline. Any failure inside the model falls back to the persistence baseline, so the entry always writes a valid forecast.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=7fvg7vmm&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
