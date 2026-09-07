select
    country_code,
    month,
    ev_type,
    registrations
from {{ ref('stg_ev_registrations') }}
