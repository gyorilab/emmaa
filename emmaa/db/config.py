import logging
from os import path, makedirs, environ
from shutil import copyfile
from configparser import ConfigParser

HERE = path.dirname(path.abspath(__file__))

DB_CONFIG_DIR = path.expanduser('~/.config/emmaa')
DB_CONFIG_PATH = path.join(DB_CONFIG_DIR, 'db_config.ini')
DEFAULT_DB_CONFIG_PATH = path.join(HERE, path.pardir,
                                   'resources/default_db_config.ini')

DB_STR_FMT = "{prefix}://{username}{password}{host}{port}/{name}"
ENV_PREFIX = 'EMMAADB'


logger = logging.getLogger('db_config')


CONFIG_EXISTS = True
if not path.exists(DB_CONFIG_DIR):
    try:
        makedirs(DB_CONFIG_DIR)
    except Exception as e:
        CONFIG_EXISTS = False
        logger.warning("Unable to create config dir: %s" % e)


if not path.exists(DB_CONFIG_PATH) and CONFIG_EXISTS:
    try:
        copyfile(DEFAULT_DB_CONFIG_PATH, DB_CONFIG_PATH)
    except Exception as e:
        CONFIG_EXISTS = False
        logger.warning("Unable to copy config file into config dir: %s" % e)


DATABASES = None


def get_databases(force_update=False, include_config=True):
    global DATABASES
    if DATABASES is None or force_update:
        DATABASES = {}
        if CONFIG_EXISTS and include_config:
            parser = ConfigParser()
            parser.read(DB_CONFIG_PATH)
            for db_name in parser.sections():
                def_dict = {k: parser.get(db_name, k)
                            for k in parser.options(db_name)}
                if def_dict['host']:
                    def_dict['host'] = '@' + def_dict['host']
                def_dict['prefix'] = def_dict['dialect']
                if def_dict['driver']:
                    def_dict['prefix'] += def_dict['driver']
                if def_dict['port']:
                    def_dict['port'] = ':' + def_dict['port']
                if def_dict['password']:
                    def_dict['password'] = ':' + def_dict['password']
                DATABASES[db_name] = DB_STR_FMT.format(**def_dict)
        DATABASES.update({k[len(ENV_PREFIX):].lower(): v
                          for k, v in environ.items()
                          if k.startswith(ENV_PREFIX)})
    return DATABASES
