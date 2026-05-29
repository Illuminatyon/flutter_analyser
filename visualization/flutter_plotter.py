"""
Visualisation des résultats d'analyse Flutter.
Trois graphiques : accélération brute, diagramme de phase (a,j), FFT.
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

from models.analysis_result import AnalysisResult
from utils.logger import get_logger

logger = get_logger(__name__)

# Constantes de mise en page
_FIGSIZE:       tuple[int, int] = (18, 5)
_LINE_WIDTH:    float = 1.5
_GRID_ALPHA:    float = 0.3
_CMAP:          str   = "viridis"
_PHASE_MARGIN:  float = 1.1


class FlutterPlotter:
    """
    Génère les 3 graphiques d'analyse Flutter à partir d'un AnalysisResult.

        - Graphique 1 : accélération Z brute
        - Graphique 2 : diagramme de phase (accélération, jerk), coloré selon le temps
        - Graphique 3 : FFT avec marquage du pic dominant
    """

    def plot(self, result: AnalysisResult) -> None:
        """
        Affiche les trois graphiques dans une même figure.

        Args:
            result: Résultat issu de FlutterAnalyser.analyser().
        """
        fig, axes = plt.subplots(1, 3, figsize=_FIGSIZE)
        fig.suptitle(
            f"Flutter MPU-6050  |  f = {result.freq_fft:.2f} Hz"
            f"  |  fs = {result.freq_reelle:.0f} Hz",
            fontsize=14,
            weight="bold",
        )

        self._plot_acceleration(axes[0], result)
        self._plot_phase(axes[1], result)
        self._plot_fft(axes[2], result)

        plt.tight_layout()
        logger.info("Affichage des graphiques.")
        plt.show()

    def _plot_acceleration(
        self,
        ax: plt.Axes,
        result: AnalysisResult,
    ) -> None:
        """Accélération Z brute en fonction du temps."""
        ax.plot(result.t, result.az_brut, "b", lw=0.8, alpha=0.9)
        ax.axhline(0, color="k", lw=0.5, ls="--")
        ax.set_title("Accélération Z brute (g)", fontsize=12, weight="bold")
        ax.set_xlabel("Temps (s)")
        ax.set_ylabel("g")
        ax.grid(True, alpha=_GRID_ALPHA)
        ax.set_xlim(result.t[0], result.t[-1])

    def _plot_phase(
        self,
        ax: plt.Axes,
        result: AnalysisResult,
    ) -> None:
        """
        Diagramme de phase (accélération, jerk) coloré selon le temps.
        Équivalent topologique de (z, vz) — théorème de Takens (1981).
        """
        points   = np.column_stack([result.az_bp, result.jerk])
        segments = [[points[i], points[i + 1]] for i in range(len(points) - 1)]
        couleurs = result.t[:-1]

        lc = LineCollection(segments, cmap=_CMAP, linewidths=_LINE_WIDTH)
        lc.set_array(couleurs)
        lc.set_clim(result.t[0], result.t[-1])
        ax.add_collection(lc)

        ax.set_xlim(result.az_bp.min() * _PHASE_MARGIN, result.az_bp.max() * _PHASE_MARGIN)
        ax.set_ylim(result.jerk.min()  * _PHASE_MARGIN, result.jerk.max()  * _PHASE_MARGIN)
        ax.axhline(0, color="k", lw=0.5, ls="--", zorder=0)
        ax.axvline(0, color="k", lw=0.5, ls="--", zorder=0)
        ax.set_title("Diagramme de phase (a, j)", fontsize=12, weight="bold")
        ax.set_xlabel("Accélération Z (g)")
        ax.set_ylabel("Jerk Z (g/s)")
        ax.grid(True, alpha=_GRID_ALPHA)

        cbar = plt.colorbar(lc, ax=ax, shrink=0.8)
        cbar.set_label("Temps (s)", fontsize=9)

    def _plot_fft(
        self,
        ax: plt.Axes,
        result: AnalysisResult,
    ) -> None:
        """FFT de l'accélération Z avec marquage du pic dominant."""
        ax.plot(result.fft_f[1:], result.fft_y[1:], "purple", lw=1.2)
        ax.axvline(
            result.freq_fft,
            color="red",
            ls="--",
            lw=2,
            label=f"Pic = {result.freq_fft:.2f} Hz",
        )
        ax.set_title("FFT Accélération Z", fontsize=12, weight="bold")
        ax.set_xlabel("Fréquence (Hz)")
        ax.set_ylabel("Amplitude")
        ax.set_xlim(0, min(150.0, float(result.fft_f[-1])))
        ax.legend(fontsize=9)
        ax.grid(True, alpha=_GRID_ALPHA)