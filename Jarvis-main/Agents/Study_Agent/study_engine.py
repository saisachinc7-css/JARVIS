"""
Study Engine for JARVIS 2.0
Manages active study sessions, state, document context, quizzes, flashcards,
multiple explanation styles, progress tracking, and zero-hallucination QA.
"""

import os
import json
import re
from typing import Dict, List, Any, Optional

from Agents.Study_Agent import config
from Agents.Study_Agent.document_parser import parse_file


class StudySession:
    """Class representing an active study session state."""

    def __init__(self):
        self.loaded_materials: Dict[str, Dict[str, Any]] = {}  # {doc_id: doc_dict}
        self.active_doc_id: Optional[str] = None
        self.active_document: Optional[Dict[str, Any]] = None
        self.current_page: int = 1
        self.explanation_style: str = "detailed"  # beginner, detailed, technical, exam
        self.strict_mode: bool = False  # strict document QA (no external facts)
        self.quiz_state: Dict[str, Any] = {
            "active": False,
            "topic": "",
            "questions": [],
            "current_index": 0,
            "user_answers": [],
            "score": 0
        }
        self.conversation_history: List[Dict[str, str]] = []
        self.last_response: str = ""

    def add_material(self, doc_data: Dict[str, Any]) -> str:
        doc_id = doc_data["title"].lower().replace(" ", "_")
        self.loaded_materials[doc_id] = doc_data
        self.active_doc_id = doc_id
        self.current_page = 1

        # Populate Active Document details
        import datetime
        import os
        file_path = doc_data.get("file_path", "")
        if file_path:
            file_path = os.path.abspath(file_path)
        
        file_size = "Unknown"
        if file_path and os.path.exists(file_path):
            try:
                sz = os.path.getsize(file_path)
                if sz > 1024 * 1024:
                    file_size = f"{sz / (1024 * 1024):.1f} MB"
                else:
                    file_size = f"{sz / 1024:.1f} KB"
            except Exception:
                pass

        self.active_document = {
            "title": doc_data.get("title", ""),
            "file_name": doc_data.get("title", ""),
            "file_path": file_path,
            "file_type": doc_data.get("file_type", ""),
            "file_size": file_size,
            "date_opened": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "open_status": "Open",
            "status": "Open",
            "extracted_text": doc_data.get("raw_text", ""),
            "raw_text": doc_data.get("raw_text", ""),
            "context": "Loaded",
            "page_count": doc_data.get("page_count", 0),
            "pages": doc_data.get("pages", [])
        }
        return doc_id

    def get_active_doc(self) -> Optional[Dict[str, Any]]:
        return self.active_document

    def get_combined_text(self, limit_chars: int = 25000) -> str:
        """Combine raw text from all loaded documents or active document."""
        if not self.loaded_materials:
            return ""

        parts = []
        for doc_id, doc in self.loaded_materials.items():
            parts.append(f"=== DOCUMENT: {doc['title']} ({doc['file_type']}) ===\n{doc['raw_text']}")

        full = "\n\n".join(parts)
        return full[:limit_chars]


# Global singleton study session
_study_session = StudySession()


def get_study_session() -> StudySession:
    global _study_session
    return _study_session


# ============================================================================
# LLM HELPER FOR STUDY ENGINE
# ============================================================================

def _call_study_llm(prompt: str, system_override: Optional[str] = None) -> str:
    """
    Call local Ollama as the primary inference engine, falling back to Gemini API (Cloud).
    Both local and cloud models are configurable via environment variables.
    """
    sys_prompt = system_override or config.SYSTEM_PROMPT
    full_prompt = f"{sys_prompt}\n\n{prompt}"

    # Load configurable models
    local_env_model = os.getenv("OLLAMA_STUDY_MODEL", "")
    cloud_env_model = os.getenv("GEMINI_STUDY_MODEL", "")

    local_models = [local_env_model] if local_env_model else []
    local_models.extend(["qwen2.5:0.5b", "qwen3:8b", "deepseek-r1:8b", "llama3.1:8b", "qwen2.5"])

    cloud_models = [cloud_env_model] if cloud_env_model else []
    cloud_models.extend(["gemini-2.5-flash", "gemini-2.0-flash-lite", "gemini-2.0-flash"])

    use_gemini_only = os.getenv("USE_GEMINI_ONLY", "false").lower() in ("true", "1", "yes")
    result_text = None

    # 1. Try local Ollama first (unless forced to Gemini only)
    if not use_gemini_only:
        try:
            import ollama
            for m in local_models:
                try:
                    res = ollama.chat(
                        model=m,
                        messages=[
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        options=config.OLLAMA_OPTIONS
                    )
                    txt = res.get("message", {}).get("content", "").strip()
                    if txt:
                        result_text = txt
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"[StudyEngine] Ollama primary call failed/unavailable: {e}")

    # 2. Fallback to Cloud Gemini API
    if not result_text:
        try:
            from Tools.screen_vision import get_screen_vision
            sv = get_screen_vision()
            if sv._api_key:
                from google import genai
                client = genai.Client(api_key=sv._api_key)

                for m in cloud_models:
                    try:
                        res = client.models.generate_content(model=m, contents=full_prompt)
                        if res.text and res.text.strip():
                            result_text = res.text.strip()
                            break
                    except Exception as e:
                        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                            continue
                        break
        except Exception as e:
            print(f"[StudyEngine] Cloud Gemini fallback error: {e}")

    if result_text:
        # Save to session history
        try:
            session = get_study_session()
            session.last_response = result_text
        except Exception:
            pass
        return result_text

    return "Sir, I encountered an error while processing the study material with the AI models. Please ensure internet access or Ollama is running."


# ============================================================================
# CORE STUDY OPERATIONS
# ============================================================================

def load_study_material(source: str) -> str:
    """
    Ingest study material from file path, URL, or pasted text.
    """
    session = get_study_session()
    doc_data = parse_file(source)

    if not doc_data.get("raw_text") or doc_data.get("page_count", 0) == 0:
        return f"Sir, I tried reading '{source}' but could not extract any text content. Please check the file path or format."

    doc_id = session.add_material(doc_data)

    response = (
        f"📚 **Study Material Successfully Loaded into Study Mode!**\n\n"
        f"• **Title**: `{doc_data['title']}`\n"
        f"• **Type**: `{doc_data['file_type']}`\n"
        f"• **Total Pages / Sections**: `{doc_data['page_count']}`\n"
        f"• **Total Words**: `{len(doc_data['raw_text'].split())}` words\n\n"
        f"Sir, I have analyzed the entire material. You can now ask me to summarize it, "
        f"explain concepts, generate quizzes, extract formulas, or test your knowledge!"
    )
    return response


def summarize_material(chapter_or_range: Optional[str] = None) -> str:
    """Generate a clean, structured summary with headings and bullet points."""
    session = get_study_session()
    doc = session.get_active_doc()

    if not doc:
        return "Sir, no study material is currently loaded. Please ask me to read a PDF or document first."

    text = doc["raw_text"][:25000]

    prompt = (
        f"Task: Generate a comprehensive, well-structured summary of the following study material.\n\n"
        f"Document: {doc['title']}\n"
        f"Target Section: {chapter_or_range or 'Full Document'}\n\n"
        f"Text Material:\n{text}\n\n"
        f"FORMAT REQUIREMENT:\n"
        f"1. Executive Overview (2-3 sentences)\n"
        f"2. Core Concepts & Topics (Use markdown headings `###` and sub-bullets)\n"
        f"3. High-Yield Takeaways (Bullet points)\n"
        f"4. Key Definitions & Terminology\n"
        f"Address the user as 'Sir'."
    )

    return _call_study_llm(prompt)


def explain_concept(concept_or_chapter: str, style: str = "detailed") -> str:
    """
    Explain concepts in multiple styles:
    beginner (ELI5), simple, detailed, technical, exam-oriented, intermediate, expert.
    """
    session = get_study_session()
    doc = session.get_active_doc()
    context = doc["raw_text"][:20000] if doc else "General Academic Context"

    style_prompts = {
        "beginner": "Explain this in simple, everyday language as if explaining to a beginner or teenager. Use analogies and real-world examples.",
        "simple": "Explain in simple, crystal-clear language with zero jargon.",
        "detailed": "Provide a thorough, comprehensive explanation covering background, mechanics, significance, and examples.",
        "technical": "Provide a rigorous, technical, and mathematically precise explanation using academic terminology.",
        "exam": "Provide an exam-oriented explanation focusing on high-yield marks, key steps, common exam questions, and marking criteria.",
        "intermediate": "Provide a balanced explanation suited for someone with basic knowledge. Focus on linking foundations to practical usage without getting bogged down in extreme technical details.",
        "expert": "Provide an expert-level explanation highlighting advanced architectures, production challenges, optimizations, edge cases, and industry standards."
    }

    style_instruction = style_prompts.get(style.lower(), style_prompts["detailed"])

    prompt = (
        f"Task: Explain '{concept_or_chapter}'.\n"
        f"Explanation Style: {style.upper()} ({style_instruction})\n\n"
        f"Study Material Context:\n{context}\n\n"
        f"Ensure your response has clear markdown structure, real-world examples, and addresses the user as 'Sir'."
    )

    return _call_study_llm(prompt)


def extract_formulas() -> str:
    """Extract all mathematical formulas, equations, units, and rules."""
    session = get_study_session()
    doc = session.get_active_doc()
    if not doc:
        return "Sir, please load a document first to extract formulas."

    prompt = (
        f"Task: Extract all mathematical formulas, equations, physical constants, laws, and chemical reactions from the study material.\n\n"
        f"Document: {doc['title']}\n"
        f"Content:\n{doc['raw_text'][:25000]}\n\n"
        f"Format as:\n"
        f"### 📐 Formulas & Equations\n"
        f"| Formula / Law | Variables & Meaning | Key Units / Applications |\n"
        f"| --- | --- | --- |\n"
        f"Followed by brief explanations of key symbols. If no formulas exist, list key quantitative rules."
    )
    return _call_study_llm(prompt)


def extract_key_points() -> str:
    """Extract key points and high-yield notes."""
    session = get_study_session()
    doc = session.get_active_doc()
    if not doc:
        return "Sir, please load study material first."

    prompt = (
        f"Task: Extract ALL essential key points, main notes, core concepts, and high-yield details from this study material.\n\n"
        f"Document: {doc['title']}\n"
        f"Content:\n{doc['raw_text'][:25000]}\n\n"
        f"Format as a comprehensive, well-structured bulleted list of notes covering every key section. Do not truncate or omit important details. Address the user as 'Sir'."
    )
    return _call_study_llm(prompt)



def find_important_definitions() -> str:
    """Extract definitions and glossaries."""
    session = get_study_session()
    doc = session.get_active_doc()
    if not doc:
        return "Sir, please load study material first."

    prompt = (
        f"Task: Find and define all important terms, jargon, and concepts from the material.\n\n"
        f"Content:\n{doc['raw_text'][:25000]}\n\n"
        f"Format as a clean Markdown Glossary table: | Term | Definition | Context/Example |"
    )
    return _call_study_llm(prompt)


def get_important_topics() -> str:
    """Identify the most important/high-yield exam topics."""
    session = get_study_session()
    doc = session.get_active_doc()
    if not doc:
        return "Sir, please load study material first."

    prompt = (
        f"Task: Analyze the material and list the top high-yield topics most likely to appear on exams or technical interviews.\n\n"
        f"Content:\n{doc['raw_text'][:25000]}\n\n"
        f"Rank them by priority (High, Medium, Critical) with a brief justification for each."
    )
    return _call_study_llm(prompt)


def generate_flashcards() -> str:
    """Generate Q&A flashcards for spaced repetition."""
    session = get_study_session()
    doc = session.get_active_doc()
    if not doc:
        return "Sir, please load study material first."

    prompt = (
        f"Task: Create 8-12 high-yield flashcards from this study material.\n\n"
        f"Content:\n{doc['raw_text'][:20000]}\n\n"
        f"Format as:\n"
        f"### 🎴 Flashcards for Revision\n\n"
        f"| Card # | Front (Question / Prompt) | Back (Answer / Explanation) |\n"
        f"| --- | --- | --- |\n"
    )
    return _call_study_llm(prompt)


def generate_revision_notes() -> str:
    """Create clean, exam-ready revision notes."""
    session = get_study_session()
    doc = session.get_active_doc()
    if not doc:
        return "Sir, please load study material first."

    prompt = (
        f"Task: Generate clean, master exam revision notes from this study material.\n\n"
        f"Document: {doc['title']}\n"
        f"Content:\n{doc['raw_text'][:25000]}\n\n"
        f"Include:\n"
        f"- Quick Mind-Map Outline\n"
        f"- Core Concepts & Definitions\n"
        f"- Common Pitfalls / Mistakes to Avoid in Exams\n"
        f"- Memory Tricks / Mnemonics (if applicable)\n"
    )
    return _call_study_llm(prompt)


def generate_questions(q_type: str = "all", num_questions: Optional[int] = None) -> str:
    """
    Generate questions (MCQs, short answer, long answer, interview).
    """
    session = get_study_session()
    doc = session.get_active_doc()
    if not doc:
        return "Sir, please load study material first."

    # Parse count
    count = 5
    if num_questions is not None:
        count = max(1, min(int(num_questions), 100))
    else:
        # Default defaults
        if q_type.lower() == "mcq":
            count = 20
        else:
            count = 5

    type_instructions = {
        "mcq": f"Generate exactly {count} Multiple-Choice Questions (MCQs) with 4 options each and answer key at the bottom.",
        "short": f"Generate exactly {count} Short Answer Questions with target length and model answers.",
        "long": f"Generate exactly {count} Long Answer / Essay Questions with marking rubrics and model answers.",
        "interview": f"Generate exactly {count} Technical / Conceptual Interview Questions with model answers and evaluation criteria.",
        "all": f"Generate a balanced set of {count} questions (including MCQs, Short Answer, and Interview questions) with complete answers."
    }

    instruction = type_instructions.get(q_type.lower(), type_instructions["all"])

    prompt = (
        f"Task: {instruction}\n\n"
        f"Document: {doc['title']}\n"
        f"Content:\n{doc['raw_text'][:25000]}\n\n"
        f"Address the user as 'Sir'."
    )
    return _call_study_llm(prompt)



# ============================================================================
# INTERACTIVE QUIZ MODE (One question at a time)
# ============================================================================

def start_interactive_quiz(num_questions: int = 5) -> str:
    """Start an interactive quiz session where questions are asked one by one."""
    session = get_study_session()
    doc = session.get_active_doc()
    if not doc:
        return "Sir, please load a study document before starting a quiz."

    # Generate quiz questions via LLM
    prompt = (
        f"Task: Generate exactly {num_questions} high-quality quiz questions based on this document.\n"
        f"Document: {doc['title']}\n"
        f"Content:\n{doc['raw_text'][:20000]}\n\n"
        f"FORMAT REQUIREMENT:\n"
        f"Return ONLY valid JSON format with a list of objects:\n"
        f"[\n"
        f'  {{"question": "Question text...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "answer": "A", "explanation": "Why A is correct..."}},\n'
        f"  ...\n"
        f"]"
    )

    json_str = _call_study_llm(prompt, system_override="You are a quiz generator. Output ONLY raw JSON list of question objects. Do not add markdown backticks.")
    
    # Clean JSON
    json_str = json_str.replace("```json", "").replace("```", "").strip()

    try:
        questions = json.loads(json_str)
    except Exception:
        # Fallback manual parsing if JSON parsing fails
        questions = [
            {
                "question": f"Based on {doc['title']}, what is the primary core concept discussed?",
                "options": ["A) Main Topic Overview", "B) Secondary Option", "C) Alternative View", "D) None of the above"],
                "answer": "A",
                "explanation": "Main Topic Overview represents the core theme of the document."
            }
        ]

    session.quiz_state = {
        "active": True,
        "topic": doc["title"],
        "questions": questions,
        "current_index": 0,
        "user_answers": [],
        "score": 0
    }

    q1 = questions[0]
    options_formatted = "\n".join(q1.get("options", []))

    response = (
        f"📝 **Interactive Quiz Started!**\n"
        f"**Topic**: `{doc['title']}` | **Total Questions**: {len(questions)}\n\n"
        f"--- \n"
        f"**Question 1 of {len(questions)}**:\n"
        f"{q1['question']}\n\n"
        f"{options_formatted}\n\n"
        f"👉 *Reply with your answer (e.g. 'A' or 'Option B') to move to the next question!*"
    )
    return response


def handle_quiz_answer(user_input: str) -> str:
    """Evaluate current quiz answer and advance to next question or show final score."""
    session = get_study_session()
    q_state = session.quiz_state

    if not q_state.get("active") or not q_state.get("questions"):
        return None

    idx = q_state["current_index"]
    questions = q_state["questions"]
    curr_q = questions[idx]

    user_ans = user_input.strip().lower()
    correct_ans = curr_q.get("answer", "A").strip().lower()

    # Smart matching:
    is_correct = False
    
    # 1. Check if user input is/starts with the correct option letter (e.g. "a", "option a", "a)", "a.")
    user_letter_match = re.match(r'^(?:option\s+)?([a-d])(?:\b|\)|:|\.)', user_ans)
    if user_letter_match:
        user_letter = user_letter_match.group(1)
        if user_letter == correct_ans:
            is_correct = True

    # 2. Check if user input matches correct answer option text
    if not is_correct:
        correct_option_text = ""
        options = curr_q.get("options", [])
        for opt in options:
            opt_clean = opt.strip()
            # Find the option string matching correct letter
            if opt_clean.lower().startswith(correct_ans):
                # Strip leading "A)", "A.", "A -", "A:" etc.
                parts = re.split(r'^[a-d][\s\)\.\-:]+', opt_clean, flags=re.IGNORECASE)
                if len(parts) > 1:
                    correct_option_text = parts[1].strip().lower()
                else:
                    correct_option_text = opt_clean.lower()
                break
        
        if correct_option_text:
            # Clean punctuation from correct_option_text and user_ans for comparison
            text_clean = re.sub(r'[^\w\s]', '', correct_option_text).strip()
            ans_clean = re.sub(r'[^\w\s]', '', user_ans).strip()
            if text_clean and ans_clean:
                if text_clean == ans_clean:
                    is_correct = True
                elif len(ans_clean) > 2 and (text_clean in ans_clean or ans_clean in text_clean):
                    is_correct = True

    if is_correct:
        q_state["score"] += 1
        feedback = "✅ **Correct, Sir!**"
    else:
        feedback = f"❌ **Not quite, Sir.** The correct answer was **{correct_ans.upper()}**."

    explanation = curr_q.get("explanation", "")
    q_state["user_answers"].append({"user": user_input, "correct": is_correct})

    q_state["current_index"] += 1
    next_idx = q_state["current_index"]

    if next_idx < len(questions):
        next_q = questions[next_idx]
        next_options = "\n".join(next_q.get("options", []))
        return (
            f"{feedback}\n"
            f"💡 *Explanation*: {explanation}\n\n"
            f"---\n"
            f"**Question {next_idx + 1} of {len(questions)}**:\n"
            f"{next_q['question']}\n\n"
            f"{next_options}\n\n"
            f"👉 *Reply with your answer for Question {next_idx + 1}.*"
        )
    else:
        # Quiz complete!
        q_state["active"] = False
        final_score = q_state["score"]
        total = len(questions)
        pct = int((final_score / total) * 100)

        history_formatted = []
        for i, q in enumerate(questions):
            ans_info = q_state["user_answers"][i] if i < len(q_state["user_answers"]) else {"user": "No answer", "correct": False}
            history_formatted.append(
                f"Question {i+1}: {q['question']}\n"
                f"Correct Answer: {q.get('answer', '')}\n"
                f"User Answer: {ans_info['user']} (Correct: {ans_info['correct']})\n"
            )
        history_str = "\n".join(history_formatted)

        doc = session.get_active_doc()
        doc_title = doc["title"] if doc else "loaded document"

        prompt = (
            f"Task: Generate a comprehensive quiz completion report and study review for the user.\n"
            f"Document Title: {doc_title}\n"
            f"Quiz Details:\n"
            f"- Total Questions: {total}\n"
            f"- Correct Answers: {final_score}\n"
            f"- Score Percentage: {pct}%\n\n"
            f"Questions and Answers History:\n{history_str}\n\n"
            f"Provide a structured analysis including:\n"
            f"1. A quick encouraging evaluation (e.g. grade, level) addressing the user as 'Sir'.\n"
            f"2. Weak Topics / Gap Analysis: Identify exactly which concepts or topics the user got wrong.\n"
            f"3. Revision Recommendations: Suggest specific sections, chapters, or concepts to focus on.\n"
            f"4. Propose Next Steps: Offer to start a new quiz, explain the concepts they missed in detail, or generate custom revision notes."
        )

        analysis = _call_study_llm(prompt)

        return (
            f"{feedback}\n"
            f"💡 *Explanation*: {explanation}\n\n"
            f"🎉 **Quiz Completed!**\n"
            f"• **Final Score**: `{final_score} / {total}` ({pct}%)\n\n"
            f"{analysis}"
        )


# ============================================================================
# MULTI-DOCUMENT COMPARISON & STRICT DOCUMENT QA
# ============================================================================

def compare_documents() -> str:
    """Compare all loaded documents in the session."""
    session = get_study_session()
    materials = session.loaded_materials

    if len(materials) < 2:
        return "Sir, please load at least 2 documents to perform a comparative analysis."

    docs_info = "\n\n".join([f"=== {d['title']} ===\n{d['raw_text'][:15000]}" for d in materials.values()])

    prompt = (
        f"Task: Perform a thorough comparative analysis between the uploaded study documents.\n\n"
        f"{docs_info}\n\n"
        f"Structure your analysis as:\n"
        f"1. Executive Comparison Overview\n"
        f"2. Similarities & Overlapping Themes\n"
        f"3. Key Differences & Contrasting Approaches (Use a Markdown Table)\n"
        f"4. Synthesis & Key Takeaways\n"
        f"Address the user as 'Sir'."
    )
    return _call_study_llm(prompt)


def retrieve_relevant_chunks(query: str, limit_chunks: int = 5, chunk_size: int = 1200, overlap: int = 200) -> str:
    """
    Perform local RAG: split text into chunks and retrieve the most relevant ones using a pure-Python TF-IDF/BM25 algorithm.
    """
    session = get_study_session()
    doc = session.get_active_doc()
    if not doc:
        return ""

    raw_text = doc.get("raw_text", "")
    if len(raw_text) <= 20000:
        # Document is small, return full text
        return raw_text

    # 1. Chunking
    chunks = []
    start = 0
    while start < len(raw_text):
        end = start + chunk_size
        chunks.append(raw_text[start:end])
        start += chunk_size - overlap

    # 2. Tokenize query & chunks
    import string
    def tokenize(text):
        text = text.lower()
        # strip punctuation
        text = text.translate(str.maketrans("", "", string.punctuation))
        return [w for w in text.split() if len(w) > 2] # ignore small words

    query_tokens = tokenize(query)
    if not query_tokens:
        return "\n\n".join(chunks[:limit_chunks])

    # 3. Calculate IDF for query tokens across chunks
    import math
    chunk_tokens_list = [tokenize(c) for c in chunks]
    num_chunks = len(chunks)
    
    idf = {}
    for token in query_tokens:
        doc_count = sum(1 for c_tokens in chunk_tokens_list if token in c_tokens)
        # Avoid division by zero
        idf[token] = math.log((num_chunks - doc_count + 0.5) / (doc_count + 0.5) + 1.0)

    # 4. Score each chunk using TF-IDF / BM25
    chunk_scores = []
    for idx, c_tokens in enumerate(chunk_tokens_list):
        score = 0.0
        token_counts = {}
        for t in c_tokens:
            token_counts[t] = token_counts.get(t, 0) + 1
            
        chunk_len = len(c_tokens)
        if chunk_len == 0:
            chunk_scores.append((idx, 0.0))
            continue
            
        for token in query_tokens:
            if token in token_counts:
                tf = token_counts[token] / chunk_len
                score += tf * idf.get(token, 0.0)
        chunk_scores.append((idx, score))

    # 5. Sort and retrieve top chunks
    chunk_scores.sort(key=lambda x: x[1], reverse=True)
    top_indices = [idx for idx, score in chunk_scores[:limit_chunks]]
    
    # Sort indices so retrieved content flows in original document order
    top_indices.sort()
    
    retrieved = []
    for idx in top_indices:
        retrieved.append(f"--- [RAG Context Chunk {idx+1}] ---\n{chunks[idx]}")
        
    return "\n\n".join(retrieved)


def answer_document_query(query: str, strict: bool = False) -> str:
    """
    Answer user questions based on loaded material.
    If strict=True, never hallucinate — if not in document, state it's missing.
    """
    session = get_study_session()
    doc = session.get_active_doc()
    if not doc:
        return "Sir, no study material is loaded yet. Please ask me to read a PDF, URL, or document first."

    # Perform RAG retrieval if document is large
    context = retrieve_relevant_chunks(query, limit_chunks=5)
    if not context:
        context = session.get_combined_text()

    strict_instruction = ""
    if strict or session.strict_mode:
        strict_instruction = (
            "STRICT GROUNDING RULE: Answer the question ONLY using facts explicitly present in the study material context below. "
            "If the answer CANNOT be found in the provided material, you MUST respond exactly: "
            "'Sir, that information is not present in the provided study material.' "
            "Do not add any additional explanations or assumptions."
        )

    prompt = (
        f"Study Material Context:\n{context}\n\n"
        f"User Question: {query}\n\n"
        f"{strict_instruction}\n"
        f"Address the user as 'Sir' and explain clearly."
    )
    return _call_study_llm(prompt)


def track_reading_progress(page: Optional[int] = None) -> str:
    """Track or continue reading progress."""
    session = get_study_session()
    doc = session.get_active_doc()

    if not doc:
        return "Sir, no study document is currently open."

    total_pages = doc["page_count"]

    if page is not None:
        session.current_page = max(1, min(page, total_pages))
        return f"Sir, I have updated your reading progress to **Page {session.current_page} of {total_pages}** for `{doc['title']}`."

    curr_p = session.current_page
    pages = doc.get("pages", [])
    
    page_content = ""
    for p in pages:
        if p.get("page_number") == curr_p:
            page_content = p.get("content", "")
            break

    if not page_content and pages:
        page_content = pages[0].get("content", "")

    prompt = (
        f"Task: Continue reading and explaining Page {curr_p} of {total_pages} from '{doc['title']}'.\n\n"
        f"Page Content:\n{page_content[:3000]}\n\n"
        f"Provide a clear, engaging explanation of this page's content as a professor teaching the user. Address the user as 'Sir'."
    )
    return _call_study_llm(prompt)


def translate_document(target_lang: str = "English") -> str:
    """Translate the active document key highlights/revision notes into another language."""
    session = get_study_session()
    doc = session.get_active_doc()
    if not doc:
        return "Sir, please load a study document first to translate."

    prompt = (
        f"Task: Extract the key highlights and revision notes from the document and translate them into {target_lang}.\n"
        f"Document: {doc['title']}\n"
        f"Content Sample:\n{doc['raw_text'][:15000]}\n\n"
        f"Provide a clear, structured translation. Address the user as 'Sir'."
    )
    return _call_study_llm(prompt)


def generate_study_roadmap() -> str:
    """Generate a step-by-step revision and study roadmap based on the loaded document."""
    session = get_study_session()
    doc = session.get_active_doc()
    if not doc:
        return "Sir, please load a study document first to generate a roadmap."

    prompt = (
        f"Task: Create a highly actionable, structured study and revision roadmap based on this document.\n"
        f"Document: {doc['title']}\n"
        f"Content:\n{doc['raw_text'][:20000]}\n\n"
        f"FORMAT REQUIREMENT:\n"
        f"1. Timeline / Phase-based breakdown (e.g. Day 1-2, Day 3-4, etc.)\n"
        f"2. Key Focus Areas for each phase\n"
        f"3. High-yield topics to study first\n"
        f"4. Suggested self-evaluation checkpoints\n"
        f"Address the user as 'Sir'."
    )
    return _call_study_llm(prompt)


def explain_visuals() -> str:
    """Explain tables, diagrams, and charts in the active document."""
    session = get_study_session()
    doc = session.get_active_doc()
    if not doc:
        return "Sir, please load a study document first."

    prompt = (
        f"Task: Extract, describe, and analyze all tables, diagrams, charts, schemas, and flowcharts mentioned or present in the document.\n"
        f"Document: {doc['title']}\n"
        f"Content:\n{doc['raw_text'][:25000]}\n\n"
        f"Examine the text for any data tables, figures, charts, or structural diagrams. "
        f"Explain their meaning, target data, structure, and why they are important to the overall topic. "
        f"If no explicit figures are found, synthesize key structured relationships into a conceptual schema or flowchart explanation for the user. "
        f"Address the user as 'Sir' and format with clear markdown."
    )
    return _call_study_llm(prompt)

