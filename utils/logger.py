"""
Configuration du logger global pour Flutter Analyser.
Tous les modules importent get_logger() plutôt qu'utiliser print()
"""
import logging
import sys

def get_logger(name: str) -> logging.Logger:
    """
    Retourne un logger nommé, configuré avec un handler console.

    Args:
        :param name: Nom du moule appelant (utiliser __name__).

    :return:
        Instance de logging.Logger prête à l'emploi.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

    return logger