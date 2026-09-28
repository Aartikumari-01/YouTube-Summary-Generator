import re
import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import google.generativeai as genai

# Page config
st.set_page_config(
    page_title="YouTube Summary Generator",
    page_icon="📺",
    layout="centered",
)

# Custom CSS for a cleaner look
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 0.25rem;
    }
    .subtitle {
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3rem;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",
        r"(?:embed\/)([0-9A-Za-z_-]{11})",
        r"(?:shorts\/)([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    # Fallback: bare 11-char ID
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", url.strip()):
        return url.strip()
    return None


def get_transcript(video_id: str) -> str:
    """Fetch and concatenate transcript text for a video.

    Compatible with both youtube-transcript-api 0.6.x (class methods)
    and 1.x (instance methods).
    """
    try:
        # New API (1.x): instance methods
        if hasattr(YouTubeTranscriptApi, "list") and callable(
            getattr(YouTubeTranscriptApi, "list")
        ):
            ytt = YouTubeTranscriptApi()
            transcript_list = ytt.list(video_id)
        else:
            # Legacy API (0.6.x)
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        try:
            transcript = transcript_list.find_transcript(["en", "en-US", "en-GB"])
        except Exception:
            # First available transcript; translate to English when possible
            transcript = next(iter(transcript_list))
            if getattr(transcript, "language_code", "") != "en":
                try:
                    transcript = transcript.translate("en")
                except Exception:
                    pass

        fetched = transcript.fetch()

        # 1.x returns FetchedTranscript with .snippets; 0.6.x returns list of dicts
        if hasattr(fetched, "snippets"):
            texts = [s.text for s in fetched.snippets]
        else:
            texts = [entry["text"] for entry in fetched]

        return " ".join(texts)
    except TranscriptsDisabled:
        raise ValueError("Transcripts are disabled for this video.")
    except NoTranscriptFound:
        raise ValueError("No transcript found for this video.")
    except Exception as e:
        raise ValueError(f"Could not retrieve transcript: {str(e)}")


def generate_summary(transcript: str, api_key: str, max_words: int = 250) -> str:
    """Generate a concise summary using Google Gemini."""
    genai.configure(api_key=api_key)
    # Current Gemini Flash model (change if Google renames models)
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""You are an expert video summarizer.
Given the transcript of a YouTube video, produce a clear, concise summary in bullet points.
Focus on the main ideas, key insights, and important takeaways.
Keep the entire summary under {max_words} words.
Do not invent information that is not in the transcript.
If the transcript is incomplete or unclear, note that briefly.

Transcript:
{transcript}
"""
    response = model.generate_content(prompt)
    return response.text


def main():
    st.markdown('<p class="main-title">📺 YouTube Summary Generator</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">Paste a YouTube link and get a short AI-powered summary</p>',
        unsafe_allow_html=True,
    )

    # Sidebar for API key and settings
    with st.sidebar:
        st.header("⚙️ Settings")
        api_key = st.text_input(
            "Google Gemini API Key",
            type="password",
            help="Get a free key at https://aistudio.google.com/apikey",
            placeholder="AIza...",
        )
        max_words = st.slider("Max summary length (words)", 100, 500, 250, 50)
        st.markdown("---")
        st.markdown(
            "**How to get an API key**\n\n"
            "1. Go to [Google AI Studio](https://aistudio.google.com/apikey)\n"
            "2. Create an API key\n"
            "3. Paste it here (it stays only in this session)"
        )
        st.markdown("---")
        st.caption("Transcripts are fetched via youtube-transcript-api. Summaries use Gemini 2.5 Flash.")

    youtube_url = st.text_input(
        "YouTube Video URL",
        placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/...",
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        generate_btn = st.button("✨ Generate Summary", type="primary", use_container_width=True)
    with col2:
        clear_btn = st.button("Clear", use_container_width=True)

    if clear_btn:
        st.rerun()

    if generate_btn:
        if not youtube_url.strip():
            st.warning("Please enter a YouTube video URL.")
            return
        if not api_key.strip():
            st.warning("Please enter your Google Gemini API key in the sidebar.")
            return

        video_id = extract_video_id(youtube_url)
        if not video_id:
            st.error("Could not extract a valid YouTube video ID from the URL.")
            return

        # Show thumbnail
        st.image(f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg", use_container_width=True)
        st.caption(f"Video ID: `{video_id}`")

        with st.status("Processing video...", expanded=True) as status:
            status.update(label="Fetching transcript...", state="running")
            try:
                transcript = get_transcript(video_id)
            except ValueError as e:
                status.update(label="Failed", state="error")
                st.error(str(e))
                return

            if not transcript or len(transcript.strip()) < 50:
                status.update(label="Failed", state="error")
                st.error("Transcript is empty or too short to summarize.")
                return

            status.update(label="Generating AI summary...", state="running")
            try:
                summary = generate_summary(transcript, api_key, max_words)
            except Exception as e:
                status.update(label="Failed", state="error")
                st.error(f"Summarization failed: {str(e)}")
                return

            status.update(label="Done!", state="complete")

        st.markdown("### 📝 Summary")
        st.markdown(summary)

        # Download option
        st.download_button(
            label="Download summary as .txt",
            data=summary,
            file_name=f"youtube_summary_{video_id}.txt",
            mime="text/plain",
        )

        # Optional: expandable full transcript
        with st.expander("View full transcript"):
            st.text_area("Transcript", transcript, height=300, disabled=True)


if __name__ == "__main__":
    main()
