import re
import streamlit as st
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)
import google.generativeai as genai

# Page config
st.set_page_config(
    page_title="YouTube Summary Generator",
    page_icon="📺",
    layout="centered",
)

# Custom CSS
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
    url = url.strip()
    patterns = [
        r"(?:youtube\.com\/watch\?v=)([0-9A-Za-z_-]{11})",
        r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",
        r"(?:youtube\.com\/embed\/)([0-9A-Za-z_-]{11})",
        r"(?:youtube\.com\/shorts\/)([0-9A-Za-z_-]{11})",
        r"(?:youtube\.com\/live\/)([0-9A-Za-z_-]{11})",
        r"(?:v=)([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    # Bare 11-char ID
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", url):
        return url
    return None


def get_transcript(video_id: str) -> str:
    """
    Fetch transcript text for a YouTube video.
    Works with youtube-transcript-api 0.6.x (get_transcript / list_transcripts).
    """
    languages = ["en", "en-US", "en-GB", "en-IN", "hi", "es", "fr", "de", "pt", "ar"]
    last_error = None

    # Method 1: direct get_transcript with language preference
    try:
        transcript_data = YouTubeTranscriptApi.get_transcript(
            video_id, languages=languages
        )
        text = " ".join(item["text"] for item in transcript_data)
        if text.strip():
            return text
    except TranscriptsDisabled:
        raise ValueError(
            "Subtitles are disabled for this video. "
            "Please try a different video that has captions (CC) enabled."
        )
    except NoTranscriptFound:
        last_error = "No transcript found in preferred languages."
    except VideoUnavailable:
        raise ValueError("This video is unavailable (private, deleted, or region-blocked).")
    except Exception as e:
        last_error = str(e)

    # Method 2: list all available transcripts and pick the best one
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        try:
            transcript = transcript_list.find_manually_created_transcript(
                ["en", "en-US", "en-GB"]
            )
            data = transcript.fetch()
            return " ".join(item["text"] for item in data)
        except Exception:
            pass

        try:
            transcript = transcript_list.find_transcript(
                ["en", "en-US", "en-GB", "en-IN"]
            )
            data = transcript.fetch()
            return " ".join(item["text"] for item in data)
        except Exception:
            pass

        for transcript in transcript_list:
            try:
                if transcript.is_translatable:
                    translated = transcript.translate("en")
                    data = translated.fetch()
                else:
                    data = transcript.fetch()
                text = " ".join(item["text"] for item in data)
                if text.strip():
                    return text
            except Exception:
                continue

        raise ValueError(
            "No usable transcript found for this video. "
            "The video may not have captions in any language."
        )
    except TranscriptsDisabled:
        raise ValueError(
            "Subtitles are disabled for this video. "
            "Please try a different video that has captions (CC) enabled."
        )
    except NoTranscriptFound:
        raise ValueError(
            "No transcript available for this video. "
            "Open the video on YouTube and check if CC (captions) is available."
        )
    except ValueError:
        raise
    except Exception as e:
        msg = last_error or str(e)
        raise ValueError(f"Could not retrieve transcript: {msg}")


def generate_summary(transcript: str, api_key: str, max_words: int = 250) -> str:
    """Generate a concise summary using Google Gemini."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    max_chars = 80000
    if len(transcript) > max_chars:
        transcript = transcript[:max_chars] + "\n\n[Transcript truncated due to length]"

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
    if not response.text:
        raise ValueError(
            "Gemini returned an empty response. Try again or check your API key."
        )
    return response.text


def main():
    st.markdown(
        '<p class="main-title">📺 YouTube Summary Generator</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="subtitle">Paste a YouTube link and get a short AI-powered summary</p>',
        unsafe_allow_html=True,
    )

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
            "3. Paste it here"
        )
        st.markdown("---")
        st.info(
            "**Important:** The YouTube video must have captions/subtitles (CC) enabled. "
            "Videos with subtitles disabled cannot be summarized."
        )
        st.caption("Powered by youtube-transcript-api + Gemini 2.5 Flash")

    youtube_url = st.text_input(
        "YouTube Video URL",
        placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/...",
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        generate_btn = st.button(
            "✨ Generate Summary", type="primary", use_container_width=True
        )
    with col2:
        clear_btn = st.button("Clear", use_container_width=True)

    if clear_btn:
        st.rerun()

    if not generate_btn:
        return

    if not youtube_url.strip():
        st.warning("Please enter a YouTube video URL.")
        return
    if not api_key.strip():
        st.warning("Please enter your Google Gemini API key in the sidebar.")
        return

    video_id = extract_video_id(youtube_url)
    if not video_id:
        st.error(
            "Could not extract a valid YouTube video ID from the URL.\n\n"
            "Supported formats:\n"
            "- https://www.youtube.com/watch?v=VIDEO_ID\n"
            "- https://youtu.be/VIDEO_ID\n"
            "- https://www.youtube.com/shorts/VIDEO_ID"
        )
        return

    st.image(
        f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        use_container_width=True,
    )
    st.caption(f"Video ID: `{video_id}`")

    with st.spinner("Fetching transcript..."):
        try:
            transcript = get_transcript(video_id)
        except ValueError as e:
            st.error(str(e))
            st.markdown(
                "**What to do:**\n"
                "- Open the video on YouTube\n"
                "- Click the **CC** button to check if captions exist\n"
                "- Try another video that has English (or any) subtitles"
            )
            return
        except Exception as e:
            st.error(f"Unexpected error while fetching transcript: {e}")
            return

    if not transcript or len(transcript.strip()) < 30:
        st.error("Transcript is empty or too short to summarize.")
        return

    st.success(f"Transcript fetched ({len(transcript.split())} words)")

    with st.spinner("Generating AI summary with Gemini..."):
        try:
            summary = generate_summary(transcript, api_key.strip(), max_words)
        except Exception as e:
            st.error(f"Summarization failed: {e}")
            st.markdown(
                "**Common causes:**\n"
                "- Invalid or expired Gemini API key\n"
                "- API quota exceeded\n"
                "- Network issue — try again"
            )
            return

    st.markdown("### 📝 Summary")
    st.markdown(summary)

    st.download_button(
        label="Download summary as .txt",
        data=summary,
        file_name=f"youtube_summary_{video_id}.txt",
        mime="text/plain",
    )

    with st.expander("View full transcript"):
        st.text_area("Transcript", transcript, height=300, disabled=True)


if __name__ == "__main__":
    main()
