{#
    SCD Type 2 history for the NYC Parks feed.

    The source API is stateless: it serves a rolling 14-day window and offers
    no way to ask what it said yesterday. Once a record changes, the previous
    version is gone from the publisher's side permanently. Raw ingestion
    upserts on the API's guid, so it too keeps only the latest state.

    This snapshot is the only place the change history exists. It is what
    makes questions like "when was this event cancelled, and how much notice
    did attendees get?" answerable at all -- that data is not obtainable from
    the source, at any price, after the fact.

    Strategy notes:

    - `check` rather than `timestamp`. The obvious candidate for a timestamp
      strategy, `ingested_at`, is rewritten on every single upsert whether or
      not anything actually changed, so it would manufacture a new version per
      run and turn the snapshot into a write log rather than a change log.
      `ingested_at` is deliberately absent from check_cols for the same reason.

    - The columns checked are the ones whose changes carry meaning for a user:
      the title (which is where cancellations are announced, as a `CANCELED:`
      prefix), the schedule, the location, and the links. `raw_payload` is
      excluded -- it restates the same fields, so including it would double
      every diff and add nothing.

    - `invalidate_hard_deletes` is off on purpose. A record leaving the feed
      is usually just the 14-day window sliding, not a deletion -- treating
      that as an end-of-life event would fabricate "cancellations" for every
      event that simply took place as scheduled.
#}

{% snapshot snap_nyc_parks_events %}

{{
    config(
        target_schema='snapshots',
        unique_key='source_record_id',
        strategy='check',
        check_cols=[
            'title',
            'startdate',
            'enddate',
            'starttime',
            'endtime',
            'location',
            'parknames',
            'categories',
            'link_url',
            'registration_url'
        ]
    )
}}

select
    source_record_id,
    title,
    startdate,
    enddate,
    starttime,
    endtime,
    location,
    parknames,
    categories,
    link_url,
    registration_url,
    lat,
    lon,
    ingested_at
from {{ source('raw', 'nyc_parks_events') }}

{% endsnapshot %}
