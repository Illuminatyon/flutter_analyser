# Flutter Analyser — MPU-6050

> Acquisition et analyse temps-réel des vibrations de flutter aérodynamique via un capteur MPU-6050 connecté à Arduino.  
> Diagramme de phase dans l'espace **(accélération, jerk)** — équivalent topologique de **(z, v_z)** par le **théorème de Takens (1981)**.

---

## Table des matières

- [Principe physique](#principe-physique)
- [Architecture du projet](#architecture-du-projet)
- [Installation](#installation)
- [Utilisation](#utilisation)
- [Pipeline de traitement](#pipeline-de-traitement)
- [Tests](#tests)
- [Configuration](#configuration)
- [Référence](#référence)

---

## Principe physique

Le **flutter** est une instabilité aéroélastique couplant les modes de flexion et de torsion d'une structure souple (aile, pale, surface de contrôle). Au-delà d'une vitesse critique, l'amortissement aérodynamique devient négatif et l'oscillation diverge.

Ce projet analyse le signal d'accélération axiale Z du MPU-6050 pour reconstruire la dynamique du système dans l'espace de phase **(a, j)** :

```
j = da/dt   (jerk = dérivée de l'accélération)
```

Par le **théorème de Takens**, cet espace est homéomorphe à l'espace d'état original **(z, v_z)** — la topologie de l'attracteur est donc préservée. Un cycle limite fermé indique un flutter établi ; une spirale divergente indique un flutter en croissance.

---

## Architecture du projet

```
flutter_analyser/
│
├── main.py                        # Point d'entrée — orchestre le tout
├── config.py                      # SensorConfig (dataclass frozen)
├── setup_project.py               # Initialisation de l'arborescence
│
├── models/
│   ├── packet.py                  # SensorPacket  — paquet binaire décodé
│   ├── acquisition.py             # AcquisitionData — échantillons bruts
│   └── analysis_result.py        # AnalysisResult — métriques + signaux
│
├── serial_io/
│   └── serial_reader.py          # SerialReader — connexion & lecture série
│
├── processing/
│   └── flutter_analyser.py       # FlutterAnalyser — pipeline signal
│
├── visualization/
│   └── flutter_plotter.py        # FlutterPlotter — 3 graphiques matplotlib
│
├── utils/
│   └── logger.py                 # Logger global (remplace print)
│
├── data/                          # Sorties CSV (ignoré par git)
├── tests/                         # 36 tests unitaires
│
├── requirements.txt
└── README.md
```

**Principe de séparation des responsabilités (SRP) :**

| Couche | Rôle | Dépend de |
|---|---|---|
| `models/` | Structures de données pures | — |
| `serial_io/` | I/O matériel uniquement | `models/`, `config` |
| `processing/` | Traitement signal, sans I/O | `models/`, `config` |
| `visualization/` | Rendu graphique, sans signal | `models/` |
| `main.py` | Orchestration | tout |

---

## Installation

**Prérequis :** Python ≥ 3.12, Arduino flashé avec le firmware MPU-6050.

```bash
# 1. Cloner le dépôt
git clone https://github.com/<vous>/flutter-analyser.git
cd flutter-analyser

# 2. Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Initialiser l'arborescence (idempotent)
python setup_project.py
```

---

## Utilisation

### Lancement standard

```bash
python main.py
```

Le programme :
1. Se connecte au port série défini dans `config.py`
2. Attend le message `READY_TRACKING` de l'Arduino (calibration gyro)
3. Effectue un compte à rebours configurable
4. Acquiert les données pendant `duree_s` secondes
5. Sauvegarde `data/mesure_flutter.csv`
6. Affiche les trois graphiques

### Adapter le port et la durée

Éditer `config.py` :

```python
DEFAULT_CONFIG = SensorConfig(
    port     = "/dev/ttyACM0",   # Linux — ou "COM3" sous Windows
    baud     = 1_000_000,
    duree_s  = 10,
    attente_s = 7,
)
```

### Analyser un CSV existant

```python
from config import DEFAULT_CONFIG
from models.acquisition import AcquisitionData
from models.packet import SensorPacket
from processing.flutter_analyser import FlutterAnalyser
from visualization.flutter_plotter import FlutterPlotter
import pandas as pd

df  = pd.read_csv("data/mesure_flutter.csv")
fs  = 1 / df["time_s"].diff().median()

data = AcquisitionData(
    samples=[
        SensorPacket(
            t_us   = int(row.time_s * 1_000),
            ax=row.ax_g, ay=row.ay_g, az=row.az_g,
            gx_dps=row.gx_dps, gy_dps=row.gy_dps, gz_dps=row.gz_dps,
        )
        for _, row in df.iterrows()
    ],
    freq_reelle=fs,
)

result = FlutterAnalyser(DEFAULT_CONFIG).analyser(data)
FlutterPlotter().plot(result)
```

---

## Pipeline de traitement

```
AcquisitionData
      │
      ▼
① _extraire_signaux()    → vecteurs t (s) et az (g)
      │
      ▼
② _detrend()             → retrait tendance linéaire (offset DC + dérive)
      │
      ▼
③ _lisser()              → filtre Savitzky-Golay (fenêtre adaptative, ordre 3)
      │
      ▼
④ _fft()                 → FFT → fréquence dominante freq_fft
      │
      ▼
⑤ _bandpass()            → Butterworth ordre 4, centré sur freq_fft
      │                     bornes : [0.4·f, 2.5·f]  ∩  [5 Hz, 0.95·f_nyq]
      ▼
⑥ _jerk()                → dérivée numérique az_bp → jerk (g/s)
      │
      ▼
⑦ métriques              → RMS, amplitude crête-à-crête
      │
      ▼
AnalysisResult
```

**Sortie graphique :**

| Graphique | Description |
|---|---|
| **Accélération Z brute** | Signal détrended en fonction du temps |
| **Diagramme de phase (a, j)** | Trajectoire colorée selon le temps — attracteur de Takens |
| **FFT** | Spectre fréquentiel avec marquage du pic dominant |

---

## Tests

```bash
python -m pytest tests/ -v
```

```
36 passed in 2.06s
```

**Couverture par module :**

| Fichier de test | Classe testée | Ce qui est vérifié |
|---|---|---|
| `test_serial_reader.py` | `SerialReader` | Décodage paquet, checksum XOR, scale gyro, rollover uint32, connexion mockée |
| `test_flutter_analyser.py` | `FlutterAnalyser` | Chaque étape du pipeline + test d'intégration sur signal synthétique |
| `test_flutter_plotter.py` | `FlutterPlotter` | Appels matplotlib, présence `LineCollection`, ligne verticale FFT |

Les tests **ne nécessitent pas de matériel** — `serial.Serial` est entièrement mocké, et les signaux synthétiques sont générés par `numpy`.

---

## Configuration

Tous les paramètres sont dans `config.py` sous forme de `dataclass frozen` :

| Paramètre | Défaut | Description |
|---|---|---|
| `port` | `/dev/ttyACM0` | Port série Arduino |
| `baud` | `1_000_000` | Débit série (bauds) |
| `duree_s` | `10` | Durée d'acquisition (s) |
| `attente_s` | `7` | Compte à rebours avant démarrage |
| `freq_cible_hz` | `45.0` | Fréquence de repli si FFT échoue (Hz) |
| `pkt_size` | `20` | Taille d'un paquet binaire (octets) |
| `gyro_scale` | `0.5` | Facteur de conversion gyroscope (°/s par LSB) |
| `calibration_timeout_s` | `30` | Timeout attente `READY_TRACKING` (s) |

---

## Référence

> Takens, F. (1981). *Detecting strange attractors in turbulence.*  
> In D. Rand & L.-S. Young (Eds.), **Dynamical Systems and Turbulence**,  
> Lecture Notes in Mathematics, Vol. 898, Springer-Verlag, pp. 366–381.  
> [https://doi.org/10.1007/BFb0091924](https://doi.org/10.1007/BFb0091924)