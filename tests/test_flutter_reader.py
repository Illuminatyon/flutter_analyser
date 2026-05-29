"""
Tests unitaires — SerialReader

On mock serial.Serial pour ne pas avoir besoin de matériel.
"""
import struct
import unittest
from unittest.mock import MagicMock, patch, call

import serial

from config import SensorConfig
from serial_io.serial_reader import SerialReader
from models.packet import SensorPacket


def _fabriquer_paquet(
    t_us: int = 1_000_000,
    ax: float = 0.01,
    ay: float = 0.02,
    az: float = 1.0,
    gx_i: int = 2,
    gy_i: int = 3,
    gz_i: int = 4,
) -> bytes:
    """Construit un paquet binaire valide de 20 octets avec checksum XOR."""
    payload = struct.pack("<I fff bbb B", t_us, ax, ay, az, gx_i, gy_i, gz_i, 0)
    cs = 0
    for b in payload[:19]:
        cs ^= b
    return payload[:19] + bytes([cs])


class TestLirePaquet(unittest.TestCase):
    """Tests de la lecture et du décodage d'un paquet binaire."""

    def setUp(self) -> None:
        self.config = SensorConfig()
        self.reader = SerialReader(self.config)
        self.reader._ser = MagicMock()

    def test_paquet_valide_retourne_sensor_packet(self) -> None:
        self.reader._ser.read.return_value = _fabriquer_paquet(az=1.0)
        paquet = self.reader._lire_paquet()
        self.assertIsNotNone(paquet)
        self.assertIsInstance(paquet, SensorPacket)

    def test_az_correctement_decode(self) -> None:
        self.reader._ser.read.return_value = _fabriquer_paquet(az=0.42)
        paquet = self.reader._lire_paquet()
        self.assertAlmostEqual(paquet.az, 0.42, places=5)

    def test_gyro_scale_applique(self) -> None:
        # gx_i = 10 → gx_dps = 10 * 0.5 = 5.0
        self.reader._ser.read.return_value = _fabriquer_paquet(gx_i=10)
        paquet = self.reader._lire_paquet()
        self.assertAlmostEqual(paquet.gx_dps, 5.0, places=5)

    def test_checksum_invalide_retourne_none(self) -> None:
        raw = bytearray(_fabriquer_paquet())
        raw[19] ^= 0xFF          # casser le checksum
        self.reader._ser.read.return_value = bytes(raw)
        self.assertIsNone(self.reader._lire_paquet())

    def test_paquet_trop_court_retourne_none(self) -> None:
        self.reader._ser.read.return_value = b"\x00" * 10
        self.assertIsNone(self.reader._lire_paquet())


class TestCalculerDelta(unittest.TestCase):
    """Tests du calcul de delta avec gestion du rollover."""

    def setUp(self) -> None:
        self.reader = SerialReader(SensorConfig())

    def test_delta_normal(self) -> None:
        delta = self.reader._calculer_delta(t_ms=100.0, t_precedent=97.0)
        self.assertAlmostEqual(delta, 3.0)

    def test_rollover_uint32(self) -> None:
        # Simule un overflow : t_ms revient à 0 après 4294967 ms
        overflow = SensorConfig().timestamp_overflow_us
        delta = self.reader._calculer_delta(t_ms=1.0, t_precedent=overflow - 1.0)
        self.assertGreater(delta, 0)
        self.assertLess(delta, 10)

    def test_saut_aberrant_clamp_a_1ms(self) -> None:
        delta = self.reader._calculer_delta(t_ms=5000.0, t_precedent=1.0)
        self.assertEqual(delta, 1.0)


class TestConnexion(unittest.TestCase):
    """Tests de la connexion et de la gestion d'erreur série."""

    def setUp(self) -> None:
        self.config = SensorConfig(port="/dev/ttyFAKE", baud=1_000_000)
        self.reader = SerialReader(self.config)

    @patch("serial_io.serial_reader.serial.Serial")
    @patch("serial_io.serial_reader.time.sleep")
    def test_connect_succes(self, _sleep: MagicMock, mock_serial: MagicMock) -> None:
        mock_serial.return_value = MagicMock()
        resultat = self.reader._connect()
        self.assertTrue(resultat)

    @patch("serial_io.serial_reader.serial.Serial",
           side_effect=serial.SerialException("port absent"))
    def test_connect_echec(self, _mock: MagicMock) -> None:
        resultat = self.reader._connect()
        self.assertFalse(resultat)


if __name__ == "__main__":
    unittest.main()