# 🥁 Drum Notation Backend

> **Production-Ready FastAPI Backend for Automatic Drum Transcription and Musical Notation Generation**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.68+-00a4a4?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.8+-3776ab?style=flat-square&logo=python)](https://python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13+-336791?style=flat-square&logo=postgresql)](https://postgresql.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red?style=flat-square)](https://sqlalchemy.org/)

---

## 📋 Table of Contents

- [🎯 Project Overview](#-project-overview)
- [🏗️ Architecture](#️-architecture)
- [🚀 Getting Started](#-getting-started)
- [📊 Database Schema](#-database-schema)
- [🛠️ API Endpoints](#️-api-endpoints)
- [🤖 ML Integration](#-ml-integration)
- [🔐 Authentication](#-authentication--security)
- [📁 Project Structure](#-project-structure)
- [🧪 Testing](#-testing)
- [🔧 Configuration](#-configuration)
- [🚀 Deployment](#-deployment)
- [📈 Status & Roadmap](#-status--roadmap)

---

## 🎯 Project Overview

### What It Does

The **Drum Notation Backend** is a comprehensive FastAPI-based system that automatically converts drum performances (video/audio) into professional musical notation. It provides a complete pipeline from media processing to AI-enhanced notation generation.

### Key Features

- 🎬 **Video & Audio Processing** - Upload and process drum performance videos
- 🎵 **Automatic Transcription** - Convert audio to structured drum notation
- 🤖 **AI Enhancement** - OpenAI-powered musical analysis and insights
- 📝 **Notation Export** - Generate professional sheet music formats
- ⚡ **Async Processing** - Background job processing for heavy operations
- 🔐 **Secure Authentication** - JWT-based user management
- 📊 **Structured Data** - JSON-based notation storage for frontend integration

### Technology Stack

- **Backend**: FastAPI 0.68+ (Python 3.8+)
- **Database**: PostgreSQL 13+ with SQLAlchemy 2.0
- **Audio**: FFmpeg, librosa, scipy, numpy, soundfile
- **AI**: OpenAI GPT-4 Integration
- **Authentication**: JWT with bcrypt
- **Async**: asyncio, asyncpg
- **Validation**: Pydantic

---

## 🏗️ Architecture

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   ML Models     │    │   External      │
│   (React/Vue)   │◄──►│   (Python)      │◄──►│   Services      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                             │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   API Layer     │  Business Logic │    Data Access Layer       │
│   - Routes      │  - Services     │    - Models                 │
│   - Validation  │  - Processing   │    - Repositories           │
│   - Auth        │  - Jobs         │    - Database               │
└─────────────────┴─────────────────┴─────────────────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │   File Storage  │    │   OpenAI API    │
│   Database      │    │   (Media Files) │    │   (Enhancement) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Core Modules

- **`users`** - User authentication and profile management
- **`roles`** - Role-based access control
- **`media`** - Video/audio file management and storage
- **`audio_processing`** - Audio extraction and preprocessing
- **`notation`** - Drum notation data management and AI enrichment
- **`jobs`** - Async background job processing
- **`vision`** - Computer vision utilities (future expansion)

### Status: ✅ **PRODUCTION READY**

All core modules are fully implemented, tested, and error-free. The backend is ready for ML integration and frontend connection.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- PostgreSQL 13+
- FFmpeg (for audio processing)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Drum-Notation-Backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Set up database**
   ```bash
   # Create PostgreSQL database
   createdb drum_notation

   # Run migrations
   alembic upgrade head
   ```

6. **Run the application**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

7. **Access the API**
   - API: `http://localhost:8000`
   - Interactive docs: `http://localhost:8000/docs`
   - ReDoc: `http://localhost:8000/redoc`

---

## 📊 Database Schema

### Core Tables

- **`users`** - User accounts and profiles
- **`roles`** - User role definitions and permissions
- **`videos`** - Uploaded video metadata
- **`audio_files`** - Extracted audio file information
- **`notations`** - Drum notation data (JSON-based)
- **`openai_enrichments`** - AI analysis and enhancements
- **`processing_jobs`** - Background job tracking

### Key Relationships

```sql
users (1) ──────── (n) videos
videos (1) ─────── (n) audio_files
videos (1) ─────── (1) notations
notations (1) ──── (n) openai_enrichments
videos (1) ─────── (n) processing_jobs
```

---

## 🛠️ API Endpoints

### 🔐 Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `POST /auth/refresh` - Refresh JWT token

### 👥 User Management
- `GET /users/me` - Get current user profile
- `PUT /users/me` - Update user profile

### 🎬 Media Management
- `POST /media/videos/upload` - Upload video file
- `GET /media/videos/` - List user's videos
- `GET /media/videos/{video_id}` - Get video details
- `DELETE /media/videos/{video_id}` - Delete video

### ⚙️ Processing Jobs
- `POST /jobs/process-video/{video_id}` - Start video processing
- `GET /jobs/{job_id}/status` - Get job status

### 🎵 Audio Processing
- `POST /audio/extract/{video_id}` - Extract audio from video
- `GET /audio/analysis/{audio_id}` - Get audio analysis
- `POST /audio/detect-drums/{audio_id}` - Run drum detection

### 🎼 Notation & AI
- `GET /notation/video/{video_id}` - Get notation for video
- `POST /notation/` - Create/update notation
- `POST /notation/{notation_id}/enrich` - AI enhancement
- `GET /notation/{notation_id}/export/{format}` - Export notation

---

## 🤖 ML Integration

### Integration Points

The backend is **fully ready** for ML model integration through these endpoints:

1. **Audio Input**
   ```python
   # ML models receive processed audio via:
   GET /audio/analysis/{audio_id}
   # Returns: sample_rate, channels, audio_data, preprocessing_info
   ```

2. **Drum Detection Results**
   ```python
   # ML models send results to:
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
           "measure_number": 1,
           "beat_number": 1.0,
           "staff_position": "F4",
           "confidence_score": 0.95
         }
       ],
       "measures": [...],
       "musical_structure": {...}
     }
   }
   ```

3. **AI Enhancement**
   ```python
   # Post-processing with OpenAI:
   POST /notation/{notation_id}/enrich
   # Provides: pattern analysis, style classification, practice tips
   ```

### ML Workflow

```
Audio File → ML Detection → Structured JSON → Backend Storage → AI Enhancement → Export
```

---

## 🔐 Authentication & Security

### JWT Token Authentication
- Access tokens (short-lived, 15 minutes)
- Refresh tokens (long-lived, 7 days)
- Role-based access control

### Security Features
- Password hashing with bcrypt
- CORS protection
- Input validation with Pydantic
- SQL injection prevention with SQLAlchemy
- Rate limiting ready (configure as needed)

---

## 📁 Project Structure

```
Drum-Notation-Backend/
├── app/
│   ├── main.py                    # FastAPI application entry point
│   ├── core/                      # Core configuration and utilities
│   │   ├── config.py              # Application settings
│   │   ├── database.py            # Database connection
│   │   ├── security.py            # JWT and authentication
│   │   ├── dependencies.py        # FastAPI dependencies
│   │   └── openai_service.py      # OpenAI integration
│   ├── db/
│   │   └── base.py                # SQLAlchemy base
│   ├── shared/
│   │   └── base_model.py          # Common model mixins
│   └── modules/                   # Feature modules
│       ├── users/                 # User management
│       ├── roles/                 # Role-based access
│       ├── media/                 # Video/audio handling
│       ├── audio_processing/      # Audio analysis
│       ├── notation/              # Drum notation core
│       ├── jobs/                  # Background processing
│       └── vision/                # Computer vision utilities
├── alembic/                       # Database migrations
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variables template
└── README.md                      # This file
```

---

## 🧪 Testing

### Run Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test category
pytest tests/test_notation/
```

### Test Categories

- **Unit Tests** - Individual component testing
- **Integration Tests** - Database and API testing
- **End-to-End Tests** - Complete workflow testing

### Manual API Testing

Use the interactive documentation at `http://localhost:8000/docs` for manual testing.

---

## 🔧 Configuration

### Environment Variables (.env)

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost/drum_notation

# Security
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# OpenAI (optional)
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4

# File Storage
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=100MB

# Processing
FFMPEG_PATH=/usr/bin/ffmpeg  # Auto-detected if in PATH
```

### Key Configuration Notes

- **Database URL**: Use asyncpg driver for optimal async performance
- **File Storage**: Configure appropriate upload directory with sufficient space
- **OpenAI**: Optional but recommended for AI enhancement features

---

## 🚀 Deployment

### Docker Deployment

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:password@db/drum_notation
    depends_on:
      - db
    volumes:
      - ./uploads:/app/uploads

  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=drum_notation
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Production Checklist

- ✅ Set strong `SECRET_KEY`
- ✅ Configure proper database credentials
- ✅ Set up SSL/TLS certificates
- ✅ Configure reverse proxy (nginx)
- ✅ Set up monitoring and logging
- ✅ Configure backup strategy
- ✅ Test ML model integration
- ✅ Verify file upload limits

---

## 📈 Status & Roadmap

### ✅ Completed (Current State)

- ✅ **Core Backend Architecture** - FastAPI + SQLAlchemy + PostgreSQL
- ✅ **User Authentication** - JWT-based auth with roles
- ✅ **Media Management** - Video upload and storage
- ✅ **Audio Processing** - FFmpeg integration and analysis
- ✅ **Notation System** - JSON-based drum notation storage
- ✅ **OpenAI Integration** - AI-powered musical analysis
- ✅ **Background Jobs** - Async processing system
- ✅ **API Documentation** - Interactive Swagger/OpenAPI docs
- ✅ **Database Schema** - Production-ready with migrations
- ✅ **Error Handling** - Comprehensive error management
- ✅ **Type Safety** - Full typing with Pydantic validation

### 🔄 Ready for Integration

- 🔄 **ML Model Integration** - Endpoints ready for external ML services
- 🔄 **Frontend Integration** - RESTful APIs ready for React/Vue/Angular
- 🔄 **Deployment** - Docker and production configurations complete

### 📋 Future Enhancements

- 🔮 **Real-time Processing** - WebSocket support for live transcription
- 🔮 **Advanced Exports** - MusicXML, MIDI, PDF generation
- 🔮 **Collaboration Features** - Multi-user notation editing
- 🔮 **Performance Analytics** - Detailed playing statistics
- 🔮 **Mobile API** - Optimized endpoints for mobile apps

---

## 🤝 Contributing

### Development Setup

1. Follow the installation steps above
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Run the test suite: `pytest`
5. Submit a pull request

### Code Standards

- Follow PEP 8 style guidelines
- Add type hints for all functions
- Write comprehensive tests
- Update documentation for new features

---

## 📞 Support & Contact

For questions, issues, or contributions, please:

1. **Check the documentation** - Most questions are answered here
2. **Review existing issues** - Your question might already be addressed
3. **Create an issue** - For bugs or feature requests
4. **Submit a PR** - For direct contributions

---

**🎵 Ready to transform drum performances into beautiful notation! 🥁**

> *Built with ❤️ for musicians and developers*