# 🎵 Media Module Documentation

## Overview

The Media Module provides comprehensive file management capabilities for the Drum Notation Backend. It supports uploading, storing, and managing audio, video, and image files with proper authentication, validation, and storage management.

## Features

- **Multi-format Support**: Audio (MP3, WAV, FLAC, M4A), Video (MP4, MOV, AVI, MKV), Images (JPG, PNG, GIF)
- **File Validation**: Content type validation, file size limits, security checks
- **Storage Management**: Organized file storage with unique naming and conflict resolution
- **User Ownership**: Files are associated with users, with proper access control
- **Soft Delete**: Files can be soft-deleted and restored
- **Statistics**: User storage usage tracking and system-wide statistics
- **Download Support**: Secure file download with proper headers

## Database Schema

### Media Table
```sql
CREATE TABLE media (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL UNIQUE,
    file_path TEXT NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    media_type VARCHAR(20) NOT NULL,
    file_size INTEGER NOT NULL,
    description TEXT,
    uploaded_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL
);
```

## API Endpoints

### Upload Media
```http
POST /media/upload
Content-Type: multipart/form-data
Authorization: Bearer {token}

file: (binary file)
description: (optional string)
```

**Response**: `201 Created`
```json
{
    "message": "File uploaded successfully",
    "media": {
        "id": "uuid",
        "original_filename": "example.mp3",
        "stored_filename": "uuid.mp3",
        "file_path": "uploads/audio/uuid.mp3",
        "content_type": "audio/mpeg",
        "media_type": "audio",
        "file_size": 1024000,
        "description": "Optional description",
        "uploaded_by": "user_uuid",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z"
    }
}
```

### List Media Files
```http
GET /media/?page=1&per_page=20&media_type=audio&user_id=uuid&owner_only=false
Authorization: Bearer {token}
```

**Response**: `200 OK`
```json
{
    "media": [...],
    "total": 42,
    "page": 1,
    "per_page": 20,
    "pages": 3
}
```

### Get Current User's Files
```http
GET /media/my-files?page=1&per_page=20&media_type=audio
Authorization: Bearer {token}
```

### Get Media Details
```http
GET /media/{media_id}
Authorization: Bearer {token}
```

### Update Media Metadata
```http
PUT /media/{media_id}
Authorization: Bearer {token}
Content-Type: application/json

{
    "original_filename": "new_name.mp3",
    "description": "Updated description"
}
```

### Download Media File
```http
GET /media/{media_id}/download
Authorization: Bearer {token}
```

### Delete Media File
```http
DELETE /media/{media_id}?hard_delete=false
Authorization: Bearer {token}
```

### Restore Deleted Media
```http
POST /media/{media_id}/restore
Authorization: Bearer {token}
```

### Get User Statistics
```http
GET /media/stats/my-usage
Authorization: Bearer {token}
```

**Response**: `200 OK`
```json
{
    "total_files": 15,
    "total_size_bytes": 52428800,
    "total_size_mb": 50.0,
    "files_by_type": {
        "audio": 10,
        "video": 3,
        "image": 2
    },
    "storage_quota_bytes": 1073741824,
    "storage_quota_mb": 1024,
    "storage_used_percentage": 4.88
}
```

### Get Storage Statistics (Admin)
```http
GET /media/stats/storage
Authorization: Bearer {token}
```

### Cleanup Orphaned Files (Admin)
```http
POST /media/admin/cleanup-orphaned
Authorization: Bearer {token}
```

## File Storage Structure

```
uploads/
├── audio/
│   ├── uuid1.mp3
│   ├── uuid2.wav
│   └── uuid3.flac
├── video/
│   ├── uuid4.mp4
│   └── uuid5.mov
└── image/
    ├── uuid6.jpg
    └── uuid7.png
```

## File Size Limits

- **Audio**: 50MB maximum
- **Video**: 100MB maximum  
- **Image**: 10MB maximum
- **User Quota**: 1GB total storage per user

## Supported File Types

### Audio Files
- MP3 (`audio/mpeg`)
- WAV (`audio/wav`, `audio/x-wav`)
- M4A (`audio/mp4`)
- FLAC (`audio/flac`)
- OGG (`audio/ogg`)

### Video Files
- MP4 (`video/mp4`)
- MOV (`video/quicktime`)
- AVI (`video/x-msvideo`)
- MKV (`video/x-matroska`)
- WebM (`video/webm`)

### Image Files
- JPEG (`image/jpeg`, `image/jpg`)
- PNG (`image/png`)
- GIF (`image/gif`)
- WebP (`image/webp`)

## Security Features

- **Authentication Required**: All endpoints require valid JWT token
- **User Ownership**: Users can only access their own files
- **File Type Validation**: Only allowed file types are accepted
- **Size Limits**: Enforced file size restrictions
- **Filename Sanitization**: Dangerous characters are blocked
- **Unique Storage Names**: Prevents filename conflicts and directory traversal

## Module Architecture

### Models (`models.py`)
- `Media`: Main media file model with relationships
- `MediaType`: Enum for supported media types

### Schemas (`schemas.py`)
- `MediaCreate`: File upload validation
- `MediaRead`: File information response
- `MediaUpdate`: Metadata update validation
- `MediaListResponse`: Paginated list response

### Repository (`repository.py`)
- Database CRUD operations
- Relationship handling with eager loading
- Soft delete support

### Service (`service.py`)
- Business logic for file operations
- File validation and storage management
- User quota enforcement

### Storage (`storage.py`)
- File system operations
- Directory management
- Cleanup utilities

### Router (`routers.py`)
- FastAPI endpoints
- Authentication integration
- Error handling

## Testing

Use the included test script to verify all endpoints:

```bash
python test_media_endpoints.py
```

The test script will:
1. Create sample test files
2. Authenticate a test user
3. Test all media endpoints
4. Clean up test data

## Error Handling

### Common Error Responses

**400 Bad Request**
```json
{
    "detail": "File type audio/x-unknown is not allowed"
}
```

**401 Unauthorized**
```json
{
    "detail": "Could not validate credentials"
}
```

**403 Forbidden**
```json
{
    "detail": "Not authorized to access this media file"
}
```

**404 Not Found**
```json
{
    "detail": "Media file not found"
}
```

**413 Request Entity Too Large**
```json
{
    "detail": "File size exceeds maximum allowed size for audio files (50MB)"
}
```

## Configuration

### Environment Variables

```bash
# File storage directory (optional, defaults to 'uploads')
MEDIA_STORAGE_DIR=uploads

# Maximum file sizes (optional, uses defaults if not set)
MAX_AUDIO_SIZE=52428800    # 50MB
MAX_VIDEO_SIZE=104857600   # 100MB  
MAX_IMAGE_SIZE=10485760    # 10MB

# User storage quota (optional, defaults to 1GB)
USER_STORAGE_QUOTA=1073741824
```

## Future Enhancements

- [ ] Cloud storage integration (AWS S3, Google Cloud Storage)
- [ ] Image thumbnails generation
- [ ] Audio waveform generation
- [ ] Video thumbnail extraction
- [ ] Bulk upload support
- [ ] File sharing and permissions
- [ ] Content-based duplicate detection
- [ ] Automatic file compression
- [ ] CDN integration
- [ ] Advanced search and filtering

## Dependencies

Required packages:
- `python-multipart`: For file upload support
- `aiofiles`: For async file operations

## Installation

1. Install dependencies:
```bash
pip install python-multipart aiofiles
```

2. Run database migration:
```bash
alembic upgrade head
```

3. Create upload directories:
```bash
mkdir -p uploads/{audio,video,image}
```

4. Start the server:
```bash
uvicorn app.main:app --reload
```

The media endpoints will be available at `http://localhost:8000/media/` and documented at `http://localhost:8000/docs`.