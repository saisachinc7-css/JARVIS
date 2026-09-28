import os
import sys
import json
import time
import psutil
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, HTTPServer

# Resolve paths
UI_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(UI_DIR)      # d:\ANTIGRAVITY\JARVIS 2.0\Jarvis-main
WORKSPACE_DIR = os.path.dirname(PROJECT_DIR)  # d:\ANTIGRAVITY\JARVIS 2.0

class HUDRequestHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/command':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                command = data.get('command', '').strip()
                if command:
                    if PROJECT_DIR not in sys.path:
                        sys.path.insert(0, PROJECT_DIR)
                    import shared_state
                    shared_state.ui_user_message(command)
                    shared_state.set_jarvis_state("processing")
                    
                    def _run_cmd(cmd_text):
                        try:
                            from Automations.Automation_Brain import Automation_Brain
                            Automation_Brain(cmd_text)
                        except Exception as e:
                            print(f"[HUD Server] Command execution error: {e}")
                            shared_state.ui_jarvis_message(f"Error: {e}")
                        finally:
                            shared_state.set_jarvis_state("idle")

                    threading.Thread(target=_run_cmd, args=(command,), daemon=True).start()

                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok", "command": command}).encode('utf-8'))
                    return
            except Exception as e:
                print(f"[HUD Server] POST error: {e}")

        self.send_response(400)
        self.end_headers()

    def do_GET(self):

        if self.path == '/api/stats':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Fetch stats
            stats = get_system_stats()
            self.wfile.write(json.dumps(stats).encode('utf-8'))
            return
        elif self.path == '/api/shutdown':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "shutdown"}).encode('utf-8'))
            
            print("[JARVIS] Shutdown requested from HUD UI. Exiting...")
            
            def delay_exit():
                time.sleep(0.5)
                os._exit(0)
            threading.Thread(target=delay_exit, daemon=True).start()
            return
            
        elif self.path == '/' or self.path == '/index.html' or self.path == '/hud':
            # Try to serve the jarvis-hud (2).html
            html_path = os.path.join(WORKSPACE_DIR, "jarvis-hud (2).html")
            if not os.path.exists(html_path):
                # Fallback to UI dir
                html_path = os.path.join(UI_DIR, "jarvis-hud (2).html")
            
            if os.path.exists(html_path):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                with open(html_path, 'r', encoding='utf-8') as f:
                    self.wfile.write(f.read().encode('utf-8'))
                return
                
        elif self.path == '/world_map.png':
            map_path = os.path.join(WORKSPACE_DIR, "world_map.png")
            if os.path.exists(map_path):
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                with open(map_path, 'rb') as f:
                    self.wfile.write(f.read())
                return

        # For any other static file, standard serving
        super().do_GET()

# Stats calculation helper
start_time = time.time()
_last_net_bytes = [time.time(), 0, 0]
try:
    counters = psutil.net_io_counters()
    _last_net_bytes[1] = counters.bytes_sent
    _last_net_bytes[2] = counters.bytes_recv
except:
    pass

# News cache structure
_news_cache = {
    "last_fetched": 0,
    "items": []
}

def fetch_latest_news() -> list:
    import urllib.request
    import xml.etree.ElementTree as ET
    
    url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5.0) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            
            news_items = []
            for item in root.findall(".//item")[:10]: # Get top 10 news items
                title = item.find("title").text
                # Clean up title (remove source suffix like " - BBC News")
                if " - " in title:
                    title = title.rsplit(" - ", 1)[0]
                news_items.append(title)
            return news_items
    except Exception as e:
        print(f"[News] Error fetching news: {e}")
        return []

def get_cached_news() -> list:
    global _news_cache
    now = time.time()
    # Cache for 10 minutes (600 seconds)
    if now - _news_cache["last_fetched"] > 600 or not _news_cache["items"]:
        def bg_fetch():
            try:
                items = fetch_latest_news()
                if items:
                    _news_cache["items"] = items
                    _news_cache["last_fetched"] = time.time()
            except Exception:
                pass
        threading.Thread(target=bg_fetch, daemon=True).start()
        
    # Return placeholder items if cache is empty on first load
    if not _news_cache["items"]:
        return [
            "Global summit reaches historical agreement on renewable energy.",
            "Tech conference showcases next-generation generative AI advances.",
            "New discoveries in space exploration reveal signs of water on Mars.",
            "Economic reports show positive growth trends across major sectors."
        ]
    return _news_cache["items"]


def get_system_stats():
    # Add project root to sys.path if not present to allow importing shared_state
    if PROJECT_DIR not in sys.path:
        sys.path.insert(0, PROJECT_DIR)
        
    try:
        import shared_state
    except ImportError:
        # Fallback if import path issues occur
        sys.path.append(os.getcwd())
        import shared_state

    # CPU
    cpu_percent = psutil.cpu_percent()
    cpu_freq = psutil.cpu_freq()
    cpu_mhz = int(cpu_freq.current) if cpu_freq else 2178
    
    # RAM
    ram = psutil.virtual_memory()
    ram_used = ram.used / (1024**3)
    ram_free = ram.available / (1024**3)
    ram_percent = ram.percent
    
    # Disk
    try:
        disk = psutil.disk_usage('C:\\')
    except:
        try:
            disk = psutil.disk_usage('/')
        except:
            disk = None
            
    disk_used = disk.used / (1024**3) if disk else 0.0
    disk_percent = disk.percent if disk else 0.0
    
    # Network speed
    now = time.time()
    try:
        counters = psutil.net_io_counters()
        dt = now - _last_net_bytes[0]
        if dt > 0:
            up_speed = max(0.0, (counters.bytes_sent - _last_net_bytes[1]) / dt / 1024)   # KB/s
            down_speed = max(0.0, (counters.bytes_recv - _last_net_bytes[2]) / dt / 1024) # KB/s
        else:
            up_speed, down_speed = 0.0, 0.0
        _last_net_bytes[0] = now
        _last_net_bytes[1] = counters.bytes_sent
        _last_net_bytes[2] = counters.bytes_recv
    except:
        up_speed, down_speed = 0.0, 0.0
        
    # GPU
    # Simulating GPU load intelligently based on active assistant state
    state = shared_state.get_jarvis_state()
    if state == "processing":
        import random
        gpu_percent = random.randint(65, 88)
    elif state == "speaking":
        import random
        gpu_percent = random.randint(15, 30)
    else:
        import random
        gpu_percent = random.randint(2, 8)
        
    # Uptime
    uptime = int(time.time() - start_time)
    
    # Chat history
    try:
        chat_history = shared_state.get_chat_history()
    except Exception:
        chat_history = []
        
    # Reminders
    try:
        from Brain.reminder_manager import get_active_reminders
        reminders_list = [{"text": r["text"], "time": r["formatted_time"]} for r in get_active_reminders()]
    except Exception:
        reminders_list = []
        
    # News
    news_list = get_cached_news()
        
    return {
        "cpu_percent": cpu_percent,
        "cpu_temp": 40.0 + (cpu_percent / 2.0),
        "cpu_mhz": cpu_mhz,
        "ram_used_gb": round(ram_used, 1),
        "ram_free_gb": round(ram_free, 1),
        "ram_percent": ram_percent,
        "disk_used_gb": round(disk_used, 1),
        "disk_percent": disk_percent,
        "net_up_kbps": round(up_speed, 1),
        "net_down_kbps": round(down_speed, 1),
        "gpu_percent": gpu_percent,
        "uptime_seconds": uptime,
        "state": state,
        "chat_history": chat_history,
        "reminders": reminders_list,
        "news": news_list
    }

_server = None

def start_hud_server():
    global _server
    port = 2080
    max_tries = 5
    for attempt in range(max_tries):
        try:
            # We bind to localhost to ensure it only listens to internal loopback
            _server = HTTPServer(('localhost', port), HUDRequestHandler)
            print(f"[HUD Server] Running on http://localhost:{port}")
            t = threading.Thread(target=_server.serve_forever, daemon=True)
            t.start()
            
            # Open browser after a small delay
            def open_browser():
                time.sleep(1.5)
                hud_url = f"http://localhost:{port}"
                print(f"[HUD Server] Opening JARVIS HUD in Chromium app mode...")
                
                launched = False
                chrome_paths = [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                    os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")
                ]
                edge_paths = [
                    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
                ]
                
                for path in chrome_paths:
                    if os.path.exists(path):
                        try:
                            import subprocess
                            subprocess.Popen([path, f"--app={hud_url}"])
                            launched = True
                            break
                        except Exception:
                            pass
                
                if not launched:
                    for path in edge_paths:
                        if os.path.exists(path):
                            try:
                                import subprocess
                                subprocess.Popen([path, f"--app={hud_url}"])
                                launched = True
                                break
                            except Exception:
                                pass
                
                if not launched:
                    webbrowser.open(hud_url)
            threading.Thread(target=open_browser, daemon=True).start()
            return True
        except OSError:
            print(f"[HUD Server] Port {port} in use, trying next...")
            port += 1
            
    print("[HUD Server] Failed to bind to any port")
    return False
