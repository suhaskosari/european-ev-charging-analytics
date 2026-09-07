select
    station_id,
    station_name,
    city_key,
    operator,
    cast(latitude as decimal(9, 5))  as latitude,
    cast(longitude as decimal(9, 5)) as longitude,
    cast(num_connectors as integer) as num_connectors,
    connector_type,
    cast(power_kw as integer) as power_kw,
    source as data_source
from {{ source('raw', 'stations') }}
