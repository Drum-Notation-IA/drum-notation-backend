# 🥁 Drum Notation Backend

A sophisticated FastAPI backend for converting drum videos into musical notation using AI-powered analysis and OpenAI enhancements.

## 📋 Table of Contents

- [🎯 Project Overview](#-project-overview)
- [🏗️ Architecture](#️-architecture)
- [🚀 Getting Started](#-getting-started)
- [📊 Database Schema](#-database-schema)
- [🛠️ API Endpoints](#️-api-endpoints)
- [🎬 Processing Workflow](#-processing-workflow)
- [🤖 OpenAI Integration](#-openai-integration)
- [🔐 Authentication & Security](#-authentication--security)
- [📁 Project Structure](#-project-structure)
- [🧪 Testing](#-testing)
- [🔧 Configuration](#-configuration)
- [🚀 Deployment](#-deployment)
- [📈 Roadmap](#-roadmap)

## 🎯 Project Overview

### What It Does

This backend processes drum performance videos and converts them into structured musical notation. It uses advanced audio processing, machine learning for drum event detection, and OpenAI for intelligent pattern analysis and educational content generation.

### Key Features

- **Video Upload & Management**: Secure video upload with metadata tracking
- **Audio Processing**: High-quality audio extraction using FFmpeg
- **Drum Detection**: ML-powered onset detection and instrument classification
- **Musical Notation**: Automatic conversion to structured notation formats
- **OpenAI Integration**: Intelligent pattern analysis, style classification, and practice suggestions
- **Export Formats**: MusicXML, MIDI, and JSON export capabilities
- **Background Processing**: Asynchronous job processing system
- **Role-Based Access**: User management with role-based permissions

### Technology Stack

- **Backend**: FastAPI (Python 3.9+)
- **Database**: PostgreSQL with async SQLAlchemy
- **Audio Processing**: FFmpeg, librosa, scipy
- **Machine Learning**: TensorFlow/PyTorch (future implementation)
- **AI Enhancement**: OpenAI GPT-4 API
- **Authentication**: JWT tokens
- **Background Jobs**: Async task processing
- **Deployment**: Docker, Docker Compose

## 🏗️ Architecture

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client App    │───▶│   FastAPI       │───▶│   PostgreSQL    │
│                 │    │   Backend       │    │   Database      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   File Storage  │
                    │  (Videos/Audio) │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐    ┌─────────────────┐
                    │   FFmpeg        │───▶│   ML Models     │
                    │ Audio Extraction│    │ Drum Detection  │
                    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   OpenAI API    │
                    │  AI Enhancement │
                    └─────────────────┘
```

### Module Status

| Module | Status | Description |
|--------|--------|-------------|
| **Users** | ✅ Complete | User authentication and management |
| **Roles** | ✅ Complete | Role-based access control |
| **Media** | ✅ Complete | Video and audio file management |
| **Jobs** | ✅ Complete | Background job processing |
| **Audio Processing** | ✅ Complete | Advanced audio analysis and drum detection |
| **Notation** | ✅ **NEW!** | Musical notation generation with OpenAI |
| **Vision** | 🔄 Skeleton | Computer vision for drum analysis |

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL 13+
- FFmpeg (required for audio processing)
- OpenAI API Key (for AI features)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd Drum-Notation-Backend
```

2. **Create virtual environment**
```bash
python -m venv dnvenv
source dnvenv/bin/activate  # On Windows: dnvenv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Install FFmpeg**
   - **Windows**: Download from https://ffmpeg.org/download.html
   - **macOS**: `brew install ffmpeg`
   - **Ubuntu/Debian**: `sudo apt install ffmpeg`

5. **Setup database**
```bash
# Create PostgreSQL database
createdb drum_notation_db

# Run migrations
alembic upgrade head
```

6. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your database and OpenAI credentials
```

7. **Run the application**
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`
API documentation: `http://localhost:8000/docs`

## 📊 Database Schema

### Core Tables

```sql
-- Users and Authentication
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    deleted_at TIMESTAMP NULL
);

-- Role-Based Access Control
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL, -- user, admin, premium
    description TEXT,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE user_roles (
    user_id UUID REFERENCES users(id),
    role_id UUID REFERENCES roles(id),
    assigned_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (user_id, role_id)
);

-- Media Management
CREATE TABLE videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    duration_seconds REAL,
    created_at TIMESTAMP DEFAULT now(),
    deleted_at TIMESTAMP NULL
);

CREATE TABLE audio_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES videos(id),
    sample_rate INTEGER NOT NULL,
    channels INTEGER NOT NULL,
    duration_seconds REAL,
    storage_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);

-- Processing Jobs
CREATE TYPE job_status AS ENUM ('pending', 'running', 'completed', 'failed');

CREATE TABLE processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES videos(id),
    job_type TEXT NOT NULL, -- separation, onset, classification, notation
    status job_status DEFAULT 'pending',
    progress REAL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT now(),
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT now()
);

-- Musical Analysis
CREATE TABLE drum_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audio_file_id UUID NOT NULL REFERENCES audio_files(id),
    time_seconds REAL NOT NULL,
    instrument TEXT NOT NULL,
    velocity REAL,
    confidence REAL,
    model_version TEXT,
    created_at TIMESTAMP DEFAULT now()
);

-- Musical Notation
CREATE TABLE notations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES videos(id),
    tempo INTEGER,
    time_signature TEXT,
    notation_json JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- 🤖 OpenAI Integration (NEW!)
CREATE TABLE openai_enrichments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notation_id UUID NOT NULL REFERENCES notations(id),
    prompt_hash TEXT NOT NULL,
    model TEXT NOT NULL,
    input_json JSONB NOT NULL,
    output_json JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);
```

## 🛠️ API Endpoints

### 🔐 Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `GET /auth/me` - Get current user info

### 👥 User Management
- `GET /users/` - List users (admin only)
- `PUT /users/{user_id}` - Update user
- `DELETE /users/{user_id}` - Delete user

### 🎬 Media Management
- `POST /media/videos/` - Upload video
- `GET /media/videos/` - List user videos
- `GET /media/videos/{video_id}` - Get video details
- `DELETE /media/videos/{video_id}` - Delete video
- `GET /media/audio-files/` - List audio files

### ⚙️ Processing Jobs
- `POST /jobs/` - Create processing job
- `GET /jobs/` - List jobs
- `GET /jobs/{job_id}` - Get job details
- `DELETE /jobs/{job_id}` - Cancel job

### 🎵 Audio Processing (15+ Endpoints!)
- `POST /audio/extract/{video_id}` - Extract audio from video
- `POST /audio/detect-onsets/{audio_id}` - Detect drum onsets
- `POST /audio/classify-drums/{audio_id}` - Classify drum sounds
- `POST /audio/separate-sources/{audio_id}` - Audio source separation
- `POST /audio/enhance/{audio_id}` - Audio enhancement
- `GET /audio/analysis/{audio_id}` - Get analysis results

### 🎼 Notation (NEW! OpenAI-Powered)
- `POST /notation/from-events` - Generate notation from events
- `GET /notation/{notation_id}` - Get notation
- `PUT /notation/{notation_id}` - Update notation
- `POST /notation/{notation_id}/enhance` - **AI-powered enhancement**
- `GET /notation/{notation_id}/with-enhancements` - Get with AI analysis
- `POST /notation/{notation_id}/variations` - **Generate AI practice variations**
- `GET /notation/{notation_id}/export` - Export (MusicXML, MIDI, JSON)
- `GET /notation/stats/overview` - User notation statistics

## 🎬 Processing Workflow

### 1. Video Upload
```bash
curl -X POST "http://localhost:8000/media/videos/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@drum_video.mp4"
```

### 2. Audio Extraction
```bash
curl -X POST "http://localhost:8000/audio/extract/{video_id}" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. Drum Detection
```bash
curl -X POST "http://localhost:8000/audio/detect-onsets/{audio_id}" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4. Generate Notation
```bash
curl -X POST "http://localhost:8000/notation/from-events" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"video_id": "uuid", "tempo": 120, "time_signature": "4/4"}'
```

### 5. AI Enhancement (NEW!)
```bash
curl -X POST "http://localhost:8000/notation/{notation_id}/enhance" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enhancement_type": "full_analysis"}'
```

## 🤖 OpenAI Integration

### Features

1. **Pattern Analysis**: Intelligent analysis of drum patterns and rhythmic complexity
2. **Style Classification**: Automatic genre and style identification
3. **Practice Instructions**: AI-generated learning suggestions and techniques
4. **Pattern Variations**: Generate practice exercises at different difficulty levels
5. **Educational Content**: Explanations of musical concepts and techniques

### Configuration

Add your OpenAI API key to `.env`:
```env
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4
OPENAI_MAX_TOKENS=1500
OPENAI_TEMPERATURE=0.7
```

### AI Enhancement Types

- `full_analysis` - Complete analysis including patterns, style, and instructions
- `pattern_analysis` - Focus on rhythmic patterns and complexity
- `style_classification` - Genre and style identification
- `practice_instructions` - Learning suggestions and techniques

### Example AI Response
```json
{
  "pattern_analysis": {
    "complexity": "intermediate",
    "key_patterns": ["basic rock beat", "fill variations"],
    "tempo_consistency": 0.92,
    "rhythmic_density": "medium"
  },
  "style_classification": {
    "primary_genre": "Rock",
    "confidence": 0.89,
    "characteristics": "Strong backbeat, consistent kick pattern"
  },
  "practice_instructions": {
    "difficulty": "intermediate",
    "focus_areas": ["hi-hat control", "fill timing"],
    "exercises": ["Metronome practice at 100 BPM", "Isolated fill practice"]
  }
}
```

## 🔐 Authentication & Security

### JWT Token Authentication
- Secure token-based authentication
- Token expiration and refresh
- Role-based access control

### Security Features
- Password hashing with bcrypt
- SQL injection prevention
- CORS configuration
- Request rate limiting (recommended for production)

## 📁 Project Structure

```
Drum-Notation-Backend/
├── app/
│   ├── core/                    # Core functionality
│   │   ├── auth.py             # Authentication logic
│   │   ├── config.py           # Configuration settings
│   │   └── openai_service.py   # 🤖 OpenAI integration
│   ├── db/                     # Database
│   │   ├── session.py          # Database sessions
│   │   └── models.py           # Model registry
│   ├── modules/                # Feature modules
│   │   ├── users/              # ✅ User management
│   │   ├── roles/              # ✅ Role-based access
│   │   ├── media/              # ✅ Video/audio management
│   │   ├── jobs/               # ✅ Background processing
│   │   ├── audio_processing/   # ✅ Advanced audio analysis
│   │   ├── notation/           # ✅ Musical notation + AI
│   │   └── vision/             # 🔄 Computer vision (future)
│   ├── shared/                 # Shared utilities
│   └── main.py                 # FastAPI application
├── alembic/                    # Database migrations
├── uploads/                    # File storage
├── requirements.txt            # Python dependencies
├── alembic.ini                # Migration configuration
├── docker-compose.yml         # Docker setup
└── README.md                  # This file
```

## 🧪 Testing

### Run Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific module tests
pytest tests/test_notation.py -v
```

### Test OpenAI Integration
```bash
# Test with mock (no API key required)
OPENAI_API_KEY="" pytest tests/test_openai_service.py

# Test with real API (requires API key)
pytest tests/test_openai_integration.py
```

### Manual API Testing
```bash
# Test audio processing
python test_audio_processing.py

# Test notation generation
curl -X POST "http://localhost:8000/notation/from-events" \
  -H "Content-Type: application/json" \
  -d '{"video_id": "uuid", "tempo": 120}'
```

## 🔧 Configuration

### Environment Variables (.env)

```env
# Database
DATABASE_URL_ASYNC=postgresql+asyncpg://user:pass@localhost/drum_notation_db
DATABASE_URL_SYNC=postgresql://user:pass@localhost/drum_notation_db

# Security
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OpenAI (NEW!)
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4
OPENAI_MAX_TOKENS=1500
OPENAI_TEMPERATURE=0.7

# File Storage
UPLOAD_DIR=uploads
MAX_FILE_SIZE=100000000  # 100MB

# Processing
FFMPEG_PATH=ffmpeg  # Or full path to ffmpeg binary
```

### Key Configuration Notes

- **FFmpeg**: Must be installed and accessible in system PATH
- **OpenAI API**: Optional but recommended for AI features
- **File Storage**: Ensure upload directory has proper permissions
- **Database**: PostgreSQL 13+ with UUID extension required

## 🚀 Deployment

### Docker Deployment

```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL_ASYNC=postgresql+asyncpg://postgres:password@db:5432/drum_notation
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - db
    volumes:
      - ./uploads:/app/uploads

  db:
    image: postgres:13
    environment:
      POSTGRES_DB: drum_notation
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Production Checklist

- [ ] Set strong SECRET_KEY
- [ ] Configure proper database credentials
- [ ] Add OpenAI API key for AI features
- [ ] Install FFmpeg on server
- [ ] Set up file storage with proper permissions
- [ ] Configure CORS for frontend domain
- [ ] Enable HTTPS/SSL
- [ ] Set up monitoring and logging
- [ ] Configure backup strategy

## 📈 Roadmap

### ✅ Completed (Current State)
- User authentication and role management
- Video upload and management
- Advanced audio processing (15+ endpoints)
- Background job system
- **OpenAI-powered notation analysis**
- Export capabilities (MusicXML, MIDI, JSON)

### 🔄 In Progress
- Enhanced ML model integration
- Real-time processing optimizations
- Advanced computer vision features

### 📋 Upcoming Features
- **Mobile App Support**: Enhanced API for mobile clients
- **Collaborative Features**: Shared notation editing
- **Advanced AI**: Custom model training and fine-tuning
- **Performance Analytics**: Detailed performance metrics
- **Educational Platform**: Structured learning paths

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Make changes and test thoroughly
4. Ensure all tests pass: `pytest`
5. Submit pull request

### Code Standards
- Follow PEP 8 style guidelines
- Write comprehensive tests
- Document all public APIs
- Use type hints throughout

## 📞 Support & Contact

- **Documentation**: Available in `/docs` endpoint
- **Issues**: Create GitHub issue for bugs or feature requests
- **API Testing**: Use interactive docs at `/docs`

---

**Built with ❤️ for the drumming community**

*This backend powers intelligent drum notation analysis with cutting-edge AI integration.*