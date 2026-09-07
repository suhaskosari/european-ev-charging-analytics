with sessions as (
    select * from {{ ref('stg_charging_sessions') }}
),
stations as (
    select station_id, city_key, country_code, region, operator, power_kw, charger_class
    from {{ ref('dim_station') }}
),
prices as (
    select country_code, date, price_eur_per_mwh from {{ ref('stg_energy_prices') }}
)
select
    sess.session_id,
    sess.station_id,
    st.city_key,
    st.country_code,
    st.region,
    st.operator,
    st.charger_class,
    sess.session_date,
    sess.session_hour,
    sess.start_time,
    sess.duration_min,
    sess.energy_kwh,
    sess.cost_eur,
    round(sess.cost_eur / nullif(sess.energy_kwh, 0), 4) as effective_price_eur_per_kwh,
    round(p.price_eur_per_mwh / 1000, 4) as wholesale_price_eur_per_kwh,
    sess.connector_type,
    sess.payment_method
from sessions sess
left join stations st on sess.station_id = st.station_id
left join prices p on st.country_code = p.country_code and sess.session_date = p.date
