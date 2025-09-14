FROM python:3.9-slim

# iptables 및 scapy 의존성 설치
RUN apt-get update && \
    apt-get install -y iptables iproute2 tcpdump libpcap-dev

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY controller.py .

CMD ["python", "-u", "controller.py"]