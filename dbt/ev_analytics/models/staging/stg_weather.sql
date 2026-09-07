select
    city_key,
    cast(date as date) as date,
    cast(temp_avg_c as decimal(5, 1)) as temp_avg_c,
    cast(precipitation_mm as decimal(6, 1)) as precipitation_mm,
    source as data_source
from {{ source('raw', 'weather') }}
