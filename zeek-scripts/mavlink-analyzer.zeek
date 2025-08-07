# MAVLink 프로토콜 분석기
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
}