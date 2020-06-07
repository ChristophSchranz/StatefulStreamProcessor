package com.github.stateful;

import org.apache.flink.api.common.typeinfo.TypeInformation;
import org.apache.flink.streaming.connectors.kafka.KafkaDeserializationSchema;
import org.apache.kafka.clients.consumer.ConsumerRecord;

import java.util.Properties;

@SuppressWarnings("serial")
public class KafkaSchema implements KafkaDeserializationSchema<KafkaRecord>
{
    @Override
    public boolean isEndOfStream(KafkaRecord nextElement) {
        return false;
    }

    @Override
    public KafkaRecord deserialize(ConsumerRecord<byte[], byte[]> record) throws Exception {
        KafkaRecord data = new KafkaRecord();
        data.key =  new String(record.key());

        // load message into properties
//        data.value = new String(record.value());
        data.content = new Properties();
        String payload = new String(record.value());
        String[] pairs = payload.replace("{", "").replace("}", "").split(",");

        for (String pair: pairs) {
            String[] s = pair.split(":");
            if (s.length < 2)  // return if there is no key-value pair
                return null;

            String key = s[0].replace("\"", "").trim();
            String value = s[1].replace("\"", "").trim();

            //put key and value depending on value type
            data.content.put(key, value);
        }

//        get timestamp, phenomenonTime can't be used properly for simulated data.
//        data.timestamp = Long.valueOf(value);
        data.timestamp = record.timestamp();
        return data;
    }

    @Override
    public TypeInformation<KafkaRecord> getProducedType() {
        return TypeInformation.of(KafkaRecord.class);
    }
}
