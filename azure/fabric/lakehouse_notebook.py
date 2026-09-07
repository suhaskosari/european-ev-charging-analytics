"""
Microsoft Fabric Lakehouse notebook (PySpark): Bronze -> Silver transform for
the EV charging platform. This is the production, Spark-scale counterpart to
python/etl_clean_transform.py -- same cleaning logic (dedup, mixed-timestamp
parsing, sign-error correction, missing-value imputation), expressed against
Delta tables in a Fabric Lakehouse instead of pandas DataFrames over local
CSVs.

Not executed as part of this repo's local demo (it requires a Fabric
Lakehouse / Spark runtime) -- included as a real, runnable notebook so the
Bronze -> Silver design in azure/README.md is concrete code, not a diagram
claim. Would be scheduled as the `Transform_Bronze_To_Silver` activity in
adf/pipeline_ev_ingestion.json, or natively via a Fabric Data Pipeline.

Run inside a Fabric notebook cell (or Databricks) attached to a Lakehouse
with `Files/bronze/ev/...` mounted; `run_date` is passed as a notebook
parameter by the orchestrating pipeline.
"""
from pyspark.sql import SparkSession, functions as F, Window

spark = SparkSession.builder.appName("ev_bronze_to_silver").getOrCreate()

run_date = spark.conf.get("run_date", None)  # injected by the ADF/Fabric pipeline parameter
BRONZE = "Files/bronze/ev"
SILVER_TABLES = "Tables/silver"


def bronze_path(source: str) -> str:
    return f"{BRONZE}/{source}/{run_date}/*.json" if run_date else f"{BRONZE}/{source}/*.json"


def clean_charging_sessions():
    df = spark.read.json(bronze_path("charging_sessions"))

    # normalize the two known timestamp formats from the CPO export
    iso_ts = F.to_timestamp("start_time")
    alt_ts = F.to_timestamp("start_time", "dd/MM/yyyy HH:mm")
    df = df.withColumn("start_time", F.coalesce(iso_ts, alt_ts))
    df = df.filter(F.col("start_time").isNotNull())

    # dedupe retry-on-timeout double-writes, keep first-seen per session_id
    w = Window.partitionBy("session_id").orderBy(F.col("_ingested_at").asc())
    df = df.withColumn("_rn", F.row_number().over(w)).filter(F.col("_rn") == 1).drop("_rn")

    # sign-error costs (billing refund coded as negative charge)
    df = df.withColumn("cost_eur", F.abs(F.col("cost_eur")))

    # impute missing energy readings from duration x rated power, joined from the stations silver table
    stations = spark.table(f"{SILVER_TABLES}.stations").select("station_id", "power_kw")
    df = df.join(stations, "station_id", "left")
    est = (F.col("duration_min") / 60) * F.col("power_kw") * 0.85
    df = df.withColumn(
        "energy_kwh",
        F.coalesce(F.col("energy_kwh"), F.least(F.round(est, 2), F.lit(95.0))),
    ).drop("power_kw")

    df = df.filter(F.col("duration_min") > 0)
    df = df.withColumn("payment_method", F.initcap(F.trim("payment_method")))

    (df.write.format("delta").mode("overwrite")
       .partitionBy("session_date" if run_date is None else None)
       .saveAsTable(f"{SILVER_TABLES}.charging_sessions"))
    return df.count()


def clean_stations():
    df = spark.read.json(bronze_path("charging_stations")).dropDuplicates(["station_id"])
    df = df.withColumn("connector_type", F.initcap(F.trim("connector_type")))
    df = df.withColumn(
        "connector_type",
        F.when(F.col("connector_type") == "Chademo", "CHAdeMO").otherwise(F.col("connector_type")),
    )
    df.write.format("delta").mode("overwrite").saveAsTable(f"{SILVER_TABLES}.stations")
    return df.count()


def clean_weather():
    df = spark.read.json(bronze_path("weather"))
    w = Window.partitionBy("city_key").orderBy("date")
    filled = F.last("temp_avg_c", ignorenulls=True).over(w.rowsBetween(Window.unboundedPreceding, 0))
    df = df.withColumn("temp_avg_c", F.coalesce("temp_avg_c", filled))
    df.write.format("delta").mode("overwrite").saveAsTable(f"{SILVER_TABLES}.weather")
    return df.count()


if __name__ == "__main__":
    n_stations = clean_stations()
    n_sessions = clean_charging_sessions()
    n_weather = clean_weather()
    print(f"Silver load complete for run_date={run_date}: "
          f"{n_stations} stations, {n_sessions} sessions, {n_weather} weather rows")
