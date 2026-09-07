-- ============================================================================
-- European EV Mobility & Charging Demand Analytics Platform - Warehouse Schema
-- Target: PostgreSQL (production, e.g. Azure Database for PostgreSQL or
-- Fabric Warehouse's T-SQL surface). Locally, dbt/DuckDB materializes the
-- same shapes for a zero-infrastructure demo -- see dbt/ev_analytics/models.
-- Star schema: one wide fact per business process, conformed dimensions.
-- ============================================================================

create schema if not exists warehouse;
set search_path to warehouse;

-- ----------------------------------------------------------------------------
-- Dimensions
-- ----------------------------------------------------------------------------

create table if not exists dim_city (
    city_key                 text         primary key,
    city_name                text         not null,
    country                  text         not null,
    country_code             char(2)      not null,
    latitude                 numeric(9, 5) not null,
    longitude                numeric(9, 5) not null,
    population_millions      numeric(6, 2),
    region                   text         not null            -- Nordics, Western/Southern/Eastern Europe
);

create table if not exists dim_station (
    station_id                text        primary key,
    station_name              text        not null,
    city_key                  text        references dim_city (city_key),
    operator                  text        not null,
    latitude                  numeric(9, 5) not null,
    longitude                 numeric(9, 5) not null,
    num_connectors             int        not null,
    connector_type              text      not null,            -- Type 2, CCS, CHAdeMO
    power_kw                    int       not null,
    charger_class                text     not null,            -- Standard/Fast/Ultra-Fast
    data_source                  text     not null default 'synthetic'
);

create table if not exists dim_date (
    date_day               date         primary key,
    year                    int         not null,
    quarter                 int         not null,
    month                   int         not null,
    month_name              text        not null,
    iso_week                int         not null,
    day_of_week             int         not null,        -- 1=Mon ... 7=Sun
    is_weekend               boolean     not null
);

-- ----------------------------------------------------------------------------
-- Facts
-- ----------------------------------------------------------------------------

create table if not exists fct_charging_sessions (
    session_id                  text       primary key,
    station_id                  text       references dim_station (station_id),
    city_key                    text       references dim_city (city_key),
    country_code                char(2)    not null,
    session_date                 date      not null references dim_date (date_day),
    session_hour                  int      not null,
    start_time                     timestamp not null,
    duration_min                    numeric(8, 1) not null,
    energy_kwh                       numeric(8, 2) not null,
    cost_eur                          numeric(8, 2) not null,
    effective_price_eur_per_kwh        numeric(8, 4),
    wholesale_price_eur_per_kwh         numeric(8, 4),
    connector_type                       text not null,
    payment_method                        text not null
);

create table if not exists fct_energy_prices (
    country_code               char(2)    not null,
    date                        date      not null references dim_date (date_day),
    price_eur_per_mwh            numeric(8, 2) not null,
    primary key (country_code, date)
);

create table if not exists fct_weather_daily (
    city_key                    text      references dim_city (city_key),
    date                          date    not null references dim_date (date_day),
    temp_avg_c                    numeric(5, 1),
    precipitation_mm                numeric(6, 1),
    data_source                      text not null default 'synthetic',
    primary key (city_key, date)
);

create table if not exists fct_traffic_daily (
    city_key                    text      references dim_city (city_key),
    date                          date    not null references dim_date (date_day),
    congestion_index               numeric(6, 1) not null,
    primary key (city_key, date)
);

create table if not exists fct_ev_registrations (
    country_code                char(2)   not null,
    month                          date    not null,
    ev_type                          text  not null,          -- BEV, PHEV
    registrations                     int  not null,
    primary key (country_code, month, ev_type)
);

-- ----------------------------------------------------------------------------
-- Indexes for common analytical access paths
-- ----------------------------------------------------------------------------
create index if not exists ix_sessions_station    on fct_charging_sessions (station_id);
create index if not exists ix_sessions_date        on fct_charging_sessions (session_date);
create index if not exists ix_sessions_city        on fct_charging_sessions (city_key);
create index if not exists ix_weather_city_date     on fct_weather_daily (city_key, date);
create index if not exists ix_traffic_city_date      on fct_traffic_daily (city_key, date);
create index if not exists ix_prices_country_date     on fct_energy_prices (country_code, date);
