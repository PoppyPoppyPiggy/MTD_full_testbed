# MTD RL training and evaluation quickstart

## How to launch PPO training
Run from the repository root so module imports resolve correctly:

```bash
python -m dvd_lite.dvd_attacks_lpc.mtd.rl_train_v05 \
  --seeker-level 2 \      # attacker difficulty (0-3)
  --total-episodes 2000 \  # number of training episodes
  --max-steps-per-episode 1000 \  # rollout horizon per episode
  --learning-rate 3e-4 \   # actor/critic optimizer lr
  --hidden-size 128 \      # MLP width
  --gamma 0.99 \           # discount factor
  --gae-lambda 0.95 \      # GAE λ
  --clip-coef 0.2 \        # PPO clipping coefficient
  --ppo-epochs 10 \        # policy update epochs per batch
  --minibatch-size 64 \    # minibatch size during PPO update
  --ent-coef 0.01 \        # entropy bonus
  --vf-coef 0.5 \          # value loss weight
  --metric-window-size 50 \# rolling average window for logs
  --wandb-project "mtd_rl_v06_comparison" \  # set to empty to disable WandB
  --run-name "ppo_v06_l2"  # tensorboard/WandB run name
```

Key behavior:
* `NetworkEnv.max_episode_steps` is set from `--max-steps-per-episode` and each episode optionally samples a random seeker level when `--train-all-seeker-levels` is passed.【F:dvd_lite/dvd_attacks_lpc/mtd/rl_train_v05.py†L75-L119】
* Training logs emit both episode rewards and the Defense/Attack/Time/DRS metric namespace plus rolling-window variants (key prefix `Window/`).【F:dvd_lite/dvd_attacks_lpc/mtd/rl_train_v05.py†L159-L219】
* Final artifacts include `final_policy.pth` and `norm_metadata.json` under `--log-dir/--run-name`.【F:dvd_lite/dvd_attacks_lpc/mtd/rl_train_v05.py†L221-L243】

## Metric names and formulas (evaluation ↔ training)
Metrics are produced by `MtdScorer.compute_epoch_metrics` and mirrored in training logs. All terms use counts from the episode info records.

### Defense metrics
* **Defense/R_succ**: breach stop rate, `1 - (#breach_success / #breach_attempt)`. Zero when no breach attempts occur.【F:dvd_lite/dvd_attacks_lpc/mtd/mtd_scoring.py†L108-L125】
* **Defense/C_def**: average defense cost per step, `total_cost / total_steps` (same as `C_def`).【F:dvd_lite/dvd_attacks_lpc/mtd/mtd_scoring.py†L127-L134】
* **Defense/CostPerBlock**: defense cost per thwarted action, `total_cost / (block_exploit + block_breach + decoy_hits)`.【F:dvd_lite/dvd_attacks_lpc/mtd/mtd_scoring.py†L136-L143】
* **Defense/S_MTD_overall**: combined score `R_succ - 0.1 * C_def` (also emitted as `S_MTD`).【F:dvd_lite/dvd_attacks_lpc/mtd/mtd_scoring.py†L207-L244】

### Attack-stage metrics
* **Attack/r_exploit_success**: exploit success ratio `#exploit_success / #exploit_attempt`. **Attack/r_exploit_block** similarly uses blocked exploits.【F:dvd_lite/dvd_attacks_lpc/mtd/mtd_scoring.py†L145-L159】
* **Attack/r_breach_success** and **Attack/r_breach_block** mirror the exploit definitions for breach attempts.【F:dvd_lite/dvd_attacks_lpc/mtd/mtd_scoring.py†L145-L159】
* **Attack/r_scan**: scan rate per step `#scan / total_steps`; **Attack/r_find**: find success ratio `#find / #scan`.【F:dvd_lite/dvd_attacks_lpc/mtd/mtd_scoring.py†L161-L168】
* **Attack/decoy_lure_rate**: decoy lure efficiency `#decoy / #exploit_attempt`. Also available as `decoy_lure_rate`.【F:dvd_lite/dvd_attacks_lpc/mtd/mtd_scoring.py†L191-L200】

### Time-to-event metrics
* **Time/TTF_mean**: average exposure when a target is found, `sum_exposure_at_find / #find`.【F:dvd_lite/dvd_attacks_lpc/mtd/mtd_scoring.py†L170-L177】
* **Time/TTEB_mean**: exposure until an exploit is blocked, `sum_exposure_at_exploit_block / #exploit_block`.【F:dvd_lite/dvd_attacks_lpc/mtd/mtd_scoring.py†L179-L184】
* **Time/TTBr_mean**: exposure until a breach succeeds, `sum_exposure_at_breach_success / #breach_success` (also aliased as `ttbr`).【F:dvd_lite/dvd_attacks_lpc/mtd/mtd_scoring.py†L186-L200】

### Diversity–Redundancy–Shuffle (DRS)
* **DRS/D_bits**: endpoint diversity entropy `-Σ p_i log2 p_i` over visit frequencies.【F:dvd_lite/dvd_attacks_lpc/mtd/mtd_scoring.py†L202-L214】
* **DRS/R_redundancy**: redundancy score `max(0, #distinct_ports - 1)`; also published as `R` and `R_redundancy`.【F:dvd_lite/dvd_attacks_lpc/mtd/mtd_scoring.py†L216-L230】
* **DRS/S_shuffle**: shuffle frequency `(shuffle_events / total_steps) * log2(#endpoints)`; also available as `S` and `S_shuffle`.【F:dvd_lite/dvd_attacks_lpc/mtd/mtd_scoring.py†L232-L244】

### Policy and seeker averages
* **Policy/ip_cd_mean**, **Policy/decoy_ratio_mean**, **Policy/bl_level_mean**: averages of the MTD meta-actions seen in the episode.【F:dvd_lite/dvd_attacks_lpc/mtd/mtd_scoring.py†L246-L258】
* **Seeker/attack_bias_mean**, **Seeker/scan_effort_mean**: averages of seeker aggressiveness parameters when present.【F:dvd_lite/dvd_attacks_lpc/mtd/mtd_scoring.py†L260-L270】
* **System/alternate_node_health** and **System/service_uptime_ratio** track averaged health and uptime where provided.【F:dvd_lite/dvd_attacks_lpc/mtd/mtd_scoring.py†L272-L288】

## Attack scripts, monitors, and scenarios at a glance
* **Attack orchestration**: `attack_orchestrator.py` resolves current MTD routing targets from `mtd/shared_state/mtd_state.json`, then launches shell attack scripts for a timed duration, recording events to `bus/bus.log`. It supports list/start/stop commands and falls back to Docker inspection to resolve target IPs when MTD state is missing.【F:dvd_lite/dvd_attacks_lpc/attack_orchestrator.py†L1-L120】
* **Monitoring bundle**: `run_monitors.py` starts telemetry, network, QoS, system, and container monitors in parallel with a shared `PYTHONPATH` so modules import cleanly, and terminates them as a group on shutdown signals.【F:dvd_lite/dvd_attacks_lpc/run_monitors.py†L1-L82】
* **Scenario playlist**: `scenarios/playlist.yml` defines sequential flight and attack actions (boot, takeoff, autopilot routes, then enumerated attack blocks) plus the master `s_cti_data_collection_full` that chains normal flight, multiple attack suites, and post-analysis to trigger the ML pipeline after data capture.【F:dvd_lite/dvd_attacks_lpc/scenarios/playlist.yml†L1-L121】
