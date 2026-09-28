# 📺 YouTube Summary Generator

Summarize **YouTube videos** or **pasted transcript text** with Google Gemini.

![Python](https://img.shields.io/badge/Python-3.9+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B)
![License](https://img.shields.io/badge/License-MIT-green)

## Features

- **Two input modes**
  - YouTube video URL (captions → audio fallback)
  - Paste transcript text (or upload `.txt`) — always works
- AI summaries with **Gemini 2.5 Flash**
- Adjustable summary length
- Download summary as `.txt`

## Why paste-text mode?

YouTube often blocks caption requests from cloud servers (Streamlit Cloud).  
If that happens: open the video on YouTube → **⋯ → Show transcript** → copy → paste in the app.

## Requirements

- Python 3.9+
- Free [Gemini API key](https://aistudio.google.com/apikey)

## Install & run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Cloud

1. Push this folder to GitHub  
2. [share.streamlit.io](https://share.streamlit.io) → New app → select repo → `app.py`  
3. Paste Gemini key in the sidebar when using the app  

## Project structure

```
youtube-summary-generator/
├── app.py
├── requirements.txt
├── LICENSE
├── .gitignore
└── README.md
```

## License

MIT
