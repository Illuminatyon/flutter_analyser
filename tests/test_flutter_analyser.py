"""
Tests unitaires — FlutterAnalyser

On injecte des signaux synthétiques connus pour vérifier
que le pipeline produit les bons résultats.
"""
import unittest

import numpy as np

from config import SensorConfig
from models.acquisition import AcquisitionData
from models.analysis_result import AnalysisResult
from models.packet import SensorPacket
from processing.flutter_analyser import FlutterAnalyser


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generer_acquisition(
    freq_signal_hz: float = 40.0,
    freq_echantillon_hz: float = 500.0,
    duree_s: float = 2.0,
    amplitude: float = 0.05,
) -> AcquisitionData:
    """
    Génère un AcquisitionData synthétique avec un sinus pur sur az.
    Utile pour vérifier que la FFT retrouve la bonne fréquence.
    """
    n  = int(freq_echantillon_hz * duree_s)
    dt = 1.0 / freq_echantillon_hz
    t  = np.arange(n) * dt
    az = amplitude * np.sin(2 * np.pi * freq_signal_hz * t)

    samples = [
        SensorPacket(
            t_us=int(ti * 1_000),   # stocké en ms dans t_us
            ax=0.0,
            ay=0.0,
            az=float(az[i]),
            gx_dps=0.0,
            gy_dps=0.0,
            gz_dps=0.0,
        )
        for i, ti in enumerate(t)
    ]

    data             = AcquisitionData()
    data.samples     = samples
    data.freq_reelle = freq_echantillon_hz
    return data


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestExtractionSignaux(unittest.TestCase):
    """Vérifie l'extraction correcte des vecteurs temps et az."""

    def setUp(self) -> None:
        self.analyser = FlutterAnalyser(SensorConfig())
        self.data     = _generer_acquisition()

    def test_longueur_vecteurs(self) -> None:
        t, az = self.analyser._extraire_signaux(self.data)
        self.assertEqual(len(t), len(self.data.samples))
        self.assertEqual(len(az), len(self.data.samples))

    def test_premier_temps_nul(self) -> None:
        t, _ = self.analyser._extraire_signaux(self.data)
        self.assertAlmostEqual(t[0], 0.0, places=5)

    def test_az_valeurs_correctes(self) -> None:
        _, az = self.analyser._extraire_signaux(self.data)
        az_attendu = self.data.samples[0].az
        self.assertAlmostEqual(az[0], az_attendu, places=6)


class TestDetrend(unittest.TestCase):
    """Vérifie que le detrend retire bien la tendance linéaire."""

    def setUp(self) -> None:
        self.analyser = FlutterAnalyser(SensorConfig())

    def test_offset_dc_retire(self) -> None:
        az = np.ones(200) * 5.0          # signal constant — offset pur
        az_d = self.analyser._detrend(az)
        self.assertAlmostEqual(float(np.mean(az_d)), 0.0, places=5)

    def test_tendance_lineaire_retiree(self) -> None:
        az = np.linspace(0, 10, 300)     # rampe linéaire
        az_d = self.analyser._detrend(az)
        self.assertAlmostEqual(float(np.std(az_d)), 0.0, places=4)


class TestFFT(unittest.TestCase):
    """Vérifie que la FFT détecte la bonne fréquence dominante."""

    def setUp(self) -> None:
        self.analyser       = FlutterAnalyser(SensorConfig())
        self.freq_signal    = 40.0
        self.freq_echantillon = 500.0

    def _signal_sinus(self, freq_hz: float, n: int = 1000) -> np.ndarray:
        dt = 1.0 / self.freq_echantillon
        t  = np.arange(n) * dt
        return 0.05 * np.sin(2 * np.pi * freq_hz * t)

    def test_frequence_dominante_detectee(self) -> None:
        az     = self._signal_sinus(self.freq_signal)
        dt     = 1.0 / self.freq_echantillon
        _, _, freq_fft = self.analyser._fft(az, dt, self.freq_echantillon)
        self.assertAlmostEqual(freq_fft, self.freq_signal, delta=1.0)

    def test_fft_f_et_fft_y_meme_longueur(self) -> None:
        az = self._signal_sinus(self.freq_signal)
        dt = 1.0 / self.freq_echantillon
        fft_f, fft_y, _ = self.analyser._fft(az, dt, self.freq_echantillon)
        self.assertEqual(len(fft_f), len(fft_y))

    def test_fallback_sur_freq_cible(self) -> None:
        # Quand aucune fréquence n'est dans le masque [5Hz, nyquist],
        # _fft doit retourner freq_cible_hz.
        # On force ce cas avec un signal de 200 points et une fs très basse
        # pour que le masque soit vide.
        az  = np.ones(4)    # masque vide garanti : rfftfreq donne [0, fs/2]
        dt  = 1.0 / 8.0     # fs=8Hz → nyquist=4Hz < _FFT_FREQ_MIN_HZ(5Hz)
        _, _, freq_fft = self.analyser._fft(az, dt, freq_reelle=8.0)
        self.assertEqual(freq_fft, SensorConfig().freq_cible_hz)


class TestBandpass(unittest.TestCase):
    """Vérifie les bornes du filtre passe-bande."""

    def setUp(self) -> None:
        self.analyser         = FlutterAnalyser(SensorConfig())
        self.freq_echantillon = 500.0
        self.dt               = 1.0 / self.freq_echantillon

    def test_f_low_inferieur_a_f_high(self) -> None:
        az = 0.05 * np.sin(2 * np.pi * 40 * np.arange(500) * self.dt)
        f_low, f_high, _ = self.analyser._bandpass(az, self.dt, self.freq_echantillon, 40.0)
        self.assertLess(f_low, f_high)

    def test_sortie_meme_longueur_que_entree(self) -> None:
        az = np.random.randn(500) * 0.01
        _, _, az_bp = self.analyser._bandpass(az, self.dt, self.freq_echantillon, 40.0)
        self.assertEqual(len(az_bp), 500)

    def test_f_high_sous_nyquist(self) -> None:
        az = 0.05 * np.sin(2 * np.pi * 40 * np.arange(500) * self.dt)
        _, f_high, _ = self.analyser._bandpass(az, self.dt, self.freq_echantillon, 40.0)
        self.assertLess(f_high, self.freq_echantillon / 2)


class TestJerk(unittest.TestCase):
    """Vérifie le calcul du jerk (dérivée de az)."""

    def setUp(self) -> None:
        self.analyser = FlutterAnalyser(SensorConfig())

    def test_jerk_sinus_est_cosinus(self) -> None:
        # d/dt [A sin(wt)] = Aw cos(wt) → jerk doit être déphasé de π/2
        freq  = 10.0
        dt    = 0.001
        t     = np.arange(1000) * dt
        az_bp = 0.1 * np.sin(2 * np.pi * freq * t)
        jerk  = self.analyser._jerk(az_bp, dt)

        # Correlation jerk/cosinus doit être forte (ignorer les bords)
        cos_ref = 0.1 * 2 * np.pi * freq * np.cos(2 * np.pi * freq * t)
        corr    = np.corrcoef(jerk[10:-10], cos_ref[10:-10])[0, 1]
        self.assertGreater(corr, 0.99)

    def test_jerk_signal_constant_est_nul(self) -> None:
        az_bp = np.ones(200) * 0.05
        jerk  = self.analyser._jerk(az_bp, 0.002)
        np.testing.assert_allclose(jerk, 0.0, atol=1e-10)


class TestAnalyserComplet(unittest.TestCase):
    """Test d'intégration — pipeline complet sur signal synthétique."""

    def test_retourne_analysis_result(self) -> None:
        data   = _generer_acquisition(freq_signal_hz=40.0)
        result = FlutterAnalyser(SensorConfig()).analyser(data)
        self.assertIsInstance(result, AnalysisResult)

    def test_freq_fft_proche_freq_signal(self) -> None:
        data   = _generer_acquisition(freq_signal_hz=40.0)
        result = FlutterAnalyser(SensorConfig()).analyser(data)
        self.assertAlmostEqual(result.freq_fft, 40.0, delta=2.0)

    def test_vecteurs_meme_longueur(self) -> None:
        data   = _generer_acquisition()
        result = FlutterAnalyser(SensorConfig()).analyser(data)
        n = len(result.t)
        self.assertEqual(len(result.az_brut), n)
        self.assertEqual(len(result.az_bp),   n)
        self.assertEqual(len(result.jerk),    n)

    def test_rms_positif(self) -> None:
        data   = _generer_acquisition()
        result = FlutterAnalyser(SensorConfig()).analyser(data)
        self.assertGreater(result.rms_az, 0.0)

    def test_resume_contient_freq_fft(self) -> None:
        data   = _generer_acquisition()
        result = FlutterAnalyser(SensorConfig()).analyser(data)
        self.assertIn("RÉSULTATS", result.resume())


if __name__ == "__main__":
    unittest.main()