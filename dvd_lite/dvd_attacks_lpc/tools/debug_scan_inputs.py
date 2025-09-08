#!/usr/bin/env python3
import glob, os
base=os.path.abspath(".")
paths={
  "pcap":glob.glob("bus/captures/pcap/**/*.pcap", recursive=True)+glob.glob("bus/captures/pcap/**/*.pcap.gz", recursive=True),
  "events":glob.glob("bus/events_*.csv"),
  "netanim":glob.glob("bus/dvd_netanim_*.xml"),
}
print("[SCAN]", base)
for k,v in paths.items():
  print(f" - {k:7s}: {len(v)}")
  if v[:3]: 
    for p in v[:3]:
      print("   ", p)
