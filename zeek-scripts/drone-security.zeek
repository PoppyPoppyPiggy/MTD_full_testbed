# 드론 보안 모니터링 스크립트
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
}