# ADF Linked Services, Datasets & Trigger

Supporting definitions referenced by [`pipeline_ev_ingestion.json`](pipeline_ev_ingestion.json).
Kept as a design document (not deployed) rather than another batch of JSON,
since the pipeline definition already demonstrates the activity-level shape.

## Linked services

| Name | Type | Connects to |
|---|---|---|
| `LS_ADLS_EVDataLake` | Azure Data Lake Storage Gen2 | `ev-datalake` storage account (bronze/silver/gold containers) |
| `LS_REST_OpenChargeMap` | REST | `api.openchargemap.io` (station locations) |
| `LS_REST_OpenMeteo` | REST | `archive-api.open-meteo.com` (historical weather) |
| `LS_REST_ENTSOE` | REST | ENTSO-E Transparency Platform (day-ahead energy prices) |
| `LS_SFTP_CPOExport` | SFTP | Charge-point-operator daily billing export drop |
| `LS_FabricWarehouse` | Fabric Warehouse (dbt-fabric target) | Gold star schema |
| `LS_KeyVault_EV` | Azure Key Vault | `OpenChargeMapApiKey`, SFTP credentials, ENTSO-E token -- referenced by the pipeline's `SecureString` parameters, never stored in the pipeline JSON itself |

## Datasets

- `DS_REST_OpenChargeMap`, `DS_REST_OpenMeteo`, `DS_REST_ENTSOE` -- parameterized REST datasets (base URL + relative URL per call).
- `DS_SFTP_CPOExport` -- delimited text, `@{formatDateTime(pipeline().TriggerTime,'yyyy-MM-dd')}_sessions.csv`.
- `DS_ADLS_Bronze_*` -- one JSON/text dataset per source, partitioned `bronze/{source}/{yyyy}/{mm}/{dd}/`.

## Trigger

```json
{
  "name": "TR_EV_Ingestion_Daily",
  "properties": {
    "type": "TumblingWindowTrigger",
    "typeProperties": {
      "frequency": "Day",
      "interval": 1,
      "startTime": "2024-01-01T02:00:00Z",
      "delay": "00:15:00",
      "retryPolicy": { "count": 3, "intervalInSeconds": 900 }
    },
    "pipeline": { "pipelineReference": { "referenceName": "PL_EV_Ingestion_Daily", "type": "PipelineReference" } }
  }
}
```

A tumbling-window trigger (rather than a plain schedule trigger) is used
because the pipeline is naturally windowed on the ingestion day -- it makes
backfills for a specific historical date a first-class, replayable operation
(`az datafactory trigger-run rerun`) instead of a one-off manual pipeline run.
