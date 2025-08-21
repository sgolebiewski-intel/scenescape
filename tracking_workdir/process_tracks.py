import sys
import os
import json
from datetime import datetime
from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt
import csv

# TODO: velocity from translation -> correlation with velocity from tracker

def parse_timestamp(ts):
    # Example: "2025-08-06T15:40:04.797Z"
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ")

def vector_norm(vec):
    return np.linalg.norm(vec)

def generate_metrics(track):
    # track: list of (time_elapsed_sec, translation, velocity, visibility_count)
    metrics = []
    prev_time = None
    prev_vel = None
    for t, _, vel, _ in track:
        if prev_time is not None:
            dt = t - prev_time
            if dt > 0:
                acc = [(v - pv) / dt for v, pv in zip(vel, prev_vel)]
                metrics.append((t, acc))
        prev_time = t
        prev_vel = vel
    return metrics

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

    # Generate metrics
    metrics = {}
    for key, track in tracks.items():
        metrics[key] = generate_metrics(track)

    # Dump each metrics to CSV
    for key, mlist in metrics.items():
        name, oid = key
        metrics_filename = f"{base_name}_metrics_{name}_{oid[:6]}.csv"
        metrics_path = os.path.join(tracks_dir, metrics_filename)
        dump_metrics_csv(mlist, metrics_path)

    # Plotting
    plt.figure(figsize=(10, 6))
    for key, mlist in metrics.items():
        if not mlist:
            continue
        times = [t for t, _ in mlist]
        acc_norms = [vector_norm(acc) for _, acc in mlist]
        label = f"{key[0]}:{key[1][:6]}"
        plt.plot(times, acc_norms, label=label)
    plt.xlabel("Time elapsed (s)")
    plt.ylabel("Acceleration norm")
    plt.title("Acceleration Norm Over Time per Track")
    plt.legend()
    plt.ylim(0, 300)  # Set fixed y-axis scale
    plt.tight_layout()
    plot_filename = f"{base_name}_acceleration_plot.png"
    plot_path = os.path.join(tracks_dir, plot_filename)
    plt.savefig(plot_path)
    plt.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python process_tracks.py <input_file>")
        sys.exit(1)
    main(sys.argv[1])
