select
    city_key,
    cast(date as date) as date,
    cast(congestion_index as decimal(6, 1)) as congestion_index
from {{ source('raw', 'traffic') }}
