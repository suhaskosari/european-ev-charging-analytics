select
    country_code,
    cast(month as date) as month,
    ev_type,
    cast(registrations as integer) as registrations
from {{ source('raw', 'ev_registrations') }}
