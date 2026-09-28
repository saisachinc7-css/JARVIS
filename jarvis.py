import os
import sys
import subprocess

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    jarvis_main_dir = os.path.join(root_dir, "Jarvis-main")
    jarvis_script = os.path.join(jarvis_main_dir, "Jarvis.py")

    if not os.path.exists(jarvis_script):
        print(f"[Launcher] Error: Cannot find {jarvis_script}")
        sys.exit(1)

    try:
        proc = subprocess.run([sys.executable, jarvis_script] + sys.argv[1:], cwd=jarvis_main_dir)
        sys.exit(proc.returncode)
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()
