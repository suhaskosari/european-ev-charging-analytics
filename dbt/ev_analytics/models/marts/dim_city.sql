select
    city_key,
    city_name,
    country,
    country_code,
    latitude,
    longitude,
    population_millions,
    region
from {{ ref('stg_cities') }}
