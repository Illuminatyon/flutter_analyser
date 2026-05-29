"""
Pipeline de traitement du signal Flutter.

Référence :
    Takens, F. (1981). Detecting strange attractors in turbulence.
    Lecture Notes in Mathematics, Vol. 898, Springer, pp. 366-381.
"""
import numpy as np
from scipy.signal import butter, filtfilt, savgol_filter
from scipy.signal import detrend as scipy_detrend

from config import SensorConfig
from models.acquisition import AcquisitionData
from models.analysis_result import AnalysisResult
from utils.logger import get_logger

logger = get_logger(__name__)

# Constantes internes du pipeline
_FFT_FREQ_MIN_HZ:  float = 5.0
_BANDPASS_LOW_FACTOR:  float = 0.4
_BANDPASS_HIGH_FACTOR: float = 2.5
_BANDPASS_MIN_WIDTH_HZ: float = 20.0
_NYQUIST_MARGIN:   float = 0.95
_BUTTER_ORDER:     int   = 4
_SAVGOL_POLY:      int   = 3


class FlutterAnalyser:
    """
    Transforme un AcquisitionData en AnalysisResult.

    Le pipeline applique dans l'ordre :
        1. Extraction du vecteur temps et de az
        2. Retrait de la tendance linéaire (detrend)
        3. Lissage Savitzky-Golay
        4. FFT pour détecter la fréquence dominante
        5. Filtre passe-bande Butterworth centré sur freq_fft
        6. Calcul du jerk (dérivée de az_bp)
        7. Métriques RMS et amplitude
    """

    def __init__(self, config: SensorConfig) -> None:
        self._config = config

    def analyser(self, data: AcquisitionData) -> AnalysisResult:
        """
        Exécute le pipeline complet sur les données d'acquisition.

        Args:
            data: Données brutes issues de SerialReader.

        Returns:
            AnalysisResult contenant signaux traités et métriques.
        """
        t, az_raw = self._extraire_signaux(data)
        dt = t[-1] / (len(t) - 1)

        az_detrend = self._detrend(az_raw)
        az_lisse   = self._lisser(az_detrend)

        fft_f, fft_y, freq_fft = self._fft(az_lisse, dt, data.freq_reelle)
        f_low, f_high, az_bp   = self._bandpass(az_detrend, dt, data.freq_reelle, freq_fft)
        jerk                   = self._jerk(az_bp, dt)

        rms_az = float(np.sqrt(np.mean(az_lisse ** 2)))
        amp_az = float((az_bp.max() - az_bp.min()) / 2)

        result = AnalysisResult(
            t=t,
            az_brut=az_detrend,
            az_bp=az_bp,
            jerk=jerk,
            fft_f=fft_f,
            fft_y=fft_y,
            freq_fft=freq_fft,
            f_low=f_low,
            f_high=f_high,
            rms_az=rms_az,
            amp_az=amp_az,
            freq_reelle=data.freq_reelle,
        )

        logger.info("\n%s", result.resume())
        return result

    def _extraire_signaux(
        self, data: AcquisitionData
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Extrait les vecteurs temps (s) et accélération Z (g) depuis les échantillons.
        """
        t  = np.array([s.t_us / 1_000.0 for s in data.samples])
        az = np.array([s.az              for s in data.samples])
        return t, az

    def _detrend(self, az: np.ndarray) -> np.ndarray:
        """Retire la tendance linéaire (offset DC + dérive lente)."""
        return scipy_detrend(az, type="linear")

    def _lisser(self, az: np.ndarray) -> np.ndarray:
        """Applique un filtre Savitzky-Golay pour réduire le bruit haute fréquence."""
        n   = len(az)
        win = min(11, n if n % 2 == 1 else n - 1)
        return savgol_filter(az, win, _SAVGOL_POLY)

    def _fft(
        self,
        az_lisse: np.ndarray,
        dt: float,
        freq_reelle: float,
    ) -> tuple[np.ndarray, np.ndarray, float]:
        """
        Calcule la FFT et détecte la fréquence dominante.

        Returns:
            Tuple (fft_f, fft_y, freq_dominante_hz).
        """
        n     = len(az_lisse)
        fft_y = np.abs(np.fft.rfft(az_lisse))
        fft_f = np.fft.rfftfreq(n, d=dt)

        f_max  = min(150.0, freq_reelle / 2 * _NYQUIST_MARGIN)
        masque = (fft_f >= _FFT_FREQ_MIN_HZ) & (fft_f <= f_max)

        freq_fft = (
            float(fft_f[masque][np.argmax(fft_y[masque])])
            if masque.any()
            else self._config.freq_cible_hz
        )

        logger.debug("Fréquence FFT dominante : %.3f Hz", freq_fft)
        return fft_f, fft_y, freq_fft

    def _bandpass(
        self,
        az: np.ndarray,
        dt: float,
        freq_reelle: float,
        freq_fft: float,
    ) -> tuple[float, float, np.ndarray]:
        """
        Applique un filtre passe-bande Butterworth centré sur freq_fft.

        Returns:
            Tuple (f_low, f_high, signal_filtré).
        """
        f_nyq  = freq_reelle / 2.0
        f_low  = max(_FFT_FREQ_MIN_HZ, freq_fft * _BANDPASS_LOW_FACTOR)
        f_high = min(f_nyq * _NYQUIST_MARGIN, freq_fft * _BANDPASS_HIGH_FACTOR)

        if f_high <= f_low + 2:
            f_high = min(f_nyq * _NYQUIST_MARGIN, f_low + _BANDPASS_MIN_WIDTH_HZ)

        b, a   = butter(_BUTTER_ORDER, [f_low / f_nyq, f_high / f_nyq], btype="band")
        az_bp  = filtfilt(b, a, az)

        logger.debug("Passe-bande : [%.1f — %.1f] Hz", f_low, f_high)
        return f_low, f_high, az_bp

    def _jerk(self, az_bp: np.ndarray, dt: float) -> np.ndarray:
        """Calcule le jerk comme dérivée numérique de l'accélération filtrée (g/s)."""
        return np.gradient(az_bp, dt)