-- Grain: one row per station per day. Utilization = the share of each
-- connector's available time actually spent charging a vehicle.
with sessions as (
    select * from {{ ref('fct_charging_sessions') }}
),
stations as (
    select station_id, city_key, city_name, country, country_code, num_connectors, charger_class
    from {{ ref('dim_station') }}
),
daily as (
    select
        station_id,
        session_date,
        count(*)                  as sessions_count,
        sum(duration_min)         as total_duration_min,
        sum(energy_kwh)           as total_energy_kwh,
        sum(cost_eur)             as total_revenue_eur,
        avg(duration_min)         as avg_duration_min
    from sessions
    group by 1, 2
)
select
    d.station_id,
    st.city_key,
    st.city_name,
    st.country,
    st.country_code,
    st.charger_class,
    d.session_date,
    d.sessions_count,
    d.total_energy_kwh,
    d.total_revenue_eur,
    round(d.avg_duration_min, 1) as avg_duration_min,
    round(least(d.total_duration_min / (24 * 60 * nullif(st.num_connectors, 0)), 1), 4) as utilization_rate
from daily d
left join stations st on d.station_id = st.station_id
