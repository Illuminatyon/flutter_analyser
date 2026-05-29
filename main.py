"""
Flutter Analyser — Point d'entrée.

Diagramme de phase dans l'espace (a, j) = (accélération, jerk).
Équivalent topologique de (z, vz) par le théorème de Takens (1981).

Référence :
    Takens, F. (1981). Detecting strange attractors in turbulence.
    Lecture Notes in Mathematics, Vol. 898, Springer, pp. 366-381.
"""
import pandas as pd

from config import DEFAULT_CONFIG
from serial_io.serial_reader import SerialReader
from processing.flutter_analyser import FlutterAnalyser
from visualization.flutter_plotter import FlutterPlotter
from utils.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    """Orchestre l'acquisition, l'analyse et la visualisation."""
    config  = DEFAULT_CONFIG
    reader  = SerialReader(config)
    analyser = FlutterAnalyser(config)
    plotter  = FlutterPlotter()

    data = reader.acquerir()
    if data is None:
        logger.error("Échec de l'acquisition — arrêt.")
        return

    rows = [
        {
            "time_s":   s.t_us / 1_000.0,
            "ax_g":     s.ax,
            "ay_g":     s.ay,
            "az_g":     s.az,
            "gx_dps":   s.gx_dps,
            "gy_dps":   s.gy_dps,
            "gz_dps":   s.gz_dps,
        }
        for s in data.samples
    ]
    df = pd.DataFrame(rows)
    df.to_csv("data/mesure_flutter.csv", index=False)
    logger.info("Données sauvegardées : data/mesure_flutter.csv")

    result = analyser.analyser(data)

    plotter.plot(result)


if __name__ == "__main__":
    main()