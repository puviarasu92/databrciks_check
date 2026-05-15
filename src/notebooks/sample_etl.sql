-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Sample ETL Notebook
-- MAGIC This notebook demonstrates a simple ETL pipeline.

-- COMMAND ----------

-- Create target schema if not exists
CREATE SCHEMA IF NOT EXISTS ${catalog}.${schema};

-- COMMAND ----------

-- Create a sample table
CREATE TABLE IF NOT EXISTS ${catalog}.${schema}.sales_summary (
  region STRING,
  total_sales DOUBLE,
  order_count BIGINT,
  updated_at TIMESTAMP
);

-- COMMAND ----------

-- Merge new data into the summary table
MERGE INTO ${catalog}.${schema}.sales_summary AS target
USING (
  SELECT
    region,
    SUM(amount) AS total_sales,
    COUNT(*) AS order_count,
    current_timestamp() AS updated_at
  FROM ${catalog}.${schema}.raw_orders
  WHERE order_date >= current_date() - INTERVAL 1 DAY
  GROUP BY region
) AS source
ON target.region = source.region
WHEN MATCHED THEN
  UPDATE SET
    total_sales = source.total_sales,
    order_count = source.order_count,
    updated_at  = source.updated_at
WHEN NOT MATCHED THEN
  INSERT (region, total_sales, order_count, updated_at)
  VALUES (source.region, source.total_sales, source.order_count, source.updated_at);
