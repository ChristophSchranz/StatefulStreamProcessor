import json
import pytz
from datetime import datetime
from confluent_kafka import Consumer
from influxdb import InfluxDBClient

# create InfluxDB Connector and create database if not already done
client = InfluxDBClient('localhost', 8086, 'root', 'root', 'machinedata')
client.create_database('machinedata')

result = client.query('select count(*) from machinedata;')
print(result)
