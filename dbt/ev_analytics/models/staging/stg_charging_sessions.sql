select
    session_id,
    station_id,
    city_key,
    cast(start_time as timestamp) as start_time,
    cast(date as date) as session_date,
    cast(hour as integer) as session_hour,
    cast(duration_min as decimal(8, 1)) as duration_min,
    cast(energy_kwh as decimal(8, 2)) as energy_kwh,
    cast(cost_eur as decimal(8, 2)) as cost_eur,
    connector_type,
    payment_method
from {{ source('raw', 'charging_sessions') }}
