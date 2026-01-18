import logging
from dataclasses import dataclass

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

file_handler = logging.FileHandler("logging.txt", mode="w")
file_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(module)s - %(lineno)d - %(message)s")
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

sql_alch_logger = logging.getLogger("sqlalchemy.engine.Engine")
sql_alch_logger.setLevel(logging.WARNING)


@dataclass
class Config:
    version: str


config = Config("0.1.0")
