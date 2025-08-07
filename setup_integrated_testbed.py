#!/bin/bash
# ===========================================
# 통합 MTD 테스트베드 설정 스크립트
# 위치: ~/MTD/MTD_full_testbed/setup_integrated_testbed.py
# ===========================================

"""
FANET NS-3 통합 MTD 테스트베드 설정 스크립트
"""

import os
import sys
import subprocess
import json
import shutil
from pathlib import Path
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestbedSetup:
    def __init__(self, base_dir: str = "~/MTD/MTD_full_testbed"):
        self.base_dir = Path(base_dir).expanduser()
        self.ensure_base_directory()
        
    def ensure_base_directory(self):
        """기본 디렉토리 구조 생성"""
        directories = [
            'configs/ardupilot',
            'configs/ns3', 
            'configs/gazebo',
            'configs/mtd',
            'configs/cti',
            'configs/falco',
            'configs/fluentd',
            'configs/zeek',
            'configs/suricata',
            'configs/prometheus',
            'configs/grafana/dashboards',
            'configs/grafana/datasources',
            'configs/kibana',
            'configs/misp',
            'configs/qgc',
            'docker/ardupilot',
            'docker/ns3',
            'docker/gazebo', 
            'docker/mtd',
            'docker/cti',
            'docker/fluentd',
            'docker/zeek',
            'docker/dvd-attacks',
            'docker/qgc',
            'logs/ardupilot',
            'logs/ns3',
            'logs/gazebo',
            'logs/mtd',
            'logs/cti',
            'logs/falco',
            'logs/fluentd',
            'logs/zeek',
            'logs/suricata',
            'logs/elasticsearch',
            'logs/dvd-companion',
            'logs/attacks',
            'logs/qgc',
            'gazebo/models',
            'gazebo/worlds',
            'zeek-scripts',
            'suricata-rules',
            'notebooks',
            'models',
            'missions',
            'results'
        ]
        
        for directory in directories:
            dir_path = self.base_dir / directory
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"디렉토리 생성: {dir_path}")

    def create_docker_files(self):
        """Docker 관련 파일 생성"""
        # ArduPilot 시작 스크립트
        ardupilot_start = """#!/bin/bash
set -e

echo "ArduPilot SITL 시작 중..."

cd /ardupilot

# 매개변수 파일 확인
if [ -f /configs/copter.parm ]; then
    echo "매개변수 파일 로드: /configs/copter.parm"
    PARAMS_FILE="/configs/copter.parm"
else
    PARAMS_FILE=""
fi

# SITL 실행
python3 Tools/autotest/sim_vehicle.py \\
    --vehicle=${SITL_VEHICLE:-copter} \\
    --location=${SITL_LOCATION:-KSFO} \\
    --instance=${SITL_INSTANCE:-0} \\
    --speedup=${SITL_SPEEDUP:-1} \\
    --out=0.0.0.0:14550 \\
    --out=0.0.0.0:14551 \\
    --console \\
    --map \\
    ${PARAMS_FILE:+--load-module $PARAMS_FILE} \\
    --no-rebuild
"""
        
        with open(self.base_dir / 'docker/ardupilot/start-ardupilot.sh', 'w') as f:
            f.write(ardupilot_start)
        
        # MTD Orchestrator Python 스크립트
        mtd_orchestrator = '''#!/usr/bin/env python3
"""
MTD Orchestrator 메인 스크립트
위치: ~/MTD/MTD_full_testbed/docker/mtd/mtd_orchestrator.py
"""

import asyncio
import docker
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Any
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MTDOrchestrator:
    def __init__(self, config_path: str = "/configs/mtd_config.json"):
        self.docker_client = docker.from_env()
        self.config = self.load_config(config_path)
        self.active_strategies = {}
        self.threat_level = 0.0
        
    def load_config(self, config_path: str) -> Dict[str, Any]:
        """MTD 설정 로드"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"설정 파일을 찾을 수 없습니다: {config_path}")
            return self.get_default_config()
    
    def get_default_config(self) -> Dict[str, Any]:
        """기본 MTD 설정"""
        return {
            "mutation_cycle": 60,
            "threat_threshold": 0.5,
            "strategies": {
                "container_migration": {
                    "enabled": True,
                    "cooldown": 30,
                    "threshold": 0.7
                },
                "port_randomization": {
                    "enabled": True,
                    "cooldown": 15,
                    "threshold": 0.5
                },
                "ip_shuffling": {
                    "enabled": True,
                    "cooldown": 45,
                    "threshold": 0.6
                }
            }
        }
    
    async def run(self):
        """MTD 오케스트레이터 실행"""
        logger.info("MTD Orchestrator 시작")
        
        while True:
            try:
                # 위협 수준 평가
                self.threat_level = await self.assess_threat_level()
                
                # MTD 전략 실행
                await self.execute_mtd_strategies()
                
                # 로그 출력
                logger.info(f"위협 수준: {self.threat_level:.2f}")
                
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"MTD 실행 오류: {e}")
                await asyncio.sleep(5)
    
    async def assess_threat_level(self) -> float:
        """위협 수준 평가"""
        threat_score = 0.0
        
        # 컨테이너 상태 확인
        try:
            containers = self.docker_client.containers.list()
            running_containers = len([c for c in containers if c.status == 'running'])
            
            if running_containers < 5:  # 최소 컨테이너 수
                threat_score += 0.2
                
        except Exception as e:
            logger.error(f"컨테이너 상태 확인 실패: {e}")
            threat_score += 0.3
        
        # 시뮬레이션된 위협 탐지
        if np.random.random() < 0.1:  # 10% 확률로 위협 발생
            threat_score += np.random.uniform(0.3, 0.8)
        
        return min(1.0, threat_score)
    
    async def execute_mtd_strategies(self):
        """MTD 전략 실행"""
        for strategy_name, strategy_config in self.config["strategies"].items():
            if not strategy_config.get("enabled", False):
                continue
                
            threshold = strategy_config.get("threshold", 0.5)
            
            if self.threat_level >= threshold:
                await self.execute_strategy(strategy_name, strategy_config)
    
    async def execute_strategy(self, strategy_name: str, config: Dict[str, Any]):
        """개별 전략 실행"""
        logger.warning(f"MTD 전략 실행: {strategy_name}")
        
        if strategy_name == "container_migration":
            await self.migrate_containers()
        elif strategy_name == "port_randomization":
            await self.randomize_ports()
        elif strategy_name == "ip_shuffling":
            await self.shuffle_ips()
    
    async def migrate_containers(self):
        """컨테이너 마이그레이션"""
        logger.info("컨테이너 마이그레이션 실행")
        # 실제 마이그레이션 로직 구현
        await asyncio.sleep(2)  # 시뮬레이션
    
    async def randomize_ports(self):
        """포트 랜덤화"""
        logger.info("포트 랜덤화 실행")
        # 실제 포트 변경 로직 구현
        await asyncio.sleep(1)  # 시뮬레이션
    
    async def shuffle_ips(self):
        """IP 주소 셔플링"""
        logger.info("IP 주소 셔플링 실행") 
        # 실제 IP 변경 로직 구현
        await asyncio.sleep(1)  # 시뮬레이션

if __name__ == "__main__":
    orchestrator = MTDOrchestrator()
    asyncio.run(orchestrator.run())
'''
        
        with open(self.base_dir / 'docker/mtd/mtd_orchestrator.py', 'w') as f:
            f.write(mtd_orchestrator)

    def create_config_files(self):
        """설정 파일들 생성"""
        
        # Falco 보안 규칙
        falco_rules = """# FANET 드론 보안 규칙
# 위치: ~/MTD/MTD_full_testbed/configs/falco/drone-rules.yaml

- rule: Drone MAVLink Injection Attack
  desc: MAVLink 패킷 주입 공격 탐지
  condition: >
    spawned_process and
    container.image.repository contains "dvd" and
    (proc.cmdline contains "mavlink" or 
     fd.name contains ":14550" or 
     fd.name contains ":14551")
  output: >
    MAVLink injection detected (user=%user.name command=%proc.cmdline 
    container=%container.name image=%container.image.repository)
  priority: CRITICAL
  tags: [drone, attack, injection]

- rule: Drone Container Privilege Escalation
  desc: 드론 컨테이너에서 권한 상승 탐지
  condition: >
    container and
    container.image.repository contains "dvd" and
    (proc.name in (su, sudo, setuid) or
     proc.cmdline contains "chmod +s")
  output: >
    Privilege escalation in drone container (user=%user.name command=%proc.cmdline 
    container=%container.name)
  priority: HIGH
  tags: [drone, privilege-escalation]

- rule: Suspicious Network Activity in FANET
  desc: FANET 네트워크에서 의심스러운 활동 탐지
  condition: >
    container and
    container.image.repository contains "ns3" and
    (fd.net != "" and fd.sport > 60000)
  output: >
    Suspicious network activity in FANET (connection=%fd.name container=%container.name)
  priority: MEDIUM
  tags: [fanet, network, suspicious]

- rule: MTD Strategy Execution
  desc: MTD 전략 실행 모니터링
  condition: >
    container and
    container.image.repository contains "mtd" and
    proc.cmdline contains "migrate"
  output: >
    MTD strategy executed (strategy=%proc.cmdline container=%container.name)
  priority: INFO
  tags: [mtd, defense]
"""
        
        with open(self.base_dir / 'configs/falco/drone-rules.yaml', 'w') as f:
            f.write(falco_rules)
        
        # Fluentd 설정
        fluentd_config = """# Fluentd 설정 파일
# 위치: ~/MTD/MTD_full_testbed/configs/fluentd/fluent.conf

<source>
  @type forward
  port 24224
  bind 0.0.0.0
</source>

# MAVLink 로그 파싱
<filter dvd.ardupilot>
  @type parser
  format json
  key_name log
  reserve_data true
  <parse>
    @type regexp
    expression /^MAV: (?<msg_type>\\w+) SYS:(?<sys_id>\\d+) COMP:(?<comp_id>\\d+) LEN:(?<length>\\d+) MSG ID:(?<msg_id>\\d+)/
  </parse>
</filter>

# NS-3 시뮬레이션 로그 파싱
<filter fanet.ns3>
  @type parser
  format json
  key_name log
  <parse>
    @type regexp
    expression /^(?<timestamp>\\d+\\.\\d+)s.*Node (?<node_id>\\d+).*(?<event_type>\\w+)/
  </parse>
</filter>

# 보안 이벤트 필터링
<filter **>
  @type grep
  <regexp>
    key message
    pattern /(ATTACK|ANOMALY|INTRUSION|SPOOFING|JAMMING|MTD)/
  </regexp>
</filter>

# Elasticsearch로 전송
<match **>
  @type elasticsearch
  host elasticsearch
  port 9200
  logstash_format true
  logstash_prefix mtd-testbed
  <buffer>
    @type memory
    flush_interval 1s
  </buffer>
</match>
"""
        
        with open(self.base_dir / 'configs/fluentd/fluent.conf', 'w') as f:
            f.write(fluentd_config)
        
        # NS-3 설정
        ns3_config = """{
  "simulation": {
    "duration": 300.0,
    "nodes": 20,
    "area": {
      "x": 1000,
      "y": 1000,
      "z": 300
    },
    "communication_range": 250.0,
    "mobility_model": "GaussMarkovMobilityModel"
  },
  "network": {
    "protocol": "802.11p",
    "frequency": 5.9e9,
    "tx_power": 23.0,
    "data_rate": "6Mbps"
  },
  "security": {
    "attack_probability": 0.1,
    "detection_rate": 0.8,
    "mtd_enabled": true,
    "trust_threshold": 0.5
  },
  "output": {
    "animation": true,
    "traces": true,
    "flow_monitor": true,
    "pcap": false
  }
}"""
        
        with open(self.base_dir / 'configs/ns3/simulation_config.json', 'w') as f:
            f.write(ns3_config)
        
        # MTD 설정
        mtd_config = """{
  "mutation_cycle": 60,
  "threat_threshold": 0.5,
  "strategies": {
    "container_migration": {
      "enabled": true,
      "cooldown": 30,
      "threshold": 0.7,
      "target_containers": ["dvd-companion", "ns3-fanet"]
    },
    "port_randomization": {
      "enabled": true,
      "cooldown": 15,
      "threshold": 0.5,
      "port_ranges": {
        "mavlink": [14000, 15000],
        "http": [8000, 9000],
        "rtsp": [5540, 5560]
      }
    },
    "ip_shuffling": {
      "enabled": true,
      "cooldown": 45,
      "threshold": 0.6,
      "ip_pool": [
        "10.13.0.10/24",
        "10.13.0.20/24", 
        "10.13.0.30/24"
      ]
    },
    "frequency_hopping": {
      "enabled": true,
      "cooldown": 20,
      "threshold": 0.4,
      "frequencies": [2.4e9, 5.2e9, 5.8e9]
    }
  },
  "monitoring": {
    "metrics_interval": 10,
    "log_level": "INFO",
    "export_metrics": true
  }
}"""
        
        with open(self.base_dir / 'configs/mtd/mtd_config.json', 'w') as f:
            f.write(mtd_config)

    def create_gazebo_files(self):
        """Gazebo 모델 및 월드 파일 생성"""
        
        # FANET 드론 모델
        drone_model = """<?xml version="1.0" ?>
<sdf version="1.6">
  <model name="fanet_drone">
    <pose>0 0 0.2 0 0 0</pose>
    <link name="base_link">
      <collision name="collision">
        <geometry>
          <box>
            <size>0.5 0.5 0.1</size>
          </box>
        </geometry>
      </collision>
      <visual name="visual">
        <geometry>
          <box>
            <size>0.5 0.5 0.1</size>
          </box>
        </geometry>
        <material>
          <ambient>0.0 0.5 1.0 1</ambient>
          <diffuse>0.0 0.5 1.0 1</diffuse>
        </material>
      </visual>
      <inertial>
        <mass>1.5</mass>
        <inertia>
          <ixx>0.1</ixx>
          <iyy>0.1</iyy>
          <izz>0.1</izz>
        </inertia>
      </inertial>
    </link>
    
    <!-- 프로펠러들 -->
    <link name="rotor_0">
      <pose>0.25 0.25 0.15 0 0 0</pose>
      <visual name="visual">
        <geometry>
          <cylinder>
            <radius>0.1</radius>
            <length>0.02</length>
          </cylinder>
        </geometry>
        <material>
          <ambient>1 0 0 1</ambient>
        </material>
      </visual>
    </link>
    
    <link name="rotor_1">
      <pose>-0.25 0.25 0.15 0 0 0</pose>
      <visual name="visual">
        <geometry>
          <cylinder>
            <radius>0.1</radius>
            <length>0.02</length>
          </cylinder>
        </geometry>
        <material>
          <ambient>1 0 0 1</ambient>
        </material>
      </visual>
    </link>
    
    <link name="rotor_2">
      <pose>-0.25 -0.25 0.15 0 0 0</pose>
      <visual name="visual">
        <geometry>
          <cylinder>
            <radius>0.1</radius>
            <length>0.02</length>
          </cylinder>
        </geometry>
        <material>
          <ambient>1 0 0 1</ambient>
        </material>
      </visual>
    </link>
    
    <link name="rotor_3">
      <pose>0.25 -0.25 0.15 0 0 0</pose>
      <visual name="visual">
        <geometry>
          <cylinder>
            <radius>0.1</radius>
            <length>0.02</length>
          </cylinder>
        </geometry>
        <material>
          <ambient>1 0 0 1</ambient>
        </material>
      </visual>
    </link>
    
    <!-- 조인트들 -->
    <joint name="rotor_0_joint" type="revolute">
      <parent>base_link</parent>
      <child>rotor_0</child>
      <axis>
        <xyz>0 0 1</xyz>
      </axis>
    </joint>
    
    <joint name="rotor_1_joint" type="revolute">
      <parent>base_link</parent>
      <child>rotor_1</child>
      <axis>
        <xyz>0 0 1</xyz>
      </axis>
    </joint>
    
    <joint name="rotor_2_joint" type="revolute">
      <parent>base_link</parent>
      <child>rotor_2</child>
      <axis>
        <xyz>0 0 1</xyz>
      </axis>
    </joint>
    
    <joint name="rotor_3_joint" type="revolute">
      <parent>base_link</parent>
      <child>rotor_3</child>
      <axis>
        <xyz>0 0 1</xyz>
      </axis>
    </joint>
  </model>
</sdf>"""
        
        drone_dir = self.base_dir / 'gazebo/models/fanet_drone'
        drone_dir.mkdir(parents=True, exist_ok=True)
        
        with open(drone_dir / 'model.sdf', 'w') as f:
            f.write(drone_model)
        
        # 모델 설정 파일
        model_config = """<?xml version="1.0"?>
<model>
  <name>FANET Drone</name>
  <version>1.0</version>
  <sdf version="1.6">model.sdf</sdf>
  
  <author>
    <name>MTD Testbed</name>
    <email>mtd@testbed.local</email>
  </author>
  
  <description>
    FANET (Flying Ad-hoc Network) 드론 모델
  </description>
</model>"""
        
        with open(drone_dir / 'model.config', 'w') as f:
            f.write(model_config)
        
        # FANET 월드 파일
        world_file = """<?xml version="1.0" ?>
<sdf version="1.6">
  <world name="fanet_world">
    
    <!-- 물리 엔진 설정 -->
    <physics name="default_physics" default="0" type="ode">
      <gravity>0 0 -9.8066</gravity>
      <ode>
        <solver>
          <type>quick</type>
          <iters>10</iters>
          <sor>1.3</sor>
        </solver>
        <constraints>
          <cfm>0.0</cfm>
          <erp>0.2</erp>
          <contact_max_correcting_vel>100.0</contact_max_correcting_vel>
          <contact_surface_layer>0.001</contact_surface_layer>
        </constraints>
      </ode>
      <max_step_size>0.002</max_step_size>
      <real_time_factor>1.000000</real_time_factor>
      <real_time_update_rate>500.000000</real_time_update_rate>
    </physics>
    
    <!-- 조명 설정 -->
    <light name="sun" type="directional">
      <cast_shadows>1</cast_shadows>
      <pose>0 0 10 0 0 0</pose>
      <diffuse>0.8 0.8 0.8 1</diffuse>
      <specular>0.2 0.2 0.2 1</specular>
      <attenuation>
        <range>1000</range>
        <constant>0.9</constant>
        <linear>0.01</linear>
        <quadratic>0.001</quadratic>
      </attenuation>
      <direction>-0.5 0.1 -0.9</direction>
    </light>
    
    <!-- 지면 -->
    <model name="ground_plane">
      <static>true</static>
      <link name="link">
        <collision name="collision">
          <geometry>
            <plane>
              <normal>0 0 1</normal>
              <size>2000 2000</size>
            </plane>
          </geometry>
          <surface>
            <contact>
              <collide_bitmask>65535</collide_bitmask>
              <ode>
                <mu>100</mu>
                <mu2>50</mu2>
              </ode>
            </contact>
            <friction>
              <ode>
                <mu>100</mu>
                <mu2>50</mu2>
              </ode>
            </friction>
          </surface>
        </collision>
        <visual name="visual">
          <cast_shadows>false</cast_shadows>
          <geometry>
            <plane>
              <normal>0 0 1</normal>
              <size>2000 2000</size>
            </plane>
          </geometry>
          <material>
            <script>
              <uri>file://media/materials/scripts/gazebo.material</uri>
              <name>Gazebo/Grey</name>
            </script>
          </material>
        </visual>
      </link>
    </model>
    
    <!-- FANET 드론들 -->
    <include>
      <uri>model://fanet_drone</uri>
      <name>drone_0</name>
      <pose>0 0 5 0 0 0</pose>
    </include>
    
    <include>
      <uri>model://fanet_drone</uri>
      <name>drone_1</name>
      <pose>100 0 5 0 0 0</pose>
    </include>
    
    <include>
      <uri>model://fanet_drone</uri>
      <name>drone_2</name>
      <pose>0 100 5 0 0 0</pose>
    </include>
    
    <include>
      <uri>model://fanet_drone</uri>
      <name>drone_3</name>
      <pose>100 100 5 0 0 0</pose>
    </include>
    
    <!-- GUI 설정 -->
    <gui fullscreen='0'>
      <camera name='user_camera'>
        <pose>250 -250 150 0 0.275643 2.35619</pose>
        <view_controller>orbit</view_controller>
      </camera>
    </gui>
    
  </world>
</sdf>"""
        
        with open(self.base_dir / 'gazebo/worlds/fanet_world.world', 'w') as f:
            f.write(world_file)

    def create_zeek_scripts(self):
        """Zeek 네트워크 분석 스크립트 생성"""
        
        # MAVLink 프로토콜 분석기
        mavlink_analyzer = """# MAVLink 프로토콜 분석기
# 위치: ~/MTD/MTD_full_testbed/zeek-scripts/mavlink-analyzer.zeek

module MAVLink;

export {
    redef enum Log::ID += { LOG };
    
    type Info: record {
        ts: time &log;
        uid: string &log;
        id: conn_id &log;
        msg_id: count &log;
        sys_id: count &log;
        comp_id: count &log;
        seq: count &log;
        payload_size: count &log;
        payload: string &optional &log;
        anomaly: bool &default=F &log;
        attack_type: string &optional &log;
    };
    
    global mavlink_ports: set[port] = { 14550/udp, 14551/udp };
    global suspicious_msg_ids: set[count] = { 300, 301, 302 };
}

event zeek_init() {
    Log::create_stream(MAVLink::LOG, [$columns=Info, $path="mavlink"]);
}

event new_connection(c: connection) {
    if (c$id$resp_p in mavlink_ports) {
        print fmt("MAVLink connection detected: %s", c$id);
    }
}

function analyze_mavlink_packet(c: connection, data: string): MAVLink::Info {
    local info: MAVLink::Info;
    info$ts = network_time();
    info$uid = c$uid;
    info$id = c$id;
    
    # MAVLink 패킷 파싱 (간단한 구현)
    if (|data| >= 8) {
        local magic = bytestring_to_count(data[0:1]);
        
        if (magic == 0xFE || magic == 0xFD) { # MAVLink v1 or v2
            info$payload_size = bytestring_to_count(data[1:2]);
            info$seq = bytestring_to_count(data[2:3]);
            info$sys_id = bytestring_to_count(data[3:4]);
            info$comp_id = bytestring_to_count(data[4:5]);
            info$msg_id = bytestring_to_count(data[5:6]);
            
            # 의심스러운 메시지 ID 확인
            if (info$msg_id in suspicious_msg_ids) {
                info$anomaly = T;
                info$attack_type = "suspicious_message";
                NOTICE([$note=MAVLink_Anomaly,
                       $conn=c,
                       $msg=fmt("Suspicious MAVLink message ID: %d", info$msg_id)]);
            }
            
            # 비정상적인 페이로드 크기 확인
            if (info$payload_size > 255) {
                info$anomaly = T;
                info$attack_type = "oversized_payload";
            }
        }
    }
    
    return info;
}

event udp_contents(c: connection, is_orig: bool, contents: string) {
    if (c$id$resp_p in mavlink_ports) {
        local info = analyze_mavlink_packet(c, contents);
        Log::write(MAVLink::LOG, info);
    }
}"""
        
        with open(self.base_dir / 'zeek-scripts/mavlink-analyzer.zeek', 'w') as f:
            f.write(mavlink_analyzer)
        
        # 드론 보안 모니터링 스크립트
        drone_security = """# 드론 보안 모니터링 스크립트
# 위치: ~/MTD/MTD_full_testbed/zeek-scripts/drone-security.zeek

@load base/protocols/conn
@load ./mavlink-analyzer

module DroneSecurity;

export {
    redef enum Notice::Type += {
        MAVLink_Injection_Attack,
        GPS_Spoofing_Attack,
        Drone_Hijacking_Attempt,
        FANET_Routing_Attack
    };
    
    type AttackPattern: record {
        name: string;
        description: string;
        threshold: count;
        time_window: interval;
    };
    
    global attack_patterns: table[string] of AttackPattern = {
        ["mavlink_flood"] = [$name="mavlink_flood", 
                            $description="MAVLink flooding attack",
                            $threshold=100, 
                            $time_window=10sec],
        ["gps_spoof"] = [$name="gps_spoof",
                        $description="GPS spoofing attack", 
                        $threshold=5,
                        $time_window=30sec]
    };
    
    global connection_counts: table[addr] of count;
    global last_reset: time;
}

event zeek_init() {
    last_reset = network_time();
    
    # 주기적인 카운터 리셋
    schedule 60sec { reset_counters() };
}

function reset_counters() {
    connection_counts = table();
    last_reset = network_time();
    schedule 60sec { reset_counters() };
}

event new_connection(c: connection) {
    local src_ip = c$id$orig_h;
    
    # 연결 수 카운트
    if (src_ip !in connection_counts) {
        connection_counts[src_ip] = 0;
    }
    connection_counts[src_ip] += 1;
    
    # 플러딩 공격 탐지
    if (connection_counts[src_ip] > 50) {
        NOTICE([$note=MAVLink_Injection_Attack,
               $conn=c,
               $msg=fmt("Potential flooding attack from %s (%d connections)", 
                       src_ip, connection_counts[src_ip])]);
    }
}

event MAVLink::mavlink_message(c: connection, info: MAVLink::Info) {
    # GPS 관련 메시지 모니터링
    if (info$msg_id == 33) { # GLOBAL_POSITION_INT
        # GPS 스푸핑 탐지 로직
        print fmt("GPS position message from %s", c$id$orig_h);
    }
    
    # 제어 명령 모니터링
    if (info$msg_id == 76) { # COMMAND_LONG
        NOTICE([$note=Drone_Hijacking_Attempt,
               $conn=c,
               $msg=fmt("Control command detected from %s", c$id$orig_h)]);
    }
}

# 라우팅 공격 탐지
event connection_state_remove(c: connection) {
    if (c$duration < 1sec && c$orig$size > 1000) {
        NOTICE([$note=FANET_Routing_Attack,
               $conn=c,
               $msg="Potential blackhole/grayhole attack detected"]);
    }
}"""
        
        with open(self.base_dir / 'zeek-scripts/drone-security.zeek', 'w') as f:
            f.write(drone_security)

    def create_requirements_files(self):
        """Python 의존성 파일들 생성"""
        
        # 메인 requirements.txt
        main_requirements = """# 기본 의존성
numpy>=1.21.0
scipy>=1.7.0
pandas>=1.3.0
matplotlib>=3.4.0
seaborn>=0.11.0
plotly>=5.0.0

# 네트워킹
asyncio>=3.4.3
aiohttp>=3.8.0
websockets>=10.0

# Docker 관리
docker>=5.0.0
docker-compose>=1.29.0

# 로깅 및 모니터링
elasticsearch>=7.15.0
pymongo>=4.0.0
redis>=4.0.0

# 보안 및 암호화
cryptography>=3.4.0
pycryptodome>=3.15.0

# 기계학습 (선택적)
scikit-learn>=1.0.0
tensorflow>=2.8.0
torch>=1.12.0
"""
        
        with open(self.base_dir / 'requirements.txt', 'w') as f:
            f.write(main_requirements)
        
        # CTI 시스템 의존성
        cti_requirements = """# CTI 시스템 의존성
stix2>=3.0.0
taxii2-client>=2.3.0
pymisp>=2.4.0
opencti-client>=5.0.0

# 기계학습
scikit-learn>=1.0.0
xgboost>=1.6.0
lightgbm>=3.3.0
tensorflow>=2.8.0

# 데이터 처리
pandas>=1.3.0
numpy>=1.21.0
scipy>=1.7.0

# 네트워킹
requests>=2.28.0
urllib3>=1.26.0

# 시각화
matplotlib>=3.4.0
plotly>=5.0.0
"""
        
        with open(self.base_dir / 'docker/cti/requirements-cti.txt', 'w') as f:
            f.write(cti_requirements)

    def create_startup_script(self):
        """통합 시작 스크립트 생성"""
        
        startup_script = """#!/bin/bash
# 통합 MTD 테스트베드 시작 스크립트
# 위치: ~/MTD/MTD_full_testbed/start_testbed.sh

set -e

# 색상 정의
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
PURPLE='\\033[0;35m'
CYAN='\\033[0;36m'
WHITE='\\033[1;37m'
NC='\\033[0m' # No Color

# 로고 출력
echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                                                               ║"
echo "║    🚁 FANET NS-3 통합 MTD 드론 보안 테스트베드              ║"
echo "║                                                               ║"
echo "║    • NS-3 FANET 네트워크 시뮬레이션                         ║"
echo "║    • ArduPilot SITL + Gazebo 드론 시뮬레이터                ║"
echo "║    • 실시간 CTI 수집 및 기계학습 분석                        ║"
echo "║    • MTD 방어 메커니즘                                       ║"
echo "║    • 기존 DVD 시스템 완전 통합                              ║"
echo "║                                                               ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# 함수 정의
check_requirements() {
    echo -e "${BLUE}📋 시스템 요구사항 확인 중...${NC}"
    
    # Docker 확인
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker가 설치되지 않았습니다.${NC}"
        exit 1
    fi
    
    # Docker Compose 확인
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}❌ Docker Compose가 설치되지 않았습니다.${NC}"
        exit 1
    fi
    
    # Python 확인
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3가 설치되지 않았습니다.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ 모든 요구사항이 충족되었습니다.${NC}"
}

build_containers() {
    echo -e "${BLUE}🔨 Docker 컨테이너 빌드 중...${NC}"
    
    # 기존 컨테이너 정리
    docker-compose -f docker-compose-mtd.yml down -v --remove-orphans 2>/dev/null || true
    
    # 컨테이너 빌드
    docker-compose -f docker-compose-mtd.yml build --no-cache
    
    echo -e "${GREEN}✅ 컨테이너 빌드 완료${NC}"
}

start_core_services() {
    echo -e "${BLUE}🚀 핵심 서비스 시작 중...${NC}"
    
    # 모니터링 서비스 먼저 시작
    docker-compose -f docker-compose-mtd.yml up -d elasticsearch kibana grafana prometheus
    
    # 잠시 대기 (ElasticSearch 초기화)
    echo -e "${YELLOW}⏳ ElasticSearch 초기화 대기 중...${NC}"
    sleep 30
    
    # 로그 수집 서비스
    docker-compose -f docker-compose-mtd.yml up -d fluentd falco-security
    
    echo -e "${GREEN}✅ 핵심 서비스 시작 완료${NC}"
}

start_simulation_services() {
    echo -e "${BLUE}🎮 시뮬레이션 서비스 시작 중...${NC}"
    
    # ArduPilot SITL
    docker-compose -f docker-compose-mtd.yml up -d ardupilot-sitl
    
    # 잠시 대기
    sleep 10
    
    # Gazebo 시뮬레이터
    docker-compose -f docker-compose-mtd.yml up -d gazebo-simulator
    
    # NS-3 FANET 시뮬레이터
    docker-compose -f docker-compose-mtd.yml up -d ns3-fanet-simulator
    
    echo -e "${GREEN}✅ 시뮬레이션 서비스 시작 완료${NC}"
}

start_security_services() {
    echo -e "${BLUE}🔒 보안 서비스 시작 중...${NC}"
    
    # MTD 오케스트레이터
    docker-compose -f docker-compose-mtd.yml up -d mtd-orchestrator
    
    # CTI 분석기
    docker-compose -f docker-compose-mtd.yml up -d cti-analyzer
    
    # 네트워크 분석 도구
    docker-compose -f docker-compose-mtd.yml up -d zeek-analyzer suricata-ids
    
    echo -e "${GREEN}✅ 보안 서비스 시작 완료${NC}"
}

start_dvd_services() {
    echo -e "${BLUE}🎯 DVD 호환 서비스 시작 중...${NC}"
    
    # DVD 컴패니언 컴퓨터
    docker-compose -f docker-compose-mtd.yml up -d dvd-companion
    
    # DVD 공격 실행기
    docker-compose -f docker-compose-mtd.yml up -d dvd-attack-runner
    
    # QGroundControl 시뮬레이터
    docker-compose -f docker-compose-mtd.yml up -d qgroundcontrol-sim
    
    echo -e "${GREEN}✅ DVD 서비스 시작 완료${NC}"
}

show_status() {
    echo -e "${BLUE}📊 시스템 상태${NC}"
    echo "================================"
    
    docker-compose -f docker-compose-mtd.yml ps
    
    echo ""
    echo -e "${CYAN}📡 접속 정보${NC}"
    echo "================================"
    echo -e "${WHITE}• Kibana 대시보드:${NC} http://localhost:5601"
    echo -e "${WHITE}• Grafana 모니터링:${NC} http://localhost:3000 (admin/mtdadmin)"
    echo -e "${WHITE}• DVD 웹 인터페이스:${NC} http://localhost:80"
    echo -e "${WHITE}• CTI API 서버:${NC} http://localhost:8090"
    echo -e "${WHITE}• MISP 플랫폼:${NC} https://localhost:8443"
    echo -e "${WHITE}• QGroundControl VNC:${NC} localhost:5900"
    echo ""
    echo -e "${WHITE}• MAVLink 연결:${NC} udp://localhost:14550"
    echo -e "${WHITE}• MAVLink GCS:${NC} udp://localhost:14551"
    echo ""
}

run_tests() {
    echo -e "${BLUE}🧪 기본 테스트 실행 중...${NC}"
    
    # 통합 테스트베드 스크립트 실행
    python3 fanet_mtd_testbed.py &
    TESTBED_PID=$!
    
    echo -e "${GREEN}✅ 테스트베드가 백그라운드에서 실행 중입니다 (PID: $TESTBED_PID)${NC}"
    echo -e "${YELLOW}⏹️  중지하려면: kill $TESTBED_PID${NC}"
}

# 메인 실행 로직
main() {
    case "${1:-all}" in
        "check")
            check_requirements
            ;;
        "build")
            check_requirements
            build_containers
            ;;
        "core")
            start_core_services
            ;;
        "sim")
            start_simulation_services
            ;;
        "security")
            start_security_services
            ;;
        "dvd")
            start_dvd_services
            ;;
        "status")
            show_status
            ;;
        "test")
            run_tests
            ;;
        "stop")
            echo -e "${YELLOW}🛑 서비스 중지 중...${NC}"
            docker-compose -f docker-compose-mtd.yml down
            echo -e "${GREEN}✅ 모든 서비스가 중지되었습니다.${NC}"
            ;;
        "clean")
            echo -e "${YELLOW}🧹 완전 정리 중...${NC}"
            docker-compose -f docker-compose-mtd.yml down -v --remove-orphans
            docker system prune -af
            echo -e "${GREEN}✅ 시스템 정리 완료${NC}"
            ;;
        "all"|*)
            check_requirements
            build_containers
            start_core_services
            start_simulation_services
            start_security_services
            start_dvd_services
            show_status
            run_tests
            ;;
    esac
}

# 시그널 핸들러
cleanup() {
    echo -e "${YELLOW}\\n🛑 종료 신호 수신. 정리 중...${NC}"
    docker-compose -f docker-compose-mtd.yml down
    exit 0
}

trap cleanup SIGINT SIGTERM

# 사용법 출력
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "사용법: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  all      모든 서비스 시작 (기본값)"
    echo "  check    시스템 요구사항 확인"
    echo "  build    Docker 컨테이너 빌드"
    echo "  core     핵심 모니터링 서비스 시작"
    echo "  sim      시뮬레이션 서비스 시작"
    echo "  security 보안 서비스 시작"
    echo "  dvd      DVD 호환 서비스 시작"
    echo "  status   시스템 상태 확인"
    echo "  test     테스트베드 실행"
    echo "  stop     모든 서비스 중지"
    echo "  clean    완전 정리 (컨테이너 및 볼륨 삭제)"
    echo ""
    exit 0
fi

# 메인 함수 실행
main "$1"
"""
        
        with open(self.base_dir / 'start_testbed.sh', 'w') as f:
            f.write(startup_script)
        
        # 실행 권한 부여
        os.chmod(self.base_dir / 'start_testbed.sh', 0o755)

    def run_setup(self):
        """전체 설정 실행"""
        logger.info("🚁 FANET NS-3 통합 MTD 테스트베드 설정 시작")
        
        try:
            logger.info("📁 디렉토리 구조 생성...")
            self.ensure_base_directory()
            
            logger.info("🐳 Docker 파일 생성...")
            self.create_docker_files()
            
            logger.info("⚙️ 설정 파일 생성...")
            self.create_config_files()
            
            logger.info("🎮 Gazebo 파일 생성...")
            self.create_gazebo_files()
            
            logger.info("🔍 Zeek 스크립트 생성...")
            self.create_zeek_scripts()
            
            logger.info("📦 Requirements 파일 생성...")
            self.create_requirements_files()
            
            logger.info("🚀 시작 스크립트 생성...")
            self.create_startup_script()
            
            logger.info("✅ 테스트베드 설정 완료!")
            logger.info(f"📍 위치: {self.base_dir}")
            logger.info("🎯 시작하려면: ./start_testbed.sh")
            
        except Exception as e:
            logger.error(f"❌ 설정 중 오류 발생: {e}")
            return False
        
        return True

if __name__ == "__main__":
    setup = TestbedSetup()
    success = setup.run_setup()
    
    if success:
        print("\\n🎉 설정이 완료되었습니다!")
        print("다음 단계:")
        print("1. cd ~/MTD/MTD_full_testbed")
        print("2. ./start_testbed.sh")
    else:
        print("\\n❌ 설정 중 오류가 발생했습니다.")
        sys.exit(1)