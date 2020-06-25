from influxdb import InfluxDBClient
from datetime import datetime
from datetime import timedelta
import dateutil.parser as dup
import time
import random
import numpy as np
import pytz

HOST = '34.107.38.233'
USER = 'admin'
PASSWORD = 'admin'
TABLE_NAME = 'machinedata'
CONTINUOUS_IMPUTATION = True
IMPUTATION_INTERVAL = 5

json_template = {
    "measurement": "spindle_load",
    "tags": {
        "thing": "R0815",
        "component": "C11",
        "level": "0% ... 20%"
    },
    "time": "2009-11-10T23:00:00Z",
    "fields": {
        "duration": 60,
        "value": 0
    }
}

def generate_samples(end_time=None, timedelta_s=600, nsamples=100, low_high_ratio=0.80, nlevels=5):    
    if end_time is None:
        end_time=datetime.now(pytz.UTC)
    d = {}
    d['time'] = np.array([end_time - timedelta(seconds=dt) for dt in sorted(random.choices(range(timedelta_s),k=nsamples), reverse=True)])
    d['duration'] = np.append(d['time'][1:] - d['time'][:-1], timedelta(0))
    
    power_low = random.choices(range(80), k=int(np.round(nsamples*low_high_ratio)))
    power_high = random.choices(range(80, 100), k=int(np.round(nsamples*(1-low_high_ratio))))
    d['power'] = np.array(power_low + power_high, dtype=int)
    random.shuffle(d['power'])
    
    # calculate power level
    level_limits = np.array([100/nlevels*x for x in range(nlevels + 1)], dtype=int)
    level_names = ["{:>2}% ... {:>3}%".format(l, h) for (l, h) in zip(level_limits[:-1], level_limits[1:])]
    d['level'] = np.array([level_names[i] for i in np.array(d['power']*nlevels/100, dtype=int) ])
    
    return d

def impute_samples(thing='R0815', component='C11', samples=None):
    if samples is None:
        samples = generate_samples()
    
    client = InfluxDBClient(HOST, 8086, USER, PASSWORD, TABLE_NAME)
    client.create_database(TABLE_NAME)
    
    json_body = []
    for i in range(len(samples['time'])):
        json_temp = json_template
        json_temp['tags']['thing'] = thing
        json_temp['tags']['component'] = component
        json_temp['tags']['level'] = samples['level'][i]
        json_temp['time'] = samples['time'][i]
        json_temp['fields']['duration'] = samples['duration'][i].seconds
        json_temp['fields']['value'] = samples['power'][i]
        json_body = [json_temp]
        # writing batches of points seems not to work
        client.write_points(json_body)
        
    client.close()
        
impute_samples(component='C11', samples=generate_samples())
impute_samples(component='C12', samples=generate_samples(low_high_ratio=0.5))
impute_samples(component='C13', samples=generate_samples(low_high_ratio=0.99))

while (True):
    time.sleep(IMPUTATION_INTERVAL)
#    print("impute")
    impute_samples(component='C11', samples=generate_samples(timedelta_s=IMPUTATION_INTERVAL, nsamples=int(IMPUTATION_INTERVAL/5+1)))
    impute_samples(component='C12', samples=generate_samples(timedelta_s=IMPUTATION_INTERVAL, nsamples=int(IMPUTATION_INTERVAL/5+1), low_high_ratio=0.5))
    impute_samples(component='C13', samples=generate_samples(timedelta_s=IMPUTATION_INTERVAL, nsamples=int(IMPUTATION_INTERVAL/5+1), low_high_ratio=0.99))
    if (CONTINUOUS_IMPUTATION):
        continue
    break
