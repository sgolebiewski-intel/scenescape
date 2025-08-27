import sys
import os
import json
from datetime import datetime
from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt
import csv
from tracking_metrics import compute_metrics, compute_fft

# TODO: velocity from translation -> correlation with velocity from tracker

def parse_timestamp(ts):
    # Example: "2025-08-06T15:40:04.797Z"
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ")

def vector_norm(vec):
    return np.linalg.norm(vec)

def generate_metrics(track):
    # track: list of (time_elapsed_sec, translation, velocity, visibility_count)
    # Extract positions as (N, 3) numpy array
    positions = np.array([translation for _, translation, _, _ in track])
    if len(positions) < 2:
        # Not enough points for metrics
        return [], None, None
    jitter_var, accel_rms, residuals = compute_metrics(positions)
    return residuals, jitter_var, accel_rms

def dump_track_csv(track, csv_path):
    # track: list of (time_elapsed_sec, translation, velocity, visibility_count)
    with open(csv_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['time_elapsed_sec', 'translation_x', 'translation_y', 'translation_z',
                         'velocity_x', 'velocity_y', 'velocity_z', 'visibility_count'])
        for t, translation, velocity, visibility_count in track:
            writer.writerow([t] + list(translation) + list(velocity) + [visibility_count])

def dump_metrics_csv(metrics, csv_path):
    # metrics: list of (time_elapsed_sec, acceleration_vector)
    with open(csv_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['time_elapsed_sec', 'acceleration_x', 'acceleration_y', 'acceleration_z', 'acceleration_norm'])
        for t, acc in metrics:
            acc_norm = vector_norm(acc)
            writer.writerow([t] + list(acc) + [acc_norm])

def main(input_file):
    data = []
    first_timestamp = None

    # Prepare output directory and base name
    tracks_dir = "tracks"
    os.makedirs(tracks_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(input_file))[0]

    with open(input_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if first_timestamp is None:
                first_timestamp = parse_timestamp(obj['timestamp'])
            time_elapsed_sec = (parse_timestamp(obj['timestamp']) - first_timestamp).total_seconds()
            name = obj.get('name', '')
            objects = obj.get('objects', [])
            if not objects:
                continue
            for o in objects:
                oid = o['id']
                translation = o['translation']
                velocity = o['velocity']
                visibility_count = len(o.get('visibility', []))
                data.append((time_elapsed_sec, name, oid, translation, velocity, visibility_count))

    # Aggregate into tracks
    tracks = defaultdict(list)
    for t, name, oid, translation, velocity, visibility_count in data:
        key = (name, oid)
        tracks[key].append((t, translation, velocity, visibility_count))

    # Sort each track by time
    for key in tracks:
        tracks[key].sort(key=lambda x: x[0])

    # Dump each track to CSV
    for key, track in tracks.items():
        name, oid = key
        csv_filename = f"{base_name}_track_{name}_{oid[:6]}.csv"
        csv_path = os.path.join(tracks_dir, csv_filename)
        dump_track_csv(track, csv_path)

    # Generate metrics and collect residuals
    metrics = {}
    metrics_stats = {}
    for key, track in tracks.items():
        residuals, jitter_var, accel_rms = generate_metrics(track)
        metrics[key] = residuals
        metrics_stats[key] = (jitter_var, accel_rms)

    # Dump each metrics (residuals) to CSV
    for key, residuals in metrics.items():
        name, oid = key
        metrics_filename = f"{base_name}_metrics_{name}_{oid[:6]}.csv"
        metrics_path = os.path.join(tracks_dir, metrics_filename)
        # Save residuals as CSV
        with open(metrics_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['residual_x', 'residual_y', 'residual_z'])
            if residuals is not None:
                for row in residuals:
                    writer.writerow(list(row))

    # Print jitter_var and accel_rms for each track
    for key, (jitter_var, accel_rms) in metrics_stats.items():
        name, oid = key
        print(f"Track {name}:{oid[:6]} - jitter_var: {jitter_var}, accel_rms: {accel_rms}")

    # --- Create subplots for each unique name ---
    unique_names = sorted(set(name for _, name, _, _, _, _ in data))
    n_names = len(unique_names)
    fig, axs = plt.subplots(n_names, 2, figsize=(12, 6 * n_names), squeeze=False)

    for i, name in enumerate(unique_names):
        # Residuals plot for this name
        for key, residuals in metrics.items():
            if key[0] != name or residuals is None or len(residuals) == 0:
                continue
            # Plot norm of residuals over time
            times = [tracks[key][j][0] for j in range(len(residuals))]
            residual_norms = [vector_norm(residuals[j]) for j in range(len(residuals))]
            label = f"{key[0]}:{key[1][:6]}"
            axs[i, 0].plot(times, residual_norms, label=label)
        axs[i, 0].set_xlabel("Time elapsed (s)")
        axs[i, 0].set_ylabel("Residual norm")
        axs[i, 0].set_title(f"Residual Norm Over Time ({name})")
        axs[i, 0].legend()
        axs[i, 0].grid(True)

        # XY position plot for this name
        for key, track in tracks.items():
            if key[0] != name or not track:
                continue
            xs = [tr[0] for _, tr, _, _ in track]
            ys = [tr[1] for _, tr, _, _ in track]
            label = f"{key[0]}:{key[1][:6]}"
            axs[i, 1].plot(xs, ys, label=label)
        axs[i, 1].set_xlabel("X position")
        axs[i, 1].set_ylabel("Y position")
        axs[i, 1].set_title(f"Tracked Object Position (XY Plane) ({name})")
        axs[i, 1].legend()
        axs[i, 1].grid(True)

    plt.tight_layout()
    plot_filename = f"{base_name}_residuals_plot.png"
    plot_path = os.path.join(tracks_dir, plot_filename)
    plt.savefig(plot_path)
    plt.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python process_tracks.py <input_file>")
        sys.exit(1)
    main(sys.argv[1])
