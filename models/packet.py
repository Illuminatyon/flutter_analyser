"""
Représentation d'un paquet binaire décodé depuis le MPU-6050
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class SensorPacket:
    """
    Un paquet de mesure brut émis par l'Arduino.

    Attributes:
        t_us: Horodatage en microsecondes (unint32, peut faire rollover).
        ax: Accélération X en g.
        ay: Accélération Y en g.
        az Accélération Z en g.
        gx_dps: Vitesse angulaire X en degrés/s.
        gy_dps: Vitesse angulaire Y en degrés/s.
        gz_dps: Vitesse angulaire Z en degrés/s.
    """

    t_us: int
    ax: float
    ay: float
    az: float
    gx_dps: float
    gy_dps: float
    gz_dps: float
