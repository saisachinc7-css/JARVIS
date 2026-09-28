import os
import subprocess

def generate_pdf():
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>J.A.R.V.I.S - Tech Specifications & Blueprint</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap');
        
        body {
            font-family: 'Inter', sans-serif;
            background-color: #ffffff;
            color: #1e293b;
            margin: 0;
            padding: 40px;
            line-height: 1.6;
        }
        
        /* Premium tech blueprint header */
        .header {
            border-bottom: 2px solid #00f0ff;
            padding-bottom: 20px;
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
        }
        
        .header-title h1 {
            margin: 0;
            font-size: 32px;
            font-weight: 800;
            color: #0b1e36;
            text-transform: uppercase;
            letter-spacing: 1.5px;
        }
        
        .header-title p {
            margin: 5px 0 0 0;
            color: #008b8b;
            font-weight: 600;
            font-size: 14px;
            letter-spacing: 1px;
            text-transform: uppercase;
        }
        
        .header-meta {
            text-align: right;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            color: #64748b;
        }
        
        /* Grid section cards */
        .section-title {
            font-size: 18px;
            font-weight: 700;
            color: #0b1e36;
            border-left: 4px solid #00f0ff;
            padding-left: 10px;
            margin-top: 30px;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .tech-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .card {
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 15px 20px;
            background-color: #f8fafc;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        
        .card h3 {
            margin-top: 0;
            margin-bottom: 8px;
            color: #0f172a;
            font-size: 16px;
            font-weight: 600;
        }
        
        .card ul {
            margin: 0;
            padding-left: 20px;
            color: #334155;
            font-size: 14px;
        }
        
        .card li {
            margin-bottom: 6px;
        }
        
        /* Table styles */
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            margin-bottom: 30px;
        }
        
        th {
            background-color: #0b1e36;
            color: #ffffff;
            font-weight: 600;
            text-align: left;
            padding: 10px 15px;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        td {
            padding: 10px 15px;
            border-bottom: 1px solid #e2e8f0;
            font-size: 13.5px;
            color: #334155;
        }
        
        tr:nth-child(even) {
            background-color: #f8fafc;
        }
        
        .package-name {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            color: #008b8b;
        }
        
        /* Layout specifications */
        .summary-box {
            background-color: #f0fdfa;
            border: 1px solid #99f6e4;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 25px;
            font-size: 14.5px;
            color: #0f766e;
        }
        
        /* Footer */
        .footer {
            margin-top: 50px;
            border-top: 1px solid #e2e8f0;
            padding-top: 15px;
            text-align: center;
            font-size: 11px;
            color: #94a3b8;
            font-family: 'JetBrains Mono', monospace;
        }
        
        @media print {
            body {
                padding: 0;
            }
            .page-break {
                page-break-before: always;
            }
        }
    </style>
</head>
<body>

    <div class="header">
        <div class="header-title">
            <h1>J.A.R.V.I.S Blueprint</h1>
            <p>System Architecture & Technology Stack Specifications</p>
        </div>
        <div class="header-meta">
            DOCUMENT ID: AP-J2-9842<br>
            VERSION: 2.1.0<br>
            CLASSIFICATION: PUBLIC
        </div>
    </div>

    <div class="summary-box">
        <strong>Executive Overview:</strong> J.A.R.V.I.S is an advanced local-first agentic AI operating system combining high-speed wake-word speech processing, dual-brain LLM reasoning, automation engines (browser, email, RAG, and email agents), and real-time state sync with a customized HUD console interface.
    </div>

    <div class="section-title">Core Systems & Programming Stack</div>
    <div class="tech-grid">
        <div class="card">
            <h3>Programming Languages</h3>
            <ul>
                <li><strong>Python 3.10+</strong>: Core logic runtime, agent control loop, background threads.</li>
                <li><strong>HTML5 / CSS3 / JavaScript (ES6)</strong>: HUD web UI, real-time telemetry gauges, Arc Reactor SVG canvas animations.</li>
            </ul>
        </div>
        <div class="card">
            <h3>Data Persistence & Memory</h3>
            <ul>
                <li><strong>SQLite</strong>: Default local relational memory structure.</li>
                <li><strong>Pyperclip Clipboard Buffer</strong>: System-wide clipboard sharing and RAG response backup memory.</li>
            </ul>
        </div>
    </div>

    <div class="section-title">Autonomous Agents & Controllers</div>
    <div class="tech-grid">
        <div class="card">
            <h3>Voice Engine (STT & TTS)</h3>
            <ul>
                <li><strong>Microphone Listener</strong>: Speed-calibrated speech-recognition buffer.</li>
                <li><strong>Wake Word Detector</strong>: Fast multi-phrase intent detection matching "Jarvis" variants.</li>
                <li><strong>Audio Queue (TTS)</strong>: Asynchronous Pygame mixer queue playing voice notifications.</li>
            </ul>
        </div>
        <div class="card">
            <h3>Automations & Integrations</h3>
            <ul>
                <li><strong>Browser Agent</strong>: Headless Playwright script handler.</li>
                <li><strong>Email Agent</strong>: Pre-filled direct compose Gmail dispatcher.</li>
                <li><strong>Google Workspace Hook</strong>: Apps Script bridge to Gmail, Drive, Calendar, Docs.</li>
            </ul>
        </div>
    </div>

    <div class="page-break"></div>

    <div class="header" style="margin-top: 40px;">
        <div class="header-title">
            <h1>J.A.R.V.I.S Blueprint</h1>
            <p>Libraries, Dependencies & Integration Map</p>
        </div>
        <div class="header-meta">
            PAGE: 2 / 2
        </div>
    </div>

    <div class="section-title">External Tooling & Models Layer</div>
    <div class="tech-grid">
        <div class="card">
            <h3>Local Reasoning Models</h3>
            <ul>
                <li><strong>Ollama</strong>: Orchestrates execution of offline LLMs.</li>
                <li><strong>Qwen 2.5 (1.5B/4B)</strong>: Primary/secondary task classification.</li>
                <li><strong>Mistral 7B</strong>: Large fallback reasoning tasks.</li>
            </ul>
        </div>
        <div class="card">
            <h3>Service Hooks</h3>
            <ul>
                <li><strong>n8n Webhooks</strong>: Web API workflow trigger.</li>
                <li><strong>Telegram Bot API</strong>: Remote telemetry bot handler.</li>
                <li><strong>Flask / Waitress</strong>: Local telemetry stats REST API.</li>
            </ul>
        </div>
    </div>

    <div class="section-title">Key Python Libraries & Packages</div>
    <table>
        <thead>
            <tr>
                <th style="width: 25%;">Package Name</th>
                <th style="width: 20%;">Category</th>
                <th style="width: 55%;">Role in J.A.R.V.I.S</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td class="package-name">pyautogui</td>
                <td>OS Automation</td>
                <td>Automates clicks, keystrokes, and UI interactions across desktop apps.</td>
            </tr>
            <tr>
                <td class="package-name">pyperclip</td>
                <td>System Clipboard</td>
                <td>Stores latest generated LLM responses to clipboard for quick paste/emailing.</td>
            </tr>
            <tr>
                <td class="package-name">pygame</td>
                <td>Audio Mixer</td>
                <td>Handles sound effects and provides non-blocking playback queue for TTS.</td>
            </tr>
            <tr>
                <td class="package-name">win32gui / win32con</td>
                <td>Windows OS API</td>
                <td>Monitors active foreground window titles for context-aware RAG operations.</td>
            </tr>
            <tr>
                <td class="package-name">speech_recognition</td>
                <td>Speech Logic</td>
                <td>Performs microphone speech-to-text processing via local/remote models.</td>
            </tr>
            <tr>
                <td class="package-name">flask / waitress</td>
                <td>REST API</td>
                <td>Serves status JSON queries to the HUD web client console loop.</td>
            </tr>
            <tr>
                <td class="package-name">beautifulsoup4</td>
                <td>Data Parsing</td>
                <td>Extracts key clean text structures from web pages and documents.</td>
            </tr>
        </tbody>
    </table>

    <div class="footer">
        JARVIS-SYSTEM-SPECIFICATIONS • GENERATED VIA HEADLESS CHROME VECTOR PRINT ENGINE • CONFIDENTIALITY: NONE
    </div>

</body>
</html>"""

    base_dir = r"d:\ANTIGRAVITY\JARVIS 2.0\Jarvis-main"
    html_path = os.path.join(base_dir, "project_blueprint.html")
    pdf_path = os.path.join(base_dir, "project_blueprint.pdf")
    
    # Save the HTML template file
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Created HTML file: {html_path}")
    
    # Render HTML to PDF using Google Chrome in headless print mode
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    cmd = [
        chrome_path,
        "--headless",
        "--disable-gpu",
        f"--print-to-pdf={pdf_path}",
        html_path
    ]
    
    print("Running Chrome print engine...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and os.path.exists(pdf_path):
        print(f"Successfully generated PDF: {pdf_path}")
    else:
        print("Error printing PDF:", res.stderr)

if __name__ == "__main__":
    generate_pdf()
