with spine as (
    select unnest(generate_series(
        cast('{{ var("start_date") }}' as date),
        cast('{{ var("end_date") }}' as date),
        interval 1 day
    )) as date_day
)
select
    date_day,
    extract(year from date_day)    as year,
    extract(quarter from date_day) as quarter,
    extract(month from date_day)   as month,
    strftime(date_day, '%B')       as month_name,
    extract(week from date_day)    as iso_week,
    isodow(date_day)               as day_of_week,
    isodow(date_day) in (6, 7)     as is_weekend
from spine
