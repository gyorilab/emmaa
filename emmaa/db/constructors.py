import os
import re
import logging

from .config import get_databases
from .manager import EmmaaDatabaseManager

logger = logging.getLogger(__name__)


def get_db(name):
    """Get a db instance based on its name in the config or env."""
    if name == 'test' and 'EMMAA_TEST_DB' in os.environ:
        db_name = os.environ['EMMAA_TEST_DB']
    else:
        defaults = get_databases()
        db_name = defaults[name]
    m = re.match('(\w+)://.*?/([\w.]+)', db_name)
    if m is None:
        logger.error("Poorly formed db name: %s" % db_name)
        return
    return EmmaaDatabaseManager(db_name, label=name)
