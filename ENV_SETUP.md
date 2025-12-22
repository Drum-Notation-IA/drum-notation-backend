# Environment Configuration Guide

This guide helps you set up the environment variables for the Drum Notation Backend.

## Required Environment Variables

Create a `.env` file in the project root with the following variables:

### Database Configuration
```env
# PostgreSQL Database URLs
DATABASE_URL_ASYNC=postgresql+asyncpg://username:password@localhost:5432/drum_notation_db
DATABASE_URL_SYNC=postgresql://username:password@localhost:5432/drum_notation_db
```

### Security Settings
```env
# JWT Authentication
SECRET_KEY=your-super-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### OpenAI Integration (Optional but Recommended)
```env
# OpenAI API Configuration
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4
OPENAI_MAX_TOKENS=1500
OPENAI_TEMPERATURE=0.7
```

### File Storage
```env
# Upload Configuration
UPLOAD_DIR=uploads
MAX_FILE_SIZE=100000000  # 100MB in bytes
```

### Audio Processing
```env
# FFmpeg Configuration
FFMPEG_PATH=ffmpeg  # Or full path: C:\path\to\ffmpeg.exe
```

## Complete Example `.env` File

```env
# Database
DATABASE_URL_ASYNC=postgresql+asyncpg://postgres:mypassword@localhost:5432/drum_notation_db
DATABASE_URL_SYNC=postgresql://postgres:mypassword@localhost:5432/drum_notation_db

# Security
SECRET_KEY=super-secret-key-for-jwt-tokens-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OpenAI (for AI-powered features)
OPENAI_API_KEY=sk-proj-your-actual-openai-api-key-here
OPENAI_MODEL=gpt-4
OPENAI_MAX_TOKENS=1500
OPENAI_TEMPERATURE=0.7

# File Storage
UPLOAD_DIR=uploads
MAX_FILE_SIZE=100000000

# Audio Processing
FFMPEG_PATH=ffmpeg
```

## Setup Instructions

### 1. Create Database
```bash
# Create PostgreSQL database
createdb drum_notation_db

# Or using psql
psql -U postgres -c "CREATE DATABASE drum_notation_db;"
```

### 2. Generate Secret Key
```bash
# Generate a secure secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Get OpenAI API Key
1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Copy the key (starts with `sk-`)
4. Add it to your `.env` file

### 4. Install FFmpeg
- **Windows**: Download from https://ffmpeg.org/download.html
- **macOS**: `brew install ffmpeg`
- **Ubuntu/Debian**: `sudo apt install ffmpeg`

### 5. Create Upload Directory
```bash
mkdir -p uploads/videos uploads/audio
```

## Production Considerations

### Security
- Use a strong, random SECRET_KEY (32+ characters)
- Keep your OpenAI API key secure and never commit it to version control
- Use environment-specific database credentials

### Performance
- Consider using connection pooling for database
- Set appropriate OpenAI rate limits
- Configure proper file size limits

### Monitoring
```env
# Optional: Add logging configuration
LOG_LEVEL=INFO
DEBUG=False
```

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Ensure PostgreSQL is running
   - Check username/password/host/port
   - Verify database exists

2. **OpenAI API Errors**
   - Verify API key is correct and active
   - Check API quota and billing
   - Ensure network connectivity

3. **FFmpeg Not Found**
   - Install FFmpeg system-wide
   - Or provide full path in FFMPEG_PATH

4. **File Upload Issues**
   - Check upload directory permissions
   - Verify MAX_FILE_SIZE setting
   - Ensure sufficient disk space

### Testing Configuration

Run the test script to verify your setup:
```bash
python test_openai_setup.py
```

This will check:
- ✅ Environment variables
- ✅ Database connectivity
- ✅ OpenAI API configuration
- ✅ File system permissions
- ✅ FFmpeg availability

## Environment-Specific Examples

### Development
```env
DATABASE_URL_ASYNC=postgresql+asyncpg://postgres:dev123@localhost:5432/drum_notation_dev
SECRET_KEY=dev-secret-key-not-for-production
OPENAI_API_KEY=sk-your-dev-api-key
DEBUG=True
LOG_LEVEL=DEBUG
```

### Production
```env
DATABASE_URL_ASYNC=postgresql+asyncpg://produser:secure_password@prod-db:5432/drum_notation_prod
SECRET_KEY=super-secure-production-key-32-chars-long
OPENAI_API_KEY=sk-your-prod-api-key
DEBUG=False
LOG_LEVEL=INFO
```

### Testing
```env
DATABASE_URL_ASYNC=postgresql+asyncpg://postgres:test123@localhost:5432/drum_notation_test
SECRET_KEY=test-secret-key
OPENAI_API_KEY=  # Empty for testing without API calls
```

## Next Steps

After setting up your `.env` file:

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Run migrations**: `alembic upgrade head`
3. **Start the server**: `uvicorn app.main:app --reload`
4. **Test the API**: Visit `http://localhost:8000/docs`

Your Drum Notation Backend with OpenAI integration is ready! 🥁🤖