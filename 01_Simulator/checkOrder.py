#!/usr/bin/env python3
import json

BROKER_HOST = "localhost"
BROKER_PORT = 1883
EVENT_FILE = "events.json"      # file of the records, not a json itself, but each row is

with open(EVENT_FILE) as f:
    i = 0
    timestamp = 0
    for line in f.readlines():
        i += 1
        record = json.loads(line)
        if record.get("Timestamp") < timestamp:
            print("unorder!")
            print(record)
            print(timestamp)
            print(i)
        timestamp = record.get("Timestamp")
    print(f"No fuck.")
