import datetime


def make_date_str(date=None):
    """Return a date string in a standardized format.

    Parameters
    ----------
    date : Optional[datetime.datetime]
        A date object to get the standardized string for. If not provided,
        utcnow() is used to construct the date. (Note: using UTC is important
        because this code may run in multiple contexts).

    Returns
    -------
    str
        The datetime string in a standardized format.
    """
    if not date:
        date = datetime.datetime.utcnow()
    return date.strftime('%Y-%m-%d-%H-%M-%S')
