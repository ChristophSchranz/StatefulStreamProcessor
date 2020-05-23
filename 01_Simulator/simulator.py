#!/usr/bin/env python3
import time
import paho.mqtt.publish as publish


BROKER_HOST = "localhost"
BROKER_PORT = 1883
EVENT_FILE = "events.json"
TOPIC_NAME = "machine/states"
SAMPLE_RATE = 1000
READ_FIRST_N = 10000

interval = 1 / SAMPLE_RATE
st_t = time.time()
st0 = st_t
with open(EVENT_FILE) as f:
# while True:  # we could create an infinite loop to get a permanent stream
    i = 0
    for line in f.readlines():
        sent = False
        while not sent:
            try:
                # publish with exactly-once delivery (pos=2)
                publish.single(TOPIC_NAME, payload=line.replace("\n", ""),
                               hostname=BROKER_HOST, port=BROKER_PORT, qos=2)
                sent = True
            except OSError as e:
                print("OSError, waiting a second and try again.")
                time.sleep(1)

        # wait until the interval is exceeded
        while time.time() < st_t + interval:
            time.sleep(0.01 * interval)
        st_t = time.time()
        time.sleep(0)

        i += 1
        # Read only the first n records of the event file
        if READ_FIRST_N:
            if i >= READ_FIRST_N:
                break

print(f"Finished in {(time.time() - st0) / i} s per publish.")
