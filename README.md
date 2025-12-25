# 🥁 Drum Notation Backend

> **Production-Ready FastAPI Backend for Automatic Drum Transcription and Musical Notation Generation**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.68+-00a4a4?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.8+-3776ab?style=flat-square&logo=python)](https://python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13+-336791?style=flat-square&logo=postgresql)](https://postgresql.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red?style=flat-square)](https://sqlalchemy.org/)

---

## 🎯 Overview

The **Drum Notation Backend** is a comprehensive FastAPI-based system that automatically converts drum performances (video/audio) into professional musical notation. It provides a complete pipeline from media processing to AI-enhanced notation generation.

### ✨ Key Features

- 🎬 **Video & Audio Processing** - Upload and process drum performance videos
- 🎵 **Automatic Transcription** - Convert audio to structured drum notation
- 🤖 **AI Enhancement** - OpenAI-powered musical analysis and insights
- 📝 **Notation Export** - Generate professional sheet music formats
- ⚡ **Async Processing** - Background job processing for heavy operations
- 🔐 **Secure Authentication** - JWT-based user management
- 📊 **Structured Data** - JSON-based notation storage for frontend integration

### 🏆 Status: **PRODUCTION READY** ✅

All core modules are fully implemented, tested, and error-free. The backend is ready for ML integration and frontend connection.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- PostgreSQL 13+
- FFmpeg (for audio processing)
- Docker & Docker Compose (recommended)

### Docker Setup (Recommended)

1. **Clone and setup environment**
   ```bash
   git clone <repository-url>
   cd Drum-Notation-Backend
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Start services**
   ```bash
   docker-compose up -d
   ```

3. **Initialize database**
   ```bash
   docker exec drum_backend alembic upgrade head
   ```

4. **Access the API**
   - API: `http://localhost:8000`
   - Interactive docs: `http://localhost:8000/docs`
   - ReDoc: `http://localhost:8000/redoc`

### Manual Setup

1. **Clone repository**
   ```bash
   git clone <repository-url>
   cd Drum-Notation-Backend
   ```

2. **Setup Python environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your database and API keys
   ```

4. **Setup database**
   ```bash
   createdb drum_notation
   alembic upgrade head
   ```

5. **Run the application**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

---

## 🏗️ Architecture

### System Components

```
Frontend (React/Vue) ←→ ML Models (Python) ←→ External APIs
                ↓              ↓                ↓
        ┌─────────────────────────────────────────────┐
        │           FastAPI Backend                   │
        ├──────────┬──────────────┬──────────────────┤
        │ API      │ Business     │ Data Access      │
        │ - Routes │ - Services   │ - Models         │
        │ - Auth   │ - Processing │ - Database       │
        │ - Valid  │ - Jobs       │ - Storage        │
        └──────────┴──────────────┴──────────────────┘
                ↓              ↓                ↓
        PostgreSQL      File Storage      OpenAI API
```

### Core Modules

- **`users`** - Authentication and profile management
- **`roles`** - Role-based access control  
- **`media`** - Video/audio file management
- **`audio_processing`** - Audio extraction and analysis
- **`notation`** - Drum notation data and AI enrichment
- **`jobs`** - Background job processing
- **`vision`** - Computer vision utilities

---

## 🛠️ API Endpoints

### 🔐 Authentication
```
POST /auth/register     - User registration
POST /auth/login        - User login  
POST /auth/refresh      - Refresh JWT token
```

### 🎬 Media Management
```
POST /media/videos/upload           - Upload video file
GET  /media/videos/                 - List user's videos
GET  /media/videos/{video_id}       - Get video details
DELETE /media/videos/{video_id}     - Delete video
```

### ⚙️ Processing & Jobs
```
POST /jobs/process-video/{video_id} - Start video processing
GET  /jobs/{job_id}/status          - Get job status
POST /audio/extract/{video_id}      - Extract audio from video
POST /audio/detect-drums/{audio_id} - Run drum detection
```

### 🎼 Notation & AI
```
GET  /notation/video/{video_id}              - Get notation for video
POST /notation/                              - Create/update notation
POST /notation/{notation_id}/enrich          - AI enhancement
GET  /notation/{notation_id}/export/{format} - Export notation
```

---

## 🤖 ML Integration Ready

### Integration Points

The backend provides these endpoints for ML model integration:

#### 1. **Audio Input**
```python
GET /audio/analysis/{audio_id}
# Returns: sample_rate, channels, audio_data, preprocessing_info
```

#### 2. **Drum Detection Results**
```python
POST /notation/
# Expected JSON structure:
{
  "video_id": "uuid",
  "tempo": 120,
  "time_signature": "4/4",
  "notation_json": {
    "timeline": [
      {
        "timestamp_seconds": 0.5,
        "drum_type": "kick",
        "velocity": 0.8,
        "confidence_score": 0.95
      }
    ]
  }
}
```

#### 3. **AI Enhancement**
```python
POST /notation/{notation_id}/enrich
# Provides: pattern analysis, style classification, practice tips
```

### ML Workflow
```
Audio File → ML Detection → Structured JSON → Backend Storage → AI Enhancement → Export
```

---

## 📊 Database Schema

### Core Tables
- **`users`** - User accounts and profiles
- **`roles`** - User role definitions  
- **`videos`** - Uploaded video metadata
- **`audio_files`** - Extracted audio files
- **`notations`** - Drum notation data (JSON-based)
- **`processing_jobs`** - Background job tracking

### Key Relationships
```sql
users (1) ──────── (n) videos
videos (1) ─────── (n) audio_files  
videos (1) ─────── (1) notations
videos (1) ─────── (n) processing_jobs
```

---

## 🔧 Configuration

### Environment Variables (.env)
```bash
# Database
DATABASE_URL_SYNC=postgresql://postgres:password@localhost/drum_notation
DATABASE_URL_ASYNC=postgresql+asyncpg://postgres:password@localhost/drum_notation

# Security
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=15

# OpenAI (optional)
OPENAI_API_KEY=your-openai-api-key

# Storage  
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=100MB

# Processing
FFMPEG_PATH=/usr/bin/ffmpeg
```

---

## 🧪 Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest

# Run with coverage
pytest --cov=app tests/

# Manual testing via interactive docs
open http://localhost:8000/docs
```

---

## 🚀 Deployment

### Docker Production
```bash
# Build and deploy
docker-compose -f docker-compose.yml up -d

# Initialize database
docker exec drum_backend alembic upgrade head

# Check status
docker-compose ps
docker-compose logs drum_backend
```

### Production Checklist
- ✅ Set strong `SECRET_KEY`
- ✅ Configure secure database credentials  
- ✅ Set up SSL/TLS certificates
- ✅ Configure reverse proxy (nginx)
- ✅ Set up monitoring and logging
- ✅ Test ML model integration

---

## 📁 Project Structure

```
Drum-Notation-Backend/
├── app/
│   ├── main.py                 # FastAPI app entry point
│   ├── core/                   # Core configuration
│   │   ├── config.py
│   │   ├── database.py  
│   │   └── security.py
│   └── modules/                # Feature modules
│       ├── users/              # User management
│       ├── media/              # Video/audio handling  
│       ├── audio_processing/   # Audio analysis
│       ├── notation/           # Drum notation core
│       └── jobs/               # Background processing
├── alembic/                    # Database migrations
├── docker-compose.yml          # Docker setup
├── requirements.txt            # Dependencies
└── README.md                   # This file
```

---

## 📈 Development Status

### ✅ Complete & Ready
- Core Backend Architecture
- User Authentication & Authorization
- Video/Audio Upload & Processing  
- Drum Notation Storage System
- OpenAI Integration
- Background Job Processing
- API Documentation
- Database Schema & Migrations
- Docker Deployment Setup

### 🔄 Ready for Integration  
- ML Model Integration (endpoints ready)
- Frontend Integration (RESTful APIs ready)
- Production Deployment

### 🚧 Future Enhancements
- Real-time processing via WebSockets
- Advanced export formats (MusicXML, MIDI, PDF)
- Collaboration features
- Mobile optimization

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make changes and add tests
4. Run test suite: `pytest`  
5. Submit a pull request

### Code Standards
- Follow PEP 8 style guidelines
- Add type hints for all functions
- Write comprehensive tests
- Update documentation

---

## 📞 Support

For questions, issues, or contributions:

1. **Check Documentation** - Most questions answered here
2. **Review Issues** - Search existing GitHub issues  
3. **Create Issue** - For bugs or feature requests
4. **Submit PR** - For direct contributions

---

**🎵 Transform drum performances into beautiful notation! 🥁**

> *Built with ❤️ for musicians and developers*