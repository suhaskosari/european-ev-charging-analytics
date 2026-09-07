with stations as (
    select * from {{ ref('stg_stations') }}
),
cities as (
    select city_key, city_name, country, country_code, region from {{ ref('stg_cities') }}
)
select
    s.station_id,
    s.station_name,
    s.city_key,
    c.city_name,
    c.country,
    c.country_code,
    c.region,
    s.operator,
    s.latitude,
    s.longitude,
    s.num_connectors,
    s.connector_type,
    s.power_kw,
    case
        when s.power_kw >= 150 then 'Ultra-Fast (150kW+)'
        when s.power_kw >= 50  then 'Fast (50-149kW)'
        else 'Standard (<50kW)'
    end as charger_class,
    s.data_source
from stations s
left join cities c on s.city_key = c.city_key
