"""
Résultat brut d'une session d'acquisition série.
"""
from dataclasses import dataclass, field
from models.packet import SensorPacket

@dataclass
class AcquisitionData:
    """Ensemble des échantillons collectés lors d'une acquisition.

    Attributes:
        :param samples:        Liste ordonnée des paquets valides reçus.
        :param freq_reelle:    Fréquence d'échantillonage effective (Hz)
        :param erreurs:        Nombre de paquets rejetés (checksum invalide).
    """

    samples: list[SensorPacket] = field(default_factory=list)
    freq_reelle: float = 0.0
    erreurs: int = 0

    @property
    def n(self) -> int:
        """Nombre d'échantillons valides."""
        return len(self.samples)

    @property
    def duree_s(self) -> float:
        """Durée réelle de l'acquisition en secondes."""
        if self.n < 2:
            return 0.0
        # Les timestamps sont stockés en ms dans SerialReader
        return self.samples[-1].t_us / 1_000 - self.samples[0].t_us / 1_000

    def est_valide(self, min_samples: int = 10):
        """Renvoie True si l'acquisition contient assez d'échantillons."""
        return self.n >= min_samples