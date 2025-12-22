# 🥁 Drum Notation Backend

A comprehensive FastAPI backend for automatic drum transcription from video content, featuring advanced audio processing, AI-powered analysis, and professional notation generation.

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
- [🤝 Contributing](#-contributing)

## 🎯 Project Overview

### What It Does
The Drum Notation Backend automatically analyzes drum performance videos and generates professional musical notation. It combines advanced audio processing, computer vision, and AI-powered analysis to provide comprehensive drum transcription services.

### Key Features
- **🎵 Audio Processing**: Extract and analyze audio from video files
- **🥁 Drum Detection**: Identify and classify drum events with high accuracy
- **🎛️ Source Separation**: Isolate individual drum components
- **🎼 Notation Generation**: Create professional drum notation
- **🤖 AI Enhancement**: OpenAI-powered musical analysis and insights
- **⚙️ Async Processing**: Background job processing with real-time updates
- **🔐 Secure APIs**: JWT authentication with role-based access
- **📊 Comprehensive Analytics**: Detailed performance metrics and insights

### Technology Stack
- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Audio Processing**: librosa, scipy, soundfile, FFmpeg
- **AI Integration**: OpenAI GPT-4 for musical analysis
- **Authentication**: JWT with bcrypt password hashing
- **Background Jobs**: Async task processing
- **Documentation**: Interactive OpenAPI/Swagger UI

## 🏗️ Architecture

### System Components

The backend follows a modular, async-first architecture:

```
┌─────────────────────────────────────────────────────────────────┐
│                           FastAPI Application                   │
├─────────────────────────────────────────────────────────────────┤
│  Authentication │  User Management │  Role Management           │
├─────────────────────────────────────────────────────────────────┤
│               Media Management (Videos & Audio)                 │
├─────────────────────────────────────────────────────────────────┤
│  Audio Processing │  Drum Detection │  Source Separation        │
├─────────────────────────────────────────────────────────────────┤
│              Notation Generation │  OpenAI Integration          │
├─────────────────────────────────────────────────────────────────┤
│                      Background Jobs Queue                      │
├─────────────────────────────────────────────────────────────────┤
│                      PostgreSQL Database                        │
└─────────────────────────────────────────────────────────────────┘
```

### Core Modules

- **`app/modules/users/`** - User management and profiles
- **`app/modules/roles/`** - Role-based access control
- **`app/modules/media/`** - Video and audio file management
- **`app/modules/audio_processing/`** - Audio analysis and drum detection
- **`app/modules/notation/`** - Notation generation and management
- **`app/modules/jobs/`** - Background task processing
- **`app/modules/vision/`** - Computer vision components
- **`app/core/`** - Core services (OpenAI, security, config)

### Status: ✅ **PRODUCTION READY**
All modules are implemented, tested, and operational.

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- PostgreSQL 13+
- FFmpeg (system dependency)
- OpenAI API Key (optional, for AI features)

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

4. **Setup database**
   ```bash
   # Create PostgreSQL database
   createdb drum_notation
   
   # Run migrations
   alembic upgrade head
   ```

5. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

6. **Start the server**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

7. **Access the API**
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/

## 📊 Database Schema

### Core Tables

```sql
-- User Management
users (id, username, email, hashed_password, created_at, updated_at)
roles (id, name, description, permissions)
user_roles (user_id, role_id)

-- Media Management
videos (id, user_id, filename, file_path, duration, status, metadata)
audio_files (id, video_id, filename, file_path, sample_rate, channels)

-- Processing
processing_jobs (id, user_id, job_type, status, progress, result_data)

-- Notation
notations (id, video_id, tempo, time_signature, notation_json)
openai_enrichments (id, notation_id, prompt_hash, model, input_json, output_json)
```

### Key Relationships
- Users → Videos (one-to-many)
- Videos → AudioFiles (one-to-many)  
- Videos → Notations (one-to-one)
- Notations → OpenAI Enrichments (one-to-many)
- Users → Processing Jobs (one-to-many)

## 🛠️ API Endpoints

### 🔐 Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `POST /auth/refresh` - Refresh JWT token

### 👥 User Management  
- `GET /users/me` - Get current user profile
- `PUT /users/me` - Update user profile
- `GET /users/{user_id}` - Get user by ID

### 🎬 Media Management
- `POST /videos/upload` - Upload video file
- `GET /videos` - List user's videos
- `GET /videos/{video_id}` - Get video details
- `DELETE /videos/{video_id}` - Delete video

### ⚙️ Processing Jobs
- `GET /jobs/my-jobs` - List user's jobs  
- `GET /jobs/{job_id}` - Get job status
- `POST /jobs/{job_id}/cancel` - Cancel job

### 🎵 Audio Processing
- `POST /audio/extract/{video_id}` - Extract audio from video
- `GET /audio/extract/{video_id}/status` - Check extraction status
- `POST /audio/detect-drums/{video_id}` - Detect drum events
- `POST /audio/detect-drums-advanced/{video_id}` - Advanced detection
- `POST /audio/separate-sources/{video_id}` - Source separation
- `POST /audio/create-stems/{video_id}` - Create professional stems
- `POST /audio/enhance-drums/{video_id}` - Enhance drum elements
- `GET /audio/analysis/comprehensive/{video_id}` - Complete analysis
- `GET /audio/features/{video_id}` - Extract audio features

### 🎼 Notation & AI
- `POST /notation/generate/{video_id}` - Generate notation
- `GET /notation/{notation_id}` - Get notation
- `POST /notation/{notation_id}/analyze` - AI analysis
- `POST /notation/{notation_id}/practice-guide` - Practice instructions
- `POST /notation/{notation_id}/style-classify` - Style classification

## 🎬 Processing Workflow

### 1. Video Upload
```python
# User uploads video file
POST /videos/upload
→ Creates Video record in database
→ Returns video_id for subsequent processing
```

### 2. Audio Extraction  
```python
# Extract audio from video
POST /audio/extract/{video_id}
→ Creates background job
→ Extracts audio using FFmpeg
→ Saves AudioFile record
```

### 3. Drum Detection
```python
# Detect and classify drum events
POST /audio/detect-drums-advanced/{video_id}
→ Analyzes audio for drum onsets
→ Classifies drum types (kick, snare, hihat, etc.)
→ Calculates velocity and confidence scores
```

### 4. Generate Notation
```python
# Create musical notation
POST /notation/generate/{video_id}
→ Processes detected events
→ Quantizes to musical grid
→ Generates notation JSON
```

### 5. AI Enhancement
```python
# Get AI-powered insights
POST /notation/{notation_id}/analyze  
→ Sends notation to OpenAI
→ Receives musical analysis and insights
→ Stores enrichment data
```

## 🤖 OpenAI Integration

### Features
- **Pattern Analysis**: Complexity scoring, rhythm analysis
- **Style Classification**: Genre identification with confidence scores  
- **Practice Instructions**: Personalized learning recommendations
- **Musical Insights**: Technical analysis and improvement tips

### Configuration
```python
# Enable OpenAI features
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4
OPENAI_MAX_TOKENS=2000
```

### AI Enhancement Types

1. **Drum Pattern Analysis**
   - Complexity assessment (beginner/intermediate/advanced)
   - Key pattern identification
   - Tempo consistency analysis
   - Rhythmic density calculation

2. **Style Classification**
   - Genre detection (rock, jazz, latin, etc.)
   - Confidence scoring
   - Musical characteristics identification

3. **Practice Recommendations**
   - Skill level assessment
   - Targeted exercises
   - Technical improvement suggestions

### Example AI Response
```json
{
  "pattern_analysis": {
    "complexity": "intermediate", 
    "key_patterns": ["basic rock beat", "hi-hat variations"],
    "tempo_consistency": 0.92,
    "rhythmic_density": "moderate"
  },
  "style_classification": {
    "primary_genre": "rock",
    "confidence": 0.87,
    "characteristics": ["steady kick pattern", "snare on 2 and 4"]
  },
  "practice_instructions": {
    "difficulty": "intermediate",
    "focus_areas": ["hi-hat control", "dynamic variation"],
    "exercises": ["practice ghost notes", "work on limb independence"]
  }
}
```

## 🔐 Authentication & Security

### JWT Token Authentication
- Secure user authentication with JWT tokens
- Token refresh mechanism
- Role-based access control (RBAC)

### Security Features
- Password hashing with bcrypt
- Request rate limiting
- CORS protection
- SQL injection prevention via SQLAlchemy ORM
- Input validation with Pydantic schemas

## 📁 Project Structure

```
Drum-Notation-Backend/
├── app/
│   ├── main.py                    # FastAPI application entry point
│   ├── core/                      # Core services and configuration
│   │   ├── config.py             # Environment configuration
│   │   ├── database.py           # Database connection
│   │   ├── security.py           # Authentication & authorization
│   │   └── openai_service.py     # OpenAI integration
│   ├── db/
│   │   ├── base.py              # Database base configuration
│   │   └── models.py            # Model registry
│   ├── modules/                  # Feature modules
│   │   ├── users/               # User management
│   │   ├── roles/               # Role-based access control
│   │   ├── media/               # Video & audio file management
│   │   ├── audio_processing/    # Audio analysis & drum detection
│   │   ├── notation/            # Notation generation & AI features
│   │   ├── jobs/                # Background task processing
│   │   └── vision/              # Computer vision components
│   └── shared/                   # Shared utilities and base classes
├── alembic/                      # Database migrations
├── tests/                        # Test suite
├── requirements.txt              # Python dependencies
├── alembic.ini                  # Database migration config
├── pytest.ini                  # Test configuration
└── README.md                    # This file
```

## 🧪 Testing

### Run Tests
```bash
# Run all tests
pytest

# Run specific module tests
pytest tests/test_openai_integration.py

# Run with coverage
pytest --cov=app tests/

# Run integration tests (requires API keys)
pytest -m integration
```

### Test Categories
- **Unit Tests**: Individual component testing
- **Integration Tests**: OpenAI and database integration  
- **Audio Processing Tests**: Audio analysis validation
- **API Tests**: Endpoint functionality

### Manual API Testing
Access the interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔧 Configuration

### Environment Variables (.env)
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost/drum_notation

# Security
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OpenAI (Optional)
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4
OPENAI_MAX_TOKENS=2000

# File Storage
UPLOAD_DIR=./uploads
TEMP_DIR=./temp
MAX_FILE_SIZE_MB=500

# Audio Processing
DEFAULT_SAMPLE_RATE=44100
DEFAULT_CHANNELS=1
```

### Key Configuration Notes
- **SECRET_KEY**: Generate a strong secret key for JWT tokens
- **DATABASE_URL**: PostgreSQL connection string
- **OPENAI_API_KEY**: Required for AI-powered features
- **File paths**: Ensure upload/temp directories exist and are writable

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
      - DATABASE_URL=postgresql://postgres:password@db/drum_notation
    depends_on:
      - db
    volumes:
      - ./uploads:/app/uploads
      - ./temp:/app/temp

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
- [ ] Configure secure DATABASE_URL  
- [ ] Set up SSL/HTTPS
- [ ] Configure CORS origins
- [ ] Set up file storage (S3, etc.)
- [ ] Configure logging and monitoring
- [ ] Set up backup strategy
- [ ] Enable rate limiting
- [ ] Configure environment-specific settings

## 📈 Roadmap

### ✅ Completed (Current State)
- ✅ Complete FastAPI backend with all modules
- ✅ User authentication and authorization
- ✅ Video upload and audio extraction
- ✅ Advanced drum detection and classification
- ✅ Source separation and audio enhancement
- ✅ Notation generation pipeline
- ✅ OpenAI integration for musical analysis
- ✅ Background job processing
- ✅ Comprehensive API documentation
- ✅ Database schema and migrations
- ✅ Security and validation
- ✅ Error handling and logging

### 🔄 Ready for Integration
- 🔄 External ML model integration (your responsibility)
- 🔄 Frontend application connection
- 🔄 Production deployment

### 📋 Future Enhancements
- 📋 Real-time WebSocket processing updates
- 📋 MIDI export functionality
- 📋 Batch processing capabilities
- 📋 Advanced notation features (dynamics, articulations)
- 📋 Mobile API optimizations

## 🤝 Contributing

### Development Setup
1. Follow the installation guide above
2. Install development dependencies: `pip install -r requirements-dev.txt`
3. Set up pre-commit hooks: `pre-commit install`
4. Run tests before submitting: `pytest`

### Code Standards
- **Style**: Follow PEP 8 with Black formatting
- **Type Hints**: Use comprehensive type annotations
- **Documentation**: Document all public APIs
- **Testing**: Write tests for new features
- **Commits**: Use conventional commit messages

## 📞 Support & Contact

For questions, issues, or contributions:
- 📧 **Issues**: Create GitHub issues for bugs or feature requests
- 📖 **Documentation**: Check `/docs` endpoint for API reference
- 🧪 **Testing**: Run test suite for validation

---

**Status**: ✅ **PRODUCTION READY** - Complete backend implementation ready for integration and deployment.

**Last Updated**: January 2025