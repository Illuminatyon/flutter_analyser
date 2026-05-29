"""
Gestion de la connexion série et lecture des paquets MPU-6050.

Référence protocole binaire :
  Taille paquet : 20 octets
  Format        : '<I fff bbb B'
  Checksum      : XOR des 19 premiers octets == octet 20
"""
import struct
import time
from typing import Optional

import serial

from config import SensorConfig
from models.acquisition import AcquisitionData
from models.packet import SensorPacket
from utils.logger import get_logger

logger = get_logger(__name__)

class SerialReader:
    """
    Gère la connexion série avec l'Arduino et lit les paquets binaires.

    Usage typique :
        reader = SerialReader(config)
        data   = reader.acquerir()
    """

    def __init__(self, config: SensorConfig) -> None:
        self._config: SensorConfig      = config
        self._ser:    Optional[serial.Serial] = None

    def acquerir(self) -> Optional[AcquisitionData]:
        """
        Ouvre le port, attend la calibration, puis collecte les données.

        Returns:
            AcquisitionData si l'acquisition réussit, None sinon.
        """
        if not self._connect():
            return None

        try:
            if not self._attendre_calibration():
                return None
            return self._collecter()
        finally:
            self._close()

    def _connect(self) -> bool:
        """Ouvre le port série. Retourne False en cas d'échec."""
        logger.info("Connexion sur %s à %d bauds...", self._config.port, self._config.baud)
        try:
            self._ser = serial.Serial(
                self._config.port,
                self._config.baud,
                timeout=5,
            )
            time.sleep(2)
            self._ser.reset_input_buffer()
            return True
        except serial.SerialException as exc:
            logger.error("Impossible d'ouvrir le port série : %s", exc)
            return False

    def _close(self) -> None:
        """Ferme le port série s'il est ouvert."""
        if self._ser and self._ser.is_open:
            self._ser.close()
            logger.debug("Port série fermé.")

    def _attendre_calibration(self) -> bool:
        """
        Attend le message READY_TRACKING de l'Arduino.

        Returns:
            True si reçu dans le délai imparti, False si timeout.
        """
        logger.info("Attente calibration Arduino...")
        deadline = time.time() + self._config.calibration_timeout_s

        while time.time() < deadline:
            try:
                line = self._ser.readline().decode("utf-8", errors="ignore").strip()
                if line:
                    logger.debug("Arduino : %s", line)
                if "READY_TRACKING" in line:
                    logger.info("Calibration OK.")
                    return True
            except Exception:  # noqa: BLE001
                continue

        logger.error("Timeout calibration (%ds)", self._config.calibration_timeout_s)
        return False

    def _collecter(self) -> Optional[AcquisitionData]:
        """
        Collecte les paquets pendant duree_s secondes.

        Returns:
            AcquisitionData peuplé, ou None si trop peu d'échantillons.
        """
        self._ser.reset_input_buffer()
        self._countdown()
        self._ser.reset_input_buffer()

        logger.info("Acquisition en cours (%ds)...", self._config.duree_s)

        data        = AcquisitionData()
        t_precedent: Optional[float] = None
        t_ecoule    = 0.0

        while True:
            paquet = self._lire_paquet()

            if paquet is None:
                data.erreurs += 1
                if data.erreurs % 50 == 0:
                    self._ser.reset_input_buffer()
                else:
                    self._ser.read(1)
                continue

            t_ms = paquet.t_us / 1_000.0

            if t_precedent is None:
                t_precedent = t_ms
                logger.debug("Premier paquet reçu (t=%.0f ms)", t_ms)

            delta = self._calculer_delta(t_ms, t_precedent)
            t_ecoule   += delta / 1_000.0
            t_precedent = t_ms

            if t_ecoule > self._config.duree_s:
                break

            # On réutilise t_us pour stocker t_ecoule en ms (cohérent avec AcquisitionData)
            paquet_avec_t = SensorPacket(
                t_us=int(t_ecoule * 1_000),
                ax=paquet.ax,
                ay=paquet.ay,
                az=paquet.az,
                gx_dps=paquet.gx_dps,
                gy_dps=paquet.gy_dps,
                gz_dps=paquet.gz_dps,
            )
            data.samples.append(paquet_avec_t)

            if len(data.samples) % 500 == 0:
                hz = len(data.samples) / t_ecoule if t_ecoule > 0 else 0
                logger.info(
                    "%.1f/%ds — %d paquets — %.0f Hz",
                    t_ecoule, self._config.duree_s, len(data.samples), hz,
                )

        if not data.est_valide():
            logger.error(
                "Pas assez de données (%d paquets, %d erreurs)",
                data.n, data.erreurs,
            )
            return None

        duree_reelle = data.duree_s
        data.freq_reelle = (data.n - 1) / duree_reelle if duree_reelle > 0 else 0.0

        logger.info("Acquisition terminée :")
        logger.info("  Paquets valides  : %d", data.n)
        logger.info("  Erreurs checksum : %d", data.erreurs)
        logger.info("  Durée réelle     : %.3f s", duree_reelle)
        logger.info("  Fréquence réelle : %.1f Hz", data.freq_reelle)

        return data

    def _lire_paquet(self) -> Optional[SensorPacket]:
        """
        Lit et décode un paquet binaire depuis le port série.

        Returns:
            SensorPacket si le checksum est valide, None sinon.
        """
        raw = self._ser.read(self._config.pkt_size)
        if len(raw) < self._config.pkt_size:
            return None

        checksum = 0
        for byte in raw[:19]:
            checksum ^= byte
        if checksum != raw[19]:
            return None

        t_us, ax, ay, az, gx_i, gy_i, gz_i, _ = struct.unpack(
            self._config.pkt_format, raw
        )
        return SensorPacket(
            t_us=t_us,
            ax=ax,
            ay=ay,
            az=az,
            gx_dps=gx_i * self._config.gyro_scale,
            gy_dps=gy_i * self._config.gyro_scale,
            gz_dps=gz_i * self._config.gyro_scale,
        )

    def _calculer_delta(self, t_ms: float, t_precedent: float) -> float:
        """Gère le rollover de l'horodatage uint32 et les sauts aberrants."""
        delta = t_ms - t_precedent
        if delta < 0:
            return self._config.timestamp_overflow_us - t_precedent + t_ms
        if delta > 1_000:
            return 1.0
        return delta

    def _countdown(self) -> None:
        """Affiche un compte à rebours avant le démarrage de l'acquisition."""
        logger.info("Démarrage dans :")
        for i in range(self._config.attente_s, 0, -1):
            logger.info("  %d...", i)
            time.sleep(1)
        logger.info("  GO !")