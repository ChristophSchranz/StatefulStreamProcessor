import logging
import os
import shutil
import sys
import tempfile

from pyflink.dataset import ExecutionEnvironment
from pyflink.table import BatchTableEnvironment, TableConfig
from pyflink.table.descriptors import FileSystem, OldCsv, Schema
from pyflink.table.types import DataTypes


def word_count():
    f5 = open("README.md", "r")
    content = f5.read()

    t_config = TableConfig()
    env = ExecutionEnvironment.get_execution_environment()
    t_env = BatchTableEnvironment.create(env, t_config)

    # register Results table in table environment
    tmp_dir = tempfile.gettempdir()
    result_path = tmp_dir + '/result'
    if os.path.exists(result_path):
        try:
            if os.path.isfile(result_path):
                os.remove(result_path)
            else:
                shutil.rmtree(result_path)
        except OSError as e:
            logging.error("Error removing directory: %s - %s.", e.filename, e.strerror)

    logging.info("Results directory: %s", result_path)

    t_env.connect(FileSystem().path(result_path)) \
        .with_format(OldCsv()
                     .field_delimiter(',')
                     .field("word", DataTypes.STRING())
                     .field("count", DataTypes.BIGINT())) \
        .with_schema(Schema()
                     .field("word", DataTypes.STRING())
                     .field("count", DataTypes.BIGINT())) \
        .register_table_sink("Results")

    elements = [(word, 1) for word in content.split(" ")]
    t_env.from_elements(elements, ["word", "count"]) \
         .group_by("word") \
         .select("word, count(1) as count") \
         .insert_into("Results")

    t_env.execute("Python batch word count")


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")

    word_count()

