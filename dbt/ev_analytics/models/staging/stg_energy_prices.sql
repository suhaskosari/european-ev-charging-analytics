select
    country_code,
    cast(date as date) as date,
    cast(price_eur_per_mwh as decimal(8, 2)) as price_eur_per_mwh
from {{ source('raw', 'energy_prices') }}
