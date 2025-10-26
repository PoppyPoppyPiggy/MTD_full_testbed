#!/bin/bash

echo -e "📦 Docker 컨테이너 정보 요약\n"
printf "%-30s %-15s %-20s %-15s %-30s\n" "컨테이너 이름" "컨테이너 ID" "상태" "IP 주소" "포트 매핑"
echo "-----------------------------------------------------------------------------------------------------------------------------"

docker ps -a --format '{{.ID}} {{.Names}} {{.Status}}' | while read id name status; do
    ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$id")
    ports=$(docker inspect -f '{{range $p, $conf := .NetworkSettings.Ports}}{{$p}} -> {{(index $conf 0).HostPort}}, {{end}}' "$id" | sed 's/, $//')
    printf "%-30s %-15s %-20s %-15s %-30s\n" "$name" "$id" "$status" "$ip" "${ports:-없음}"
done
