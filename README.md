# 🥁 AI-Powered Drum Transcription System

## 🎯 Overview
An intelligent system that transcribes drum performances into musical notation using AI/ML. Instead of traditional audio frequency analysis, this project leverages deep learning to identify and separate individual drum instruments for higher accuracy.

## ✨ Features

- **AI-Powered Detection** - Uses machine learning to identify drum hits with higher accuracy than traditional FFT-based methods
- **Instrument Separation** - Isolates individual drum components (snare, kick, hi-hat, etc.) before transcription
- **Real-time Processing** - Processes video/audio input with low latency
- **Interactive Frontend** - Visualizes drum notation in real-time
- **Database Backend** - PostgreSQL for efficient storage and retrieval of transcriptions

## 🛠 Tech Stack

### Backend
- **Python 3.10+**
- **FastAPI** - Modern, fast web framework
- **SQLAlchemy** - ORM for database interactions
- **PostgreSQL** - Primary database
- **Celery** - For background processing tasks

### AI/ML Components
- **Librosa** - Audio analysis
- **PyTorch** - Deep learning framework
- **Spleeter** - For source separation
- **OpenCV** - Video processing

### Frontend
- **React.js** - Frontend framework
- **VexFlow** - Music notation rendering
- **Web Audio API** - For audio visualization

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- PostgreSQL 14+
- Node.js 16+
- FFmpeg

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/drum-ai-transcriber.git
   cd drum-notation-backend
   ```

2. **Set up Python environment**
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory:
   ```env
   # Database
   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/drum_ai
   
   # AI/ML Settings
   MODEL_PATH=./models/drum_transcriber.pth
   
   # App Settings
   DEBUG=True
   ```

5. **Initialize database**
   ```bash
   alembic upgrade head
   ```

6. **Start the development server**
   ```bash
   uvicorn app.main:app --reload
   ```

## 🎥 How It Works

1. **Input Processing**
   - Accepts video/audio input
   - Extracts audio track
   
2. **Source Separation**
   - Uses AI to separate drum components
   - Identifies individual drum instruments
   
3. **Transcription**
   - Converts audio events to MIDI
   - Maps to standard drum notation
   
4. **Visualization**
   - Renders interactive drum notation
   - Syncs with original audio

## 📂 Project Structure

```
drum-notation-backend/
├── app/
│   ├── api/               # API routes
│   ├── core/              # Core functionality
│   ├── models/            # Database models
│   ├── services/          # Business logic
│   │   ├── audio/         # Audio processing
│   │   ├── ai/            # ML models
│   │   └── transcription/ # Notation logic
│   └── main.py            # FastAPI app
├── tests/                 # Test suite
├── alembic/               # Database migrations
├── .env                   # Environment variables
└── requirements.txt       # Python dependencies
```

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments
- [Librosa](https://librosa.org/) for audio analysis
- [VexFlow](https://www.vexflow.com/) for music notation
- [Spleeter](https://research.deezer.com/technology/spleeter/) for source separation