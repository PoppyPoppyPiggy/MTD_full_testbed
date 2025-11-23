# dvd_lite/dvd_attacks_lpc/mtd/mtd_config.py
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class NATBackendConfig:
    mode: str = "iptables"  # or "nft"
    nat_table: str = "nat"
    prerouting_chain: str = "PREROUTING"
    mtd_chain: str = "MTD_SERVICE_CHAIN"


@dataclass
class ServiceConfig:
    public_host_ip: str = "127.0.0.1"
    public_port: int = 14550
    protocol: str = "udp"


@dataclass
class ActionDef:
    id: int
    name: str
    type: str  # "DNAT", "BLACKLIST", "CHANNEL_HOP" 등
    target: Optional[str] = None  # 예: "10.13.0.2:14550"
    params: Dict[str, str] = field(default_factory=dict)


@dataclass
class RLConfig:
    action_space_size: int
    observation_dim: int
    state_file: Path
    log_dir: Path


@dataclass
class MTDConfig:
    nat_backend: NATBackendConfig
    service: ServiceConfig
    actions: List[ActionDef]
    state_file: Path
    metrics_log: Path
    cti_status_file: Optional[Path] = None
    rl_config: Optional[RLConfig] = None

    @classmethod
    def load(cls, path: str | Path) -> "MTDConfig":
        path = Path(path)
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        nat_backend = NATBackendConfig(**raw.get("nat_backend", {}))
        service = ServiceConfig(**raw.get("service", {}))
        actions = [ActionDef(**a) for a in raw.get("actions", [])]

        state_file = Path(raw.get("state_file", "mtd/shared_state/mtd_state.json"))
        metrics_log = Path(raw.get("metrics_log", "mtd/shared_state/mtd_metrics.jsonl"))
        cti_status_file = raw.get("cti_status_file")
        if cti_status_file:
            cti_status_file = Path(cti_status_file)

        rl_raw = raw.get("rl", None)
        rl_config = None
        if rl_raw:
            rl_config = RLConfig(
                action_space_size=len(actions),
                observation_dim=rl_raw.get("observation_dim", 16),
                state_file=state_file,
                log_dir=Path(rl_raw.get("log_dir", "mtd/shared_state/rl_logs")),
            )

        return cls(
            nat_backend=nat_backend,
            service=service,
            actions=actions,
            state_file=state_file,
            metrics_log=metrics_log,
            cti_status_file=cti_status_file,
            rl_config=rl_config,
        )

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), indent=2, default=str)
