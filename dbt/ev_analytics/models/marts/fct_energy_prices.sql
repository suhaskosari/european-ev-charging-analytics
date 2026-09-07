select
    country_code,
    date,
    price_eur_per_mwh
from {{ ref('stg_energy_prices') }}
