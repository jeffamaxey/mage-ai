from .constants import TimeInterval, TIME_INTERVAL_TO_TIME_DELTA
from .utils import calculate_metric_for_series, clean_series
from datetime import datetime
from dateutil.relativedelta import relativedelta
import dateutil.parser
import math
import numpy as np
import pandas as pd


MAX_BUCKETS = 40
TIME_SERIES_BUCKETS = 40


def build_buckets(min_value, max_value, max_buckets):
    diff = max_value - min_value
    total_interval = 1 + diff
    bucket_interval = total_interval / max_buckets
    number_of_buckets = max_buckets

    is_integer = False
    parts = str(diff).split('.')
    is_integer = True if len(parts) == 1 else int(parts[1]) == 0
    if is_integer and total_interval <= max_buckets:
        number_of_buckets = int(total_interval)
        bucket_interval = 1
    elif bucket_interval > 1:
        bucket_interval = math.ceil(bucket_interval)
    else:
        bucket_interval = round(bucket_interval * 100, 1) / 100

    buckets = []
    for i in range(number_of_buckets):
        min_v = min_value + (i * bucket_interval)
        max_v = min_value + ((i + 1) * bucket_interval)
        if max_value >= min_v:
            buckets.append(dict(
                max_value=max_v,
                min_value=min_v,
                values=[],
            ))

    return buckets, bucket_interval


def build_histogram_data(arr, max_buckets):
    max_value = max(arr)
    min_value = min(arr)

    buckets, bucket_interval = build_buckets(min_value, max_value, max_buckets)

    if bucket_interval == 0:
        return

    bins = [b['min_value'] for b in buckets] + [buckets[-1]['max_value']]
    count, _ = np.histogram(arr, bins=bins)

    x = []
    y = []

    for idx, bucket in enumerate(buckets):
        x.append(dict(
            max=bucket['max_value'],
            min=bucket['min_value'],
        ))
        y.append(dict(value=count[idx]))

    return dict(
        x=x,
        y=y,
    )


def build_time_series_buckets(df, datetime_column, time_interval, metrics):
    time_values = df[datetime_column]
    datetimes = clean_series(time_values)
    if datetimes.size <= 1:
        return []

    datetimes = datetimes.unique()
    min_value_datetime = datetimes.min()
    max_value_datetime = datetimes.max()

    if type(min_value_datetime) is str:
        min_value_datetime = dateutil.parser.parse(min_value_datetime)
    if type(max_value_datetime) is str:
        max_value_datetime = dateutil.parser.parse(max_value_datetime)

    # If you manually convert the datetime column to a datetime, Pandas will use numpy.datetime64
    # type. This type does not have the methods year, month, day, etc that is used down below.
    datetimes_temp = []
    for dt in datetimes:
        if type(dt) is np.datetime64:
            datetimes_temp.append(pd.to_datetime(dt.astype(datetime)).to_pydatetime())
        else:
            datetimes_temp.append(dt)
    datetimes = datetimes_temp
    if type(min_value_datetime) is np.datetime64:
        min_value_datetime = pd.to_datetime(min_value_datetime.astype(datetime)).to_pydatetime()
    if type(max_value_datetime) is np.datetime64:
        max_value_datetime = pd.to_datetime(max_value_datetime.astype(datetime)).to_pydatetime()

    a, b = [dateutil.parser.parse(d) if type(d) is str else d for d in sorted(datetimes)[:2]]

    year = min_value_datetime.year
    month = min_value_datetime.month
    day = min_value_datetime.day
    hour = min_value_datetime.hour
    minute = min_value_datetime.minute

    start_datetime = min_value_datetime

    if TimeInterval.ORIGINAL == time_interval:
        diff = (b - a).total_seconds()
        if diff >= 60 * 60 * 24 * 365:
            time_interval = TimeInterval.YEAR
        elif diff >= 60 * 60 * 24 * 30:
            time_interval = TimeInterval.MONTH
        elif diff >= 60 * 60 * 24 * 7:
            time_interval = TimeInterval.WEEK
        elif diff >= 60 * 60 * 24:
            time_interval = TimeInterval.DAY
        elif diff >= 60 * 60:
            time_interval = TimeInterval.HOUR
        elif diff >= 60:
            time_interval = TimeInterval.SECOND
        else:
            time_interval = TimeInterval.SECOND

    if TimeInterval.DAY == time_interval:
        start_datetime = datetime(year, month, day, 0, 0, 0)
    elif TimeInterval.HOUR == time_interval:
        start_datetime = datetime(year, month, day, hour, 0, 0)
    elif TimeInterval.MINUTE == time_interval:
        start_datetime = datetime(year, month, day, hour, minute, 0)
    elif TimeInterval.MONTH == time_interval:
        start_datetime = datetime(year, month, 1, 0, 0, 0)
    elif TimeInterval.SECOND == time_interval:
        start_datetime = datetime(year, month, day, hour, minute, 0)
    elif TimeInterval.WEEK == time_interval:
        start_datetime = min_value_datetime - relativedelta(
            days=min_value_datetime.isocalendar()[2],
        )
        start_datetime = datetime(
            start_datetime.year,
            start_datetime.month,
            start_datetime.day,
            0,
            0,
            0,
        )
    elif TimeInterval.YEAR == time_interval:
        start_datetime = datetime(year, 1, 1, 0, 0, 0)

    df_copy = df.copy()
    df_copy[datetime_column] = \
        pd.to_datetime(df[datetime_column]).apply(lambda x: x if pd.isnull(x) else x.timestamp())

    values = [[] for _ in metrics]
    buckets = []

    while not buckets or buckets[-1] <= max_value_datetime.timestamp():
        min_date_ts = start_datetime.timestamp() if not buckets else buckets[-1]
        max_date = datetime.fromtimestamp(min_date_ts) + TIME_INTERVAL_TO_TIME_DELTA[time_interval]
        buckets.append(max_date.timestamp())

        df_in_range = df_copy[(
            df_copy[datetime_column] >= min_date_ts
        ) & (
            df_copy[datetime_column] < max_date.timestamp()
        )]

        for idx, metric in enumerate(metrics):
            aggregation = metric['aggregation']
            column = metric['column']
            series = df_in_range[column]
            values[idx].append(calculate_metric_for_series(series, aggregation))

    return buckets, values
