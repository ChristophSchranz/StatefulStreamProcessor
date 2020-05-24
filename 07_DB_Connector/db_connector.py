import json

from influxdb import InfluxDBClient

json_body = [
    {
        "measurement": "machinedata",
        "tags": {
            "thing": "TM001",
            "quantity": "test_q2"
        },
        "time": "2009-11-10T23:00:02Z",  # this key must be unique
        "fields": {
            "result": 12.3
        }
    }
]
client = InfluxDBClient('localhost', 8086, 'root', 'root', 'machinedata')
client.create_database('machinedata')
client.write_points(json_body)
result = client.query("select * from machinedata;")
print(json.dumps({"data": list(result.get_points())}, indent=2))

# client.drop_database("machinedata")
