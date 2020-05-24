
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import TableConfig, DataTypes, StreamTableEnvironment

# create ExecutionEnvironment, relate explicitly to StreamExecutionEnvironmnent
env = StreamExecutionEnvironment.get_execution_environment()

# set table_config with default properties for now
table_config = TableConfig()
table_config.set_null_check(False)

# Create table environment where the source and sink tables will be registered
table_env = StreamTableEnvironment.create(env, table_config)

from pyflink.table.descriptors import Kafka, Json, OldCsv, Schema
sourcetable = table_env\
    .connect(Kafka.properties({'update-mode':'append', 'connector.topic':'machine.data',
                               'connector.properties.zookeeper.connect':'localhost:2181',
                               'connector.properties.bootstrap.servers':'localhost:9092'}))\
    .with_format(Json().
                 json_schema("{type:'object',properties:{thing: {type: 'string'},quantity:{type:'string'},phenomenonTime:{type:'integer'},result:{type:'number'}}}"))\
    .with_schema(Schema().field("thing", "VARCHAR").field("quantity","VARCHAR").field("phenomenonTime","INT")
                 .field("result","DOUBLE")).register_table_source("Source")

