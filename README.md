# Drum Notation Backend - Project Structure

## 📁 **Clean Project Overview**

This document outlines the clean, organized structure of the Drum Notation ML Backend after removing unnecessary files and optimizing for development.

```
Drum-Notation-Backend/
├── 📁 alembic/                    # Database migrations
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
├── 📁 app/                        # Main application code
│   ├── 📁 core/                   # Core functionality
│   │   ├── config.py              # Configuration settings
│   │   ├── database.py            # Database connection & session
│   │   ├── dependencies.py        # FastAPI dependencies (auth, etc.)
│   │   ├── password_utils.py      # Password validation utilities
│   │   └── security.py            # Authentication & password hashing
│   ├── 📁 db/                     # Database models base
│   │   └── base.py                # SQLAlchemy base class
│   ├── 📁 modules/                # Feature modules
│   │   ├── 📁 audio_processing/   # Audio ML processing
│   │   │   ├── detection.py       # Drum hit detection
│   │   │   ├── separation.py      # Audio source separation
│   │   │   └── service.py         # Audio processing service
│   │   ├── 📁 jobs/               # Background job processing
│   │   │   ├── models.py          # Job status models
│   │   │   ├── router.py          # Job API endpoints
│   │   │   └── worker.py          # Background workers
│   │   ├── 📁 media/              # File upload & storage
│   │   │   ├── models.py          # Video/Audio file models
│   │   │   ├── router.py          # Upload API endpoints
│   │   │   ├── schemas.py         # Media data schemas
│   │   │   ├── service.py         # Media processing service
│   │   │   └── storage.py         # File storage utilities
│   │   ├── 📁 notation/           # Musical notation generation
│   │   │   ├── models.py          # Notation data models
│   │   │   ├── router.py          # Notation API endpoints
│   │   │   ├── schemas.py         # Notation data schemas
│   │   │   └── service.py         # Notation generation service
│   │   ├── 📁 users/              # User management (COMPLETE ✅)
│   │   │   ├── __init__.py        # Module exports
│   │   │   ├── models.py          # User database model
│   │   │   ├── repository.py      # Data access layer
│   │   │   ├── router.py          # API endpoints
│   │   │   ├── schemas.py         # Request/response models
│   │   │   └── service.py         # Business logic
│   │   ├── 📁 vision/             # Computer vision (pose detection)
│   │   │   ├── mediapipe.py       # MediaPipe implementation
│   │   │   └── openpose.py        # OpenPose implementation
│   │   └── 📁 workers/            # Celery workers
│   │       └── celery_app.py      # Celery configuration
│   ├── 📁 shared/                 # Shared utilities
│   │   └── base_model.py          # Base model with timestamps & soft delete
│   ├── __init__.py                # App package init
│   └── main.py                    # FastAPI application entry point
├── 📁 tests/                      # Test files
│   └── test_users.py              # User module tests
├── 📁 dnvenv/                     # Virtual environment (gitignored)
├── .env                           # Environment variables (gitignored)
├── .env.example                   # Environment variables template
├── .gitignore                     # Git ignore rules
├── alembic.ini                    # Alembic configuration
├── README.md                      # Project documentation
└── requirements.txt               # Python dependencies
```

## 🎯 **Module Status**

| Module | Status | Description |
|--------|--------|-------------|
| **Users** | ✅ **COMPLETE** | Full CRUD, authentication, JWT tokens |
| **Roles** | ✅ **COMPLETE** | Role-based access control |
| **Media** | ✅ **COMPLETE** | File upload, storage, and management |
| **Audio Processing** | 🟡 Skeleton | ML models for drum detection |
| **Jobs** | 🟡 Skeleton | Background processing queue |
| **Notation** | 🟡 Skeleton | Musical notation generation |
| **Vision** | 🟡 Skeleton | Pose detection for drumming |

## 🔧 **Core Components**

### **Configuration (`app/core/config.py`)**
- Environment-based settings
- Database URLs, JWT secrets
- Auto-generates secure keys in development

### **Database (`app/core/database.py`)**
- Async PostgreSQL connection
- Session management
- Connection pooling

### **Security (`app/core/security.py`)**
- bcrypt password hashing
- JWT token generation/validation
- Handles 72-byte bcrypt limitation

### **Authentication (`app/core/dependencies.py`)**
- JWT token validation
- Current user dependency injection
- Optional authentication support

## 👤 **Users Module (Complete)**

The users module is fully implemented with:

### **API Endpoints:**
- `POST /users/register` - User registration
- `POST /users/login` - Authentication
- `GET /users/me` - Current user info
- `PATCH /users/me` - Update profile
- `POST /users/change-password` - Change password
- `DELETE /users/me` - Delete account
- `GET /users/` - List all users (admin)
- And more...

### **Features:**
- ✅ User registration with email validation
- ✅ Secure password hashing (bcrypt)
- ✅ JWT-based authentication
- ✅ Complete CRUD operations
- ✅ Soft delete functionality
- ✅ Password change with validation
- ✅ Email uniqueness enforcement
- ✅ Async database operations

## 🔐 **Roles Module (Complete)**

Role-based access control system:

### **API Endpoints:**
- `POST /roles/` - Create new role
- `GET /roles/` - List all roles
- `POST /roles/assign` - Assign role to user
- `DELETE /roles/remove` - Remove role from user
- `GET /roles/{role_id}/users` - List users with role
- And more...

### **Features:**
- ✅ Many-to-many user-role relationships
- ✅ Role assignment and removal
- ✅ Complete CRUD operations
- ✅ Relationship management
- ✅ Eager loading to prevent async issues

## 🎵 **Media Module (Complete)**

Comprehensive file management system:

### **API Endpoints:**
- `POST /media/upload` - Upload media files
- `GET /media/` - List media files with pagination
- `GET /media/my-files` - Current user's files
- `GET /media/{id}` - Get media details
- `PUT /media/{id}` - Update media metadata
- `DELETE /media/{id}` - Delete media file
- `GET /media/{id}/download` - Download file
- `POST /media/{id}/restore` - Restore deleted file
- `GET /media/stats/my-usage` - User statistics

### **Features:**
- ✅ Multi-format support (Audio: MP3, WAV, FLAC; Video: MP4, MOV; Images: JPG, PNG)
- ✅ File validation and size limits
- ✅ Organized storage with unique naming
- ✅ User ownership and access control
- ✅ Soft delete and restore
- ✅ Storage quota management (1GB per user)
- ✅ Statistics and usage tracking
- ✅ Secure download with proper headers

## 🗃️ **Database Schema**

The database is designed for the complete drum notation system:

```sql
-- Users (implemented)
users (id, email, password_hash, created_at, updated_at, deleted_at)

-- Roles (implemented)
roles (id, name, description, created_at, updated_at, deleted_at)
user_roles (user_id, role_id, assigned_at)

-- Media (implemented)
media (id, original_filename, stored_filename, file_path, content_type, 
       media_type, file_size, description, uploaded_by, created_at, updated_at, deleted_at)

-- Audio Processing (ready for implementation)  
audio_files (id, media_id, sample_rate, channels, ...)
drum_events (id, audio_file_id, time_seconds, instrument, velocity, ...)

-- Job Processing (ready for implementation)
processing_jobs (id, media_id, job_type, status, progress, ...)

-- Notation (ready for implementation)
notations (id, media_id, tempo, time_signature, notation_json, ...)

-- AI Enhancement (ready for implementation)
openai_enrichments (id, notation_id, model, input_json, output_json, ...)
```

## 🚀 **Getting Started**

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

3. **Run migrations:**
   ```bash
   alembic upgrade head
   ```

4. **Start the server:**
   ```bash
   uvicorn app.main:app --reload
   ```

5. **Test the API:**
   ```bash
   curl -X POST "http://127.0.0.1:8000/users/register" \
        -H "Content-Type: application/json" \
        -d '{"email": "test@example.com", "password": "SecurePass123!"}'
   ```

## 📋 **Next Development Steps**

1. **Audio Processing** - Integrate ML models for drum detection
2. **Jobs Module** - Background processing with Celery  
3. **Vision Module** - Computer vision for drumstick tracking
4. **Notation Module** - Generate musical notation from analysis
5. **Integration** - Connect media files to audio processing pipeline

## 🧪 **Testing**

- Run tests: `pytest tests/`
- User module has comprehensive test coverage
- Tests include CRUD operations, authentication, and error cases

## 🔒 **Security Features**

- bcrypt password hashing with 72-byte limit handling
- JWT token authentication with configurable expiration
- Input validation with Pydantic schemas
- SQL injection protection with SQLAlchemy
- Soft delete for data retention
- Environment-based configuration

## 📁 **File Storage Structure**

```
uploads/
├── audio/          # MP3, WAV, FLAC, M4A files
├── video/          # MP4, MOV, AVI, MKV files
└── image/          # JPG, PNG, GIF, WebP files
```

## 🧪 **Testing Media Module**

Run the comprehensive media endpoint tests:
```bash
python test_media_endpoints.py
```

This will test:
- File upload with validation
- File listing and pagination
- Metadata updates
- File downloads
- Soft delete and restore
- Storage statistics

---

**Project Status**: Core modules complete ✅ | Media system ready ✅ | Ready for ML integration 🚀