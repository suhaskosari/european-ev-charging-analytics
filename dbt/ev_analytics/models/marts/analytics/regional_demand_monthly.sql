with sessions as (
    select * from {{ ref('fct_charging_sessions') }}
)
select
    country_code,
    city_key,
    date_trunc('month', session_date) as month,
    count(*)                          as sessions_count,
    sum(energy_kwh)                   as total_energy_kwh,
    sum(cost_eur)                     as total_revenue_eur,
    round(avg(energy_kwh), 2)         as avg_energy_kwh_per_session,
    round(avg(duration_min), 1)       as avg_duration_min,
    count(distinct station_id)        as active_stations
from sessions
group by 1, 2, 3
