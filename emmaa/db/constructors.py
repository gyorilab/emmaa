import re
import logging
import os

from .config import get_databases
from .manager import QueryDatabaseManager, StatementDatabaseManager

logger = logging.getLogger(__name__)


def get_db(name):
    """Get a db instance based on its name in the config or env."""
    defaults = get_databases()
    db_name, db_type = defaults[name]
    m = re.match('(\w+)://.*?/*([\w.]+)', db_name)
    if m is None:
        logger.error("Poorly formed db name: %s" % db_name)
        return
    if db_type == 'query':
        return QueryDatabaseManager(db_name, label=name)
    elif db_type == 'statement':
        return StatementDatabaseManager(db_name, label=name)
