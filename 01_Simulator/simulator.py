#!/usr/bin/env python3
import time
import paho.mqtt.publish as publish

# Note that MQTT publish is a bottleneck that can't publish more than 1000 S/s.
BROKER_HOST = "localhost"
BROKER_PORT = 1883
EVENT_FILE = "events.json"      # file of the records, not a json itself, but each row is
TOPIC_NAME = "machine/states"   # mqtt topic name to produce to
SAMPLE_RATE = 10              # sample rate in messages per second
READ_FIRST_N = None             # only read the first n lines of the file


if __name__ == "__main__":
    st0 = st_t = time.time()
    interval = 1 / SAMPLE_RATE
    print("Starting the Simulator and publish the measurements via MQTT.")

    with open(EVENT_FILE) as f:
        events = f.readlines()

    i = 0
    try:
        # infinite loop to get a permanent stream
        while True:
            for line in events:
                if "actSpeed" not in line and "vaTorque" not in line and "vaLoad" not in line:
                    continue
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
    except KeyboardInterrupt:
        print("Graceful stopped.")

    print(f"Finished in {(time.time() - st0) / i} s per publish. Wrote {i} records.")
