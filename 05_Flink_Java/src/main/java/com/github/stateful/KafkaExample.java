package com.github.stateful;

// make sure that the maven dependencies are correctly set!

import org.apache.flink.api.common.functions.ReduceFunction;
import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.api.java.utils.ParameterTool;
import org.apache.flink.streaming.api.TimeCharacteristic;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.windowing.time.Time;
import org.apache.flink.streaming.connectors.kafka.FlinkKafkaConsumer;
import org.apache.flink.streaming.connectors.kafka.FlinkKafkaProducer;
import org.apache.flink.streaming.connectors.kafka.FlinkKafkaProducer.Semantic;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.common.serialization.StringSerializer;
import org.apache.flink.api.common.functions.AggregateFunction;

import java.time.LocalTime;

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
            args = new String[]{"--input-topic", "machine.data", "--output-topic", "machine.out",
                    "--bootstrap.servers", "localhost:9092", "--zookeeper.connect", "localhost:2181",
                    "--group.id", "myconsumer"};
        } else
            System.out.println("Arguments:");
        for (String a: args)
            System.out.print(a + " ");
        System.out.println();

        // parse input arguments to new instance of Flink's ParameterTool class
        final ParameterTool parameterTool = ParameterTool.fromArgs(args);
        StreamExecutionEnvironment env = KafkaExampleUtil.prepareExecutionEnv(parameterTool);
        // to use allowed lateness and timestamp from kafka message
        env.setStreamTimeCharacteristic(TimeCharacteristic.EventTime);

//      input string {"thing": "R0815", "quantity": "vaCurr_X10", "phenomenonTime": 1554101188221, "result": 5.81060791015625}

        // create Kafka Consumer
        FlinkKafkaConsumer<String> source = new FlinkKafkaConsumer<>(
                parameterTool.getRequired("input-topic"),
                new SimpleStringSchema(),  // load records as String, should be changed later
                parameterTool.getProperties());

        // create Kafka Producer
        FlinkKafkaProducer<String> kafkaProducer =
                new FlinkKafkaProducer<String>(
                        parameterTool.getRequired("output-topic"),
                        ((value, timestamp) ->
                                new ProducerRecord<byte[], byte[]>(
                                        parameterTool.getRequired("output-topic"),
                                        "myKey".getBytes(),
                                        value.getBytes())),
                        parameterTool.getProperties(),
                        Semantic.AT_LEAST_ONCE);

        Producer<String> p = new Producer<String>(
                parameterTool.getRequired("bootstrap.servers"),
                StringSerializer.class.getName());

        // create data-stream
        DataStream<String> stream = env.addSource(source);

        stream
                .timeWindowAll(Time.seconds(5)) // ignoring grouping per key
                .reduce(new ReduceFunction<String>()
                {
                    @Override
                    public String reduce(String value1, String value2) throws Exception
                    {
                        System.out.println(LocalTime.now() + " -> " + value1 + "   " + value2);
                        return value1+value2;
                    }
                });
//        stream
//                .filter((record) -> record.value != null && !record.value.isEmpty())
//                .keyBy(record -> record.key)
//                .timeWindow(Time.seconds(5))
//                .allowedLateness(Time.milliseconds(500))
//                .aggregate(new AggregateFunction<KafkaRecord, String, String>()  // kafka aggregate API is very simple but same can be achieved by Flink's reduce
//                {
//                    @Override
//                    public String createAccumulator() {
//                        return "";
//                    }
//
//                    @Override
//                    public String add(KafkaRecord record, String accumulator) {
//                        return accumulator + record.value.length();
//                    }
//
//                    @Override
//                    public String getResult(String accumulator) {
//                        return accumulator;
//                    }
//
//                    @Override
//                    public String merge(String a, String b) {
//                        return a+b;
//                    }
//                });
        stream.addSink(kafkaProducer);

        // produce a number as string every second
        new NumberGenerator(p, parameterTool.getRequired("output-topic")).start();

        // print input in stdout
//        stream.print();
        p.send("output-topic", "hua" );
        // for visual topology of the pipeline. Paste the below output in https://flink.apache.org/visualizer/
        System.out.println( env.getExecutionPlan() );

//        // add sink to data-stream
//        stream.addSink(
//                new FlinkKafkaProducer<>(
//                        parameterTool.getRequired("output-topic"),
////                        new KeyedSerializationSchemaWrapper<>(new KafkaEventSchema()),
//                        new SimpleStringSchema(),  // load records as String, should be changed later
//                        parameterTool.getProperties())
////                        FlinkKafkaProducer.Semantic.EXACTLY_ONCE)
//        );

        // execute the data-stream
        env.execute("Modern Kafka Example");
    }
}
