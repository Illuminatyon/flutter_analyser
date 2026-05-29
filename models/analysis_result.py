"""
Résultat du pipeline de traitement du signal Flutter.
"""
from dataclasses import dataclass
import numpy as np

@dataclass
class AnalysisResult:
    """
    Métriques et signaux produits par FlutterAnalyser.

    Attributes:
        t:          Vacteur temps (s)
        az_brut:    Accélération Z détrended, non filtrée (g).
        az_bp:      Accélération Z filtrée passe_bande (g).
        jerk:       Dérivée temporelle de az_bh (g/s)
        fft_f       Vecteur fréquences FFT (Hz)
        fft_y:      Amplitudes FFT correspondantes.
        freq_fft:   Fréquence dominante détectée (Hz).
        f_low:      Borne basse du filtre passe-bande (Hz).
        f_high:     Borne haute du filtre passe-bande (Hz).
        rms_az:     RMS de l'accélération Z brute (g).
        amp_az:     Amplitude crête-à-crête / 2 de az_bp (g).
        freq_relle: Fréquence d'échantillonnage effetive (Hz)
    """

    t:        np.ndarray
    az_brut:  np.ndarray
    az_bp:    np.ndarray
    jerk:     np.ndarray
    fft_f:    np.ndarray
    fft_y:    np.ndarray
    freq_fft: float
    f_low:    float
    f_high:   float
    rms_az:   float

    def resumre(self) -> str:
        """Retourne un résumé formaté des métriques principales"""
        sep = "=" * 55
        dt = self.t[-1] / (len(self.t) - 1) if len(self.t) > 1 else 0.0
        lines = [
            sep,
            "  RÉSULTATS",
            sep,
            f"  Échantillons           : {len(self.t)}",
            f"  dt moyen               : {dt * 1000:.3f} ms",
            f"  Fréquence FFT          : {self.freq_fft:.3f} Hz"
            f"  (T={1 / self.freq_fft * 1000:.1f} ms)",
            f"  RMS accélération Z     : {self.rms_az * 1000:.2f} mg",
            f"  Amplitude accélération : {self.amp_az * 1000:.2f} mg",
            f"  Filtre passe-bande     : [{self.f_low:.1f} — {self.f_high:.1f}] Hz",
            "",
            "  Réf: Takens (1981), Lect. Notes Math. Vol.898, pp.366-381",
            sep,
        ]
        return "\n".join(lines)