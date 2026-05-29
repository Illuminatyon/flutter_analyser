"""
Flutter Analyser — MPU-6050 — Protocole Binaire
Diagramme de phase dans l'espace (a, j) = (acceleration, jerk)
Equivalent topologique de (z, vz) par le theoreme de Takens (1981).

Reference :
  Takens, F. (1981). Detecting strange attractors in turbulence.
  Lecture Notes in Mathematics, Vol. 898, Springer, pp. 366-381.
"""
import serial  # bibliothèque pour la connexion entre arduino et python
import time
import struct
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from scipy.signal import savgol_filter, detrend, butter, filtfilt

# ─── CONFIGURATION ───────────────────────────────────────────────────────────
PORT = "/dev/ttyACM0"
BAUD = 1000000
DUREE_S = 10
ATTENTE_S = 7
FREQ_CIBLE = 45  # Hz — centre du passe-bande
# ─────────────────────────────────────────────────────────────────────────────

PKT_SIZE = 20
PKT_FORMAT = '<I fff bbb B'


def lire_paquet(ser):
    raw = ser.read(PKT_SIZE)
    if len(raw) < PKT_SIZE:
        return None
    cs = 0
    for b in raw[:19]:
        cs ^= b
    if cs != raw[19]:
        return None
    t_us, ax, ay, az, gx_i, gy_i, gz_i, _ = struct.unpack(PKT_FORMAT, raw)
    return t_us, ax, ay, az, gx_i * 0.5, gy_i * 0.5, gz_i * 0.5


def acquerir(port, baud, duree_s):
    donnees = []

    print(f"Connexion sur {port} a {baud} bauds...")
    try:
        ser = serial.Serial(port, baud, timeout=5)
    except serial.SerialException as e:
        print(f"ERREUR : {e}")
        return None

    time.sleep(2)
    ser.reset_input_buffer()

    print("Attente calibration Arduino...")
    pret = False
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                print(f"  Arduino: {line}")
            if 'READY_TRACKING' in line:
                pret = True
                break
        except Exception:
            continue

    if not pret:
        print("TIMEOUT calibration")
        ser.close()
        return None

    ser.reset_input_buffer()

    print(f"\nDemarrage dans :")
    for i in range(ATTENTE_S, 0, -1):
        print(f"  {i}...", end='\r', flush=True)
        time.sleep(1)
    print("  GO !          ")
    ser.reset_input_buffer()

    print(f"Acquisition en cours ({duree_s}s)...")

    t_debut = None
    t_precedent = None
    t_ecoule = 0.0
    erreurs = 0
    paquets_ok = 0

    while True:
        pkt = lire_paquet(ser)
        if pkt is None:
            erreurs += 1
            if erreurs % 50 == 0:
                ser.reset_input_buffer()
            else:
                ser.read(1)
            continue

        t_us, ax, ay, az, gx, gy, gz = pkt
        t_ms = t_us / 1000.0

        if t_debut is None:
            t_debut = t_ms
            t_precedent = t_ms
            print(f"  Premier paquet recu (t={t_ms:.0f}ms)")

        delta = t_ms - t_precedent
        if delta < 0:
            delta = 4294967.296 - t_precedent + t_ms
        elif delta > 1000:
            delta = 1.0

        t_ecoule += delta / 1000.0
        t_precedent = t_ms

        if t_ecoule > duree_s:
            break

        donnees.append([t_ecoule, ax, ay, az, gx, gy, gz])
        paquets_ok += 1

        if paquets_ok % 500 == 0:
            hz = paquets_ok / t_ecoule if t_ecoule > 0 else 0
            print(f"  {t_ecoule:.1f}/{duree_s}s — {paquets_ok} paquets — {hz:.0f} Hz",
                  end='\r', flush=True)

    ser.close()

    if len(donnees) < 10:
        print(f"\nPas assez de donnees ({len(donnees)} paquets, {erreurs} erreurs)")
        return None

    duree_reelle = donnees[-1][0] - donnees[0][0]
    freq_reelle = (len(donnees) - 1) / duree_reelle if duree_reelle > 0 else 0

    print(f"\n\nAcquisition terminee:")
    print(f"  Paquets valides : {len(donnees)}")
    print(f"  Erreurs checksum: {erreurs}")
    print(f"  Duree reelle    : {duree_reelle:.3f} s")
    print(f"  Frequence reelle: {freq_reelle:.1f} Hz")

    return donnees, freq_reelle


def analyser(donnees, freq_reelle):
    cols = ['time_s', 'ax_g', 'ay_g', 'az_g', 'gx_dps', 'gy_dps', 'gz_dps']
    df = pd.DataFrame(donnees, columns=cols)
    t = df['time_s'].values
    dt = t[-1] / (len(t) - 1)

    # ── Accélération Z — retirer offset DC ───────────────────────────────────
    az = detrend(df['az_g'].values, type='linear')
    win = min(11, len(az) if len(az) % 2 == 1 else len(az) - 1)
    az_s = savgol_filter(az, win, 3)

    # ── FFT sur az ────────────────────────────────────────────────────────────
    N = len(az_s)
    fft_y = np.abs(np.fft.rfft(az_s))
    fft_f = np.fft.rfftfreq(N, d=dt)
    mask_fft = (fft_f >= 5) & (fft_f <= min(150, freq_reelle / 2 * 0.95))
    freq_fft = fft_f[mask_fft][np.argmax(fft_y[mask_fft])] if mask_fft.any() else FREQ_CIBLE

    # ── Filtre passe-bande centré sur freq_fft ────────────────────────────────
    f_nyq = freq_reelle / 2.0
    f_low = max(5.0, freq_fft * 0.4)
    f_high = min(f_nyq * 0.95, freq_fft * 2.5)
    if f_high <= f_low + 2:
        f_high = min(f_nyq * 0.95, f_low + 20)

    b, a = butter(4, [f_low / f_nyq, f_high / f_nyq], btype='band')
    az_bp = filtfilt(b, a, az)

    # ── Jerk = dérivée de l'accélération filtrée ─────────────────────────────
    jerk = np.gradient(az_bp, dt)  # g/s

    # ── Métriques ─────────────────────────────────────────────────────────────
    rms_az = np.sqrt(np.mean(az_s ** 2))
    amp_az = (az_bp.max() - az_bp.min()) / 2

    print("\n" + "=" * 55)
    print("  RESULTATS")
    print("=" * 55)
    print(f"  Echantillons           : {N}")
    print(f"  dt moyen               : {dt * 1000:.3f} ms")
    print(f"  Frequence FFT          : {freq_fft:.3f} Hz  (T={1 / freq_fft * 1000:.1f} ms)")
    print(f"  RMS acceleration Z     : {rms_az * 1000:.2f} mg")
    print(f"  Amplitude acceleration : {amp_az * 1000:.2f} mg")
    print(f"  Filtre passe-bande     : [{f_low:.1f} — {f_high:.1f}] Hz")
    print()
    print("  Ref: Takens (1981), Lect. Notes Math. Vol.898, pp.366-381")
    print("=" * 55 + "\n")

    df.to_csv('mesure_flutter.csv', index=False)
    print("Donnees sauvegardees: mesure_flutter.csv")

    # ── Graphiques — 3 diagrammes uniquement ─────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle(
        f"Flutter MPU-6050  |  f = {freq_fft:.2f} Hz  |  fs = {freq_reelle:.0f} Hz",
        fontsize=14, weight='bold')

    # ── 1. ACCELERATION BRUTE ────────────────────────────────────────────────
    axes[0].plot(t, az, 'b', lw=0.8, alpha=0.9)
    axes[0].axhline(0, color='k', lw=0.5, ls='--')
    axes[0].set_title("Acceleration Z brute (g)", fontsize=12, weight='bold')
    axes[0].set_xlabel("Temps (s)")
    axes[0].set_ylabel("g")
    axes[0].legend(fontsize=9)
    axes[0].grid(True, alpha=0.3)
    axes[0].set_xlim(t[0], t[-1])

    # ── 2. DIAGRAMME DE PHASE (a, j) — COLORÉ SELON LE TEMPS ─────────────────
    points = np.column_stack([az_bp, jerk])
    segments = []
    colors = []

    for i in range(len(points) - 1):
        seg = [points[i], points[i + 1]]
        segments.append(seg)
        colors.append(t[i])

    lc = LineCollection(segments, cmap='viridis', linewidths=1.5)
    lc.set_array(np.array(colors))
    lc.set_clim(t[0], t[-1])

    line = axes[1].add_collection(lc)

    axes[1].set_xlim(az_bp.min() * 1.1, az_bp.max() * 1.1)
    axes[1].set_ylim(jerk.min() * 1.1, jerk.max() * 1.1)

    axes[1].axhline(0, color='k', lw=0.5, ls='--', zorder=0)
    axes[1].axvline(0, color='k', lw=0.5, ls='--', zorder=0)
    axes[1].set_title("Diagramme de phase (a, j)", fontsize=12, weight='bold')
    axes[1].set_xlabel("Acceleration Z (g)")
    axes[1].set_ylabel("Jerk Z (g/s)")
    axes[1].grid(True, alpha=0.3)

    cbar = plt.colorbar(line, ax=axes[1], shrink=0.8)
    cbar.set_label('Temps (s)', fontsize=9)

    # ── 3. FFT ────────────────────────────────────────────────────────────────
    axes[2].plot(fft_f[1:], fft_y[1:], 'purple', lw=1.2)
    axes[2].axvline(freq_fft, color='red', ls='--', lw=2,
                    label=f"Pic = {freq_fft:.2f} Hz")
    axes[2].set_title("FFT Acceleration Z", fontsize=12, weight='bold')
    axes[2].set_xlabel("Frequence (Hz)")
    axes[2].set_ylabel("Amplitude")
    axes[2].set_xlim(0, min(150, fft_f[-1]))
    axes[2].legend(fontsize=9)
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.show()


# ── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    resultat = acquerir(PORT, BAUD, DUREE_S)
    if resultat:
        donnees, freq_reelle = resultat
        analyser(donnees, freq_reelle)
    else:
        print("\nEchec acquisition")