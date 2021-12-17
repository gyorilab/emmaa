import re
import logging
import os

from .config import get_databases
from .manager import QueryDatabaseManager, StatementDatabaseManager

logger = logging.getLogger(__name__)


def get_db(name):
    """Get a db instance based on its name in the config or env."""
    defaults = get_databases()
    db_name = defaults[name]
    m = re.match('(\w+)://.*?/([\w.]+)', db_name)
    if m is None:
        logger.error("Poorly formed db name: %s" % db_name)
        return
    return QueryDatabaseManager(db_name, label=name)


def get_statements_db():
    """Get the statements database."""
    return StatementDatabaseManager(os.environ['STATEMENTS_DB_HOST'])
