"""
Configuration centrale du Flutter Analyser.
Toutes les constantes matérielles et d'acquisition sont regroupées ici.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class SensorConfig:
    """
    Paramètres de configuration du capteur MPU-6050 et de l'acquisition.
    """

    # Connexion série
    port: str = "/dev/ttyACM0"
    baud: int = 1_000_000

    # Acquisition
    duree_s: int = 10
    attente_s: int = 7

    # Signal
    freq_cible_hz: float = 45.0 # Centre du passe-bande (Hz)

    # Protocole Binaire
    pkt_size: int = 20
    pkt_format: str = "<I fff bbb B"

    # Facteur de conversion gyroscope (degrés/s par unité brute)
    gyro_scale: float = 0.5

    # Seuil de détection d'overflow horodatage (micromètre - rollow uint32)
    timestamp_overflow_us: float = 4_294_967.296

    # Timeout calibration Arduino (s)
    calibration_timeout_s: int = 30

# Instance par défaut - importable par toutes les classes
DEFAULT_CONFIG = SensorConfig()