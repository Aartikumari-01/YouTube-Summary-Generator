"""
YouTube / Text Summary Generator
- Mode 1: YouTube URL → captions or audio → summary
- Mode 2: Paste transcript text → summary
"""

import os
import re
import tempfile
import time
import shutil
from pathlib import Path

import streamlit as st
import google.generativeai as genai

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import (
        TranscriptsDisabled,
        NoTranscriptFound,
        VideoUnavailable,
    )
    HAS_YTT = True
except ImportError:
    HAS_YTT = False

try:
    import yt_dlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False

st.set_page_config(
    page_title="YouTube Summary Generator",
    page_icon="📺",
    layout="centered",
)

st.markdown(
    """
    <style>
    .main-title { font-size: 2.2rem; font-weight: 700; text-align: center; margin-bottom: 0.25rem; }
    .subtitle { text-align: center; color: #666; margin-bottom: 1.5rem; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3rem; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)


def extract_video_id(url: str) -> str | None:
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
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", url):
        return url
    return None


def _clean_vtt(raw: str) -> str:
    lines, seen = [], set()
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(("WEBVTT", "Kind:", "Language:")):
            continue
        if re.match(r"^\d+$", line) or "-->" in line or re.match(r"^\d{2}:\d{2}", line):
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line and line not in seen:
            seen.add(line)
            lines.append(line)
    return " ".join(lines)


def transcript_via_api(video_id: str) -> str:
    if not HAS_YTT:
        raise RuntimeError("youtube-transcript-api not installed")
    langs = ["en", "en-US", "en-GB", "en-IN", "hi", "es", "fr", "de"]
    try:
        data = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
        text = " ".join(i["text"] for i in data)
        if text.strip():
            return text
    except TranscriptsDisabled:
        raise ValueError("CAPTIONS_DISABLED")
    except NoTranscriptFound:
        pass
    except VideoUnavailable:
        raise ValueError("Video unavailable (private, deleted, or region-blocked).")
    except Exception as e:
        err = str(e).lower()
        if "blocking" in err or "ip" in err or "blocked" in err:
            raise ValueError("IP_BLOCKED")
        raise

    try:
        tl = YouTubeTranscriptApi.list_transcripts(video_id)
        for fn in (
            lambda: tl.find_manually_created_transcript(["en", "en-US"]),
            lambda: tl.find_generated_transcript(["en", "en-US", "en-IN"]),
            lambda: tl.find_transcript(["en", "en-US", "en-GB", "hi"]),
        ):
            try:
                t = fn()
                data = t.fetch()
                text = " ".join(i["text"] for i in data)
                if text.strip():
                    return text
            except Exception:
                continue
        for t in tl:
            try:
                if getattr(t, "is_translatable", False):
                    t = t.translate("en")
                data = t.fetch()
                text = " ".join(i["text"] for i in data)
                if text.strip():
                    return text
            except Exception:
                continue
    except Exception as e:
        err = str(e).lower()
        if "blocking" in err or "ip" in err or "blocked" in err:
            raise ValueError("IP_BLOCKED")
        if "disabled" in err:
            raise ValueError("CAPTIONS_DISABLED")
    raise ValueError("NO_CAPTIONS")


def transcript_via_ytdlp(video_id: str) -> str:
    if not HAS_YTDLP:
        raise RuntimeError("yt-dlp not installed")
    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmp:
        opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en", "en-US", "en-GB", "hi"],
            "subtitlesformat": "vtt",
            "outtmpl": str(Path(tmp) / "%(id)s"),
            "quiet": True,
            "no_warnings": True,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except Exception as e:
            raise ValueError(f"yt-dlp subs failed: {e}")

        vtts = list(Path(tmp).glob("*.vtt"))
        if not vtts:
            raise ValueError("NO_CAPTIONS")
        vtts.sort(key=lambda p: (0 if ".en" in p.name else 1, p.name))
        text = _clean_vtt(vtts[0].read_text(encoding="utf-8", errors="ignore"))
        if not text.strip():
            raise ValueError("NO_CAPTIONS")
        return text


def get_caption_transcript(video_id: str) -> tuple[str, str]:
    errors = []
    if HAS_YTT:
        try:
            return transcript_via_api(video_id), "captions (API)"
        except ValueError as e:
            errors.append(str(e))
        except Exception as e:
            errors.append(str(e))

    if HAS_YTDLP:
        try:
            return transcript_via_ytdlp(video_id), "captions (yt-dlp)"
        except ValueError as e:
            errors.append(str(e))
        except Exception as e:
            errors.append(str(e))

    joined = " ".join(errors)
    if "IP_BLOCKED" in joined or "blocking" in joined.lower():
        raise ValueError("IP_BLOCKED")
    if "CAPTIONS_DISABLED" in joined or "disabled" in joined.lower():
        raise ValueError("CAPTIONS_DISABLED")
    raise ValueError("NO_CAPTIONS")


def download_audio(video_id: str, max_duration_sec: int = 1800) -> Path:
    if not HAS_YTDLP:
        raise RuntimeError("yt-dlp required for audio fallback")

    url = f"https://www.youtube.com/watch?v={video_id}"
    tmpdir = tempfile.mkdtemp(prefix="yt_audio_")
    outtmpl = str(Path(tmpdir) / "audio.%(ext)s")

    info_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(info_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    duration = info.get("duration") or 0
    if duration > max_duration_sec:
        raise ValueError(
            f"Video is too long ({duration // 60} min). "
            f"Audio fallback supports up to {max_duration_sec // 60} minutes."
        )

    opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "64",
            }
        ],
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception:
        opts.pop("postprocessors", None)
        opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

    files = list(Path(tmpdir).glob("audio.*"))
    if not files:
        raise ValueError("Could not download audio from this video.")
    return files[0]


def summarize_from_audio(audio_path: Path, api_key: str, max_words: int) -> str:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    uploaded = genai.upload_file(str(audio_path))
    for _ in range(60):
        meta = genai.get_file(uploaded.name)
        if meta.state.name == "ACTIVE":
            break
        if meta.state.name == "FAILED":
            raise ValueError("Gemini failed to process the audio file.")
        time.sleep(2)
    else:
        raise ValueError("Timed out waiting for Gemini to process audio.")

    prompt = f"""Listen to this YouTube video audio and produce a clear, concise summary in bullet points.
Focus on the main ideas, key insights, and important takeaways.
Keep the entire summary under {max_words} words.
If speech is unclear or missing, say so briefly.
Do not invent content that is not in the audio.
"""
    response = model.generate_content([prompt, uploaded])
    try:
        genai.delete_file(uploaded.name)
    except Exception:
        pass
    if not getattr(response, "text", None):
        raise ValueError("Gemini returned an empty response for the audio.")
    return response.text


def summarize_from_text(transcript: str, api_key: str, max_words: int) -> str:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    if len(transcript) > 80000:
        transcript = transcript[:80000] + "\n\n[Transcript truncated]"
    prompt = f"""You are an expert content summarizer.
Given the transcript / text below, produce a clear, concise summary in bullet points.
Focus on the main ideas, key insights, and important takeaways.
Keep the entire summary under {max_words} words.
Do not invent information that is not in the text.

Text:
{transcript}
"""
    response = model.generate_content(prompt)
    if not getattr(response, "text", None):
        raise ValueError("Gemini returned an empty response. Check API key / quota.")
    return response.text


def main():
    st.markdown(
        '<p class="main-title">📺 YouTube Summary Generator</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="subtitle">Summarize from a YouTube link <b>or</b> paste transcript text</p>',
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("⚙️ Settings")
        api_key = st.text_input(
            "Google Gemini API Key",
            type="password",
            help="https://aistudio.google.com/apikey",
            placeholder="AIza...",
        )
        max_words = st.slider("Max summary length (words)", 100, 500, 250, 50)
        use_audio_fallback = st.checkbox(
            "YouTube: use audio if no captions",
            value=True,
            help="When using a YouTube URL, download audio and summarize speech if captions fail.",
        )
        st.markdown("---")
        st.markdown(
            "**API key**\n\n1. [Google AI Studio](https://aistudio.google.com/apikey)\n2. Create key → paste here"
        )
        st.markdown("---")
        st.info(
            "**Two ways to use**\n\n"
            "1. **YouTube URL** – fetch captions or audio\n"
            "2. **Paste text** – paste any transcript and summarize\n\n"
            "Paste-text mode always works (no YouTube IP issues)."
        )
        st.caption(f"API={'✓' if HAS_YTT else '✗'} · yt-dlp={'✓' if HAS_YTDLP else '✗'}")

    mode = st.radio(
        "Input type",
        ["YouTube video URL", "Paste transcript text"],
        horizontal=True,
    )

    youtube_url = ""
    pasted_text = ""

    if mode == "YouTube video URL":
        youtube_url = st.text_input(
            "YouTube Video URL",
            placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/...",
        )
    else:
        pasted_text = st.text_area(
            "Paste transcript / text here",
            height=220,
            placeholder="Paste the full transcript or any long text you want summarized...",
        )
        uploaded = st.file_uploader(
            "Or upload a .txt file",
            type=["txt", "md"],
        )
        if uploaded is not None:
            pasted_text = uploaded.read().decode("utf-8", errors="ignore")

    c1, c2 = st.columns(2)
    with c1:
        go = st.button("✨ Generate Summary", type="primary", use_container_width=True)
    with c2:
        if st.button("Clear", use_container_width=True):
            st.rerun()

    if not go:
        return

    if not api_key.strip():
        st.warning("Enter your Gemini API key in the sidebar.")
        return

    # ── Mode: paste text ─────────────────────────────────────────
    if mode == "Paste transcript text":
        if not pasted_text or len(pasted_text.strip()) < 30:
            st.warning("Please paste a longer transcript (at least a few sentences).")
            return

        st.info(f"Text length: **{len(pasted_text.split())} words**")

        with st.spinner("Generating summary with Gemini..."):
            try:
                summary = summarize_from_text(pasted_text.strip(), api_key.strip(), max_words)
            except Exception as e:
                st.error(f"Summarization failed: {e}")
                return

        st.success("Done · method: **pasted text**")
        st.markdown("### 📝 Summary")
        st.markdown(summary)
        st.download_button(
            "Download summary (.txt)",
            data=summary,
            file_name="text_summary.txt",
            mime="text/plain",
        )
        with st.expander("Original text"):
            st.text_area("Input", pasted_text, height=200, disabled=True)
        return

    # ── Mode: YouTube URL ────────────────────────────────────────
    if not youtube_url.strip():
        st.warning("Enter a YouTube URL.")
        return

    video_id = extract_video_id(youtube_url)
    if not video_id:
        st.error("Invalid YouTube URL.")
        return

    st.image(
        f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        use_container_width=True,
    )
    st.caption(f"Video ID: `{video_id}`")

    transcript = None
    method = None
    audio_path = None

    with st.spinner("Trying captions..."):
        try:
            transcript, method = get_caption_transcript(video_id)
        except ValueError as e:
            code = str(e)
            if code == "IP_BLOCKED":
                st.warning(
                    "YouTube blocked caption requests from this server. "
                    + ("Trying audio fallback..." if use_audio_fallback else
                       "Enable audio fallback, use **Paste transcript text**, or run locally.")
                )
            elif code in ("CAPTIONS_DISABLED", "NO_CAPTIONS"):
                st.warning(
                    "No captions for this video. "
                    + ("Trying audio fallback..." if use_audio_fallback else
                       "Enable audio fallback or paste the transcript manually.")
                )
            else:
                st.warning(f"Caption issue: {e}")

    if transcript is None and use_audio_fallback:
        if not HAS_YTDLP:
            st.error("yt-dlp required for audio fallback.")
            return
        with st.spinner("Downloading audio..."):
            try:
                audio_path = download_audio(video_id)
                method = "audio → Gemini"
            except Exception as e:
                st.error(f"Audio download failed: {e}")
                st.info(
                    "Tip: copy the transcript from YouTube (Show transcript) "
                    "and use **Paste transcript text** mode."
                )
                return

    if transcript is None and audio_path is None:
        st.error(
            "Could not get captions or audio.\n\n"
            "**Easiest fix:** On YouTube open the video → ⋯ → Show transcript → "
            "copy text → switch to **Paste transcript text** mode."
        )
        return

    with st.spinner("Generating summary with Gemini..."):
        try:
            if transcript is not None:
                summary = summarize_from_text(transcript, api_key.strip(), max_words)
            else:
                summary = summarize_from_audio(audio_path, api_key.strip(), max_words)
        except Exception as e:
            st.error(f"Summarization failed: {e}")
            return
        finally:
            if audio_path is not None:
                try:
                    shutil.rmtree(audio_path.parent, ignore_errors=True)
                except Exception:
                    pass

    st.success(f"Done · method: **{method}**")
    st.markdown("### 📝 Summary")
    st.markdown(summary)
    st.download_button(
        "Download summary (.txt)",
        data=summary,
        file_name=f"summary_{video_id}.txt",
        mime="text/plain",
    )
    if transcript:
        with st.expander("Full transcript"):
            st.text_area("Transcript", transcript, height=280, disabled=True)


if __name__ == "__main__":
    main()
