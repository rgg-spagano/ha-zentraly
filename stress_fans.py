#!/usr/bin/env python3
"""
stress_fans.py — Sube la CPU al máximo para calentar la compu y forzar los fans.

Uso:
    python3 stress_fans.py            # 60 segundos, todos los cores
    python3 stress_fans.py -t 30      # 30 segundos
    python3 stress_fans.py -t 120 -c 4  # 120 segundos, 4 cores
"""

import argparse
import multiprocessing
import signal
import sys
import time

# ── temperatura (opcional, solo macOS con osx-cpu-temp o powermetrics) ──────
def _read_temp_macos() -> str | None:
    """Intenta leer la temperatura de la CPU en macOS."""
    try:
        import subprocess
        result = subprocess.run(
            ["osx-cpu-temp"],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    try:
        import subprocess
        result = subprocess.run(
            ["sudo", "powermetrics", "-n", "1", "-i", "100",
             "--samplers", "thermal"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if "CPU die temperature" in line:
                return line.strip()
    except Exception:
        pass
    return None


# ── worker que quema CPU ─────────────────────────────────────────────────────
def _burn(stop_event):
    """Loop infinito de punto flotante hasta que stop_event se active."""
    while not stop_event.is_set():
        _ = sum(i * i for i in range(10_000))


# ── barra de progreso simple ─────────────────────────────────────────────────
def _bar(elapsed: int, total: int, width: int = 30) -> str:
    filled = int(width * elapsed / total)
    bar = "█" * filled + "░" * (width - filled)
    pct = int(100 * elapsed / total)
    return f"[{bar}] {pct:3d}%"


def main():
    parser = argparse.ArgumentParser(description="CPU stress test para fans")
    parser.add_argument("-t", "--time", type=int, default=60,
                        help="Duración en segundos (default: 60)")
    parser.add_argument("-c", "--cores", type=int,
                        default=multiprocessing.cpu_count(),
                        help="Número de cores a usar (default: todos)")
    args = parser.parse_args()

    duration = args.time
    cores = min(args.cores, multiprocessing.cpu_count())

    print(f"\n🔥  Stress test — {cores} core(s) por {duration}s")
    print(f"    CPUs disponibles: {multiprocessing.cpu_count()}")

    temp = _read_temp_macos()
    if temp:
        print(f"    Temperatura inicial: {temp}")
    else:
        print("    (instala `osx-cpu-temp` para ver temperatura en tiempo real)")

    print("\n    Presiona Ctrl+C para detener antes.\n")

    stop_event = multiprocessing.Event()
    workers = [
        multiprocessing.Process(target=_burn, args=(stop_event,))
        for _ in range(cores)
    ]

    def _shutdown(sig=None, frame=None):
        print("\n\n    Deteniendo workers…")
        stop_event.set()
        for w in workers:
            w.join(timeout=2)
            if w.is_alive():
                w.terminate()
        print("    ✓ Listo.\n")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    for w in workers:
        w.start()

    start = time.time()
    try:
        while True:
            elapsed = int(time.time() - start)
            remaining = duration - elapsed

            temp_str = ""
            t = _read_temp_macos()
            if t:
                temp_str = f"  |  {t}"

            bar = _bar(min(elapsed, duration), duration)
            print(f"\r    {bar}  {remaining:3d}s restantes{temp_str}   ", end="", flush=True)

            if elapsed >= duration:
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    _shutdown()


if __name__ == "__main__":
    main()
