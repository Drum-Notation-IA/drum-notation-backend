# Audio Processing Module

## Overview

The Audio Processing Module is a comprehensive system for analyzing drum performances from video files. It provides advanced audio extraction, drum detection, source separation, and pattern analysis capabilities powered by machine learning and digital signal processing techniques.

## Features

### 🎵 Audio Extraction
- FFmpeg-based audio extraction from video files
- Support for multiple sample rates and channel configurations
- High-quality WAV output optimized for drum analysis
- Background job processing with progress tracking

### 🥁 Drum Detection
- Multi-algorithm onset detection (spectral flux, energy-based, complex domain)
- Machine learning-based drum classification
- Support for multiple drum types: kick, snare, hi-hat, cymbals, toms
- Velocity and confidence analysis
- Tempo and meter detection

### 🎛️ Source Separation
- Advanced source separation algorithms:
  - Non-negative Matrix Factorization (NMF)
  - Independent Component Analysis (ICA)
  - Spectral masking
- Drum isolation from mixed audio
- Professional stem export for DAW integration

### 🎼 Pattern Analysis
- Rhythmic pattern detection
- Beat quantization
- Complexity scoring
- Musical structure analysis

### 🔊 Audio Enhancement
- Frequency-specific drum enhancement
- Dynamic range compression
- Harmonic/percussive separation
- Multi-band processing

## Module Structure

```
audio_processing/
├── __init__.py
├── README.md                 # This file
├── router.py                 # FastAPI endpoints
├── service.py               # Core audio processing service
├── detection.py             # Drum detection algorithms
├── separation.py            # Source separation algorithms
└── schemas.py              # Pydantic response schemas
```

## Dependencies

### Required
- `librosa` - Advanced audio analysis
- `soundfile` - Audio I/O operations
- `scipy` - Signal processing algorithms
- `numpy` - Numerical computations
- `scikit-learn` - Machine learning algorithms
- `ffmpeg` - Audio/video processing (system dependency)

### Optional
- `resampy` - High-quality audio resampling
- `essentia` - Advanced audio analysis features
- `xgboost` - Enhanced ML classification
- `lightgbm` - Fast gradient boosting

## API Endpoints

### Audio Extraction
- `POST /audio/extract/{video_id}` - Extract audio from video
- `GET /audio/extract/{video_id}/status` - Check extraction status
- `GET /audio/info/{video_id}` - Get audio file information

### Audio Analysis
- `GET /audio/features/{video_id}` - Extract audio features
- `POST /audio/analyze/{video_id}` - Start comprehensive analysis
- `GET /audio/analysis/comprehensive/{video_id}` - Get complete analysis

### Drum Detection
- `POST /audio/detect-drums/{video_id}` - Basic drum detection
- `POST /audio/detect-drums-advanced/{video_id}` - Advanced ML detection

### Source Separation
- `POST /audio/separate-sources/{video_id}` - Separate drum sources
- `POST /audio/create-stems/{video_id}` - Create professional stems
- `POST /audio/enhance-drums/{video_id}` - Enhance drum elements

### Job Management
- `GET /audio/jobs/my-jobs` - List user's audio jobs
- `POST /audio/jobs/{job_id}/cancel` - Cancel running job
- `POST /audio/jobs/{job_id}/retry` - Retry failed job
- `GET /audio/pipeline/{video_id}` - Get processing pipeline status

### Settings & Administration
- `GET /audio/settings/recommended` - Get recommended settings
- `GET /audio/settings/supported-formats` - List supported formats
- `POST /audio/admin/cleanup-temp` - Clean temporary files
- `GET /audio/admin/statistics` - Get processing statistics

## Usage Examples

### Basic Audio Extraction
```python
# Extract audio from video
response = await client.post("/audio/extract/video_uuid", params={
    "sample_rate": 44100,
    "channels": 1
})

# Check extraction status
status = await client.get("/audio/extract/video_uuid/status")
```

### Advanced Drum Detection
```python
# Detect drums with ML algorithms
detection_result = await client.post("/audio/detect-drums-advanced/video_uuid", params={
    "confidence_threshold": 0.6,
    "save_events": True
})

print(f"Detected {detection_result['detection_results']['total_events']} drum events")
```

### Source Separation
```python
# Separate drum sources
separation_result = await client.post("/audio/separate-sources/video_uuid", params={
    "method": "spectral",
    "save_sources": True
})

# Create professional stems
stems = await client.post("/audio/create-stems/video_uuid", params={
    "export_format": "wav",
    "bit_depth": 24,
    "normalize": True
})
```

### Comprehensive Analysis
```python
# Get complete audio analysis
analysis = await client.get("/audio/analysis/comprehensive/video_uuid", params={
    "include_detection": True,
    "include_separation": False,
    "include_patterns": True
})

print(f"Tempo: {analysis['tempo_analysis']['tempo']} BPM")
print(f"Detected {analysis['drum_detection']['total_events']} drum events")
```

## Configuration

### Detection Configuration
```python
class DrumDetectionConfig:
    # Onset detection
    onset_threshold = 0.3
    onset_min_distance = 0.05  # seconds
    
    # Frequency bands for drum classification
    frequency_bands = {
        "kick": (20, 120),
        "snare": (150, 300),
        "hihat": (8000, 16000),
        "crash": (6000, 20000),
    }
    
    # Classification thresholds
    classification_threshold = 0.6
    velocity_threshold = 0.1
```

### Separation Configuration
```python
class SeparationConfig:
    # STFT parameters
    n_fft = 2048
    hop_length = 512
    
    # Source separation
    n_components = 8
    max_iterations = 200
    
    # Masking
    mask_threshold = 0.1
    mask_smoothing = True
```

## Algorithm Details

### Drum Detection Pipeline
1. **Onset Detection**: Multi-algorithm approach combining spectral flux, energy-based, and complex domain methods
2. **Feature Extraction**: Spectral features, energy patterns, frequency band analysis, MFCCs, chroma features
3. **Classification**: Rule-based classification with frequency band analysis and spectral characteristics
4. **Post-processing**: Duplicate removal, velocity smoothing, temporal filtering

### Source Separation Methods
1. **Spectral Masking**: Frequency-based separation using drum-specific frequency bands
2. **NMF**: Non-negative Matrix Factorization for parts-based decomposition
3. **ICA**: Independent Component Analysis for blind source separation

### Quality Metrics
- **Signal-to-Distortion Ratio (SDR)**: Measures separation quality
- **Source Diversity**: Inter-source correlation analysis
- **Reconstruction Error**: Difference between original and reconstructed audio

## Performance Considerations

### Recommended Settings
- **Sample Rate**: 44100 Hz (standard for drum analysis)
- **Channels**: 1 (mono recommended for drum detection)
- **Format**: WAV (uncompressed for best quality)
- **Bit Depth**: 16-bit minimum, 24-bit recommended

### Processing Times
- **Audio Extraction**: 30-60 seconds per minute of video
- **Drum Detection**: 1-3 minutes per minute of audio
- **Source Separation**: 2-5 minutes per minute of audio
- **Stem Creation**: 3-7 minutes per minute of audio

### Memory Usage
- **Basic Analysis**: ~100MB per minute of audio
- **Source Separation**: ~500MB per minute of audio
- **Temporary Files**: 2-5x original audio file size

## Error Handling

### Common Issues
1. **Missing FFmpeg**: Install FFmpeg system dependency
2. **Audio Libraries Unavailable**: Install librosa, soundfile, scipy
3. **Memory Issues**: Reduce processing chunk size or use shorter audio clips
4. **Format Issues**: Ensure input video has audio track

### Error Responses
All endpoints return structured error responses:
```json
{
    "detail": "Error description",
    "error_type": "ProcessingError",
    "video_id": "uuid",
    "timestamp": "2024-01-01T00:00:00Z"
}
```

## Testing

Run the comprehensive test suite:
```bash
python test_audio_processing.py
```

The test script covers:
- Library availability and imports
- Synthetic audio generation
- Detection algorithm testing
- Source separation validation
- Integration testing
- Performance benchmarking

## Future Enhancements

### Planned Features
- Real-time audio processing
- WebSocket progress updates
- Custom drum kit training
- MIDI export functionality
- Cloud processing integration
- Advanced ML models (transformer-based)

### Algorithm Improvements
- Deep learning-based drum detection
- Improved source separation with DNN models
- Automatic drum kit identification
- Groove analysis and humanization metrics
- Multi-track drum separation

## Contributing

When contributing to the audio processing module:

1. **Testing**: Always run the test suite before submitting changes
2. **Performance**: Profile new algorithms and document performance impacts
3. **Documentation**: Update this README for new features or API changes
4. **Dependencies**: Minimize new dependencies and make them optional when possible
5. **Error Handling**: Provide clear error messages and fallback behaviors

## Troubleshooting

### Installation Issues
```bash
# Install audio dependencies
pip install librosa soundfile scipy numpy scikit-learn

# Install FFmpeg (system dependency)
# Ubuntu/Debian: apt-get install ffmpeg
# macOS: brew install ffmpeg
# Windows: Download from https://ffmpeg.org/
```

### Common Problems
- **"Audio processing libraries not available"**: Install missing Python packages
- **"FFmpeg not found"**: Install FFmpeg system dependency
- **Memory errors**: Reduce audio chunk size or use lower quality settings
- **Slow processing**: Consider using GPU acceleration if available

### Debug Mode
Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## License

This module is part of the Drum Notation Backend project and follows the same license terms.

---

For questions or issues, please refer to the main project documentation or create an issue in the project repository.