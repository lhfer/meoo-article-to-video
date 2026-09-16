#!/usr/bin/env python3
"""Onset/tempo measurement for one music file (numpy + scipy; run through `uv run --with numpy --with scipy`).
Estimates are not a listening review: onset metrics cannot establish musical quality or the absence of vocals."""
import argparse, json, subprocess, sys
import numpy as np
from scipy import signal

def analyze(path, max_hits=40):
    meta = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:format_tags', '-of', 'json', str(path)]))['format']
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-vn', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'])
    y = np.frombuffer(raw, np.float32)
    sr, hop, size = 16000, 160, 1024
    frames = np.lib.stride_tricks.sliding_window_view(y, size)[::hop]
    spectrum = np.abs(np.fft.rfft(frames * np.hanning(size), axis=1))
    power = spectrum ** 2
    freqs = np.fft.rfftfreq(size, 1 / sr)
    rms = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-12)
    low = np.sqrt(np.mean(power[:, (freqs >= 35) & (freqs <= 180)], axis=1))
    flux = np.mean(np.maximum(0, np.diff(np.log1p(spectrum), axis=0)), axis=1)
    novelty = np.maximum(0, flux - signal.medfilt(flux, 51))
    start, end = min(500, len(novelty) // 10), min(7500, len(novelty))
    section = novelty[start:end]
    ac = signal.fftconvolve(section, section[::-1], mode='full')[len(section) - 1:]
    lo, hi = int(6000 / 180), min(len(ac), int(6000 / 72) + 1)
    candidates, _ = signal.find_peaks(ac[lo:hi]); candidates = candidates + lo
    candidates = candidates[np.argsort(ac[candidates])[::-1]][:3]
    estimates = [round(6000 / int(i), 1) for i in candidates]
    peaks, props = signal.find_peaks(novelty, distance=15, prominence=max(1e-6, float(np.quantile(novelty, 0.75))))
    prominences = props.get('prominences', np.zeros(len(peaks)))
    order = np.argsort(prominences)[::-1][:max_hits]
    hits = sorted([{'seconds': round(float(peaks[i] * hop / sr), 3), 'prominence': round(float(prominences[i]), 4),
                    'lowEnergy': round(float(low[min(len(low) - 1, peaks[i])]), 4)} for i in order], key=lambda h: h['seconds'])
    # Share of energy in the speech band (1–4 kHz): high values mean the bed will fight the narration even when ducked.
    band = float(np.sum(power[:, (freqs >= 1000) & (freqs <= 4000)]) / (np.sum(power) + 1e-12))
    strong = [h for h in hits if h['prominence'] >= 0.5 * max(x['prominence'] for x in hits)] if hits else []
    conf = float(ac[candidates[0]] / (ac[candidates[1]] + 1e-12)) if len(candidates) > 1 else (1.0 if len(candidates) else 0.0)
    threshold = float(np.quantile(rms, 0.85) * 0.50)
    active = np.flatnonzero(rms[:1500] > threshold)
    bpm = estimates[0] if estimates else None
    return {
        'file': str(path), 'durationSeconds': round(float(meta['duration']), 3), 'tags': meta.get('tags', {}),
        'tempoEstimatesBpm': estimates, 'barSeconds': round(240 / bpm, 3) if bpm else None,
        'tempoConfidence': round(min(1.0, max(0.0, (conf - 1.0) / 1.0)), 3), 'speechBandRatio': round(band, 4),
        'firstStrongHitSeconds': strong[0]['seconds'] if strong else None,
        'activeEnergyFromSeconds': round(float(active[0] * hop / sr), 2) if len(active) else None,
        'detectedOnsetsPerSecond': round(float(len(peaks) / (len(y) / sr)), 2),
        'rmsDbfs': round(float(20 * np.log10(np.sqrt(np.mean(y ** 2)) + 1e-12)), 2),
        'crestFactorDb': round(float(20 * np.log10((np.max(np.abs(y)) + 1e-12) / (np.sqrt(np.mean(y ** 2)) + 1e-12))), 2),
        'energy10SecondWindowsDbfs': [round(float(20 * np.log10(np.sqrt(np.mean(rms[i:i + 1000] ** 2)) + 1e-12)), 1) for i in range(0, len(rms), 1000)],
        'hits': [{'id': f'bgm.hit_{i + 1}', **h} for i, h in enumerate(hits)],
        'listeningReview': 'not_completed',
        'note': 'Tempo may have half/double-time ambiguity. Dynamics and onset metrics cannot establish subjective musical quality or absence of vocals.',
    }

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('file'); ap.add_argument('--max-hits', type=int, default=40); a = ap.parse_args()
    print(json.dumps(analyze(a.file, a.max_hits), ensure_ascii=False))
