def get_extension(text):
    text = text.replace("create", "").lower()
    ex = ".txt"  # Default extension if no match found

    # Programming Languages
    if "python file" in text:
        text=text.replace("python file","")
        ex = ".py"
    elif "java file" in text:
        text=text.replace("java file","")
        ex = ".java"
    elif "c file" in text:
        text=text.replace("c file","")
        ex = ".c"
    elif "cpp file" in text or "c++ file" in text:
        text=text.replace("cpp file","")
        ex = ".cpp"
    elif "c sharp file" in text or "c# file" in text:
        text=text.replace("c sharp file","")
        ex = ".cs"
    elif "go file" in text:
        text=text.replace("go file","")
        ex = ".go"
    elif "rust file" in text:
        text=text.replace("rust file","")
        ex = ".rs"
    elif "kotlin file" in text:
        text=text.replace("kotlin file","")
        ex = ".kt"
    elif "swift file" in text:
        text=text.replace("swift file","")
        ex = ".swift"

    # Web
    elif "html file" in text:
        text=text.replace("html file","")
        ex = ".html"
    elif "css file" in text:
        text=text.replace("css file","")
        ex = ".css"
    elif "javascript file" in text or "js file" in text:
        text=text.replace("javascript file","")
        ex = ".js"
    elif "typescript file" in text:
        text=text.replace("typescript file","")
        ex = ".ts"

    # Data / Config
    elif "json file" in text:
        text=text.replace("json file","")
        ex = ".json"
    elif "xml file" in text:
        text=text.replace("xml file","")
        ex = ".xml"
    elif "yaml file" in text or "yml file" in text:
        text=text.replace("yaml file","")
        ex = ".yaml"
    elif "csv file" in text:
        text=text.replace("csv file","")
        ex = ".csv"
    elif "ini file" in text:
        text=text.replace("ini file","")
        ex = ".ini" 
    elif "env file" in text:
        text=text.replace("env file","")
        ex = ".env"

    # Documents
    elif "text file" in text or "txt file" in text:
        text=text.replace("text file","")
        ex = ".txt"
    elif "markdown file" in text or "md file" in text:
        text=text.replace("markdown file","")
        ex = ".md"
    elif "pdf file" in text:
        text=text.replace("pdf file","")
        ex = ".pdf"
    elif "word file" in text or "doc file" in text:
        text=text.replace("word file","")
        ex = ".docx"
    elif "excel file" in text or "sheet file" in text:
        text=text.replace("excel file","")
        ex = ".xlsx"
    elif "powerpoint file" in text or "ppt file" in text:
        text=text.replace("powerpoint file","")
        ex = ".pptx"

    # Audio
    elif "mp3 file" in text or "audio file" in text:
        text=text.replace("mp3 file","")
        ex = ".mp3"
    elif "wav file" in text:
        text=text.replace("wav file","")
        ex = ".wav"
    elif "aac file" in text:
        text=text.replace("aac file","")
        ex = ".aac"
    elif "flac file" in text:
        text=text.replace("flac file","")
        ex = ".flac"
    elif "ogg file" in text:
        text=text.replace("ogg file","")
        ex = ".ogg"

    # Video
    elif "mp4 file" in text or "video file" in text:
        text=text.replace("mp4 file","")
        ex = ".mp4"
    elif "mkv file" in text:
        text=text.replace("mkv file","")
        ex = ".mkv"
    elif "avi file" in text:
        text=text.replace("avi file","")
        ex = ".avi"
    elif "mov file" in text:
        text=text.replace("mov file","")
        ex = ".mov"
    elif "webm file" in text:
        text=text.replace("webm file","")
        ex = ".webm"

    # Images
    elif "image file" in text or "jpg file" in text or "jpeg file" in text:
        text=text.replace("image file","")
        text=text.replace("jpg file","")
        text=text.replace("jpeg file","")
        ex = ".jpg"
    elif "png file" in text:
        text=text.replace("png file","")
        ex = ".png"
    elif "gif file" in text:
        text=text.replace("gif file","")
        ex = ".gif"
    elif "svg file" in text:
        text=text.replace("svg file","")
        ex = ".svg"
    elif "webp file" in text:
        text=text.replace("webp file","")
        ex = ".webp"

    # Archives
    elif "zip file" in text:
        text=text.replace("zip file","")
        ex = ".zip"
    elif "rar file" in text:
        text=text.replace("rar file","")
        ex = ".rar"
    elif "7z file" in text:
        text=text.replace("7z file","")
        ex = ".7z"
    elif "tar file" in text:
        text=text.replace("tar file","")
        ex = ".tar"
    elif "gz file" in text:
        text=text.replace("gz file","")
        ex = ".gz"

    # Scripts / System
    elif "shell file" in text or "bash file" in text:
        text=text.replace("shell file","")
        text=text.replace("bash file","")
        ex = ".sh"
    elif "batch file" in text:
        text=text.replace("batch file","")
        ex = ".bat"
    elif "powershell file" in text:
        text=text.replace("powershell file","")
        ex = ".ps1"
    elif "executable file" in text or "exe file" in text:
        text=text.replace("executable file","")
        text=text.replace("exe file","")
        ex = ".exe"

    # Dev / Other
    elif "sql file" in text:
        text=text.replace("sql file","")
        ex = ".sql"
    elif "log file" in text:
        text=text.replace("log file","")
        ex = ".log"
    elif "dockerfile" in text:
        text=text.replace("dockerfile","")
        ex = "Dockerfile"
    elif "gitignore file" in text:
        text=text.replace("gitignore file","")
        ex = ".gitignore"

    else:
        ex = ".txt"  # Default to text file
    return ex, text  # Return both extension and cleaned text


def create_file(text=None):
    if text is None:
        text = input("Enter file type and name: ")
    
    selected_ex, cleaned_text = get_extension(text)

    if "named" in text or "with name" in text:
        cleaned_text = cleaned_text.replace("named", "")
        cleaned_text = cleaned_text.replace("with name", "")
        cleaned_text = cleaned_text.strip()
        
        # Remove any remaining file type words
        filename = cleaned_text.strip()
        if filename:
            with open(f"{filename}{selected_ex}", "w"):
                pass
            print(f"Created: {filename}{selected_ex}")
        else:
            with open(f"demo{selected_ex}", "w"):
                pass
            print(f"Created: demo{selected_ex}")
    else:
        with open(f"demo{selected_ex}", "w"):
            pass
        print(f"Created: demo{selected_ex}")


if __name__ == "__main__":
    create_file()