import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import savgol_filter
from mpl_toolkits.mplot3d import Axes3D


# --- Function to detrend trajectory (remove local trend per axis) ---
def detrend(signal, window=11, poly=2):
    trend = savgol_filter(signal, window_length=window, polyorder=poly)
    return signal - trend


# --- Compute metrics for a 3D trajectory ---
def compute_metrics(traj):
    """
    Compute jitter variance, acceleration RMS, and residuals for a 3D trajectory.

    Parameters
    ----------
    traj : np.ndarray
        Shape (N,3) array of positions (x,y,z).

    Returns
    -------
    jitter_var : float
        Average variance of detrended residuals across dimensions.
    accel_rms : float
        Average root mean square of acceleration across dimensions.
    residuals : np.ndarray
        Shape (N,3) detrended residuals.
    """
    residuals = np.zeros_like(traj)
    jitter_vars = []
    accel_rms_vals = []

    for dim in range(traj.shape[1]):
        coord = traj[:, dim]
        res = detrend(coord)
        residuals[:, dim] = res

        # Jitter variance
        jitter_vars.append(np.var(res))

        # Acceleration (second difference)
        accel = coord[2:] - 2 * coord[1:-1] + coord[:-2]
        accel_rms_vals.append(np.sqrt(np.mean(accel**2)))

    jitter_var = np.mean(jitter_vars)
    accel_rms = np.mean(accel_rms_vals)
    return jitter_var, accel_rms, residuals


# --- FFT utility (for one dimension) ---
def compute_fft(residuals, fs=1.0):
    """
    Compute frequency spectrum of residuals.

    Parameters
    ----------
    residuals : np.ndarray
        1D detrended signal.
    fs : float
        Sampling rate (default=1.0 per frame).

    Returns
    -------
    freqs : np.ndarray
        Frequency bins.
    fft_vals : np.ndarray
        Magnitude spectrum.
    """
    N = len(residuals)
    freqs = np.fft.rfftfreq(N, d=1/fs)
    fft_vals = np.abs(np.fft.rfft(residuals)) / N
    return freqs, fft_vals


# --- Main script logic (only runs if executed directly) ---
if __name__ == "__main__":
    np.random.seed(0)

    # Generate synthetic 3D trajectory
    frames = np.arange(0, 100)
    smooth_traj = np.stack([
        0.05 * frames,   # x
        0.03 * frames,   # y
        0.02 * frames    # z
    ], axis=1)

    # Add jitter (Gaussian noise in all 3 axes)
    traj_jitter = smooth_traj + np.random.normal(0, 0.2, smooth_traj.shape)

    # Add abrupt jerk at frame 50
    traj_jerky = traj_jitter.copy()
    traj_jerky[50:, :] += np.array([2.0, 2.0, 2.0])

    # Compute metrics
    jitter_clean, accel_clean, res_clean = compute_metrics(smooth_traj)
    jitter_jittery, accel_jittery, res_jitter = compute_metrics(traj_jitter)
    jitter_jerky, accel_jerky, res_jerky = compute_metrics(traj_jerky)

    print("Smooth trajectory:", jitter_clean, accel_clean)
    print("With jitter:", jitter_jittery, accel_jittery)
    print("With jitter + jerk:", jitter_jerky, accel_jerky)

    # --- Plotting (as before) ---
    fig = plt.figure(figsize=(14, 10))

    ax = fig.add_subplot(2, 3, 1, projection='3d')
    ax.plot(smooth_traj[:, 0], smooth_traj[:, 1], smooth_traj[:, 2], 'g-', label='Smooth')
    ax.plot(traj_jitter[:, 0], traj_jitter[:, 1], traj_jitter[:, 2], 'r--', label='Jittery')
    ax.plot(traj_jerky[:, 0], traj_jerky[:, 1], traj_jerky[:, 2], 'b-.', label='Jitter+Jerk')
    ax.set_title("3D Trajectories")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.legend()

    dims = ["X", "Y", "Z"]
    for i in range(3):
        ax_r = fig.add_subplot(2, 3, 2 + i)
        ax_r.plot(res_clean[:, i], 'g-', label=f'Smooth (Var={np.var(res_clean[:, i]):.3f})')
        ax_r.plot(res_jitter[:, i], 'r--', label=f'Jitter (Var={np.var(res_jitter[:, i]):.3f})')
        ax_r.plot(res_jerky[:, i], 'b-.', label=f'Jitter+Jerk (Var={np.var(res_jerky[:, i]):.3f})')
        ax_r.set_title(f"Residuals ({dims[i]}-axis)")
        ax_r.set_xlabel("Frame")
        ax_r.set_ylabel("Residual")
        ax_r.legend()
        ax_r.grid(True)

    fig.savefig("tracking_jitter_analysis_3d_residuals.png", dpi=150)

    fig_fft, axes_fft = plt.subplots(1, 3, figsize=(14, 4))
    for i in range(3):
        freqs_clean, fft_clean = compute_fft(res_clean[:, i])
        freqs_jitter, fft_jitter = compute_fft(res_jitter[:, i])
        freqs_jerky, fft_jerky = compute_fft(res_jerky[:, i])

        axes_fft[i].plot(freqs_clean, fft_clean, 'g-', label='Smooth')
        axes_fft[i].plot(freqs_jitter, fft_jitter, 'r--', label='Jitter')
        axes_fft[i].plot(freqs_jerky, fft_jerky, 'b-.', label='Jitter+Jerk')
        axes_fft[i].set_title(f"FFT Spectrum ({dims[i]}-axis)")
        axes_fft[i].set_xlabel("Frequency [1/frame]")
        axes_fft[i].set_ylabel("Magnitude")
        axes_fft[i].legend()
        axes_fft[i].grid(True)

    fig_fft.savefig("tracking_fft_3d.png", dpi=150)

    fig_metrics, axm = plt.subplots(figsize=(6, 5))
    labels = ["Smooth", "Jitter", "Jitter+Jerk"]
    jitter_vals = [jitter_clean, jitter_jittery, jitter_jerky]
    accel_vals = [accel_clean, accel_jittery, accel_jerky]
    x = np.arange(len(labels))
    width = 0.35
    axm.bar(x - width/2, jitter_vals, width, label='Jitter Var')
    axm.bar(x + width/2, accel_vals, width, label='Accel RMS')
    axm.set_xticks(x)
    axm.set_xticklabels(labels)
    axm.set_title("Quantitative Metrics (averaged over x,y,z)")
    axm.legend()
    axm.grid(True, axis='y')

    fig_metrics.savefig("tracking_metrics_bar.png", dpi=150)
