# 📺 YouTube Summary Generator

A Streamlit web app that takes a YouTube video link, extracts its transcript, and generates a concise AI-powered summary using **Google Gemini**.

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B)
![License](https://img.shields.io/badge/License-MIT-green)

## Features

- Accepts standard YouTube URLs, short links (`youtu.be`), embeds, and Shorts
- Fetches transcripts (prefers English; falls back / translates when possible)
- Summarizes with **Gemini 2.5 Flash** into clear bullet-point takeaways
- Adjustable summary length
- Video thumbnail preview
- Download summary as `.txt`
- View full transcript in an expander

## Demo flow

1. Paste your Gemini API key in the sidebar  
2. Paste a YouTube video URL  
3. Click **Generate Summary**

## Requirements

- Python 3.9+
- A free [Google AI Studio API key](https://aistudio.google.com/apikey)

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/youtube-summary-generator.git
cd youtube-summary-generator

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run the app

```bash
streamlit run app.py
```

Open the URL shown in the terminal (usually http://localhost:8501).

## Notes

- The video must have captions/subtitles available (auto-generated or manual).
- Very long videos may produce long transcripts; Gemini 2.5 Flash handles large context well, but extremely long content can still hit limits.
- Your API key is used only in the current browser session and is never stored by the app.

## Tech stack

| Component             | Library / Service       |
|-----------------------|-------------------------|
| UI                    | Streamlit               |
| Transcript extraction | youtube-transcript-api  |
| Generative AI         | Google Gemini 2.5 Flash |

## Project structure

```
youtube-summary-generator/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
├── LICENSE             # MIT License
├── .gitignore
└── README.md
```

## License

MIT
