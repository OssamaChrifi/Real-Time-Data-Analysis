from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *

import time
import sys
sys.path.insert(0,'.')

KAFKA_TOPIC_NAME = "orderstopicdemo"
KAFKA_BOOTSTRAP_SERVER = 'localhost:9092'

file_path = 'in/customers.csv'

mysql_host_name = 'localhost'
mysql_port_no = '3306'
mysql_database_name = 'sales_db'
mysql_driver_class = 'com.mysql.cj.jdbc.Driver'
mysql_table_name = 'total_sales_by_source_state'
mysql_user_name = 'root'
mysql_password = 'datamaking'
mysql_jdbc_url = 'jdbc:mysql://'+mysql_host_name+':'+mysql_port_no+'/'+mysql_database_name

cassandra_host_name = 'localhost'
cassandra_port_no = '9042'
cassandra_keyspace_name = 'sales_ks'
cassandra_table_name = 'orders'

def save_to_cassandra(current_df, epoc_id):
    print("printing epoc_id: ")
    print(epoc_id)

    print("Printing befor cassandra table save: "+str(epoc_id))
    current_df \
    .write \
    .format("org.apache.spark.sql.cassandra") \
    .mode("append") \
    .options(table=cassandra_table_name, keyspace=cassandra_keyspace_name) \
    .save()
    
    print("Printing after cassandra table save : "+str(epoc_id))

def save_to_mysql(current_df, epoc_id):
    
    print('Printing epoc_id: ')
    print(epoc_id)

    processed_at = time.strftime("%Y-%m-%d %H:%M:%S")

    current_df_final = current_df \
        .withColumn("processed_at", lit(processed_at)) \
        .withColumn("batch_id", lit(epoc_id))
    
    print("Printing befor mysql table save : "+str(epoc_id))
    current_df_final \
    .write \
    .format("jdbc") \
    .mode("append") \
    .option("driver", mysql_driver_class) \
    .option("url", mysql_jdbc_url) \
    .option("dbtable", mysql_table_name) \
    .option("user", mysql_user_name) \
    .option("password", mysql_password) \
    .save()
    
    print("Printing after mysql table save : "+str(epoc_id))
    

if __name__ == '__main__':
    print('Data Processing Application Started ...')
    print(time.strftime("%Y-%m-%d %H:%M:%S"))

    spark = SparkSession \
        .builder \
        .appName('Pyspark Structured Streaming with kafka and Cassandra') \
        .master('local[*]') \
        .config("spark.jars", "/usr/share/java/mysql-connector-java-8.2.0.jar") \
        .config('spark.cassandra.connection.host', cassandra_host_name) \
        .config('spark.cassandra.connection.port', cassandra_port_no) \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel('error')

    orders_df = spark \
        .readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVER) \
        .option("subscribe", KAFKA_TOPIC_NAME) \
        .option("startingOffsets", "latest") \
        .load()
    
    print("Print Schema of orders:")
    orders_df.printSchema()

    orders_df1 = orders_df.selectExpr("CAST(value AS STRING)", "timestamp")

    orders_schema = StructType() \
        .add('ID', IntegerType()) \
        .add('Created At', StringType()) \
        .add('Discount', FloatType()) \
        .add("Product ID", IntegerType()) \
        .add('Quantity', IntegerType()) \
        .add('Subtotal', FloatType()) \
        .add('Tax', FloatType()) \
        .add('Total', FloatType()) \
        .add('User ID', IntegerType())

    # Define the schema to match the Cassandra table
    cassandra_schema = StructType([
        StructField("order_id", IntegerType(), False),
        StructField("created_at", StringType(), True),
        StructField("customer_id", IntegerType(), True),
        StructField("discount", FloatType(), True),
        StructField("product_id", StringType(), True),
        StructField("quantity", StringType(), True),
        StructField("subtotal", FloatType(), True),
        StructField("tax", FloatType(), True),
        StructField("timestamp", StringType(), True),
        StructField("total", FloatType(), True)
    ])

    orders_df2 = orders_df1 \
        .select(from_json(col("value"), orders_schema).alias("orders"), 'timestamp')
    
    orders_df3 = orders_df2.select("orders.*", "timestamp")

    # Rename the columns to match the Cassandra table
    orders_df3 = orders_df3.withColumnRenamed("ID", "order_id")
    orders_df3 = orders_df3.withColumnRenamed("Created At", "created_at")
    orders_df3 = orders_df3.withColumnRenamed("Product ID", "product_id")
    orders_df3 = orders_df3.withColumnRenamed("Quantity", "quantity")
    orders_df3 = orders_df3.withColumnRenamed("Subtotal", "subtotal")
    orders_df3 = orders_df3.withColumnRenamed("Discount", "discount")
    orders_df3 = orders_df3.withColumnRenamed("Tax", "tax")
    orders_df3 = orders_df3.withColumnRenamed("User ID", "customer_id")

    # Cast the columns of your DataFrame to match the Cassandra schema
    for field in cassandra_schema:
        column_name = field.name
        data_type = field.dataType
        orders_df3 = orders_df3.withColumn(column_name, orders_df3[column_name].cast(data_type))

    # Reorder the columns to match the Cassandra table schema
    column_order = [
        "order_id", "created_at", "customer_id", "discount", "product_id",
        "quantity", "subtotal", "tax", "timestamp", "total"
    ]
    orders_df3 = orders_df3.select(column_order)

    orders_df3 \
    .writeStream \
    .trigger(processingTime='15 seconds') \
    .outputMode("update") \
    .foreachBatch(save_to_cassandra) \
    .start()

    customer_df = spark.read.csv(file_path, header=True, inferSchema = True)
    customer_df.printSchema()
    customer_df.show(5, False)

    orders_df4 = orders_df3.join(customer_df, customer_df.ID == orders_df3['customer_id'], how = 'inner')
    print("Printing Schema of orders_df4:")
    orders_df4.printSchema()

    orders_df5 = orders_df4 \
    .groupBy('source', 'state') \
    .agg(sum('total')) \
    .select('source','state', col('sum(total)').alias('total_sum_amount')) 
    print("Printing Schema of orders_df5:")
    orders_df5.printSchema()

    trans_detail_write_stream = orders_df5 \
        .writeStream \
        .trigger(processingTime='15 seconds') \
        .outputMode("update") \
        .option("truncate", "false") \
        .format("console") \
        .start()
    
    orders_df5 \
    .writeStream \
    .trigger(processingTime='15 seconds') \
    .outputMode("update") \
    .foreachBatch(save_to_mysql)\
    .start()

    trans_detail_write_stream.awaitTermination()

    print("Pyspark Structures Streaming witch Kafka Demo Application Completed")
