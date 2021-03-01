import logging

__version__ = '1.13.0'

logging_format = '%(levelname)s: [%(asctime)s] %(name)s - %(message)s'
logging.basicConfig(format=logging_format, level=logging.INFO,
                    datefmt='%Y-%m-%d %H:%M:%S')

logger = logging.getLogger('emmaa')
