{#
    This product is explicitly NYC-local: every event in it happens in New
    York City, and "is this event still upcoming?" only means anything in
    New York's wall-clock time.

    The warehouse, however, runs in UTC (docker-compose's postgres:16
    defaults to Etc/UTC). Using bare `current_timestamp` / `current_date`
    therefore silently asks "is this still upcoming *in UTC*?", which is
    wrong for 4-5 hours of every single day: between 8pm EDT and midnight
    EDT, UTC has already rolled over to tomorrow, so tonight's remaining
    NYC events get excluded from the mart as "expired" while they are in
    fact still hours away.

    That was a real, observed bug -- 15 events happening that evening in
    NYC were being dropped from mart_activity_candidates at 8:13pm EDT.

    These two macros are the single place that decision lives. Use them
    instead of bare current_timestamp/current_date in every model and
    singular test that reasons about "now" or "today".
#}

{% macro nyc_now() %}
    (current_timestamp at time zone 'America/New_York')
{% endmacro %}


{% macro nyc_today() %}
    (current_timestamp at time zone 'America/New_York')::date
{% endmacro %}
