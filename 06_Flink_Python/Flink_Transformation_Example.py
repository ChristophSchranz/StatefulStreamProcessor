import glob
import os
import sys

from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import TableConfig, DataTypes, StreamTableEnvironment

# create ExecutionEnvironment, relate explicitly to StreamExecutionEnvironmnent
env = StreamExecutionEnvironment.get_execution_environment()

# set table_config with default properties for now
table_config = TableConfig()
table_config.set_null_check(False)

# Create table environment where the source and sink tables will be registered
table_env = StreamTableEnvironment.create(env, table_config)

from pyflink.table.descriptors import Kafka, Json, OldCsv, Schema, FileSystem

directories = ['/flink/lib']
for directory in directories:
    for jar in glob.glob(os.path.join(directory, '*.jar')):
        sys.path.append(jar)

# from org.apache.flink.streaming.connectors.kafka import FlinkKafkaConsumer11
# from org.apache.flink.streaming.connectors.kafka import FlinkKafkaConsumer09

OldCsv()
print("debug 010")

Kafka()
print("debug 020")
Json()
print("debug 030")


sourcetable = table_env \
    .connect(Kafka()
             .properties({'update-mode': 'append', 'connector.topic': 'machine.data',
                          'connector.properties.zookeeper.connect': 'localhost:2181',
                          'connector.properties.bootstrap.servers.': 'localhost:9092'})) \
    .with_format(Json().
                 json_schema(
    "{type:'object',properties:{thing: {type: 'string'},quantity:{type:'string'},phenomenonTime:{type:'integer'},result:{type:'number'}}}") \
                .fail_on_missing_field(False)) \
    .with_schema(Schema()
                 .field("thing", DataTypes.STRING())
                 .field("quantity", DataTypes.STRING())
                 .field("phenomenonTime", DataTypes.INT())
                 .field("result", DataTypes.DOUBLE())) \
    .create_temporary_table("Source")

print(type(sourcetable))
print(sourcetable)

# sinktable = table_env\
#     .connect(Kafka().properties({'update-mode':'append', 'connector.topic':'machine.out',
#                                'connector.properties.zookeeper.connect':'localhost:2181',
#                                'connector.properties.bootstrap.servers':'localhost:9092'})) \
#     .with_format(Json().
#                  json_schema("{type:'object',properties:{thing: {type: 'string'},quantity:{type:'string'},phenomenonTime:{type:'integer'},result:{type:'number'}}}"))\
#     .with_schema(Schema().field("thing", "VARCHAR").field("quantity", "VARCHAR").field("phenomenonTime", "INT")
#                  .field("result", "DOUBLE")).create_temporary_table("Sink")
#
#
# result = table_env.from_path('Source').select("*").insert_into("Sink")
# print(type(result))
# result.print_schema()


table_env.connect(
    FileSystem().path("file://flink/result.csv")) \
    .with_format(OldCsv()
                 .field_delimiter(',')
                 .field('thing', DataTypes.STRING())
                 .field('quantity', DataTypes.STRING())
                 .field('phenomenonTime', DataTypes.INT())
                 .field('result', DataTypes.DOUBLE())) \
    .with_schema(Schema()
                 .field('thing', DataTypes.STRING())
                 .field('quantity', DataTypes.STRING())
                 .field('phenomenonTime', DataTypes.INT())
                 .field('result', DataTypes.DOUBLE())) \
    .create_temporary_table('Sink')

result = table_env.from_path('Source').select("*").insert_into("Sink")

table_env.execute("Python Kafka stream")
