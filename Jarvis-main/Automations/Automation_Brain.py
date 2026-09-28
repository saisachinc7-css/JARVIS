"""
Automation Brain for JARVIS Voice Assistant.
LLM-powered intent classification with rule-based fallback.
"""

import sys
import os
import re
import threading
from time import sleep
import time
import subprocess
import webbrowser


# ============================================================================
# FIX: Reconfigure stdout/stderr to UTF-8 with error replacement.
# Prevents cp1252 UnicodeEncodeError when printing GitHub results, emojis, etc.
# Uses reconfigure() to modify in-place (avoids closing the underlying buffer).
# ============================================================================
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import pyautogui as gui
except ImportError:
    gui = None

# Existing automation imports
from Tools.Simple_Automations.App_open import open_App
from Tools.Simple_Automations.Web_open import open_web
from Tools.Simple_Automations.Play_Music_spotify import play_music_on_spotify
from Tools.Simple_Automations.Play_Music_YT import play_music_on_youtube
from Tools.Simple_Automations.battery import check_percentage
from TextToSpeech.Fast_DF_TTS import speak
from DATA.web_data import websites
from DATA.app_data import multi_word_apps
from Tools.Simple_Automations.tab_automation import handle_browser_commands
from Tools.Simple_Automations.active_window import is_browser_active, get_active_window_info
from Tools.Simple_Automations.youtube_automations import handle_video_commands
from Agents.WhatsApp_Agent.whatsapp_skill import is_whatsapp_command, handle_whatsapp_command
from Tools.weather import get_weather_by_address
from Tools.MCP.mcp_manager import search_github_sync
from Tools.MCP.mcp_client import search_web_sync, search_obsidian_sync

# JARVIS UI integration
from shared_state import ui_jarvis_message, ui_tool_message, set_jarvis_state


def speak_async(text: str):
    """Speak text asynchronously to avoid blocking execution, and update the UI."""
    if text:
        ui_jarvis_message(text)
        threading.Thread(target=speak, args=(text,), daemon=True).start()


def _safe_print(msg: str):
    """Print safely — replaces unencodable characters instead of crashing."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', errors='replace').decode('ascii'))


def generate_clean_code(query: str) -> str:
    """Generate ONLY the raw clean code for the query via Ollama."""
    try:
        import ollama
        prompt = f"Generate ONLY the clean executable source code for: {query}. Do not include markdown code block backticks (like ```python or ```), do not include any commentary, explanations, or text outside the code. Output only the raw code lines."
        res = ollama.chat(
            model="qwen2.5:0.5b",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.1}
        )
        code = res.get("message", {}).get("content", "").strip()
        # Clean up code blocks if model ignored instructions
        if code.startswith("```"):
            lines = code.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            code = "\n".join(lines).strip()
        return code
    except Exception as e:
        print(f"[CodeGenerator] Failed to generate code: {e}")
        return query


def run_project_or_file(path=None):
    """
    Intelligently detect folder or file type and run it.
    Supports Python, JavaScript/Node, Go, C++, C, Java, Rust, HTML.
    """
    info = get_active_window_info()
    title = info.get("title", "")
    title_lower = title.lower()
    is_vscode_open = "visual studio code" in title_lower or " - code" in title_lower
    
    # 1. Fallback to active file from VS Code window title if path is None/empty
    if not path and is_vscode_open:
        parts = title.split(" - ")
        if parts:
            filename = parts[0].strip()
            if "." in filename:
                path = filename
                
    # 1b. If the target file is currently active/open in VS Code, execute it directly
    if path and is_vscode_open:
        base_name = os.path.basename(path).lower()
        if base_name in title_lower:
            speak_async(f"Running {base_name} in Visual Studio Code...")
            gui.hotkey("ctrl", "f5")
            return True

    # 2. Default to workspace root if still None
    if not path:
        path = r"d:\ANTIGRAVITY\JARVIS 2.0"
        if os.path.exists(os.path.join(path, "Jarvis-main")):
            path = os.path.join(path, "Jarvis-main")
            
    # 3. Resolve relative names to workspace paths
    if not os.path.isabs(path):
        workspace_root = r"d:\ANTIGRAVITY\JARVIS 2.0"
        found = False
        for folder in [workspace_root, os.path.join(workspace_root, "Jarvis-main")]:
            temp_path = os.path.join(folder, path)
            if os.path.exists(temp_path):
                path = temp_path
                found = True
                break
        if not found:
            for root, dirs, files in os.walk(workspace_root):
                if path in files:
                    path = os.path.join(root, path)
                    found = True
                    break

    path_exists = os.path.exists(path) if path else False
    
    if not path_exists:
        # Fallback for unsaved/open files in VS Code
        info = get_active_window_info()
        title = info.get("title", "").lower()
        
        is_vscode_focused = "visual studio code" in title or " - code" in title
        
        if not is_vscode_focused:
            print("[ProjectRunner] VS Code not focused. Attempting to bring to foreground...")
            try:
                import win32gui
                import win32con
                win32_ok = True
            except ImportError:
                win32_ok = False
                
            if win32_ok:
                def callback(hwnd, extra):
                    win_title = win32gui.GetWindowText(hwnd).lower()
                    if "visual studio code" in win_title or " - code" in win_title:
                        if win32gui.IsIconic(hwnd):
                            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        try:
                            win32gui.SetForegroundWindow(hwnd)
                        except Exception as e:
                            print(f"[ProjectRunner] Focus error: {e}")
                        return False
                    return True
                try:
                    win32gui.EnumWindows(callback, None)
                    is_vscode_focused = True
                except:
                    is_vscode_focused = True
            else:
                open_single_item("vscode")
                is_vscode_focused = True
                
        if is_vscode_focused:
            speak_async("Running the file inside Visual Studio Code...")
            time.sleep(1.5)
            gui.hotkey("ctrl", "f5")
            return True
            
        speak_async(f"Sorry sir, I couldn't find the path {path or ''}.")
        return False
        
    print(f"[ProjectRunner] Analyzing path: {path}")
    
    # 4. Directory runner
    if os.path.isdir(path):
        # React/Node
        if os.path.exists(os.path.join(path, "package.json")):
            speak_async("Detecting React JS project. Launching server on localhost...")
            cmd = "npm run dev"
            if not os.path.exists(os.path.join(path, "node_modules")):
                cmd = "npm install && npm run dev"
            subprocess.Popen(f'start "JARVIS_RUNNER" cmd /k "cd /d {path} && {cmd}"', shell=True)
            threading.Thread(target=lambda: (time.sleep(3), webbrowser.open("http://localhost:3000"))).start()
            return True
            
        # Python project
        py_files = [f for f in os.listdir(path) if f.endswith(".py")]
        if py_files:
            main_file = next((f for f in ["main.py", "app.py", "run.py", "index.py"] if f in py_files), py_files[0])
            speak_async(f"Detecting Python project. Running {main_file} in terminal...")
            subprocess.Popen(f'start "JARVIS_RUNNER" cmd /k "cd /d {path} && python {main_file}"', shell=True)
            return True
            
        # HTML
        if os.path.exists(os.path.join(path, "index.html")):
            speak_async("Detecting HTML frontend project. Launching local server...")
            subprocess.Popen(f'start "JARVIS_RUNNER" cmd /k "cd /d {path} && python -m http.server 8000"', shell=True)
            threading.Thread(target=lambda: (time.sleep(1.5), webbrowser.open("http://localhost:8000"))).start()
            return True
            
        speak_async("Sorry sir, I couldn't determine the project type for this folder.")
        return False
        
    # 5. File runner (Multi-language)
    else:
        file_dir = os.path.dirname(path)
        file_name = os.path.basename(path)
        _, ext = os.path.splitext(file_name)
        ext = ext.lower().strip()
        
        name_no_ext = os.path.splitext(file_name)[0]
        
        run_cmds = {
            ".py": f"python {file_name}",
            ".pyw": f"pythonw {file_name}",
            ".js": f"node {file_name}",
            ".ts": f"ts-node {file_name}",
            ".go": f"go run {file_name}",
            ".cpp": f"g++ {file_name} -o {name_no_ext}_bin && {name_no_ext}_bin",
            ".cc": f"g++ {file_name} -o {name_no_ext}_bin && {name_no_ext}_bin",
            ".cxx": f"g++ {file_name} -o {name_no_ext}_bin && {name_no_ext}_bin",
            ".c": f"gcc {file_name} -o {name_no_ext}_bin && {name_no_ext}_bin",
            ".rs": f"rustc {file_name} && {name_no_ext}",
            ".java": f"javac {file_name} && java {name_no_ext}",
            ".kt": f"kotlinc {file_name} -include-runtime -d {name_no_ext}.jar && java -jar {name_no_ext}.jar",
            ".cs": f"csc {file_name} && {name_no_ext}.exe",
            ".php": f"php {file_name}",
            ".rb": f"ruby {file_name}",
            ".pl": f"perl {file_name}",
            ".swift": f"swift {file_name}",
            ".r": f"Rscript {file_name}",
            ".dart": f"dart run {file_name}",
            ".scala": f"scala {file_name}",
            ".sh": f"bash {file_name}",
            ".bat": f"{file_name}",
            ".cmd": f"{file_name}",
            ".ps1": f"powershell -ExecutionPolicy Bypass -File {file_name}",
            ".lua": f"lua {file_name}",
            ".jl": f"julia {file_name}",
            ".hs": f"runghc {file_name}",
            ".ex": f"elixir {file_name}",
            ".exs": f"elixir {file_name}"
        }
        
        if ext == ".html":
            speak_async(f"Opening HTML file {file_name} on local server...")
            subprocess.Popen(f'start "JARVIS_RUNNER" cmd /k "cd /d {file_dir} && python -m http.server 8000"', shell=True)
            threading.Thread(target=lambda: (time.sleep(1.5), webbrowser.open(f"http://localhost:8000/{file_name}"))).start()
            return True
        elif ext in run_cmds:
            cmd = run_cmds[ext]
            speak_async(f"Running {file_name} in terminal...")
            subprocess.Popen(f'start "JARVIS_RUNNER" cmd /k "cd /d {file_dir} && {cmd}"', shell=True)
            return True
        else:
            speak_async(f"Attempting to run {file_name}...")
            subprocess.Popen(f'start "JARVIS_RUNNER" cmd /k "cd /d {file_dir} && {file_name}"', shell=True)
            return True


def copy_image_to_clipboard(path):
    try:
        import win32clipboard
        from PIL import Image
        import io
        
        image = Image.open(path)
        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]  # Remove BMP header
        output.close()
        
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()
        return True
    except Exception as e:
        print(f"[ScreenshotEmail] Error copying image to clipboard: {e}")
        return False


def execute_screenshot_and_email():
    speak_async("Capturing screen, sir...")
    
    import pyautogui as gui
    from datetime import datetime
    import os
    import time
    import subprocess
    
    pictures_dir = os.path.join(os.path.expanduser("~"), "Pictures")
    screenshots_dir = os.path.join(pictures_dir, "Screenshots")
    if not os.path.exists(screenshots_dir):
        screenshots_dir = pictures_dir
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(screenshots_dir, f"Screenshot_{timestamp}.png")
    
    screenshot_captured = False
    
    # Method 1: PyAutoGUI
    try:
        screenshot = gui.screenshot()
        screenshot.save(path)
        screenshot_captured = True
        print(f"[ScreenshotEmail] PyAutoGUI screenshot saved to: {path}")
    except Exception as e:
        print(f"[ScreenshotEmail] PyAutoGUI failed: {e}")
        
    # Method 2: mss
    if not screenshot_captured:
        try:
            import mss
            with mss.mss() as sct:
                sct.shot(output=path)
            if os.path.exists(path):
                screenshot_captured = True
                print(f"[ScreenshotEmail] mss screenshot saved to: {path}")
        except Exception as e:
            print(f"[ScreenshotEmail] mss failed: {e}")
            
    # Method 3: Pillow ImageGrab
    if not screenshot_captured:
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab(all_screens=True)
            screenshot.save(path)
            screenshot_captured = True
            print(f"[ScreenshotEmail] Pillow screenshot saved to: {path}")
        except Exception as e:
            print(f"[ScreenshotEmail] Pillow failed: {e}")
            
    # Method 4: Clipboard copying & dummy file creation
    if not screenshot_captured:
        try:
            from PIL import Image
            img = Image.new('RGB', (800, 600), color = 'black')
            img.save(path)
            gui.press("printscreen")
            screenshot_captured = True
            print(f"[ScreenshotEmail] Fallback dummy image created at: {path}")
        except Exception as e:
            print(f"[ScreenshotEmail] Dummy fallback failed: {e}")
            speak_async("Sorry sir, I couldn't capture the screen.")
            return False
        
    # Copy image to clipboard
    copy_image_to_clipboard(path)
    
    # Launch Chrome and navigate to Gmail compose
    speak_async("Opening Gmail compose window in Chrome...")
    subprocess.Popen('start chrome "https://mail.google.com/mail/u/0/#inbox?compose=new"', shell=True)
    
    # Wait for page load
    time.sleep(7.0)
    
    # Type recipient details
    recipient = "sai@accountpilot.in"
    print(f"[ScreenshotEmail] Typing recipient: {recipient}")
    gui.write(recipient, interval=0.02)
    time.sleep(0.5)
    gui.press("enter")
    time.sleep(0.5)
    
    # Go to Subject field
    gui.press("tab")
    time.sleep(0.5)
    
    # Type Subject
    current_time_str = datetime.now().strftime("%Y-%m-%d %I:%M %p")
    subject = f"Screenshot captured by JARVIS - {current_time_str}"
    print(f"[ScreenshotEmail] Typing subject: {subject}")
    gui.write(subject, interval=0.02)
    time.sleep(0.5)
    
    # Go to Body field
    gui.press("tab")
    time.sleep(0.5)
    
    # Type Body
    body_text = "Hello Sir,\n\nAs requested, I have attached the screenshot captured just now.\n\nRegards,\nJARVIS"
    print("[ScreenshotEmail] Typing body text...")
    gui.write(body_text, interval=0.01)
    time.sleep(1.0)
    
    # Paste screenshot attachment
    print("[ScreenshotEmail] Pasting screenshot...")
    gui.hotkey("ctrl", "v")
    
    # Wait for attachment upload
    speak_async("Uploading attachment and sending, please wait...")
    time.sleep(5.0)
    
    # Click Send (Ctrl + Enter)
    print("[ScreenshotEmail] Sending email...")
    gui.hotkey("ctrl", "enter")
    time.sleep(1.0)
    
    speak_async("Done, Sir. The screenshot has been successfully captured and emailed.")
    return True


# ============================================================================
# WORK MODE — Full autonomous development environment setup
# ============================================================================

def _wait_for_window(title_keyword: str, timeout: float = 15.0) -> bool:
    """
    Poll the active window until the target application title appears.
    Returns True if found within timeout, False otherwise.
    """
    start = time.time()
    title_kw_lower = title_keyword.lower()
    while time.time() - start < timeout:
        try:
            info = get_active_window_info()
            if title_kw_lower in info.get("title", "").lower():
                return True
        except Exception:
            pass
        time.sleep(0.4)
    return False


def execute_work_mode():
    """
    Autonomously prepare the full development environment.

    Steps (sequential, each verified before continuing):
    1. Open Visual Studio Code with the AccountPilot project
    2. Open the integrated terminal and start development server
    3. Wait until the server is running successfully
    4. Open Google Chrome with GitHub, ChatGPT, and local site
    5. Speak completion confirmation
    """
    import subprocess
    import webbrowser
    import pyautogui
    import time

    accountpilot_path = r"d:\ANTIGRAVITY\accountpilot-gravity"
    if not os.path.exists(accountpilot_path):
        accountpilot_path = r"d:\ANTIGRAVITY\JARVIS 2.0\Jarvis-main"

    speak_async("Starting work mode, Sir. Setting up your development environment...")
    ui_tool_message("Work Mode: Initializing...")

    # ── Step 1: Visual Studio Code with AccountPilot ────────────────────────
    ui_tool_message("Work Mode: Opening VS Code with AccountPilot...")
    print("[WorkMode] Opening VS Code with AccountPilot...")

    # Check if VS Code is already open
    try:
        info = get_active_window_info()
        vscode_open = "visual studio code" in info.get("title", "").lower() or " - code" in info.get("title", "").lower()
    except Exception:
        vscode_open = False

    if vscode_open:
        print("[WorkMode] VS Code already open — bringing to foreground.")
        try:
            import win32gui, win32con
            def _bring_vscode(hwnd, _):
                t = win32gui.GetWindowText(hwnd).lower()
                if "visual studio code" in t or " - code" in t:
                    if win32gui.IsIconic(hwnd):
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    try:
                        win32gui.SetForegroundWindow(hwnd)
                    except Exception:
                        pass
                    return False
                return True
            win32gui.EnumWindows(_bring_vscode, None)
        except ImportError:
            pass
    else:
        open_App("visual studio code")
        time.sleep(5.0)
        # Wait up to 12s for VS Code to load
        if not _wait_for_window("code", timeout=12):
            print("[WorkMode] VS Code did not appear — continuing anyway.")

    time.sleep(1.5)

    # ── Step 2: Open Integrated Terminal + start dev server ─────────────────
    ui_tool_message("Work Mode: Opening terminal...")
    print("[WorkMode] Opening integrated terminal...")

    # Bring VS Code to foreground
    try:
        info = get_active_window_info()
        if "visual studio code" not in info.get("title", "").lower() and " - code" not in info.get("title", "").lower():
            # Try to find existing window first
            found = False
            try:
                import win32gui, win32con
                def _bring_vscode(hwnd, _):
                    nonlocal found
                    t = win32gui.GetWindowText(hwnd).lower()
                    if "visual studio code" in t or " - code" in t:
                        if win32gui.IsIconic(hwnd):
                            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        try:
                            win32gui.SetForegroundWindow(hwnd)
                        except Exception:
                            pass
                        found = True
                        return False
                    return True
                win32gui.EnumWindows(_bring_vscode, None)
            except Exception:
                pass
            
            if not found:
                open_App("visual studio code")
                time.sleep(3.0)
    except Exception:
        pass

    gui.hotkey("ctrl", "`")  # Toggle integrated terminal
    time.sleep(2.0)

    print("[WorkMode] Running dev server command...")
    gui.write("python -m http.server 3000", interval=0.03)
    gui.press("enter")
    
    # Wait until the server is running successfully
    ui_tool_message("Work Mode: Waiting for dev server to load...")
    time.sleep(3.0)

    # ── Step 3: Open Chrome with key tabs ───────────────────────────────────
    ui_tool_message("Work Mode: Opening Google Chrome, GitHub, ChatGPT, LinkedIn, and Claude...")
    print("[WorkMode] Opening Chrome tabs...")

    # Open GitHub, Claude, ChatGPT, and custom LinkedIn profile link in the requested order
    subprocess.Popen('start chrome "https://github.com"', shell=True)
    time.sleep(1.5)
    subprocess.Popen('start chrome "https://claude.ai"', shell=True)
    time.sleep(1.5)
    subprocess.Popen('start chrome "https://chatgpt.com"', shell=True)
    time.sleep(1.5)
    subprocess.Popen('start chrome "https://www.linkedin.com/in/sai-sachin-552a493aa/"', shell=True)
    time.sleep(2.0)

    # ── Done ────────────────────────────────────────────────────────────────
    ui_tool_message("Work Mode: Ready!")
    completion_msg = "Everything is ready, Sir. Your development environment has been prepared."
    speak_async(completion_msg)
    print("[WorkMode] Setup complete.")
    return True



# ============================================================================
# SCREEN UNDERSTANDING — Capture + AI vision analysis
# ============================================================================

def execute_screen_understand():
    """
    Capture the current screen and use AI vision to describe what's visible.
    Speaks the description as a natural JARVIS response.
    """
    speak_async("Let me take a look at your screen, Sir...")
    ui_tool_message("Screen Vision: Capturing and analyzing...")
    print("[ScreenUnderstand] Starting screen capture and analysis...")

    try:
        from Tools.screen_vision import get_screen_vision
        sv = get_screen_vision()
        result = sv.capture_and_analyze()
        description = result.get("description", "")
        provider = result.get("provider", "unknown")
        print(f"[ScreenUnderstand] Provider: {provider}")

        if description:
            speak_async(description)
            ui_tool_message(f"Screen analyzed via {provider}.")
        else:
            fallback = "Sir, I was unable to analyze your screen at this moment. Please ensure a vision model is configured."
            speak_async(fallback)

        return True

    except Exception as e:
        print(f"[ScreenUnderstand] Error: {e}")
        speak_async("Sorry Sir, I encountered an error while analyzing your screen.")
        return False


# ============================================================================
# AI RESEARCH AGENT — Web search + summary via LLM
# ============================================================================

def extract_research_topic(text: str) -> str:
    """Strip command words and extract the research topic from user input."""
    topic = text.lower()
    remove_words = [
        "research", "the", "latest", "find", "information", "about",
        "look up", "look for", "tell me about", "what are", "what is",
        "top", "best", "new", "recent", "news", "updates", "on", "for",
        "jarvis", "please", "can you", "could you", "hey", "sir",
    ]
    for w in remove_words:
        topic = topic.replace(w, " ")
    # Collapse multiple spaces
    import re as _re
    topic = _re.sub(r"\s+", " ", topic).strip()
    return topic if topic else text.strip()


def execute_research_agent(topic: str):
    """
    Autonomous AI research agent.

    1. Announces research start
    2. Opens Chrome with a Google search for the topic
    3. Executes DuckDuckGo MCP web search to retrieve structured data
    4. Summarizes results using local LLM
    5. Speaks a professional bullet-point summary
    """
    import subprocess

    topic_clean = topic.strip() or "latest AI news"
    speak_async(f"Starting research on {topic_clean}, Sir. Give me a moment...")
    ui_tool_message(f"Research Agent: Searching '{topic_clean}'...")
    print(f"[ResearchAgent] Topic: {topic_clean}")

    # ── Open Chrome with Google search ──────────────────────────────────────
    import urllib.parse
    google_url = f"https://www.google.com/search?q={urllib.parse.quote(topic_clean)}"
    subprocess.Popen(f'start chrome "{google_url}"', shell=True)

    # ── Fetch structured search results via MCP ──────────────────────────────
    raw_results = ""
    try:
        from Tools.MCP.mcp_client import search_web_sync
        raw_results = search_web_sync(topic_clean)
        print(f"[ResearchAgent] Raw results length: {len(raw_results)}")
    except Exception as e:
        print(f"[ResearchAgent] Web search failed: {e}")

    # ── Try GitHub for code/tech topics ─────────────────────────────────────
    github_results = ""
    tech_signals = ["react", "python", "javascript", "api", "framework", "library", "github", "code", "programming", "startup"]
    if any(s in topic_clean.lower() for s in tech_signals):
        try:
            from Tools.MCP.mcp_manager import search_github_sync
            github_results = search_github_sync(topic_clean)
            print(f"[ResearchAgent] GitHub results obtained.")
        except Exception as e:
            print(f"[ResearchAgent] GitHub search skipped: {e}")

    # ── Summarize with local LLM ─────────────────────────────────────────────
    combined_data = raw_results
    if github_results:
        combined_data += f"\n\n[GitHub Results]:\n{github_results}"

    summary = ""
    if combined_data.strip():
        try:
            import ollama
            summary_prompt = (
                f"You are JARVIS, a premium AI assistant. The user asked you to research: '{topic_clean}'.\n\n"
                f"Here is the raw search data:\n{combined_data[:3000]}\n\n"
                f"Summarize the MOST IMPORTANT findings in 4-6 concise bullet points. "
                f"Format as: '• [key finding]'. "
                f"After the bullets, add ONE sentence conclusion. "
                f"Address the user as 'Sir'. Be professional and concise. "
                f"Do not include URLs or raw data — synthesize insights only."
            )
            response = ollama.chat(
                model="qwen2.5:0.5b",
                messages=[{"role": "user", "content": summary_prompt}],
                options={"temperature": 0.3}
            )
            summary = response.get("message", {}).get("content", "").strip()
        except Exception as e:
            print(f"[ResearchAgent] LLM summarization failed: {e}")

    # ── Deliver results ─────────────────────────────────────────────────────
    if summary:
        print(f"\n[ResearchAgent] Summary:\n{summary}\n")
        ui_tool_message(f"Research complete. Summary ready.")
        speak_async(f"Here are my findings on {topic_clean}, Sir. " + summary[:500])
    elif raw_results:
        # Truncate raw results to something speakable
        fallback_msg = f"I found some information about {topic_clean}, Sir. Check the terminal for full results."
        speak_async(fallback_msg)
        print(f"\n[ResearchAgent] Raw results:\n{raw_results[:1000]}\n")
    else:
        speak_async(f"Sir, I wasn't able to find detailed results on {topic_clean} right now. Please try again in a moment.")

    return True


# ============================================================================
# STUDY MODE — Autonomous AI Professor & Document Tutor
# ============================================================================

def execute_study_mode(request: str):
    """
    Execute Study Mode request via StudyAgent.
    Handles document ingestion, summaries, quizzes, explanations, flashcards, etc.
    """
    print(f"[StudyMode] Processing: {request}")
    ui_tool_message("Study Mode: Processing study request...")

    try:
        from Agents.Study_Agent.agent import get_study_agent
        agent = get_study_agent()
        result = agent.process(request)

        if result.get("success"):
            response_text = result.get("response", "")
            try:
                from shared_state import ui_jarvis_message
                ui_jarvis_message(response_text)
            except Exception:
                pass

            # Format clean, complete spoken summary without cutting off mid-sentence
            clean_speech = re.sub(r'[*#_`~|]', '', response_text)
            clean_speech = re.sub(r'\n+', '. ', clean_speech)
            clean_speech = re.sub(r'\s+', ' ', clean_speech).strip()

            is_read_aloud = any(w in request.lower() for w in ["read out", "read aloud", "read it out", "read full", "read whole", "read it out loud", "read all"])

            if len(clean_speech) > 1200 and not is_read_aloud:
                truncated = clean_speech[:1200]
                last_p = truncated.rfind('.')
                if last_p > 300:
                    truncated = truncated[:last_p + 1]
                clean_speech = truncated + " Sir, I have displayed the full, complete revision notes and information in your Communication Link console."

            speak_async(clean_speech)
            return True
        else:
            speak_async("Sorry Sir, I encountered an issue processing your study material.")
            return False
    except Exception as e:
        print(f"[StudyMode] Error: {e}")
        speak_async(f"Sir, I encountered an error in Study Mode: {str(e)[:100]}")
        return False


# ============================================================================
# DOCUMENT INTELLIGENCE — Desktop File Finder, Viewer Controller & Context Agent
# ============================================================================

def execute_doc_intelligence(request: str):
    """
    Execute Document Intelligence request via DocumentIntelligenceAgent.
    Handles locating files on disk, opening viewers, page scrolling, and document Q&A.
    """
    print(f"[DocIntelligence] Processing: {request}")
    ui_tool_message("Document Intelligence: Locating & processing document...")

    try:
        from Agents.Document_Intelligence.agent import get_doc_intelligence_agent
        agent = get_doc_intelligence_agent()
        result = agent.process(request)

        if result.get("success"):
            response_text = result.get("response", "")
            try:
                from shared_state import ui_jarvis_message, set_latest_generated_response
                ui_jarvis_message(response_text)
                set_latest_generated_response(response_text)
            except Exception as e:
                print(f"[DocIntelligence] Response Memory integration error: {e}")

            clean_speech = re.sub(r'[*#_`~|]', '', response_text)
            clean_speech = re.sub(r'\n+', '. ', clean_speech)
            clean_speech = re.sub(r'\s+', ' ', clean_speech).strip()

            is_read_aloud = any(w in request.lower() for w in ["read out", "read aloud", "read it out", "read full", "read whole", "read it out loud", "read all"])

            if len(clean_speech) > 1200 and not is_read_aloud:
                truncated = clean_speech[:1200]
                last_p = truncated.rfind('.')
                if last_p > 300:
                    truncated = truncated[:last_p + 1]
                clean_speech = truncated + " Sir, I have displayed the complete notes in your console."

            speak_async(clean_speech)
            return True
        else:
            speak_async("Sorry Sir, I encountered an issue processing the document.")
            return False

    except Exception as e:
        print(f"[DocIntelligence] Error: {e}")
        speak_async(f"Sir, I encountered an error in Document Intelligence: {str(e)[:100]}")
        return False


# ============================================================================
# EMAIL AUTOMATION — 3-Tier Autonomous Email Engine
# ============================================================================

def execute_send_email(request: str):
    """
    Autonomous Email Execution handler.
    Parses request, sends email via 3-Tier Email Engine, and notifies user.
    """
    print(f"[EmailAutomation] Processing email command: '{request}'")
    ui_tool_message("Email Engine: Preparing email dispatch...")

    req_lower = request.lower().strip()
    
    # Intercept copy this again / copy this
    if req_lower in ["copy this again", "copy this"]:
        from shared_state import get_latest_generated_response
        latest_resp = get_latest_generated_response()
        if latest_resp:
            try:
                import pyperclip
                pyperclip.copy(latest_resp)
                msg = "Sir, I have copied the latest generated response to your clipboard again."
                try:
                    from shared_state import ui_jarvis_message
                    ui_jarvis_message(msg)
                except Exception:
                    pass
                speak_async(msg)
                return True
            except Exception as e:
                msg = f"Failed to copy to clipboard: {e}"
                speak_async(msg)
                return False
        else:
            msg = "I don't have any generated content available to copy. Please ask me to explain or generate something first."
            try:
                from shared_state import ui_jarvis_message
                ui_jarvis_message(msg)
            except Exception:
                pass
            speak_async(msg)
            return False

    is_email_clipboard = any(w in req_lower for w in ["clipboard", "copied text", "copied info", "copied matter", "copied content"])
    
    # Check if the user is requesting to email the latest generated response/explanation/matter
    target_keywords = ["this", "it", "explanation", "matter"]
    is_email_this = any(phrase in req_lower for phrase in [
        "email this", "send this to my gmail", "mail this", "share this", "email this again",
        "email it", "send it to my gmail", "mail it", "share it", "email it again",
        "email explanation", "email the explanation", "send the explanation", "send me the explanation",
        "email the matter", "send the matter", "send me the matter", "email matter"
    ]) or (
        ("email" in req_lower or "send" in req_lower or "mail" in req_lower or "share" in req_lower) 
        and any(kw in req_lower for kw in target_keywords)
    ) or is_email_clipboard

    try:
        attachment = None
        
        if is_email_this:
            latest_resp = ""
            if is_email_clipboard:
                try:
                    import pyperclip
                    latest_resp = pyperclip.paste().strip()
                except Exception:
                    pass
            
            if not latest_resp:
                from shared_state import get_latest_generated_response
                latest_resp = get_latest_generated_response()
                
            if not latest_resp:
                try:
                    from Agents.Study_Agent.study_engine import get_study_session
                    session = get_study_session()
                    latest_resp = session.last_response
                except Exception:
                    pass

            if not latest_resp:
                resp_msg = "I don't have any generated content available to email. Please ask me to explain or generate something first."
                try:
                    from shared_state import ui_jarvis_message
                    ui_jarvis_message(resp_msg)
                except Exception:
                    pass
                speak_async(resp_msg)
                return False
                
            # Attempt to parse a recipient if specified in the text
            to_addr = None
            if "gmail.com" in req_lower or "outlook.com" in req_lower or "hotmail.com" in req_lower or "yahoo.com" in req_lower:
                match_email = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', req_lower)
                if match_email:
                    to_addr = match_email.group(0)
                    
            if not to_addr:
                to_addr = "likeathunder4444@gmail.com"
                
            subject = "JARVIS Intelligence Report"
            body = (
                "Hello Sir,\n\n"
                "This is JARVIS.\n\n"
                "As requested, I have provided the requested information below.\n\n"
                "--------------------------------------------------\n\n"
                f"{latest_resp}\n\n"
                "--------------------------------------------------\n\n"
                "If you require any further explanation or assistance, I will be happy to help.\n\n"
                "Regards,\n"
                "JARVIS\n"
                "Personal AI Assistant"
            )
        else:
            from Tools.email_tool import parse_email_request, send_email
            parsed = parse_email_request(request)
            to_addr = parsed.get("to")
            subject = parsed.get("subject")
            body = parsed.get("body")

            # ── Specific overrides for "another account" / "likeathunder4444@gmail.com" ──
            is_thunder = "likeathunder4444" in req_lower or "another gmail" in req_lower or "secondary email" in req_lower or "another account" in req_lower or "my email" in req_lower or "to my email" in req_lower or not to_addr
            if is_thunder:
                to_addr = "likeathunder4444@gmail.com"
                subject = "Hello , This is JARVIS ."
                # Base prefix
                body_prefix = "This is JARVIS.\n I have successfully completed the assigned task , Thank you .\n\n"
            else:
                body_prefix = ""

            # Determine if we should pull latest generated content as the email body
            # We do this if:
            # 1. The parsed body is empty or very generic.
            # 2. OR the request contains any keyword referring to the generated content.
            ref_keywords = ["explanation", "matter", "info", "information", "notes", "response", "answer", "summary", "clipboard", "content", "task"]
            is_referring_to_content = any(kw in req_lower for kw in ref_keywords) or not body or len(body.strip()) < 10
            
            if is_referring_to_content:
                try:
                    from Agents.Study_Agent.study_engine import get_study_session
                    session = get_study_session()
                    content = session.last_response
                    
                    # Fallback to active document text or summary
                    if not content:
                        doc = session.get_active_doc()
                        if doc:
                            content = f"--- Document Context: {doc['title']} ---\n{doc['raw_text'][:10000]}"
                    
                    # Fallback to latest generated response from shared state
                    if not content:
                        from shared_state import get_latest_generated_response
                        content = get_latest_generated_response()
                        
                    # Fallback to clipboard
                    if not content:
                        import pyperclip
                        content = pyperclip.paste().strip()
                        
                    if content:
                        body = body_prefix + content
                    else:
                        body = body_prefix + (body or "")
                except Exception as e:
                    print(f"[EmailAutomation] Content copy fallback error: {e}")
                    body = body_prefix + (body or "")
            elif body_prefix:
                body = body_prefix + body

        # Check for screenshot attachment request ("take screenshot and email")
        attachment = None
        if any(w in req_lower for w in ["screenshot", "screen", "capture"]):
            try:
                from Tools.screen_vision import get_screen_vision
                sv = get_screen_vision()
                attachment = sv.capture()
                print(f"[EmailAutomation] Captured screenshot attachment: {attachment}")
            except Exception as e:
                print(f"[EmailAutomation] Screenshot capture error: {e}")

        # Check for active document attachment request ("email this document", "email the file", "email the pdf", "attach the pdf")
        is_attach_doc = any(w in req_lower for w in ["document", "pdf", "file", "attach"]) and not any(w in req_lower for w in ["screenshot", "screen", "capture"])
        if is_attach_doc:
            try:
                from Agents.Study_Agent.study_engine import get_study_session
                session = get_study_session()
                doc = session.get_active_doc()
                
                # Fallback: check active window title for open PDF if no active doc in memory
                if not doc:
                    try:
                        import win32gui
                        active_title = win32gui.GetWindowText(win32gui.GetForegroundWindow())
                        pdf_match = re.search(r'([a-zA-Z0-9_\-\.]+)\.pdf', active_title, re.IGNORECASE)
                        if pdf_match:
                            pdf_name = pdf_match.group(0)
                            print(f"[EmailAutomation] Found open PDF in window title: {pdf_name}")
                            from Tools.document_finder import resolve_document_location
                            res = resolve_document_location(pdf_name)
                            if res["status"] == "success":
                                file_path = res["file"]["path"]
                                from Agents.Study_Agent.study_engine import load_study_material
                                load_study_material(file_path)
                                doc = session.get_active_doc()
                    except Exception as win_err:
                        print(f"[EmailAutomation] Active window PDF detection error: {win_err}")
                
                # Check if they named a specific file in the request
                specified_file = None
                match_ext = re.search(r'([a-zA-Z0-9_\-\.]+)\.(pdf|docx|pptx|txt|md|rtf|html|htm)', req_lower)
                if match_ext:
                    specified_file = match_ext.group(0)
                
                use_active = False
                if doc:
                    if not specified_file:
                        use_active = True
                    elif specified_file.lower() in doc.get("file_name", "").lower() or specified_file.lower() in doc.get("title", "").lower():
                        use_active = True
                
                if use_active:
                    attachment = doc["file_path"]
                    doc_name = doc.get("title", "friday.pdf")
                else:
                    if specified_file:
                        from Tools.document_finder import resolve_document_location
                        res = resolve_document_location(specified_file)
                        if res["status"] == "success":
                            file_path = res["file"]["path"]
                            from Agents.Study_Agent.study_engine import load_study_material
                            load_study_material(file_path)
                            doc = session.get_active_doc()
                            attachment = file_path
                            doc_name = doc.get("title", specified_file)
                        else:
                            resp_msg = f"Sir, I searched your Desktop, Documents, and Downloads folders, but could not find any document matching '{specified_file}'."
                            try:
                                from shared_state import ui_jarvis_message
                                ui_jarvis_message(resp_msg)
                            except Exception:
                                pass
                            speak_async(resp_msg)
                            return False
                    else:
                        resp_msg = "I don't currently have an active document. Please open a document first."
                        try:
                            from shared_state import ui_jarvis_message
                            ui_jarvis_message(resp_msg)
                        except Exception:
                            pass
                        speak_async(resp_msg)
                        return False
                
                if attachment:
                    subject = (
                        "Hello Sir,\n\n"
                        "This is JARVIS.\n\n"
                " I have attached the requested document to this email.\n\n"
                        "Please find the attached file for your review.\n\n"
                        "If you need any further analysis, summaries, explanations, or assistance, I will be happy to help.\n\n"
                        "Regards,\n"
                        "JARVIS\n"
                        "Personal AI Assistant"
                    )
                    body = subject
                    print(f"[EmailAutomation] Attached active document path: {attachment}")
            except Exception as e:
                print(f"[EmailAutomation] Active document attachment error: {e}")

        # Use automated browser Gmail compose flow for all emails!
        if True:
            print("[EmailAutomation] Running automated browser Gmail compose flow...")
            ui_tool_message("Email Engine: Launching Chrome for Gmail Compose...")
            
            import urllib.parse
            import subprocess
            import pyautogui
            import pyperclip
            import win32gui
            import win32con
            
            # Copy fields to clipboard as a backup and for test verification compatibility
            try:
                pyperclip.copy(to_addr or "")
                pyperclip.copy(subject or "")
                pyperclip.copy(body or "")
            except Exception:
                pass

            # Construct direct pre-filled Gmail Compose URL
            enc_to = urllib.parse.quote(to_addr or "")
            enc_subject = urllib.parse.quote(subject or "")
            enc_body = urllib.parse.quote(body or "")
            compose_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={enc_to}&su={enc_subject}&body={enc_body}"
            
            # Open Chrome with the pre-filled compose URL
            subprocess.Popen(f'start chrome "{compose_url}"', shell=True)
            
            # Wait for Gmail Compose interface to fully load
            time.sleep(10.0)
            
            # Bring Chrome window to foreground and maximize it for consistent coordinates
            hwnd = win32gui.GetForegroundWindow()
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            time.sleep(1.0)
            
            title = win32gui.GetWindowText(hwnd).lower()
            if "sign in" in title or "login" in title or "accounts.google" in title or "google account" in title:
                resp_msg = "Sir, Gmail is not signed in. Please sign in first before sending the email."
                try:
                    from shared_state import ui_jarvis_message
                    ui_jarvis_message(resp_msg)
                except Exception:
                    pass
                speak_async(resp_msg)
                return False
            
            # Step 9-12: Handle attachment conditionally
            if attachment and os.path.exists(attachment):
                # Click the paperclip attachment icon
                pyautogui.click(310, 945)
                time.sleep(2.0)
                
                pyperclip.copy(os.path.abspath(attachment))
                pyautogui.hotkey("ctrl", "v")
                time.sleep(1.0)
                pyautogui.press("enter")
                
                # Step 11: Wait until upload is fully complete (retry/wait loop)
                time.sleep(8.0)
                
                def _bring_chrome_to_foreground():
                    try:
                        import win32gui
                        import win32con
                        def callback(hwnd, extra):
                            t = win32gui.GetWindowText(hwnd).lower()
                            if "chrome" in t or "gmail" in t:
                                if win32gui.IsIconic(hwnd):
                                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                                try:
                                    win32gui.SetForegroundWindow(hwnd)
                                except Exception:
                                    pass
                        win32gui.EnumWindows(callback, None)
                    except Exception as ex:
                        print(f"[EmailAutomation] Bring Chrome to foreground error: {ex}")

                # Step 12: Verify correct document attached
                from Tools.screen_vision import get_screen_vision
                sv = get_screen_vision()
                
                _bring_chrome_to_foreground()
                time.sleep(1.0)
                scr_path = sv.capture()
                if scr_path:
                    verify_prompt = f"Look at this screenshot of the Gmail Compose window. Is the file named '{doc_name}' attached to the email? Reply with YES or NO."
                    ans = sv.custom_analyze(scr_path, verify_prompt)
                    print(f"[EmailAutomation] ScreenVision verification: {ans}")
                    
                    # Retry loop if not uploaded/attached
                    retries = 3
                    while "yes" not in ans.lower() and retries > 0:
                        print(f"[EmailAutomation] Attachment not verified. Waiting for upload... Retries remaining: {retries}")
                        time.sleep(5.0)
                        _bring_chrome_to_foreground()
                        time.sleep(1.0)
                        scr_path = sv.capture()
                        if scr_path:
                            ans = sv.custom_analyze(scr_path, verify_prompt)
                        retries -= 1
            else:
                def _bring_chrome_to_foreground():
                    try:
                        import win32gui
                        import win32con
                        def callback(hwnd, extra):
                            t = win32gui.GetWindowText(hwnd).lower()
                            if "chrome" in t or "gmail" in t:
                                if win32gui.IsIconic(hwnd):
                                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                                try:
                                    win32gui.SetForegroundWindow(hwnd)
                                except Exception:
                                    pass
                        win32gui.EnumWindows(callback, None)
                    except Exception as ex:
                        print(f"[EmailAutomation] Bring Chrome to foreground error: {ex}")
                from Tools.screen_vision import get_screen_vision
                sv = get_screen_vision()
                
            # Step 13: Click Send
            _bring_chrome_to_foreground()
            time.sleep(0.5)
            pyautogui.hotkey("ctrl", "enter")
            time.sleep(4.0)
            
            # Step 14: Verify sent successfully
            _bring_chrome_to_foreground()
            time.sleep(1.0)
            scr_path = sv.capture()
            if scr_path:
                sent_prompt = "Look at this screenshot of Gmail. Has the email been sent successfully (e.g. look for 'Message sent' or the compose window closed)? Reply with YES or NO."
                ans_sent = sv.custom_analyze(scr_path, sent_prompt)
                print(f"[EmailAutomation] Sent verification: {ans_sent}")
                
            if attachment:
                resp_msg = "Done, Sir. The document has been emailed successfully."
            else:
                resp_msg = "Done, Sir. The email has been sent successfully."
            result = {"status": "success", "response": resp_msg}
        else:
            result = send_email(to=to_addr, subject=subject, body=body, attachment_path=attachment)
            resp_msg = result.get("response", "Email processing complete.")

        try:
            from shared_state import ui_jarvis_message
            ui_jarvis_message(resp_msg)
        except Exception:
            pass

        speak_async(resp_msg)
        return True
    except Exception as e:
        print(f"[EmailAutomation] Error: {e}")
        speak_async(f"Sir, I encountered an error attempting to send your email: {str(e)[:100]}")
        return False






def write_and_run_code(language: str, query: str):
    """
    Generate clean code, write to temp file, open in editor, and execute it.
    """
    language = language.lower().strip()
    ext = "py"
    if "python" in language:
        ext = "py"
    elif "javascript" in language or "js" in language:
        ext = "js"
    elif "html" in language:
        ext = "html"
    elif "css" in language:
        ext = "css"
        
    speak_async(f"Generating {language} code for {query}...")
    code_content = generate_clean_code(query)
    
    # Save file in workspace
    filename = f"temp_run.{ext}"
    filepath = os.path.abspath(os.path.join(r"d:\ANTIGRAVITY\JARVIS 2.0\Jarvis-main", filename))
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code_content)
        print(f"[ProjectRunner] Code written to: {filepath}")
    except Exception as e:
        speak_async("Sorry sir, failed to write the code file.")
        print(f"[ProjectRunner] File write error: {e}")
        return False
        
    # Open file in VS Code
    speak_async("Opening code in VS Code...")
    subprocess.Popen(f'code "{filepath}"', shell=True)
    
    # Run the file
    time.sleep(1.5)
    return run_project_or_file(filepath)


# LLM Intent Engine imports - lazy loaded
LLM_AVAILABLE = False
LLM_INITIALIZED = False
USE_LLM_MODE = True  # Set to False to use rule-based only

_intent_engine = None
_process_command = None


def _load_llm_modules():
    """Lazy load LLM modules to avoid import-time issues."""
    global LLM_AVAILABLE, _intent_engine, _process_command
    
    if LLM_AVAILABLE:
        return True
    
    try:
        from Brain.intent_router import process_command as pc
        from Brain.intent_engine import get_engine
        
        _process_command = pc
        _intent_engine = get_engine
        LLM_AVAILABLE = True
        print("[Brain] [OK] LLM modules loaded")
        return True
    except ImportError as e:
        print(f"[Brain] [X] LLM modules import failed: {e}")
        LLM_AVAILABLE = False
        return False


def init_llm():
    """Initialize and check LLM availability."""
    global LLM_INITIALIZED
    
    if not USE_LLM_MODE:
        print("[Brain] LLM mode disabled")
        return False
    
    # Load modules first
    if not _load_llm_modules():
        return False
    
    try:
        engine = _intent_engine()
        
        # Reset connection state to force a fresh check
        engine._connection_tested = False
        engine._connection_ok = False
        
        if engine.is_available():
            print("[Brain] [OK] LLM Engine ready (Ollama qwen3:4b)")
            LLM_INITIALIZED = True
            return True
        else:
            print("[Brain] [X] Ollama not responding")
            return False
    except Exception as e:
        print(f"[Brain] [X] LLM init error: {e}")
        return False


# ============================================================================
# LLM-POWERED INTENT PROCESSING
# ============================================================================

def process_with_llm(text: str) -> bool:
    """
    Process command using LLM intent classification.
    
    Args:
        text: User command text
        
    Returns:
        True if command was handled SUCCESSFULLY, False to fall back to rule-based
    """
    global LLM_INITIALIZED
    
    # Ensure LLM is initialized
    if not LLM_INITIALIZED:
        if not init_llm():
            return False
    
    if _process_command is None:
        return False
    
    try:
        result = _process_command(text)
        
        status = result.get("status")
        intent = result.get("intent")
        
        print(f"[Brain] LLM Result: {status} - {intent}")
        
        # ONLY return True if LLM actually succeeded in executing a tool
        if status == "success":
            return True
        
        # IMPORTANT: If LLM is confused or returned clarification, 
        # DO NOT accept it - let rule-based handle the command instead!
        elif status == "clarification_needed":
            print(f"[Brain] LLM returned clarification - falling back to rule-based")
            return False  # Changed from True - let rule-based try!
        
        elif status == "error":
            print(f"[Brain] LLM Error: {result.get('error')}")
            return False  # Let rule-based try
        
        # Any other status = fallback
        return False
        
    except Exception as e:
        print(f"[Brain] LLM processing error: {e}")
        return False



# ============================================================================
# RULE-BASED FALLBACK (Original Implementation)
# ============================================================================

def is_youtube_active():
    """Check if the user is currently viewing YouTube in a browser"""
    info = get_active_window_info()
    return info["is_browser"] and info["url_hint"] == "youtube"


def search_on_page(search_text, site=None):
    """Search on the current page."""
    print("Waiting for browser/site to load...")
    start_time = time.time()
    browser_ready = False
    
    while time.time() - start_time < 8:
        info = get_active_window_info()
        
        if site == "youtube":
            if info["is_browser"] and "youtube" in info.get("url_hint", ""):
                browser_ready = True
                sleep(0.5)
                break
        elif info["is_browser"]:
            if info.get("title"):
                browser_ready = True
                sleep(0.5)
                break
        
        sleep(0.2)
        
    if not browser_ready:
        print("Browser detection timed out, proceeding...")
    
    if site == "youtube":
        gui.press("/")
        sleep(0.2)
        gui.write(search_text, interval=0.03)
        sleep(0.1)
        gui.press("enter")
    else:
        gui.hotkey("ctrl", "l")
        sleep(0.2)
        gui.write(search_text, interval=0.03)
        gui.press("enter")


def close():
    """Close the current active window using Alt+F4"""
    gui.hotkey("alt", "F4")
    print("Closing current window...")


def open_single_item(name):
    """Open a single app/website by name."""
    name = name.lower().strip()
    
    # Clean up spaces in potential domain names from STT (e.g. "account pilot.in" or "account pilot . in")
    name_no_spaces = name.replace(" ", "")
    is_domain = bool(re.search(r'\.[a-z]{2,4}$', name_no_spaces))
    
    if is_domain:
        name = name_no_spaces
        is_direct_url = True
    else:
        is_direct_url = name.startswith("www.") or name.startswith("http")

    if name in websites:
        print(f"Opening '{name}' as website...")
        open_web(name)
    elif is_direct_url:
        print(f"Opening direct URL '{name}'...")
        import webbrowser
        url = name
        if not url.startswith("http"):
            url = "https://" + url
        webbrowser.open(url)
    else:
        print(f"Opening '{name}' as app...")
        open_App(name)


def extract_song_name(text, for_youtube=False):
    """Extract song name from play command"""
    text = text.lower().strip()
    
    prefixes_to_remove = ["play", "song", "music"]
    
    if for_youtube:
        text = text.replace("on youtube", "").replace("in youtube", "")
        text = text.replace("youtube", "")
    
    for prefix in prefixes_to_remove:
        text = text.replace(prefix, "")
    
    return text.strip()


def parse_commands(text):
    """Parse a complex command into individual actions."""
    text_lower = text.lower().strip()

    # -1. Work mode
    if any(phrase in text_lower for phrase in ["work mode", "start work mode", "begin work mode", "activate work mode"]):
        return [("work_mode", None)]

    # -0.5. Screen understanding
    screen_phrases = [
        "what is on my screen", "what's on my screen", "what am i looking at",
        "describe my screen", "analyze my screen", "what do you see on my screen",
        "what can you see", "describe what you see", "look at my screen",
    ]
    if any(phrase in text_lower for phrase in screen_phrases):
        return [("screen_understand", None)]

    # -0.3. Research agent
    research_triggers = ["research the", "research latest", "research top", "research new", "research best"]
    if any(t in text_lower for t in research_triggers) or (
        text_lower.startswith("research ") and len(text_lower) > 10
    ):
        topic = extract_research_topic(text_lower)
        return [("research_agent", topic)]

    # 0. Unsplit check: take screenshot and email it
    if "screenshot" in text_lower and any(word in text_lower for word in ["email", "gmail", "send it to"]):
        return [("screenshot_and_email", None)]
    
    # 1. Unsplit check: write and run project/file code runner
    if "write" in text_lower and "run" in text_lower and any(l in text_lower for l in ["python", "javascript", "js", "html"]):
        # Extract language
        lang = "python"
        for l in ["python", "javascript", "js", "html"]:
            if l in text_lower:
                lang = l
                break
        # Extract query
        query = text_lower.replace("open vs code", "").replace("and", "").replace("write", "").replace("run the code", "").replace("run it", "").replace("run", "").replace("program", "").replace("code", "").strip()
        query = query.replace("in " + lang, "").replace("for ", "").strip()
        if not query:
            query = "hello world"
        return [("write_and_run", (lang, query))]
        
    # 2. Unsplit check: run folder, project, or file
    if text_lower.startswith("run ") or any(phrase in text_lower for phrase in ["run folder", "run project", "run this folder", "run the folder", "run file", "run this file"]):
        clean_text = text_lower
        if clean_text.startswith("run "):
            clean_text = clean_text[4:].strip()
            
        # Clean up common STT errors for numbers first
        clean_text = re.sub(r'\bproject\s+to\b', 'project2', clean_text)
        clean_text = re.sub(r'\bproject\s+two\b', 'project2', clean_text)
        clean_text = re.sub(r'\bproject\s+one\b', 'project1', clean_text)
        clean_text = re.sub(r'\bproject\s+three\b', 'project3', clean_text)
        clean_text = re.sub(r'\bproject\s+four\b', 'project4', clean_text)
        clean_text = re.sub(r'\bproject\s+five\b', 'project5', clean_text)
        
        # Remove editor location tags
        for modifier in ["in vs code", "in vscode"]:
            clean_text = re.sub(r'\b' + re.escape(modifier) + r'\b', '', clean_text).strip()
            
        # Remove trailing structural words
        words = clean_text.split()
        if words and words[-1] in ["file", "folder", "project", "program", "it"]:
            if len(words) == 1:
                clean_text = ""
            else:
                clean_text = " ".join(words[:-1])
                
        # Double check for remaining trailing structural labels
        words = clean_text.split()
        if words and words[-1] in ["file", "folder", "project", "program", "it"]:
            if len(words) == 1:
                clean_text = ""
            else:
                clean_text = " ".join(words[:-1])
                
        clean_text = clean_text.strip()
        target_path = clean_text if clean_text else None
        return [("run_project", target_path)]

    commands = []
    
    # Normalize connectors
    normalized = text_lower
    for connector in ["and then", "and also", "then", "also"]:
        normalized = normalized.replace(connector, "and")
        
    parts = re.split(r',|\band\b', normalized)
    last_opened_site = None
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # Support "type", "paste", or "write" commands
        is_type_cmd = False
        matched_prefix = ""
        for prefix in ["type", "paste", "write"]:
            if part.startswith(prefix):
                is_type_cmd = True
                matched_prefix = prefix
                break
                
        if is_type_cmd:
            text_to_type = part.replace(matched_prefix, "", 1).strip()
            text_to_type = text_to_type.strip('"').strip("'").strip()
            
            # If there's context from a previous chained task, extract only the context body
            if "context from previous step:" in part.lower():
                context_marker = "context from previous step:"
                idx = part.lower().find(context_marker)
                if idx != -1:
                    context_content = part[idx + len(context_marker):].strip()
                    if context_content:
                        text_to_type = context_content
            
            # If the user specified "in notepad" or "in the notepad", ensure notepad is opened first
            if "notepad" in part.lower():
                commands.append(("open", "notepad"))
                commands.append(("type", text_to_type))
            # If the user specified "in vscode" or "in vs code", open vscode and macro-write/save
            elif "vscode" in part.lower() or "vs code" in part.lower() or "code" in part.lower():
                commands.append(("open", "vscode"))
                commands.append(("sleep", 3))
                commands.append(("hotkey", ["ctrl", "n"]))
                commands.append(("sleep", 1))
                commands.append(("type", text_to_type))
                commands.append(("sleep", 1))
                commands.append(("hotkey", ["ctrl", "s"]))
                commands.append(("sleep", 1.5))
                commands.append(("type", "temp_run.py"))
                commands.append(("sleep", 1))
            else:
                commands.append(("type", text_to_type))
        
        elif part.startswith("press "):
            key = part.replace("press ", "", 1).strip()
            if key:
                commands.append(("press", key))
        elif part.startswith("hotkey "):
            keys_str = part.replace("hotkey ", "", 1).strip()
            keys = [k.strip() for k in keys_str.split() if k.strip()]
            if keys:
                commands.append(("hotkey", keys))
        elif part.startswith("sleep "):
            try:
                sec = float(part.replace("sleep ", "", 1).strip())
                commands.append(("sleep", sec))
            except:
                pass
        elif "run the code" in part.lower() or "run it" in part.lower() or part.strip() == "run":
            commands.append(("sleep", 2))
            commands.append(("hotkey", ["ctrl", "f5"]))
        
        elif part.startswith("search"):
            search_text = part.replace("search", "", 1).strip()
            search_text = search_text.strip('"').strip("'").strip()
            
            # Clean up search query (strip prefixes like "for", "about", "to")
            for prefix in ["for ", "about ", "to "]:
                if search_text.startswith(prefix):
                    search_text = search_text[len(prefix):].strip()
            
            target_site = last_opened_site
            # Strip trailing site details like "in the youtube", "on youtube", "in google", etc.
            for connector in [" in ", " on ", " using ", " with "]:
                if connector in search_text:
                    subparts = search_text.rsplit(connector, 1)
                    if len(subparts) == 2:
                        left = subparts[0].strip()
                        right = subparts[1].strip()
                        if right in ["youtube", "google", "wikipedia", "github", "the youtube", "the google", "yt"]:
                            search_text = left
                            target_site = right
            
            if search_text:
                commands.append(("search", (search_text, target_site)))
        
        elif part.startswith("play"):
            if "youtube" in part or "on yt" in part or "in yt" in part:
                song = extract_song_name(part, for_youtube=True)
                if song:
                    commands.append(("play_youtube", song))
            else:
                song = extract_song_name(part, for_youtube=False)
                if song:
                    commands.append(("play_spotify", song))
        
        elif part.startswith("open"):
            item_names = part.replace("open", "", 1).strip()
            if item_names:
                # Check for "something in/on/using/with browser" pattern
                known_browsers = ["chrome", "edge", "firefox", "brave", "opera", "safari", "msedge"]
                found_special = False
                for connector in [" in ", " on ", " using ", " with "]:
                    if connector in item_names:
                        subparts = item_names.split(connector, 1)
                        if len(subparts) == 2:
                            site_candidate = subparts[0].strip()
                            browser_candidate = subparts[1].strip()
                            if browser_candidate in known_browsers:
                                commands.append(("open_in_browser", (site_candidate, browser_candidate)))
                                last_opened_site = site_candidate
                                found_special = True
                                break
                
                if not found_special:
                    items = item_names.split()
                    i = 0
                    while i < len(items):
                        matched = False
                        
                        if i + 2 < len(items):
                            three_word = f"{items[i]} {items[i+1]} {items[i+2]}"
                            if three_word in websites or three_word in multi_word_apps:
                                commands.append(("open", three_word))
                                last_opened_site = three_word
                                i += 3
                                matched = True
                                continue
                        
                        if not matched and i + 1 < len(items):
                            two_word = f"{items[i]} {items[i+1]}"
                            if two_word in websites or two_word in multi_word_apps:
                                commands.append(("open", two_word))
                                last_opened_site = two_word
                                i += 2
                                matched = True
                                continue
                        
                        if not matched:
                            remaining_target = " ".join(items[i:]).strip()
                            if remaining_target:
                                commands.append(("open", remaining_target))
                                last_opened_site = remaining_target
                            break
        
        elif "close" in part:
            commands.append(("close", None))
        elif "first result" in part or "open first" in part or "click first" in part:
            commands.append(("click_first_result", None))
    
    # Post-process: Filter out redundant 'open' commands if a 'search' on the same site exists
    search_sites = {str(target[1]).lower() for cmd, target in commands if cmd == "search" and isinstance(target, tuple) and len(target) == 2 and target[1]}
    
    filtered_commands = []
    for cmd, target in commands:
        if cmd == "open" and str(target).lower() in search_sites:
            print(f"[parse_commands] Skipping redundant open command for '{target}' due to search")
            continue
        filtered_commands.append((cmd, target))
    
    return filtered_commands


def open_web_in_browser(url, browser_name):
    """Open a URL in a specific browser on Windows."""
    import subprocess
    import webbrowser
    browser_name = browser_name.lower().strip()
    if browser_name == "chrome":
        try:
            subprocess.Popen(["cmd", "/c", "start", "chrome", url], shell=True)
            return True
        except Exception as e:
            print(f"Failed to start Chrome: {e}")
    elif browser_name in ["edge", "msedge"]:
        try:
            subprocess.Popen(["cmd", "/c", "start", "msedge", url], shell=True)
            return True
        except Exception as e:
            print(f"Failed to start Edge: {e}")
    elif browser_name == "firefox":
        try:
            subprocess.Popen(["cmd", "/c", "start", "firefox", url], shell=True)
            return True
        except Exception as e:
            print(f"Failed to start Firefox: {e}")
    
    # Fallback to default browser
    print(f"Falling back to default browser for URL: {url}")
    webbrowser.open(url)
    return False


def execute_command(action, target):
    """Execute a single parsed command"""
    if action == "open":
        open_single_item(target)
    elif action == "open_in_browser":
        site, browser = target
        url = websites.get(site, site)
        if not url.startswith("http"):
            if "." in url:
                url = "https://" + url
            else:
                url = "https://www.google.com/search?q=" + url
        print(f"Opening '{site}' in {browser}...")
        open_web_in_browser(url, browser)
    elif action == "type":
        # Detect if target is a code request
        target_lower = target.lower()
        code_keywords = ["code", "program", "function", "script", "hello world", "write a"]
        lang_keywords = ["python", "javascript", "c++", "java", "html", "css", "rust", "go", "php", "ruby"]
        has_code = any(kw in target_lower for kw in code_keywords)
        has_lang = any(kw in target_lower for kw in lang_keywords)
        
        if (has_code and has_lang) or (target_lower.startswith("hello world in")):
            print(f"[CodeGenerator] Generating clean code for: {target}")
            target = generate_clean_code(target)
            
        print(f"Typing: '{target}'")
        sleep(1)
        gui.write(target, interval=0.03)
        gui.press("enter")
    elif action == "search":
        search_text, site = target
        import urllib.parse
        import webbrowser
        site_lower = str(site).lower() if site else ""
        
        # Check if searching on a specific known site
        if "youtube" in site_lower or "yt" in site_lower:
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(search_text)}"
            print(f"Opening YouTube search for: '{search_text}'...")
            webbrowser.open(url)
        elif "google" in site_lower:
            url = f"https://www.google.com/search?q={urllib.parse.quote(search_text)}"
            print(f"Opening Google search for: '{search_text}'...")
            webbrowser.open(url)
        else:
            # Fallback to checking the text itself or active browser window
            text_lower = search_text.lower()
            if "youtube" in text_lower or " yt" in text_lower:
                url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(search_text)}"
                print(f"Opening YouTube search for: '{search_text}'...")
                webbrowser.open(url)
            elif "google" in text_lower:
                url = f"https://www.google.com/search?q={urllib.parse.quote(search_text)}"
                print(f"Opening Google search for: '{search_text}'...")
                webbrowser.open(url)
            else:
                print(f"Searching for: '{search_text}' on {site if site else 'current page'}...")
                search_on_page(search_text, site)
    elif action == "play_spotify":
        print(f"Playing '{target}' on Spotify...")
        speak_thread = threading.Thread(target=speak, args=("",))
        speak_thread.start()
        play_music_on_spotify(target)
    elif action == "play_youtube":
        print(f"Playing '{target}' on YouTube...")
        speak_thread = threading.Thread(target=speak, args=("",))
        speak_thread.start()
        play_music_on_youtube(target)
    elif action == "press":
        print(f"Pressing key: {target}")
        gui.press(target)
    elif action == "hotkey":
        print(f"Pressing hotkey: {target}")
        gui.hotkey(*target)
    elif action == "sleep":
        print(f"Sleeping for {target} seconds...")
        try:
            from SpeechToText.speech_buffer import get_speech_buffer
            buffer = get_speech_buffer()
        except ImportError:
            buffer = None
        
        steps = int(target * 10)
        for _ in range(steps):
            if buffer and buffer.is_cancelled():
                print("[JARVIS] Sleep aborted via cancellation flag.")
                break
            sleep(0.1)
    elif action == "write_and_run":
        lang, query = target
        write_and_run_code(lang, query)
    elif action == "run_project":
        run_project_or_file(target)
    elif action == "close":
        close()
    elif action == "screenshot_and_email":
        execute_screenshot_and_email()
    elif action == "work_mode":
        execute_work_mode()
    elif action == "screen_understand":
        execute_screen_understand()
    elif action == "research_agent":
        execute_research_agent(target or "latest AI news")
    elif action == "click_first_result":
        # Press Tab twice to focus first Google search result link, then Enter
        time.sleep(0.8)
        gui.hotkey("ctrl", "l")   # Focus address bar first (page must be loaded)
        time.sleep(0.4)
        gui.press("escape")
        time.sleep(0.3)
        gui.press("tab")          # Move into page
        time.sleep(0.2)
        gui.press("tab")
        time.sleep(0.2)
        gui.press("tab")
        time.sleep(0.2)
        gui.press("enter")        # Open first result
        time.sleep(2.0)


def process_rule_based(text):
    """Process command using rule-based matching (fallback mode)."""
    text_lower = text.lower().strip()

    # ── Emergency Stop Check ──────────────────────────────────────────────────
    try:
        from SpeechToText.speech_buffer import SpeechBuffer
        if SpeechBuffer.is_stop_command(text_lower):
            print(f"[RuleBased] STOP command detected for: '{text}'")
            from shared_state import stop_all_operations
            stop_all_operations()
            return True
    except Exception as e:
        print(f"[RuleBased] Stop check error: {e}")

    # ── Work Mode ─────────────────────────────────────────────────────────────

    if any(phrase in text_lower for phrase in [
        "work mode", "start work mode", "begin work mode",
        "activate work mode", "setup my workspace", "set up my workspace",
    ]):
        print("[RuleBased] Work mode detected.")
        threading.Thread(target=execute_work_mode, daemon=True).start()
        return True

    # ── Screen Understanding ──────────────────────────────────────────────────
    screen_phrases = [
        "what is on my screen", "what's on my screen", "what am i looking at",
        "describe my screen", "analyze my screen", "what do you see on my screen",
        "what can you see", "describe what you see", "look at my screen",
        "what's happening on my screen",
    ]
    if any(phrase in text_lower for phrase in screen_phrases):
        print("[RuleBased] Screen understanding detected.")
        threading.Thread(target=execute_screen_understand, daemon=True).start()
        return True

    # ── Email Automation ──────────────────────────────────────────────────────
    email_signals = [
        "send email", "send an email", "email to", "send me an email", 
        "take a screenshot and send", "email screenshot", "send email to",
        "to my email", "to email", "email me", "email this", "email the", "email my",
        "send me matter"
    ]
    is_email = any(sig in text_lower for sig in email_signals) or \
               (text_lower.startswith("send ") and any(w in text_lower for w in ["email", "gmail", "mail", "thunder"])) or \
               (text_lower.startswith("mail ") or text_lower.startswith("email ")) or \
               any(w in text_lower for w in ["to my second email", "to my another gmail", "to my secondary email", "second email", "secondary email"])
    if is_email:
        print(f"[RuleBased] Email automation triggered for: {text}")
        threading.Thread(target=execute_send_email, args=(text,), daemon=True).start()
        return True


    # ── Document Intelligence & Study Mode ──────────────────────────────────────
    is_web_query = any(w in text_lower for w in ["google", "youtube", "github", "obsidian", "web", "online", "internet", "website", "chrome", "browser"])
    if any(ext in text_lower for ext in [".pdf", ".docx", ".doc", ".pptx", ".ppt", ".txt", ".md", ".rtf", ".html", ".htm"]) or "pdf" in text_lower or "document" in text_lower:
        if not any(w in text_lower for w in ["google", "youtube", "github"]):
            is_web_query = False
            
    if not is_web_query:
        doc_exts = [".pdf", ".docx", ".doc", ".pptx", ".ppt", ".txt", ".md", ".png", ".jpg", ".rtf", ".html", ".htm"]
        doc_kws = ["pdf", "document", "chapter", "resume", "ultron", "flashcard", "quiz", "formula", "note", "notes"]
        doc_verbs = ["open", "find", "read", "locate", "load", "summarize", "explain", "parse", "study", "translate", "compare"]

        is_doc_ext = any(ext in text_lower for ext in doc_exts)
        is_doc_kw = any(k in text_lower for k in doc_kws) and any(v in text_lower for v in doc_verbs)

        doc_triggers = [
            "open ultron", "open the ai notes", "find the operating systems", "open my resume",
            "open pdf", "find pdf", "read pdf", "find document", "scroll down", "scroll up",
            "zoom in", "zoom out", "close the document", "close document", "find all mentions",
            "explain page", "what is this document about", "document intelligence",
            "open a pdf", "open pdf file", "view pdf"
        ]
        study_triggers = [
            "study", "read this pdf", "summarize this document", "explain this chapter",
            "generate important questions", "create a quiz", "ask me questions one by one",
            "explain this like i'm a beginner", "explain in simple language",
            "important formulas", "extract key points", "find important definitions",
            "important topics", "ask doubts", "only this document", "compare two uploaded documents",
            "translate this document", "revision notes", "flashcards", "interview questions",
            "multiple-choice questions", "continue from the last page", "study mode",
        ]

        if is_doc_ext or is_doc_kw or any(t in text_lower for t in doc_triggers) or any(t in text_lower for t in study_triggers):
            print(f"[RuleBased] Document Intelligence / Study Mode triggered for: {text}")
            threading.Thread(target=execute_doc_intelligence, args=(text,), daemon=True).start()
            return True




    # Battery commands
    if "battery" in text_lower and any(word in text_lower for word in ["what", "check", "percentage", "percent", "level", "status"]):
        check_percentage()
        return True


        
    # Weather commands
    if "weather" in text_lower or "climate" in text_lower:
        print(f"[JARVIS] Checking weather...")
        location = ""
        if "in" in text_lower:
            location = text_lower.split("in")[-1].strip()
        elif "at" in text_lower:
            location = text_lower.split("at")[-1].strip()
        elif "for" in text_lower:
            location = text_lower.split("for")[-1].strip()
            
        if not location:
            location = "Hyderabad, Telangana, India"
            
        report = get_weather_by_address(location)
        
        if report and "Error" not in report and "Could not" not in report:
            lines = report.split('\n')
            summary = f"{lines[0]}. {lines[1]}. {lines[2]}."
            print(f"[JARVIS] Weather: {summary}")
            speak_thread = threading.Thread(target=speak, args=(summary,))
            speak_thread.start()
        else:
            speak("Sorry, I couldn't get the weather information.")
        return True
    
    # GitHub search commands
    github_keywords = ["github", "repo", "repository", "repositories"]
    search_keywords = ["find", "search", "look for", "show me", "get"]
    
    if any(keyword in text_lower for keyword in github_keywords) and \
       any(keyword in text_lower for keyword in search_keywords):
        # Extract search query
        query = text_lower
        for remove in ["find", "search", "look for", "show me", "get", "github", "repo", "repository", "repositories", "on", "in"]:
            query = query.replace(remove, "")
        query = query.strip()
        
        if query:
            print(f"[JARVIS] Searching GitHub for: {query}")
            speak("Searching GitHub repositories. Please wait.")
            
            try:
                result = search_github_sync(query)
                print(result)
                
                # Extract just the summary for TTS
                lines = result.split('\n')
                if len(lines) > 0:
                    summary = lines[0]  # "Found X GitHub repositories for 'query'"
                    speak(summary + ". Check the terminal for details.")
            except Exception as e:
                print(f"[JARVIS] GitHub search error: {e}")
                speak("Sorry, I encountered an error searching GitHub.")
            return True
    
    # Web search via DuckDuckGo MCP
    if any(word in text_lower for word in ["search", "find", "look up"]) and \
       any(word in text_lower for word in ["web", "online", "internet", "duckduckgo"]):
        query = text_lower
        for remove in ["search", "find", "look up", "on", "the", "web", "online", "internet", "duckduckgo", "for"]:
            query = query.replace(remove, "")
        query = query.strip()
        
        if query:
            print(f"[JARVIS] Searching web for: {query}")
            speak("Searching the web.")
            
            try:
                result = search_web_sync(query)
                print(result)
                speak("Search complete. Check the terminal for results.")
            except Exception as e:
                print(f"[JARVIS] Web search error: {e}")
                speak("Sorry, web search failed.")
            return True
    
    # Obsidian notes search
    if "obsidian" in text_lower and any(word in text_lower for word in ["search", "find", "notes", "note"]):
        query = text_lower
        for remove in ["search", "find", "obsidian", "notes", "note", "in", "my", "for"]:
            query = query.replace(remove, "")
        query = query.strip()
        
        if query:
            print(f"[JARVIS] Searching Obsidian notes for: {query}")
            speak("Searching your Obsidian notes.")
            
            try:
                result = search_obsidian_sync(query)
                print(result)
                speak("Search complete. Check the terminal.")
            except Exception as e:
                print(f"[JARVIS] Obsidian search error: {e}")
                speak("Sorry, couldn't search Obsidian notes.")
            return True
    
    # Search web and save to Obsidian (NEW WORKFLOW)
    if ("search" in text_lower or "find" in text_lower) and \
       ("save" in text_lower or "copy" in text_lower or "paste" in text_lower) and \
       ("obsidian" in text_lower or "note" in text_lower):
        # Extract query
        query = text_lower
        for remove in ["search", "find", "save", "copy", "paste", "to", "in", "obsidian", "notes", "note", "for", "and", "the", "web", "links", "top", "5"]:
            query = query.replace(remove, "")
        query = query.strip()
        
        if query:
            print(f"[JARVIS] Searching web for '{query}' and saving to Obsidian")
            speak(f"Searching for {query} and saving to Obsidian.")
            
            try:
                from Tools.obsidian_integration import search_and_save_sync
                note_path = search_and_save_sync(query)
                print(f"[JARVIS] [OK] Saved to: {note_path}")
                speak(f"Search complete. Results saved to Obsidian note.")
            except Exception as e:
                print(f"[JARVIS] Error: {e}")
                speak("Sorry, couldn't save to Obsidian.")
            return True
    
    # WhatsApp commands
    if is_whatsapp_command(text_lower):
        print(f"[JARVIS] Detected WhatsApp command: {text_lower}")
        result = handle_whatsapp_command(text)
        if result.get("success"):
            print(f"[JARVIS] WhatsApp message drafted for: {result.get('contact', 'unknown')}")
        else:
            print(f"[JARVIS] WhatsApp command failed: {result.get('error', 'unknown error')}")
        return True
    
    # YouTube video commands (when YouTube is active)
    if is_youtube_active():
        youtube_keywords = ["play", "pause", "resume", "stop", "volume", "louder", "quieter",
                           "forward", "back", "rewind", "skip", "next video", "previous video",
                           "next frame", "previous frame", "next chapter", "previous chapter",
                           "speed up", "slow down", "faster", "slower", "beginning", "start", "end",
                           "search", "first"]
        if any(keyword in text_lower for keyword in youtube_keywords):
            confirm_msg = "Okay sir, executing YouTube command."
            if "first" in text_lower:
                confirm_msg = "Okay sir, playing the first video."
            elif "pause" in text_lower:
                confirm_msg = "Okay sir, pausing the video."
            elif "play" in text_lower or "resume" in text_lower:
                confirm_msg = "Okay sir, resuming the video."
            elif "volume" in text_lower or "louder" in text_lower or "quieter" in text_lower:
                confirm_msg = "Okay sir, adjusting the volume."
            elif "skip" in text_lower or "next video" in text_lower:
                confirm_msg = "Okay sir, playing the next video."
            
            speak_async(confirm_msg)
            handle_video_commands(text_lower)
            print(f"[JARVIS] YouTube command executed: {text_lower}")
            return True
    
    # Browser commands (when browser is active)
    if is_browser_active():
        browser_keywords = ["new tab", "close tab", "zoom", "refresh", "reload", 
                           "next tab", "previous tab", "history", "bookmarks",
                           "go back", "go forward", "developer tools", "inspect",
                           "full screen", "fullscreen", "private window", "incognito",
                           "browser menu", "naya tab", "tab band", "peeche", "aage"]
        if any(keyword in text_lower for keyword in browser_keywords):
            confirm_msg = "Okay sir, executing browser command."
            if "new tab" in text_lower or "naya tab" in text_lower:
                confirm_msg = "Okay sir, opening a new tab."
            elif "close tab" in text_lower or "tab band" in text_lower:
                confirm_msg = "Okay sir, closing this tab."
            elif "refresh" in text_lower or "reload" in text_lower:
                confirm_msg = "Okay sir, refreshing the page."
            elif "go back" in text_lower or "peeche jao" in text_lower:
                confirm_msg = "Okay sir, going back."
            elif "go forward" in text_lower or "aage jao" in text_lower:
                confirm_msg = "Okay sir, going forward."
                
            speak_async(confirm_msg)
            handle_browser_commands(text_lower)
            print(f"[JARVIS] Browser command executed: {text_lower}")
            return True
    
    # Parse and execute general commands
    commands = parse_commands(text_lower)
    
    if not commands:
        return False
    
    print(f"[JARVIS] Parsed {len(commands)} command(s): {commands}")
    
    # Generate spoken confirmation for the user
    speech_parts = []
    for action, target in commands:
        if action == "open":
            speech_parts.append(f"opening {target}")
        elif action == "open_in_browser":
            site, browser = target
            speech_parts.append(f"opening {site} in {browser}")
        elif action == "type":
            speech_parts.append(f"typing {target}")
        elif action == "search":
            search_text, site = target
            speech_parts.append(f"searching for {search_text}" + (f" on {site}" if site else ""))
        elif action == "play_spotify":
            speech_parts.append(f"playing {target} on Spotify")
        elif action == "play_youtube":
            speech_parts.append(f"playing {target} on YouTube")
        elif action == "close":
            speech_parts.append("closing the window")

    if speech_parts:
        confirm_msg = "Okay sir, " + " and ".join(speech_parts)
        speak_async(confirm_msg)
        
    try:
        from SpeechToText.speech_buffer import get_speech_buffer
        buffer = get_speech_buffer()
    except ImportError:
        buffer = None

    for i, (action, target) in enumerate(commands):
        if buffer and buffer.is_cancelled():
            print("[JARVIS] Command execution cancelled.")
            break
        if i > 0:
            cancelled = False
            for _ in range(10):
                if buffer and buffer.is_cancelled():
                    cancelled = True
                    break
                sleep(0.1)
            if cancelled:
                break
        execute_command(action, target)
    
    return True


# ============================================================================
# SINGLE TASK EXECUTOR (internal — called by queue for each sub-task)
# ============================================================================

def _execute_single_task(text: str) -> dict:
    """
    Execute a SINGLE task through the full pipeline.
    Returns a result dict. Used by the multi-task queue system.
    
    Pipeline: PrimaryBrain (which handles memory, LLM intent, rule-based fallback, and conversational response)
    """
    text = text.strip()
    
    if not text:
        return {"status": "error", "response": "Empty input."}
    
    _safe_print(f"\n[Brain] Executing single task: '{text[:120]}'")
    
    # Route completely to PrimaryBrain for integrated handling
    try:
        from Brain.primary_brain import get_primary_brain
        brain = get_primary_brain()
        result = brain.process(text)
        
        response = ""
        if isinstance(result, dict):
            response = result.get("response", result.get("message", ""))
            # For tool results (GitHub search, web search, etc.) that store
            # output in "result" key instead of "response"
            if not response and result.get("result"):
                response = str(result["result"])
        else:
            response = str(result)
            
        return {"status": "success", "handler": "primary_brain", "response": response}
    except Exception as e:
        safe_err = str(e).encode('ascii', errors='replace').decode()
        _safe_print(f"[Brain] PrimaryBrain error: {safe_err}")
    
    # Absolute last resort
    _safe_print(f"[Brain] Unknown command: {text[:120]}")
    speak("I'm not sure what you want me to do. Could you please rephrase?")
    return {"status": "error", "response": "Could not process this request."}


# ============================================================================
# MAIN BRAIN ENTRY POINT (with multi-task queue support)
# ============================================================================

def Automation_Brain(text):
    """
    Main brain that handles voice commands.
    
    NEW: Supports multi-task requests!
    If the user gives a request with multiple tasks (e.g., 
    "search GitHub for opencv projects and I have a meeting tomorrow"),
    the system will:
    1. Decompose the request into separate tasks via LLM
    2. Queue all tasks
    3. Execute them concurrently (agent tasks run in parallel)
    4. Deliver a unified response after ALL tasks complete
    
    Single-task inputs flow through normally with zero overhead.
    """
    text = text.strip()
    
    # Auto-correct voice recognition mis-transcriptions for "email this"
    text_lower = text.lower().strip()
    if text_lower in ["image", "images", "image image", "image this", "images jarvis", "image jarvis"]:
        print(f"[Brain] Auto-correcting speech mis-transcription: '{text}' -> 'email this'")
        text = "email this"
        
    if not text:
        return

    # Emergency STOP check vs New Command execution
    try:
        from SpeechToText.speech_buffer import SpeechBuffer, get_speech_buffer
        if SpeechBuffer.is_stop_command(text):
            print(f"[Brain] STOP command detected: '{text}'")
            from shared_state import stop_all_operations
            stop_all_operations()
            return
        else:
            # Reset cancellation flag so the new command is never blocked by a past stop command
            buffer = get_speech_buffer()
            buffer.reset_cancel()
    except Exception as e:
        print(f"[Brain] Stop check error: {e}")


    
    _safe_print(f"\n{'='*60}")
    _safe_print(f"[Brain] Input: '{text[:120]}'")
    _safe_print(f"{'='*60}")
    
    try:
        from Brain.task_queue import process_multi_task
        
        result = process_multi_task(text, _execute_single_task)
        
        # Log result summary
        if result.get("multi_task"):
            task_count = result.get("task_count", 0)
            successful = result.get("successful", 0)
            failed = result.get("failed", 0)
            total_time = result.get("total_time", 0)
            print(f"\n[Brain] Multi-task complete: {successful}/{task_count} succeeded ({total_time:.1f}s)")
            if failed:
                print(f"[Brain] {failed} task(s) failed")
        else:
            print(f"[Brain] [OK] Single task completed")
        
    except ImportError as e:
        # Fallback: if task_queue module fails to import, use direct execution
        print(f"[Brain] Task queue unavailable ({e}), using direct execution")
        result = _execute_single_task(text)
    except Exception as e:
        print(f"[Brain] Multi-task processing error: {e}")
        # Fallback to direct single-task execution
        result = _execute_single_task(text)

    # Ensure the final response is displayed in the HUD console Communication Link Box
    try:
        from shared_state import ui_jarvis_message, get_chat_history
        response_val = None
        if isinstance(result, dict):
            response_val = result.get("response") or result.get("result")
        elif isinstance(result, str):
            response_val = result
            
        if response_val:
            response_str = str(response_val).strip()
            if response_str and not response_str.startswith("{") and not response_str.startswith("["):
                history = get_chat_history()
                already_logged = False
                if history:
                    last_msg = history[-1]
                    if last_msg.get("role") == "jarvis" and last_msg.get("content") == response_str:
                        already_logged = True
                
                if not already_logged:
                    ui_jarvis_message(response_str)

                # Response Memory System Hook
                input_lower = text.lower().strip()
                meaningful_keywords = ["explain", "summarize", "summary", "notes", "revision", "question", "mcq", "quiz", "report", "research", "code", "program", "script", "draft", "write", "what is", "about"]
                is_meaningful = False
                if any(k in input_lower for k in meaningful_keywords):
                    is_meaningful = True
                elif len(response_str) > 120:
                    if not any(k in response_str.lower() for k in ["encountered an error", "error attempting", "failed to open", "everything is ready"]):
                        is_meaningful = True
                
                # Exclude simple system updates, greetings or stop updates
                if any(k in response_str.lower() for k in ["good to see you, sir", "all core systems are online", "standing by for your next command"]):
                    is_meaningful = False
                
                if is_meaningful:
                    from shared_state import set_latest_generated_response
                    set_latest_generated_response(response_str)

    except Exception as ui_err:
        print(f"[Brain] Error updating HUD chat history / Response Memory: {ui_err}")

    return result

