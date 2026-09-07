-- Grain: one row per city per calendar day. Joins charging demand to its
-- candidate drivers (weather, traffic, energy price, weekday) at the grain
-- the statistics and forecasting layers need -- so python/forecasting.py and
-- python/stats_demand_drivers.py can each read one table instead of
-- re-deriving this join.
with sessions_daily as (
    select
        city_key,
        session_date as date,
        count(*)          as sessions_count,
        sum(energy_kwh)   as total_energy_kwh,
        sum(cost_eur)     as total_revenue_eur
    from {{ ref('fct_charging_sessions') }}
    group by 1, 2
),
cities as (
    select city_key, city_name, country, country_code from {{ ref('dim_city') }}
),
calendar as (
    select date_day as date, day_of_week, is_weekend from {{ ref('dim_date') }}
)
select
    c.city_key,
    ci.city_name,
    ci.country,
    ci.country_code,
    c.date,
    cal.day_of_week,
    cal.is_weekend,
    coalesce(sd.sessions_count, 0)    as sessions_count,
    coalesce(sd.total_energy_kwh, 0)  as total_energy_kwh,
    coalesce(sd.total_revenue_eur, 0) as total_revenue_eur,
    w.temp_avg_c,
    w.precipitation_mm,
    t.congestion_index,
    p.price_eur_per_mwh
from (select distinct city_key, date from {{ ref('fct_weather_daily') }}) c
left join sessions_daily sd on c.city_key = sd.city_key and c.date = sd.date
left join cities ci on c.city_key = ci.city_key
left join calendar cal on c.date = cal.date
left join {{ ref('fct_weather_daily') }} w on c.city_key = w.city_key and c.date = w.date
left join {{ ref('fct_traffic_daily') }} t on c.city_key = t.city_key and c.date = t.date
left join {{ ref('fct_energy_prices') }} p on ci.country_code = p.country_code and c.date = p.date
