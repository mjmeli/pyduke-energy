"""Utility functions."""

from datetime import date, datetime, timezone

from dateutil import parser


def str_to_datetime(val: str):
    """Convert a string to a datetime object."""
    return parser.parse(val)


def str_to_date(val: str):
    """Convert a string to a date object."""
    return str_to_datetime(val).date()


def date_to_datetime(val: date):
    """Convert a date to a datetime with time component at 0:00."""
    return datetime(val.year, val.month, val.day)


def date_to_utc_timestamp(val: date):
    """Convert a date to a UTC timestamp based on 0:00 UTC for that day."""
    return date_to_datetime(val).replace(tzinfo=timezone.utc).timestamp()


def utc_timestamp_to_datetime(val: int):
    """Convert a UTC timezone to a UTC datetime."""
    return datetime.utcfromtimestamp(val).replace(tzinfo=timezone.utc)
