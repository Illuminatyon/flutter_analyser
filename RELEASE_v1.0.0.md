# Release v1.0.0 — Flutter Analyser

**Date :** 29 mai 2026  
**Status :** ✅ Production Ready

## Vue d'ensemble

Flutter Analyser est un système complet d'acquisition et d'analyse temps-réel des vibrations de flutter aéroélastique via un capteur **MPU-6050** connecté à Arduino.

Le projet reconstruit la dynamique du système dans l'**espace de phase (accélération, jerk)** en appliquant le **théorème de Takens (1981)**, permettant une détection fiable des cycles limites caractéristiques du flutter.

## ✨ Fonctionnalités principales

### Analyse physique avancée
- ✅ Détection automatique de flutter aéroélastique via attracteur topologique
- ✅ Reconstruction de l'espace de phase **(a, j)** équivalent à **(z, v_z)**
- ✅ Pipeline de traitement signal robuste avec 7 étapes optimisées
- ✅ FFT intelligente pour identification fréquence dominante
- ✅ Filtre Butterworth adaptatif ordre 4 (bande [0.4·f, 2.5·f])

### Visualisation
- ✅ Trois graphiques interconnectés :
  - Accélération Z brute (détrended)
  - Diagramme de phase 2D coloré temporellement
  - Spectre FFT avec annotation du pic dominant
- ✅ Export automatique en CSV (`data/mesure_flutter.csv`)

### Architecture solide
- ✅ **Séparation des responsabilités** (SRP) stricte
- ✅ Modèles de données typés (dataclasses)
- ✅ **36 tests unitaires** (100% sans matériel)
- ✅ Configuration centralisée (dataclass frozen)
- ✅ Logging global structuré

## Pipeline de traitement

```
Données brutes (MPU-6050)
    ↓
① Extraction signaux (t, az)
    ↓
② Détrending linéaire (offset + dérive)
    ↓
③ Lissage Savitzky-Golay (fenêtre adaptative, ordre 3)
    ↓
④ FFT → détection fréquence dominante
    ↓
⑤ Filtre passe-bande Butterworth (ordre 4)
    ↓
⑥ Calcul Jerk (dérivée de l'accélération)
    ↓
⑦ Extraction métriques (RMS, crête-à-crête)
    ↓
Résultats + Visualisation
```

## 📦 Contenu de la release

### Structure du projet

```
flutter_analyser/
├── main.py                    # Orchestration principale
├── config.py                  # Configuration centralisée
├── setup_project.py           # Initialisation projet
│
├── models/
│   ├── packet.py             # SensorPacket (décodage binaire)
│   ├── acquisition.py        # AcquisitionData (échantillons)
│   └── analysis_result.py    # AnalysisResult (métriques)
│
├── serial_io/
│   └── serial_reader.py      # I/O série Arduino
│
├── processing/
│   └── flutter_analyser.py   # Pipeline signal complet
│
├── visualization/
│   └── flutter_plotter.py    # Rendu matplotlib (3 graphiques)
│
├── utils/
│   └── logger.py             # Logging structuré
│
├── tests/                    # 36 tests unitaires
├── requirements.txt
└── README.md
```

### Dépendances principales

- **Python ≥ 3.12**
- **numpy** — calculs vectorisés
- **scipy** — FFT, filtres Butterworth, Savitzky-Golay
- **pandas** — gestion CSV
- **matplotlib** — visualisation
- **pyserial** — communication série
- **pytest** — tests unitaires

## 🚀 Installation & Démarrage

### Installation rapide

```bash
git clone https://github.com/Illuminatyon/flutter_analyser.git
cd flutter_analyser
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows

pip install -r requirements.txt
python setup_project.py
```

### Lancement

```bash
python main.py
```

Le programme :
1. Se connecte au port série Arduino
2. Attend calibration (message `READY_TRACKING`)
3. Effectue compte à rebours
4. Acquiert les données
5. Sauvegarde CSV et affiche graphiques

### Configuration port & durée

Éditer `config.py` :

```python
DEFAULT_CONFIG = SensorConfig(
    port = "/dev/ttyACM0",    # ou "COM3" Windows
    baud = 1_000_000,
    duree_s = 10,
    attente_s = 7,
)
```

## ✅ Tests & Qualité

```bash
python -m pytest tests/ -v
```

**Résultat :** ✅ **36 tests passed**

### Couverture

| Module | Classe | Couverture |
|---|---|---|
| `test_serial_reader.py` | `SerialReader` | Décodage, checksum, scale gyro, rollover |
| `test_flutter_analyser.py` | `FlutterAnalyser` | Pipeline complet + signal synthétique |
| `test_flutter_plotter.py` | `FlutterPlotter` | Matplotlib, LineCollection, FFT marker |

**Pas de matériel requis** — mocking complet de la série, signaux synthétiques numpy.

## 📐 Fondements théoriques

Ce projet implémente le **théorème de Takens (1981)** :

> Une série temporelle unidimensionnelle d'un système dynamique contient toute l'information topologique du système original.

**Application :** L'espace de phase **(accélération, jerk)** reconstruit est **homéomorphe** à l'espace d'état original **(z, v_z)**. Un **cycle limite fermé** indique la présence de flutter.

### Référence

> Takens, F. (1981). *Detecting strange attractors in turbulence.* In D. Rand & L.-S. Young (Eds.), **Dynamical Systems and Turbulence**, Lecture Notes in Mathematics, Vol. 898, Springer-Verlag, pp. 366–381.  
> https://doi.org/10.1007/BFb0091924

## 🎓 Cas d'usage

- ✅ **Chercheurs en aéroélasticité** — Analyse dynamique temps-réel
- ✅ **Ingénieurs aéronautiques** — Détection flutter en vol ou en soufflerie
- ✅ **Étudiants en physique** — Démonstration pratique Takens
- ✅ **Prototypage rapide** — Validation concepts avant certification

## 📄 License

MIT License — Libre d'utilisation, modification et redistribution.

## 🤝 Support & Feedback

Pour toute question, bug ou amélioration → [GitHub Issues](https://github.com/Illuminatyon/flutter_analyser/issues)

**Merci d'utiliser Flutter Analyser !** 🚀
