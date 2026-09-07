with reg as (
    select * from {{ ref('fct_ev_registrations') }}
),
pivoted as (
    select
        country_code,
        month,
        sum(case when ev_type = 'BEV' then registrations else 0 end)  as bev_registrations,
        sum(case when ev_type = 'PHEV' then registrations else 0 end) as phev_registrations,
        sum(registrations) as total_registrations
    from reg
    group by 1, 2
)
select
    country_code,
    month,
    bev_registrations,
    phev_registrations,
    total_registrations,
    sum(total_registrations) over (
        partition by country_code order by month
        rows between unbounded preceding and current row
    ) as cumulative_registrations,
    round(
        100.0 * total_registrations / nullif(lag(total_registrations) over (partition by country_code order by month), 0) - 100,
        1
    ) as mom_growth_pct
from pivoted
