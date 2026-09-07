select
    city_key,
    city_name,
    country,
    country_code,
    cast(latitude as decimal(9, 5))  as latitude,
    cast(longitude as decimal(9, 5)) as longitude,
    cast(population_millions as decimal(6, 2)) as population_millions,
    region
from {{ source('raw', 'cities') }}
