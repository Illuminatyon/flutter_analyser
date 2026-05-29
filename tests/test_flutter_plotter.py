"""
Tests unitaires — FlutterPlotter

On vérifie que plot() appelle bien les méthodes internes
et que les méthodes privées ne lèvent pas d'exception
sur des données synthétiques valides.
On patch plt.show() pour ne pas ouvrir de fenêtre graphique.
"""
import unittest
from unittest.mock import patch, MagicMock

import numpy as np

from models.analysis_result import AnalysisResult
from visualization.flutter_plotter import FlutterPlotter


# ── Helper ────────────────────────────────────────────────────────────────────

def _generer_result(n: int = 500) -> AnalysisResult:
    """Construit un AnalysisResult synthétique minimal."""
    freq   = 40.0
    fs     = 500.0
    dt     = 1.0 / fs
    t      = np.arange(n) * dt
    az_bp  = 0.05 * np.sin(2 * np.pi * freq * t)
    jerk   = np.gradient(az_bp, dt)
    fft_y  = np.abs(np.fft.rfft(az_bp))
    fft_f  = np.fft.rfftfreq(n, d=dt)

    return AnalysisResult(
        t=t,
        az_brut=az_bp * 0.9,
        az_bp=az_bp,
        jerk=jerk,
        fft_f=fft_f,
        fft_y=fft_y,
        freq_fft=freq,
        f_low=16.0,
        f_high=100.0,
        rms_az=float(np.sqrt(np.mean(az_bp ** 2))),
        amp_az=float((az_bp.max() - az_bp.min()) / 2),
        freq_reelle=fs,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestFlutterPlotterInit(unittest.TestCase):
    """Vérifie que FlutterPlotter s'instancie sans argument."""

    def test_instanciation(self) -> None:
        plotter = FlutterPlotter()
        self.assertIsNotNone(plotter)


class TestPlotAppelleMethodes(unittest.TestCase):
    """Vérifie que plot() délègue bien aux trois sous-méthodes."""

    @patch("visualization.flutter_plotter.plt.show")
    @patch("visualization.flutter_plotter.plt.tight_layout")
    @patch("visualization.flutter_plotter.plt.subplots")
    def test_trois_sous_methodes_appelees(
        self,
        mock_subplots: MagicMock,
        _tight: MagicMock,
        _show: MagicMock,
    ) -> None:
        axes   = [MagicMock(), MagicMock(), MagicMock()]
        mock_subplots.return_value = (MagicMock(), axes)

        plotter = FlutterPlotter()
        plotter._plot_acceleration = MagicMock()
        plotter._plot_phase        = MagicMock()
        plotter._plot_fft          = MagicMock()

        plotter.plot(_generer_result())

        plotter._plot_acceleration.assert_called_once()
        plotter._plot_phase.assert_called_once()
        plotter._plot_fft.assert_called_once()

    @patch("visualization.flutter_plotter.plt.show")
    def test_show_appele(self, mock_show: MagicMock) -> None:
        plotter = FlutterPlotter()
        plotter.plot(_generer_result())
        mock_show.assert_called_once()


class TestPlotAcceleration(unittest.TestCase):
    """Vérifie que _plot_acceleration ne lève pas d'exception."""

    def test_sans_exception(self) -> None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        _, ax = plt.subplots()
        FlutterPlotter()._plot_acceleration(ax, _generer_result())
        plt.close("all")


class TestPlotPhase(unittest.TestCase):
    """Vérifie que _plot_phase construit une LineCollection valide."""

    def test_sans_exception(self) -> None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        _, ax = plt.subplots()
        FlutterPlotter()._plot_phase(ax, _generer_result())
        plt.close("all")

    def test_collection_presente(self) -> None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.collections import LineCollection

        _, ax = plt.subplots()
        FlutterPlotter()._plot_phase(ax, _generer_result())

        collections = [c for c in ax.collections if isinstance(c, LineCollection)]
        self.assertTrue(len(collections) > 0)
        plt.close("all")


class TestPlotFFT(unittest.TestCase):
    """Vérifie que _plot_fft trace bien la ligne verticale du pic."""

    def test_sans_exception(self) -> None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        _, ax = plt.subplots()
        FlutterPlotter()._plot_fft(ax, _generer_result())
        plt.close("all")

    def test_ligne_verticale_freq_fft(self) -> None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        result  = _generer_result()
        _, ax   = plt.subplots()
        FlutterPlotter()._plot_fft(ax, result)

        # axvline crée une ligne dont xdata vaut [freq_fft, freq_fft]
        lignes_verticales = [
            l for l in ax.lines
            if len(l.get_xdata()) == 2
            and l.get_xdata()[0] == l.get_xdata()[1]
        ]
        self.assertTrue(any(
            abs(l.get_xdata()[0] - result.freq_fft) < 0.01
            for l in lignes_verticales
        ))
        plt.close("all")


if __name__ == "__main__":
    unittest.main()