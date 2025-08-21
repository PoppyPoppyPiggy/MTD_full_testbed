#!/usr/bin/env python3
"""
LPC 상태머신 (Python) - bus.log로도 기록되도록 보강
"""
import time, random, logging, asyncio, os
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from typing import Optional

# --- BUS LOG 헬퍼 ---
BUS_LOG = os.environ.get("BUS_LOG")

def bus_print(line: str):
    print(line)
    if BUS_LOG:
        with open(BUS_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")

class LPCState(Enum):
    IDLE="idle"; RECON="recon"; PROBE="probe"; NIBBLE="nibble"; HOLD="hold"; ESCALATE="escalate"; RETREAT="retreat"
class BackoffStrategy(Enum):
    NONE="none"; LINEAR="linear"; EXPONENTIAL="exp"

@dataclass
class LPCConfig:
    duty_cycle: float = 0.1
    interval_ms: int = 15000
    jitter_pct: float = 30.0
    backoff: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    step_size: float = 0.1
    max_budget: int = 120
    noise_ratio: float = 0.2
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    rotate_targets: bool = True
    persistence_hours: int = 24
    throttle_on_alert: bool = True

@dataclass
class LPCState_Context:
    current_state: LPCState = LPCState.IDLE
    budget_used: int = 0
    success_count: int = 0
    failure_count: int = 0
    detection_count: int = 0
    last_action_time: Optional[datetime] = None
    current_interval: int = 15000
    backoff_multiplier: float = 1.0
    target_index: int = 0
    session_start: datetime = None
    alert_level: int = 0

class LPCStateMachine:
    def __init__(self, config: LPCConfig, attack_name: str):
        self.config=config; self.attack_name=attack_name
        self.context=LPCState_Context()
        self.context.session_start=datetime.now()
        self.context.current_interval=config.interval_ms
        self.transition_rules={
          LPCState.IDLE:self._idle, LPCState.RECON:self._recon, LPCState.PROBE:self._probe,
          LPCState.NIBBLE:self._nibble, LPCState.HOLD:self._hold, LPCState.ESCALATE:self._escalate,
          LPCState.RETREAT:self._retreat
        }
        self.logger=logging.getLogger(f"LPC.{attack_name}")

    def _log_bus(self, msg:str, **kw):
        ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        params=" ".join([f"{k}={v}" for k,v in kw.items()])
        line=f"[{ts}] [{self.attack_name}] {msg} {params}".strip()
        bus_print(line); self.logger.info(line)

    def _is_within_window(self)->bool:
        if not self.config.window_start or not self.config.window_end: return True
        now=datetime.now().time()
        s=datetime.strptime(self.config.window_start,"%H:%M").time()
        e=datetime.strptime(self.config.window_end,"%H:%M").time()
        return (s<=now<=e) if s<=e else (now>=s or now<=e)

    def _jit_interval(self)->int:
        base=self.context.current_interval
        rng=base*(self.config.jitter_pct/100.0)
        jitter=random.uniform(-rng,rng)
        return max(1000,int(base+jitter))

    def _apply_backoff(self, success:bool):
        if success:
            self.context.backoff_multiplier=1.0; self.context.current_interval=self.config.interval_ms
        else:
            if self.config.backoff==BackoffStrategy.LINEAR: self.context.backoff_multiplier+=0.5
            elif self.config.backoff==BackoffStrategy.EXPONENTIAL: self.context.backoff_multiplier*=2.0
            self.context.backoff_multiplier=min(10.0,self.context.backoff_multiplier)
            self.context.current_interval=int(self.config.interval_ms*self.context.backoff_multiplier)

    def _check_budget(self)->bool: return self.context.budget_used < self.config.max_budget
    def _throttle(self)->bool: return self.config.throttle_on_alert and self.context.alert_level>=2

    def _idle(self)->LPCState:
        if not self._is_within_window(): return LPCState.IDLE
        if not self._check_budget(): return LPCState.RETREAT
        if (datetime.now()-self.context.session_start).total_seconds()>self.config.persistence_hours*3600: return LPCState.RETREAT
        return LPCState.RECON
    def _recon(self)->LPCState: return LPCState.RETREAT if self.context.detection_count>0 else LPCState.PROBE
    def _probe(self)->LPCState:
        if self.context.detection_count>2: return LPCState.RETREAT
        if self.context.success_count>0: return LPCState.NIBBLE
        if self.context.failure_count>3: return LPCState.HOLD
        return LPCState.PROBE
    def _nibble(self)->LPCState:
        if self._throttle(): return LPCState.HOLD
        if self.context.success_count>5: return LPCState.ESCALATE
        if self.context.detection_count>1: return LPCState.RETREAT
        return LPCState.NIBBLE
    def _hold(self)->LPCState: return LPCState.PROBE if self.context.alert_level<2 else LPCState.HOLD
    def _escalate(self)->LPCState: return LPCState.RETREAT if self.context.detection_count>0 else LPCState.ESCALATE
    def _retreat(self)->LPCState: return LPCState.IDLE

    def transition(self, mtd_event:Optional[str]=None, detection_signal:Optional[str]=None)->LPCState:
        old=self.context.current_state
        if mtd_event: self._log_bus("mtd_event_detected", event=mtd_event); self.context.alert_level=min(3,self.context.alert_level+1)
        if detection_signal: self._log_bus("detection_signal", signal=detection_signal); self.context.detection_count+=1; self.context.alert_level=3
        new=self.transition_rules[self.context.current_state]()
        if new!=old:
            self.context.current_state=new
            self._log_bus("state_transition", from_state=old.value, to_state=new.value,
                          budget_used=self.context.budget_used, alert_level=self.context.alert_level)
        return new

    def should_act(self)->bool:
        if not self._is_within_window() or not self._check_budget(): return False
        if self.context.current_state not in {LPCState.PROBE,LPCState.NIBBLE,LPCState.ESCALATE}: return False
        if random.random()>self.config.duty_cycle: return False
        if self._throttle() and random.random()>(self.config.duty_cycle/2.0): return False
        return True

    def record_action_result(self, success:bool):
        self.context.budget_used+=1; self.context.last_action_time=datetime.now()
        if success: self.context.success_count+=1
        else: self.context.failure_count+=1
        self._apply_backoff(success)
        self._log_bus("action_result", success=success, budget_used=self.context.budget_used,
                      backoff_multiplier=round(self.context.backoff_multiplier,2))

class AttackPrimitives:
    def __init__(self, attack_name:str): self.attack_name=attack_name; self.logger=logging.getLogger(f"Primitives.{attack_name}")
    def _log_bus(self, primitive:str, **kw):
        ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        params=" ".join([f"{k}={v}" for k,v in kw.items()])
        bus_print(f"[{ts}] [{self.attack_name}] primitive={primitive} {params}".strip()); self.logger.info(params)

    def wifi_slow_probe(self, intensity:str="low")->bool:
        lv={"low":{"scan_rate":0.1,"signal_variation":2.0},"medium":{"scan_rate":0.3,"signal_variation":5.0},"high":{"scan_rate":0.8,"signal_variation":10.0}}
        lvl=lv.get(intensity,lv["low"]); success=random.random()<0.7
        self._log_bus("wifi_slow_probe", intensity=intensity, scan_rate=lvl["scan_rate"], signal_variation=lvl["signal_variation"], success=success)
        return success
    def telemetry_trickle(self, intensity:str="low")->bool:
        lv={"low":{"pps_limit":5,"latency_increase":2}, "medium":{"pps_limit":15,"latency_increase":8}, "high":{"pps_limit":30,"latency_increase":20}}
        lvl=lv.get(intensity,lv["low"]); success=random.random()<0.8
        self._log_bus("telemetry_trickle", intensity=intensity, pps_limit=lvl["pps_limit"], latency_increase_ms=lvl["latency_increase"], success=success)
        return success
    def mavlink_param_nudge(self, param_name:str="AUTO", step_size:float=0.01)->bool:
        safe=["ATC_RAT_RLL_FF","ATC_RAT_PIT_FF","PSC_POSXY_P"]
        actual=random.choice(safe) if param_name=="AUTO" else param_name
        noise=random.uniform(-step_size*0.5, step_size*0.5); step=step_size+noise
        success=random.random()<0.6
        self._log_bus("mavlink_param_nudge", param=actual, step=round(step,4), noise=round(noise,4), success=success)
        return success
    def gps_offset_drift(self, offset_m:float=0.2)->bool:
        acc=offset_m*random.uniform(0.8,1.2)
        lat=acc*random.uniform(-1,1); lon=acc*random.uniform(-1,1); alt=offset_m*0.1*random.uniform(-1,1)
        success=random.random()<0.75
        self._log_bus("gps_offset_drift", lat_offset_m=round(lat,3), lon_offset_m=round(lon,3), alt_offset_m=round(alt,3), total_offset_m=round(acc,3), success=success)
        return success
    def power_route_bias(self, bias_factor:float=1.1)->bool:
        q=int(bias_factor*10); cpu=(bias_factor-1)*100; success=random.random()<0.85
        self._log_bus("power_route_bias", bias_factor=bias_factor, queue_additions=q, cpu_overhead_pct=round(cpu,1), success=success)
        return success

class LPCAttackModule:
    def __init__(self, attack_name:str, config:LPCConfig):
        self.attack_name=attack_name; self.config=config
        self.state_machine=LPCStateMachine(config, attack_name); self.primitives=AttackPrimitives(attack_name); self.is_running=False
    async def run_lpc_loop(self, duration:int=0):
        self.is_running=True; start=datetime.now(); end=start+timedelta(seconds=duration) if duration>0 else None
        try:
            while self.is_running:
                st=self.state_machine.transition()
                if end and datetime.now()>=end: break
                if st==LPCState.RETREAT: break
                if self.state_machine.should_act():
                    ok=await self._exec_action(); self.state_machine.record_action_result(ok)
                await asyncio.sleep(self.state_machine._jit_interval()/1000.0)
        except Exception as e:
            bus_print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [{self.attack_name}] error msg={e}")
        finally:
            self.is_running=False
    async def _exec_action(self)->bool:
        st=self.state_machine.context.current_state
        if st==LPCState.PROBE:  return self.primitives.wifi_slow_probe("low")
        if st==LPCState.NIBBLE: return random.choice([
            lambda: self.primitives.telemetry_trickle("medium"),
            lambda: self.primitives.mavlink_param_nudge(step_size=0.005),
            lambda: self.primitives.gps_offset_drift(0.1)])()
        if st==LPCState.ESCALATE: return random.choice([
            lambda: self.primitives.telemetry_trickle("high"),
            lambda: self.primitives.mavlink_param_nudge(step_size=0.02),
            lambda: self.primitives.gps_offset_drift(0.5),
            lambda: self.primitives.power_route_bias(1.3)])()
        return False
    def stop(self): self.is_running=False

async def test_lpc_attack():
    cfg=LPCConfig(duty_cycle=0.08, interval_ms=10000, jitter_pct=25.0,
                  backoff=BackoffStrategy.EXPONENTIAL, max_budget=50,
                  window_start=None, window_end=None)
    atk=LPCAttackModule("test_lpc_attack", cfg)
    bus_print("=== LPC 공격 테스트 시작 ===")
    await atk.run_lpc_loop(duration=30)
    bus_print("=== LPC 공격 테스트 완료 ===")

if __name__=="__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_lpc_attack())
