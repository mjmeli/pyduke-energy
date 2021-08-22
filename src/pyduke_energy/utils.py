from datetime import date, datetime, timezone
from dateutil import parser

def str_to_datetime(str: str):
    return parser.parse(str)

def str_to_date(str: str):
    return str_to_datetime(str).date()

def date_to_datetime(dt: date):
    return datetime(dt.year, dt.month, dt.day)

def date_to_utc_timestamp(dt: date):
    return date_to_datetime(dt).replace(tzinfo=timezone.utc).timestamp()

def utc_timestamp_to_datetime(ts: int):
    return datetime.utcfromtimestamp(ts).replace(tzinfo=timezone.utc)