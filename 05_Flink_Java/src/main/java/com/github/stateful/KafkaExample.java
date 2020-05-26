package com.github.stateful;

// make sure that the maven dependencies are correctly set!

import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.connectors.kafka.FlinkKafkaConsumer;
import org.apache.flink.streaming.connectors.kafka.FlinkKafkaProducer;

/**
 * A simple example that shows how to read from and write to modern Kafka. This will read String messages
 * from the input topic, parse them into a POJO type {@link KafkaEvent}, group by some key, and finally
 * perform a rolling addition on each key for which the results are written back to another topic.
 *
 * <p>This example also demonstrates using a watermark assigner to generate per-partition
 * watermarks directly in the Flink Kafka consumer. For demonstration purposes, it is assumed that
 * the String messages are of formatted as a (word,frequency,timestamp) tuple.
 *
 * <p>Example usage:
 * 	--input-topic machine.data --output-topic machine.out --bootstrap.servers localhost:9092
 * 	--zookeeper.connect localhost:2181 --group.id myconsumer
 */
public class KafkaExample extends KafkaExampleUtil {

    public static void main(String[] args) throws Exception {
        // load input arguments or using defaults if none were given
        if (args.length <= 1) {
            System.out.println("no arguments were given, using default arguments:");
            args = new String[]{"--input-topic", "machine.data", "--output-topic", "machine.out", "--bootstrap.servers",
                    "localhost:9092", "--zookeeper.connect", "localhost:2181", "--group.id", "myconsumer"};
        } else
            System.out.println("Arguments:");
        for (String a: args)
            System.out.print(a + " ");
        System.out.println();

        // parse input arguments to new instance of Flink's ParameterTool class
        final ParameterTool parameterTool = ParameterTool.fromArgs(args);
        StreamExecutionEnvironment env = KafkaExampleUtil.prepareExecutionEnv(parameterTool);

//      input string {"thing": "R0815", "quantity": "vaCurr_X10", "phenomenonTime": 1554101188221, "result": 5.81060791015625}

        // create Kafka Consumer
        FlinkKafkaConsumer<String> source = new FlinkKafkaConsumer<>(
                parameterTool.getRequired("input-topic"),
                new SimpleStringSchema(),  // load records as String, should be changed later
                parameterTool.getProperties());

        // create data-stream
        DataStream<String> input = env.addSource(source);
//                keyBy("timestamp");
//                map(new RollingAdditionMapper());

        // print input in stdout
        input.print();

        // add sink to data-stream
        input.addSink(
                new FlinkKafkaProducer<>(
                        parameterTool.getRequired("output-topic"),
//                        new KeyedSerializationSchemaWrapper<>(new KafkaEventSchema()),
                        new SimpleStringSchema(),  // load records as String, should be changed later
                        parameterTool.getProperties())
//                        FlinkKafkaProducer.Semantic.EXACTLY_ONCE)
        );

        // execute the data-stream
        env.execute("Modern Kafka Example");
    }
}
