select
    city_key,
    date,
    temp_avg_c,
    precipitation_mm,
    data_source
from {{ ref('stg_weather') }}
