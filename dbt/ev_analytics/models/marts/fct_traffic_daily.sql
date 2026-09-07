select
    city_key,
    date,
    congestion_index
from {{ ref('stg_traffic') }}
