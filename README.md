# 🥁 Drum Notation Backend

A comprehensive FastAPI-based backend system for automated drum notation generation from video recordings. This system processes drum performance videos, extracts audio, detects drum hits using machine learning, and generates musical notation.

## 📋 Table of Contents

- [🎯 Project Overview](#-project-overview)
- [🏗️ Architecture](#️-architecture)
- [🚀 Getting Started](#-getting-started)
- [📊 Database Schema](#-database-schema)
- [🛠️ API Endpoints](#️-api-endpoints)
- [🎬 Video Processing Workflow](#-video-processing-workflow)
- [🔐 Authentication & Security](#-authentication--security)
- [📁 Project Structure](#-project-structure)
- [🧪 Testing](#-testing)
- [🔧 Configuration](#-configuration)
- [📚 Development Guide](#-development-guide)
- [🚀 Deployment](#-deployment)

---

## 🎯 Project Overview

### What It Does
The Drum Notation Backend converts drum performance videos into accurate musical notation through:
1. **Video Upload**: Users upload drum performance recordings
2. **Audio Extraction**: System extracts high-quality audio from videos
3. **Drum Detection**: ML models identify drum hits and classify instruments
4. **Notation Generation**: Creates standard musical notation from detected events
5. **AI Enhancement**: Optional OpenAI integration for notation refinement

### Key Features
- ✅ **User Management**: Complete authentication with JWT tokens
- ✅ **Role-Based Access**: Admin, user, and premium user roles
- ✅ **Video Storage**: Secure upload and management of drum videos
- 🔄 **Audio Processing**: Extract and analyze audio from videos
- 🔄 **ML Pipeline**: Drum onset detection and instrument classification
- 🔄 **Notation Engine**: Generate MusicXML and visual notation
- 🔄 **Background Jobs**: Async processing with status tracking
- ✅ **RESTful API**: Comprehensive OpenAPI documentation

### Technology Stack
- **Backend**: FastAPI with async/await support
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: JWT tokens with bcrypt password hashing
- **File Storage**: Local storage with cloud-ready architecture
- **ML Framework**: Ready for TensorFlow/PyTorch integration
- **API Documentation**: Automatic OpenAPI/Swagger generation

---

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Drum Notation Backend                   │
├─────────────────────────────────────────────────────────────┤
│  📤 Video Upload    │  🎵 Audio Extract  │  🤖 ML Processing │
│  👤 User Auth       │  📊 Job Queue      │  📝 Notation Gen  │
│  🔒 Role System     │  💾 File Storage   │  🎯 API Gateway   │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                      PostgreSQL Database                   │
├─────────────────────────────────────────────────────────────┤
│  users  │  roles  │  videos  │  audio_files  │  jobs       │
│  user_roles       │  drum_events             │  notations  │
└─────────────────────────────────────────────────────────────┘
```

### Module Status

| Module | Status | Description | API Prefix |
|--------|--------|-------------|------------|
| **👤 Users** | ✅ **Complete** | Authentication, CRUD, JWT tokens | `/users` |
| **🔐 Roles** | ✅ **Complete** | Role-based access control | `/roles` |
| **🎬 Videos** | ✅ **Complete** | Video upload, storage, management | `/videos` |
| **🎵 Audio Processing** | 🔄 Ready | ML models for drum detection | `/audio` |
| **⚙️ Jobs** | 🔄 Ready | Background processing queue | `/jobs` |
| **📝 Notation** | 🔄 Ready | Musical notation generation | `/notation` |
| **👁️ Vision** | 🔄 Ready | Computer vision for drumstick tracking | `/vision` |

---

## 🚀 Getting Started

### Prerequisites
```bash
# Required software
Python 3.10+
PostgreSQL 13+
Git

# Optional for development
Docker & Docker Compose
```

### Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd Drum-Notation-Backend
```

2. **Set up virtual environment:**
```bash
python -m venv dnvenv
source dnvenv/bin/activate  # On Windows: dnvenv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your database credentials and settings
```

5. **Set up database:**
```bash
# Create PostgreSQL database
createdb drum_notation

# Run migrations
alembic upgrade head
```

6. **Create upload directories:**
```bash
mkdir -p uploads/{videos,audio}
```

7. **Start the server:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

8. **Access the API:**
- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/

---

## 📊 Database Schema

### Core Tables (Implemented)

```sql
-- Users and Authentication
users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP NULL
);

-- Role-Based Access Control
roles (
    id UUID PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP NULL
);

user_roles (
    user_id UUID REFERENCES users(id),
    role_id UUID REFERENCES roles(id),
    assigned_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id)
);

-- Video Storage and Management
videos (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id) NOT NULL,
    filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    duration_seconds FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP NULL
);

-- Extracted Audio Files
audio_files (
    id UUID PRIMARY KEY,
    video_id UUID REFERENCES videos(id) NOT NULL,
    sample_rate INTEGER NOT NULL,
    channels INTEGER NOT NULL,
    duration_seconds FLOAT,
    storage_path TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP NULL
);
```

### Processing Tables (Ready for Implementation)

```sql
-- Background Job Processing
CREATE TYPE job_status AS ENUM ('pending', 'running', 'completed', 'failed');

processing_jobs (
    id UUID PRIMARY KEY,
    video_id UUID REFERENCES videos(id) NOT NULL,
    job_type TEXT NOT NULL, -- 'audio_extraction', 'drum_detection', 'notation_generation'
    status job_status DEFAULT 'pending',
    progress FLOAT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    deleted_at TIMESTAMP NULL
);

-- Detected Drum Events
drum_events (
    id UUID PRIMARY KEY,
    audio_file_id UUID REFERENCES audio_files(id) NOT NULL,
    time_seconds FLOAT NOT NULL,
    instrument TEXT NOT NULL, -- 'kick', 'snare', 'hi-hat', 'crash', etc.
    velocity FLOAT,
    confidence FLOAT,
    model_version TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP NULL
);

-- Generated Musical Notation
notations (
    id UUID PRIMARY KEY,
    video_id UUID REFERENCES videos(id) NOT NULL,
    tempo INTEGER,
    time_signature TEXT,
    notation_json JSONB NOT NULL, -- MusicXML or custom notation format
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP NULL
);

-- AI Enhancement Results
openai_enrichments (
    id UUID PRIMARY KEY,
    notation_id UUID REFERENCES notations(id) NOT NULL,
    prompt_hash TEXT NOT NULL,
    model TEXT NOT NULL,
    input_json JSONB NOT NULL,
    output_json JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP NULL
);

-- ML Model Versioning
models (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    task TEXT NOT NULL, -- 'onset_detection', 'classification', 'separation'
    storage_path TEXT NOT NULL,
    metrics JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    deleted_at TIMESTAMP NULL,
    UNIQUE (name, version)
);
```

---

## 🛠️ API Endpoints

### 🔐 Authentication Endpoints

| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| `POST` | `/users/register` | Register new user | ✅ |
| `POST` | `/users/login` | Login and get JWT token | ✅ |
| `GET` | `/users/me` | Get current user info | ✅ |
| `PUT` | `/users/me` | Update current user | ✅ |
| `POST` | `/users/change-password` | Change password | ✅ |
| `DELETE` | `/users/me` | Delete account | ✅ |

### 👥 User & Role Management

| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| `GET` | `/users/` | List all users (admin) | ✅ |
| `GET` | `/users/{id}` | Get user by ID | ✅ |
| `POST` | `/roles/` | Create new role | ✅ |
| `GET` | `/roles/` | List all roles | ✅ |
| `POST` | `/roles/assign` | Assign role to user | ✅ |
| `DELETE` | `/roles/remove` | Remove role from user | ✅ |

### 🎬 Video Management

| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| `POST` | `/videos/upload` | Upload drum performance video | ✅ |
| `GET` | `/videos/` | List videos with pagination | ✅ |
| `GET` | `/videos/my-videos` | Get current user's videos | ✅ |
| `GET` | `/videos/{id}` | Get video details | ✅ |
| `PUT` | `/videos/{id}` | Update video metadata | ✅ |
| `DELETE` | `/videos/{id}` | Delete video (soft/hard) | ✅ |
| `GET` | `/videos/{id}/download` | Download video file | ✅ |
| `POST` | `/videos/{id}/restore` | Restore deleted video | ✅ |
| `GET` | `/videos/stats/my-usage` | Get storage statistics | ✅ |

### 🎵 Video Processing

| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| `POST` | `/videos/{id}/extract-audio` | Extract audio from video | 🔄 |
| `GET` | `/videos/{id}/processing-status` | Check processing status | 🔄 |
| `POST` | `/videos/{id}/analyze-drums` | Start drum detection | 🔄 |
| `POST` | `/videos/{id}/generate-notation` | Generate notation | 🔄 |

### ⚙️ Background Jobs (Planned)

| Method | Endpoint | Description | Status |
|--------|----------|-------------|---------|
| `GET` | `/jobs/` | List processing jobs | 🔄 |
| `GET` | `/jobs/{id}` | Get job status | 🔄 |
| `DELETE` | `/jobs/{id}` | Cancel job | 🔄 |
| `POST` | `/jobs/{id}/retry` | Retry failed job | 🔄 |

---

## 🎬 Video Processing Workflow

### 1. Video Upload
```bash
# Upload drum performance video
curl -X POST "http://localhost:8000/videos/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@drum_performance.mp4"

# Response includes video ID for tracking
{
  "message": "Video uploaded successfully",
  "video": {
    "id": "video-uuid-here",
    "filename": "drum_performance.mp4",
    "storage_path": "uploads/videos/unique-filename.mp4",
    "duration_seconds": 120.5
  }
}
```

### 2. Audio Extraction (Future)
```bash
# Extract audio for processing
curl -X POST "http://localhost:8000/videos/{video_id}/extract-audio" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Creates background job for FFmpeg processing
{
  "job_id": "job-uuid-here",
  "status": "pending",
  "message": "Audio extraction job queued"
}
```

### 3. Drum Detection (Future)
```bash
# Analyze extracted audio for drum events
curl -X POST "http://localhost:8000/videos/{video_id}/analyze-drums" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Uses ML models to detect drum hits
{
  "job_id": "job-uuid-here",
  "status": "running",
  "detected_events": 127,
  "confidence_avg": 0.89
}
```

### 4. Notation Generation (Future)
```bash
# Generate musical notation from drum events
curl -X POST "http://localhost:8000/videos/{video_id}/generate-notation" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Creates standard music notation
{
  "notation_id": "notation-uuid-here",
  "tempo": 120,
  "time_signature": "4/4",
  "measures": 32
}
```

---

## 🔐 Authentication & Security

### JWT Token Authentication
```bash
# 1. Register user
curl -X POST "http://localhost:8000/users/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "drummer@example.com", "password": "securepass123"}'

# 2. Login to get token
curl -X POST "http://localhost:8000/users/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=drummer@example.com&password=securepass123"

# 3. Use token in requests
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  "http://localhost:8000/videos/my-videos"
```

### Role-Based Access Control
```bash
# Assign admin role
curl -X POST "http://localhost:8000/roles/assign" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user-uuid", "role_name": "admin"}'

# Check user roles
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:8000/users/me"
```

### Security Features
- ✅ **Password Hashing**: bcrypt with salt
- ✅ **JWT Tokens**: Configurable expiration
- ✅ **Input Validation**: Pydantic schemas
- ✅ **SQL Injection Protection**: SQLAlchemy ORM
- ✅ **File Upload Security**: Type and size validation
- ✅ **Soft Delete**: Data retention and recovery
- ✅ **CORS Support**: Configurable origins

---

## 📁 Project Structure

```
Drum-Notation-Backend/
├── 📁 alembic/                    # Database migrations
│   ├── versions/                  # Migration files
│   ├── env.py                     # Alembic configuration
│   └── script.py.mako             # Migration template
│
├── 📁 app/                        # Main application
│   ├── 📁 core/                   # Core functionality
│   │   ├── config.py              # Settings and configuration
│   │   ├── database.py            # Database connection
│   │   ├── dependencies.py        # FastAPI dependencies
│   │   ├── password_utils.py      # Password validation
│   │   └── security.py            # JWT and hashing
│   │
│   ├── 📁 db/                     # Database setup
│   │   ├── base.py                # SQLAlchemy base
│   │   └── models.py              # Model imports
│   │
│   ├── 📁 modules/                # Feature modules
│   │   ├── 📁 users/              # ✅ User management
│   │   │   ├── models.py          # User model
│   │   │   ├── schemas.py         # Pydantic schemas
│   │   │   ├── repository.py      # Data access layer
│   │   │   ├── service.py         # Business logic
│   │   │   └── router.py          # API endpoints
│   │   │
│   │   ├── 📁 roles/              # ✅ Role management
│   │   │   ├── models.py          # Role models
│   │   │   ├── schemas.py         # Role schemas
│   │   │   ├── service.py         # Role logic
│   │   │   └── routers.py         # Role endpoints
│   │   │
│   │   ├── 📁 media/              # ✅ Video management (renamed from media)
│   │   │   ├── models.py          # Video & AudioFile models
│   │   │   ├── schemas.py         # Video schemas
│   │   │   ├── repository.py      # Video data access
│   │   │   ├── service.py         # Video business logic
│   │   │   ├── storage.py         # File storage utilities
│   │   │   └── routers.py         # Video endpoints (/videos)
│   │   │
│   │   ├── 📁 audio_processing/   # 🔄 ML audio analysis
│   │   │   ├── models.py          # Processing models
│   │   │   ├── detection.py       # Onset detection
│   │   │   ├── classification.py  # Instrument classification
│   │   │   └── service.py         # Audio processing logic
│   │   │
│   │   ├── 📁 jobs/               # 🔄 Background processing
│   │   │   ├── models.py          # Job models
│   │   │   ├── worker.py          # Celery workers
│   │   │   └── service.py         # Job management
│   │   │
│   │   ├── 📁 notation/           # 🔄 Musical notation
│   │   │   ├── models.py          # Notation models
│   │   │   ├── generator.py       # Notation generation
│   │   │   └── service.py         # Notation logic
│   │   │
│   │   └── 📁 vision/             # 🔄 Computer vision
│   │       ├── mediapipe.py       # Pose detection
│   │       └── drumstick.py       # Stick tracking
│   │
│   ├── 📁 shared/                 # Shared utilities
│   │   └── base_model.py          # Base model with timestamps
│   │
│   └── main.py                    # FastAPI app entry point
│
├── 📁 uploads/                    # File storage
│   ├── videos/                    # Uploaded videos
│   └── audio/                     # Extracted audio
│
├── 📁 tests/                      # Test suite
│   ├── test_users.py              # User tests
│   ├── test_videos.py             # Video tests
│   └── conftest.py                # Test configuration
│
├── .env                           # Environment variables
├── .gitignore                     # Git ignore rules
├── alembic.ini                    # Alembic configuration
├── requirements.txt               # Python dependencies
└── README.md                      # This documentation
```

---

## 🧪 Testing

### Run Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest

# Run specific test file
pytest tests/test_users.py

# Run with coverage
pytest --cov=app tests/
```

### Manual API Testing

**Using cURL:**
```bash
# Test video upload
curl -X POST "http://localhost:8000/videos/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test_video.mp4"

# Test user registration
curl -X POST "http://localhost:8000/users/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "testpass123"}'
```

**Using Interactive Docs:**
1. Start server: `uvicorn app.main:app --reload`
2. Visit: http://localhost:8000/docs
3. Use "Authorize" button with JWT token
4. Test endpoints interactively

### Test Database
```bash
# Create test database
createdb drum_notation_test

# Run tests with test database
DATABASE_URL_ASYNC="postgresql+asyncpg://user:pass@localhost/drum_notation_test" pytest
```

---

## 🔧 Configuration

### Environment Variables (.env)
```env
# Database Configuration
DATABASE_URL_ASYNC=postgresql+asyncpg://user:password@localhost/drum_notation
DATABASE_URL_SYNC=postgresql://user:password@localhost/drum_notation

# Security
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# File Storage
UPLOAD_DIR=uploads
MAX_VIDEO_SIZE_MB=500
MAX_USER_STORAGE_GB=5

# External Services (Future)
OPENAI_API_KEY=your-openai-key
REDIS_URL=redis://localhost:6379

# Development
DEBUG=True
LOG_LEVEL=INFO
```

### Video Processing Limits
```python
# File size limits
MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500MB
MAX_USER_STORAGE = 5 * 1024 * 1024 * 1024  # 5GB

# Supported video formats
SUPPORTED_FORMATS = [
    "video/mp4",
    "video/quicktime",  # .mov
    "video/x-msvideo",  # .avi
    "video/x-matroska",  # .mkv
    "video/webm"
]
```

---

## 📚 Development Guide

### Adding New Modules

1. **Create module structure:**
```bash
mkdir -p app/modules/new_module
touch app/modules/new_module/{__init__.py,models.py,schemas.py,repository.py,service.py,router.py}
```

2. **Implement components:**
```python
# models.py - Database models
class NewModel(BaseModel):
    __tablename__ = "new_table"
    # Define columns and relationships

# schemas.py - Pydantic schemas
class NewModelCreate(BaseModel):
    # Define validation schemas

# repository.py - Data access
class NewRepository:
    async def get_by_id(self, db: AsyncSession, id: UUID):
        # Implement CRUD operations

# service.py - Business logic
class NewService:
    def __init__(self):
        self.repository = NewRepository()
    # Implement business operations

# router.py - API endpoints
router = APIRouter(prefix="/new", tags=["new"])
# Define endpoints
```

3. **Register module:**
```python
# app/main.py
from app.modules.new_module.router import router as new_router
app.include_router(new_router)

# app/db/models.py
from app.modules.new_module.models import NewModel
```

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "Add new feature"

# Apply migrations
alembic upgrade head

# Check current revision
alembic current

# Rollback migration
alembic downgrade -1
```

### Code Quality
```bash
# Format code
black app/ tests/

# Sort imports
isort app/ tests/

# Check types
mypy app/

# Lint code
flake8 app/ tests/
```

---

## 🚀 Deployment

### Docker Deployment
```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL_ASYNC=postgresql+asyncpg://postgres:password@db/drum_notation
    depends_on:
      - db
      
  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=drum_notation
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      
volumes:
  postgres_data:
```

### Production Setup
```bash
# 1. Set up production environment
export ENVIRONMENT=production
export DEBUG=False

# 2. Configure secure database
export DATABASE_URL_ASYNC="postgresql+asyncpg://user:pass@prod-db/drum_notation"

# 3. Set up reverse proxy (nginx)
# Configure SSL certificates
# Set up domain and DNS

# 4. Deploy with gunicorn
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker

# 5. Set up monitoring and logging
```

### Cloud Deployment Options
- **AWS**: ECS, RDS, S3 for file storage
- **Google Cloud**: Cloud Run, Cloud SQL, Cloud Storage
- **Azure**: Container Instances, PostgreSQL, Blob Storage
- **Heroku**: Simple deployment with PostgreSQL add-on

---

## 📈 Future Roadmap

### Phase 1: ML Integration (Next)
- [ ] Audio extraction with FFmpeg
- [ ] Drum onset detection models
- [ ] Instrument classification
- [ ] Background job processing

### Phase 2: Notation Generation
- [ ] MusicXML generation
- [ ] Visual notation rendering
- [ ] Tempo and time signature detection
- [ ] Export to various formats

### Phase 3: Advanced Features
- [ ] Computer vision for drumstick tracking
- [ ] Multi-camera angle support
- [ ] Real-time processing
- [ ] Mobile app integration

### Phase 4: AI Enhancement
- [ ] OpenAI integration for notation improvement
- [ ] Style analysis and suggestions
- [ ] Educational content generation
- [ ] Performance analysis

---

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Make changes and add tests
4. Run test suite: `pytest`
5. Commit changes: `git commit -m 'Add amazing feature'`
6. Push to branch: `git push origin feature/amazing-feature`
7. Create Pull Request

### Code Standards
- Follow PEP 8 style guide
- Add type hints to all functions
- Write comprehensive tests
- Update documentation
- Use conventional commit messages

---

## 📞 Support & Contact

### Documentation
- **API Docs**: http://localhost:8000/docs
- **Database Schema**: See section above
- **Examples**: Check `/tests` directory

### Issues & Bugs
- Create GitHub issues with detailed descriptions
- Include error logs and reproduction steps
- Tag with appropriate labels

### License
This project is licensed under the MIT License - see the LICENSE file for details.

---

**🎵 Ready to transform drum performances into beautiful musical notation! 🥁**

Start with: `uvicorn app.main:app --reload` and visit `http://localhost:8000/docs`
