# DAX Measures

Paste these into a dedicated `_Measures` table in Power BI (Model view -> New Table -> `_Measures = {BLANK()}`, then add each measure to it) once the model in [data_model.md](data_model.md) is built.

## Charging Sessions & Energy

```dax
Total Sessions =
DISTINCTCOUNT ( fct_charging_sessions[session_id] )

Total Energy (kWh) =
SUM ( fct_charging_sessions[energy_kwh] )

Total Revenue (EUR) =
SUM ( fct_charging_sessions[cost_eur] )

Average Session Energy (kWh) =
DIVIDE ( [Total Energy (kWh)], [Total Sessions] )

Average Session Duration (min) =
AVERAGE ( fct_charging_sessions[duration_min] )

Average Effective Price (EUR/kWh) =
DIVIDE ( [Total Revenue (EUR)], [Total Energy (kWh)] )

Sessions YoY % =
VAR CurrentSessions = [Total Sessions]
VAR PriorYearSessions =
    CALCULATE ( [Total Sessions], SAMEPERIODLASTYEAR ( dim_date[date_day] ) )
RETURN
    DIVIDE ( CurrentSessions - PriorYearSessions, PriorYearSessions )

Weekend Session Share % =
VAR WeekendSessions = CALCULATE ( [Total Sessions], dim_date[is_weekend] = TRUE )
RETURN
    DIVIDE ( WeekendSessions, [Total Sessions] )
```

## Station Utilization

```dax
Average Utilization % =
AVERAGE ( station_utilization[utilization_rate] )

Peak Utilization % =
MAX ( station_utilization[utilization_rate] )

Underutilized Stations ( <20% ) =
CALCULATE (
    DISTINCTCOUNT ( station_utilization[station_id] ),
    station_utilization[utilization_rate] < 0.20
)

Active Stations =
DISTINCTCOUNT ( fct_charging_sessions[station_id] )

Sessions per Station =
DIVIDE ( [Total Sessions], [Active Stations] )
```

## EV Market Growth

```dax
Total EV Registrations =
SUM ( fct_ev_registrations[registrations] )

BEV Share % =
VAR BevRegs = CALCULATE ( [Total EV Registrations], fct_ev_registrations[ev_type] = "BEV" )
RETURN
    DIVIDE ( BevRegs, [Total EV Registrations] )

Registrations MoM % =
VAR PrevMonth =
    CALCULATE ( [Total EV Registrations], DATEADD ( dim_date[date_day], -1, MONTH ) )
RETURN
    DIVIDE ( [Total EV Registrations] - PrevMonth, PrevMonth )
```

## Weather / Traffic / Energy Price Context

```dax
Average Temperature (C) =
AVERAGE ( fct_weather_daily[temp_avg_c] )

Average Congestion Index =
AVERAGE ( fct_traffic_daily[congestion_index] )

Average Wholesale Price (EUR/MWh) =
AVERAGE ( fct_energy_prices[price_eur_per_mwh] )

Cold Day Sessions ( <5C ) =
CALCULATE (
    [Total Sessions],
    FILTER ( fct_weather_daily, fct_weather_daily[temp_avg_c] < 5 )
)
```

## Forecast overlay (import `charging_demand_forecast.csv` as its own table)

```dax
Forecast Sessions =
SUM ( charging_demand_forecast[forecast_sessions] )
```
Plot this as a dashed line continuing the `Total Sessions` trend per city --
the underlying data already tags each row `type = "forecast"` so the two
series render as one continuous line with a visual style break at today's date.

## Expansion candidate overlay (import `station_expansion_candidates.csv`)

```dax
Expansion Candidate Count =
CALCULATE (
    COUNTROWS ( station_expansion_candidates ),
    station_expansion_candidates[expansion_candidate] = TRUE
)
```
Use `candidate_latitude` / `candidate_longitude` as a second series on the
map visual from `data_model.md`'s Network Expansion page, filtered to
`expansion_candidate = TRUE`.
