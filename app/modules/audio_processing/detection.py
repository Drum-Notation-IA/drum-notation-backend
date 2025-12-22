import logging
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

# Import audio processing libraries with error handling
try:
    import librosa
    import scipy.signal
    from scipy import ndimage

    AUDIO_LIBS_AVAILABLE = True
except ImportError:
    AUDIO_LIBS_AVAILABLE = False
    librosa = None
    scipy = None
    ndimage = None

from app.modules.media.models import AudioFile
from app.modules.media.repository import AudioFileRepository

logger = logging.getLogger(__name__)


class DrumEvent:
    """Represents a detected drum event"""

    def __init__(
        self,
        timestamp: float,
        drum_type: str,
        confidence: float,
        velocity: float,
        frequency: Optional[float] = None,
        duration: Optional[float] = None,
    ):
        self.timestamp = timestamp
        self.drum_type = drum_type
        self.confidence = confidence
        self.velocity = velocity
        self.frequency = frequency
        self.duration = duration

    def to_dict(self) -> Dict:
        """Convert to dictionary representation"""
        return {
            "timestamp": self.timestamp,
            "drum_type": self.drum_type,
            "confidence": self.confidence,
            "velocity": self.velocity,
            "frequency": self.frequency,
            "duration": self.duration,
        }


class DrumDetectionConfig:
    """Configuration for drum detection algorithms"""

    def __init__(self):
        # Onset detection parameters
        self.hop_length = 512
        self.window_length = 2048
        self.sr = 44100

        # Onset detection thresholds
        self.onset_threshold = 0.3
        self.onset_min_distance = 0.05  # Minimum time between onsets (seconds)

        # Frequency band definitions for drum classification
        self.frequency_bands = {
            "kick": (20, 120),  # Kick drum frequency range
            "snare": (150, 300),  # Snare drum fundamental
            "hihat": (8000, 16000),  # Hi-hat frequency range
            "crash": (6000, 20000),  # Crash cymbal
            "tom_low": (80, 200),  # Low tom
            "tom_mid": (200, 400),  # Mid tom
            "tom_high": (400, 800),  # High tom
        }

        # Classification thresholds
        self.classification_threshold = 0.6
        self.velocity_threshold = 0.1

        # Spectral features for classification
        self.n_mfcc = 13
        self.n_chroma = 12
        self.n_spectral_features = 7


class DrumDetector:
    """Advanced drum detection and classification system"""

    def __init__(self, config: Optional[DrumDetectionConfig] = None):
        self.config = config or DrumDetectionConfig()
        self.audio_repository = AudioFileRepository()

        # Pre-computed feature extractors
        self._initialize_extractors()

    def _initialize_extractors(self):
        """Initialize feature extraction components"""
        if not AUDIO_LIBS_AVAILABLE:
            logger.warning("Audio processing libraries not available")
            return

        # Initialize spectral analysis windows
        if scipy and scipy.signal:
            self.stft_window = scipy.signal.get_window(
                "hann", self.config.window_length
            )
        else:
            self.stft_window = None

    async def detect_drums_from_audio_file(
        self, db: AsyncSession, audio_file: AudioFile, save_events: bool = True
    ) -> List[DrumEvent]:
        """
        Detect drum events from an audio file

        Args:
            db: Database session
            audio_file: AudioFile model instance
            save_events: Whether to save detected events to database

        Returns:
            List of detected drum events
        """
        if not AUDIO_LIBS_AVAILABLE:
            raise RuntimeError("Audio processing libraries not available")

        try:
            # Load audio data
            if librosa is None:
                raise RuntimeError("librosa is not available")
            audio_path = str(audio_file.storage_path)
            y, sr = librosa.load(audio_path, sr=self.config.sr)

            logger.info(f"Loaded audio: {len(y)} samples at {sr}Hz")

            # Detect onsets
            onsets = await self._detect_onsets(y, int(sr))
            logger.info(f"Detected {len(onsets)} onsets")

            # Extract features around each onset
            features = await self._extract_onset_features(y, int(sr), onsets)

            # Classify drum types
            drum_events = await self._classify_drum_events(onsets, features, int(sr))

            # Post-process and filter events
            drum_events = await self._post_process_events(drum_events)

            # Save to database if requested
            if save_events and drum_events:
                await self._save_drum_events(db, str(audio_file.id), drum_events)

            logger.info(f"Detected {len(drum_events)} drum events")
            return drum_events

        except Exception as e:
            logger.error(f"Drum detection failed: {e}")
            raise

    async def _detect_onsets(self, y: np.ndarray, sr: int) -> np.ndarray:
        """
        Detect onset times using multiple onset detection algorithms

        Args:
            y: Audio time series
            sr: Sample rate

        Returns:
            Array of onset times in seconds
        """
        # Spectral flux onset detection
        if librosa is not None:
            onset_frames_flux = librosa.onset.onset_detect(
                y=y,
                sr=sr,
                hop_length=self.config.hop_length,
                threshold=self.config.onset_threshold,
                pre_max=3,
                post_max=3,
                pre_avg=3,
                post_avg=5,
            )
        else:
            onset_frames_flux = np.array([])

        # Energy-based onset detection
        if librosa is not None:
            onset_frames_energy = librosa.onset.onset_detect(
                y=y,
                sr=sr,
                hop_length=self.config.hop_length,
                threshold=self.config.onset_threshold * 0.8,
                units="frames",
                onset_envelope=librosa.onset.onset_strength(
                    y=y, sr=sr, aggregate=np.median, hop_length=self.config.hop_length
                ),
            )
        else:
            onset_frames_energy = np.array([])

        # Complex domain onset detection (good for percussive sounds)
        if librosa is not None:
            stft = librosa.stft(
                y, hop_length=self.config.hop_length, n_fft=self.config.window_length
            )
            onset_frames_complex = librosa.onset.onset_detect(
                onset_envelope=librosa.onset.onset_strength(
                    S=np.abs(stft),
                    sr=sr,
                    hop_length=self.config.hop_length,
                    aggregate=np.median,
                ),
                sr=sr,
                hop_length=self.config.hop_length,
                threshold=self.config.onset_threshold * 1.2,
            )
        else:
            onset_frames_complex = np.array([])

        # Combine onset detections
        all_onset_frames = np.concatenate(
            [onset_frames_flux, onset_frames_energy, onset_frames_complex]
        )

        # Convert to time and remove duplicates
        if librosa is not None:
            all_onset_times = librosa.frames_to_time(
                all_onset_frames, sr=sr, hop_length=self.config.hop_length
            )
        else:
            all_onset_times = np.array([])

        # Remove onsets that are too close together
        unique_onsets = []
        all_onset_times_sorted = np.sort(all_onset_times)

        for onset_time in all_onset_times_sorted:
            if (
                not unique_onsets
                or (onset_time - unique_onsets[-1]) >= self.config.onset_min_distance
            ):
                unique_onsets.append(onset_time)

        return np.array(unique_onsets)

    async def _extract_onset_features(
        self, y: np.ndarray, sr: int, onsets: np.ndarray
    ) -> List[Dict[str, np.ndarray]]:
        """
        Extract features around each detected onset

        Args:
            y: Audio time series
            sr: Sample rate
            onsets: Array of onset times in seconds

        Returns:
            List of feature dictionaries for each onset
        """
        features = []

        # Define analysis window around each onset
        window_before = 0.01  # 10ms before onset
        window_after = 0.2  # 200ms after onset

        for onset_time in onsets:
            try:
                # Extract audio segment around onset
                start_sample = max(0, int((onset_time - window_before) * sr))
                end_sample = min(len(y), int((onset_time + window_after) * sr))
                segment = y[start_sample:end_sample]

                if len(segment) < sr * 0.05:  # Skip segments shorter than 50ms
                    continue

                # Extract various features
                feature_dict = {}

                # Spectral features
                if librosa is not None:
                    # Extract spectral features
                    stft = librosa.stft(segment, hop_length=self.config.hop_length)
                    magnitude = np.abs(stft)

                    feature_dict["spectral_centroid"] = (
                        librosa.feature.spectral_centroid(S=magnitude, sr=sr).mean()
                    )

                    feature_dict["spectral_rolloff"] = librosa.feature.spectral_rolloff(
                        S=magnitude, sr=sr
                    ).mean()

                    feature_dict["spectral_bandwidth"] = (
                        librosa.feature.spectral_bandwidth(S=magnitude, sr=sr).mean()
                    )

                    feature_dict["zero_crossing_rate"] = (
                        librosa.feature.zero_crossing_rate(segment).mean()
                    )

                    # Energy features
                    feature_dict["rms_energy"] = librosa.feature.rms(y=segment).mean()

                    # Frequency band energies
                    for drum_type, (
                        low_freq,
                        high_freq,
                    ) in self.config.frequency_bands.items():
                        # Create frequency mask
                        freqs = librosa.fft_frequencies(
                            sr=sr, n_fft=self.config.window_length
                        )
                        freq_mask = (freqs >= low_freq) & (freqs <= high_freq)

                        # Calculate energy in this band
                        if magnitude.size > 0:
                            band_energy = np.sum(magnitude[freq_mask, :], axis=0).mean()
                        else:
                            band_energy = 0.0
                        feature_dict[f"{drum_type}_energy"] = band_energy
                else:
                    # Default values when librosa is not available
                    feature_dict["spectral_centroid"] = 1000.0
                    feature_dict["spectral_rolloff"] = 2000.0
                    feature_dict["spectral_bandwidth"] = 500.0
                    feature_dict["zero_crossing_rate"] = 0.1
                    feature_dict["rms_energy"] = 0.1

                    # Default energy values for each drum type
                    for drum_type in self.config.frequency_bands.keys():
                        feature_dict[f"{drum_type}_energy"] = 0.1

                # Tempo and rhythm features (for context)
                if (
                    len(segment) > sr * 0.1 and librosa is not None
                ):  # Only for segments longer than 100ms
                    tempo, beats = librosa.beat.beat_track(y=segment, sr=sr)
                    feature_dict["local_tempo"] = tempo
                else:
                    feature_dict["local_tempo"] = 120.0

                # MFCC features
                if librosa is not None:
                    mfcc = librosa.feature.mfcc(
                        y=segment, sr=sr, n_mfcc=self.config.n_mfcc
                    )
                    feature_dict["mfcc"] = mfcc.mean(axis=1)

                    # Chroma features
                    chroma = librosa.feature.chroma_stft(y=segment, sr=sr)
                    feature_dict["chroma"] = chroma.mean(axis=1)
                else:
                    feature_dict["mfcc"] = np.zeros(self.config.n_mfcc)
                    feature_dict["chroma"] = np.zeros(self.config.n_chroma)

                features.append(feature_dict)

            except Exception as e:
                logger.warning(
                    f"Feature extraction failed for onset at {onset_time}s: {e}"
                )
                continue

        return features

    async def _classify_drum_events(
        self, onsets: np.ndarray, features: List[Dict[str, np.ndarray]], sr: int
    ) -> List[DrumEvent]:
        """
        Classify detected onsets as different drum types

        Args:
            onsets: Array of onset times
            features: List of feature dictionaries
            sr: Sample rate

        Returns:
            List of classified drum events
        """
        drum_events = []

        for i, (onset_time, feature_dict) in enumerate(zip(onsets, features)):
            try:
                # Rule-based classification using frequency band energies
                drum_type, confidence = await self._classify_single_event(feature_dict)

                # Calculate velocity from RMS energy
                velocity = min(1.0, feature_dict.get("rms_energy", 0.0) * 10)

                # Estimate fundamental frequency for tonal drums
                frequency = None
                if drum_type in ["tom_low", "tom_mid", "tom_high", "kick"]:
                    frequency = feature_dict.get("spectral_centroid", None)

                # Create drum event
                if confidence >= self.config.classification_threshold:
                    # Ensure proper type conversion for velocity and frequency
                    velocity_val = (
                        float(velocity)
                        if hasattr(velocity, "item")
                        else float(velocity)
                    )
                    frequency_val = None
                    if frequency is not None:
                        frequency_val = (
                            float(frequency)
                            if hasattr(frequency, "item")
                            else float(frequency)
                        )

                    event = DrumEvent(
                        timestamp=onset_time,
                        drum_type=drum_type,
                        confidence=confidence,
                        velocity=velocity_val,
                        frequency=frequency_val,
                        duration=0.1,  # Default duration
                    )
                    drum_events.append(event)

            except Exception as e:
                logger.warning(f"Classification failed for onset {i}: {e}")
                continue

        return drum_events

    async def _classify_single_event(self, features: Dict) -> Tuple[str, float]:
        """
        Classify a single drum event based on its features

        Args:
            features: Feature dictionary for the event

        Returns:
            Tuple of (drum_type, confidence)
        """
        # Initialize scores for each drum type
        scores = {}

        # Rule-based classification using frequency band energies
        for drum_type in self.config.frequency_bands.keys():
            energy_key = f"{drum_type}_energy"
            if energy_key in features:
                scores[drum_type] = features[energy_key]
            else:
                scores[drum_type] = 0.0

        # Additional rules based on spectral features
        spectral_centroid = features.get("spectral_centroid", 0)
        spectral_rolloff = features.get("spectral_rolloff", 0)
        zero_crossing_rate = features.get("zero_crossing_rate", 0)

        # Kick drum: low frequency, high energy
        if spectral_centroid < 200:
            scores["kick"] *= 1.5

        # Snare: mid frequency with noise component
        if 150 <= spectral_centroid <= 400 and zero_crossing_rate > 0.1:
            scores["snare"] *= 1.3

        # Hi-hat: high frequency, sharp attack
        if spectral_centroid > 5000 and zero_crossing_rate > 0.15:
            scores["hihat"] *= 1.4

        # Crash: very high frequency, sustained
        if spectral_rolloff > 8000:
            scores["crash"] *= 1.2

        # Find the drum type with highest score
        if not scores or max(scores.values()) == 0:
            return "unknown", 0.0

        best_drum = max(scores.keys(), key=lambda k: scores[k])
        max_score = scores[best_drum]

        # Normalize confidence (simple normalization)
        total_energy = sum(scores.values())
        confidence = max_score / total_energy if total_energy > 0 else 0.0
        confidence = min(1.0, confidence * 2)  # Scale and cap at 1.0

        return best_drum, confidence

    async def _post_process_events(self, events: List[DrumEvent]) -> List[DrumEvent]:
        """
        Post-process detected events to improve accuracy

        Args:
            events: List of detected drum events

        Returns:
            Filtered and processed drum events
        """
        if not events:
            return events

        # Sort events by timestamp
        events.sort(key=lambda e: e.timestamp)

        # Remove events with very low velocity
        events = [e for e in events if e.velocity >= self.config.velocity_threshold]

        # Remove duplicate events (same drum type within short time window)
        filtered_events = []
        for event in events:
            # Check for duplicates
            is_duplicate = False
            for prev_event in reversed(filtered_events[-5:]):  # Check last 5 events
                time_diff = event.timestamp - prev_event.timestamp
                if (
                    time_diff < 0.02  # Within 20ms
                    and event.drum_type == prev_event.drum_type
                    and abs(event.velocity - prev_event.velocity) < 0.1
                ):
                    is_duplicate = True
                    break

            if not is_duplicate:
                filtered_events.append(event)

        # Apply velocity smoothing for rapid sequences
        if len(filtered_events) > 1:
            for i in range(1, len(filtered_events)):
                prev_event = filtered_events[i - 1]
                curr_event = filtered_events[i]

                # Smooth velocity for rapid hits of same drum
                if (
                    curr_event.timestamp - prev_event.timestamp < 0.1
                    and curr_event.drum_type == prev_event.drum_type
                ):
                    # Average the velocities
                    avg_velocity = (prev_event.velocity + curr_event.velocity) / 2
                    curr_event.velocity = avg_velocity

        return filtered_events

    async def _save_drum_events(
        self, db: AsyncSession, audio_file_id: str, drum_events: List[DrumEvent]
    ) -> None:
        """
        Save detected drum events to database

        Args:
            db: Database session
            audio_file_id: ID of the audio file
            events: List of drum events to save
        """
        try:
            # This would integrate with your drum_events table
            # For now, we'll log the events
            logger.info(
                f"Saving {len(drum_events)} drum events for audio file {audio_file_id}"
            )

            for event in drum_events:
                logger.debug(
                    f"Event: {event.drum_type} at {event.timestamp:.3f}s, "
                    f"velocity: {event.velocity:.2f}, confidence: {event.confidence:.2f}"
                )

            # TODO: Implement actual database saving
            # This would create DrumEvent models and save them to the database

        except Exception as e:
            logger.error(f"Failed to save drum events: {e}")
            raise

    async def detect_tempo_and_meter(
        self, y: np.ndarray, sr: int
    ) -> Dict[str, Union[float, List[float], str]]:
        """
        Detect tempo and time signature of the audio

        Args:
            y: Audio time series
            sr: Sample rate

        Returns:
            Dictionary containing tempo and meter information
        """
        if not AUDIO_LIBS_AVAILABLE:
            return {"tempo": 120.0, "beat_times": [], "meter": "4/4"}

        try:
            # Detect tempo and beats
            if librosa is not None:
                tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
                beat_times = librosa.frames_to_time(beats, sr=sr)
            else:
                tempo = 120.0
                beat_times = np.array([])

            # Estimate time signature
            meter = await self._estimate_meter(beat_times)

            return {
                "tempo": float(tempo),
                "beat_times": beat_times.tolist(),
                "meter": meter,
                "beats_per_measure": 4
                if meter == "4/4"
                else 3
                if meter == "3/4"
                else 4,
            }

        except Exception as e:
            logger.error(f"Tempo detection failed: {e}")
            return {"tempo": 120.0, "beat_times": [], "meter": "4/4"}

    async def _estimate_meter(self, beat_times: np.ndarray) -> str:
        """
        Estimate time signature from beat times

        Args:
            beat_times: Array of beat times in seconds

        Returns:
            Time signature string (e.g., "4/4", "3/4")
        """
        if len(beat_times) < 8:
            return "4/4"  # Default

        # Find the most common beat pattern
        # This is a simplified approach - a more sophisticated method
        # would analyze the accent patterns

        # Calculate intervals for meter analysis would go here in future enhancement

        # Look for patterns that suggest different meters
        # For now, default to 4/4
        return "4/4"

    async def get_drum_statistics(self, events: List[DrumEvent]) -> Dict:
        """
        Calculate statistics about detected drum events

        Args:
            events: List of drum events

        Returns:
            Dictionary of statistics
        """
        if not events:
            return {
                "total_events": 0,
                "drum_counts": {},
                "average_velocity": 0.0,
                "duration": 0.0,
                "events_per_second": 0.0,
            }

        # Count events by drum type
        drum_counts = {}
        for event in events:
            drum_counts[event.drum_type] = drum_counts.get(event.drum_type, 0) + 1

        # Calculate statistics
        total_events = len(events)
        duration = events[-1].timestamp - events[0].timestamp if events else 0
        average_velocity = (
            np.mean(np.array([e.velocity for e in events])) if events else 0.0
        )
        events_per_second = total_events / duration if duration > 0 else 0

        # Find most active drum
        most_active_drum = (
            max(drum_counts.keys(), key=lambda k: drum_counts[k])
            if drum_counts
            else None
        )

        return {
            "total_events": total_events,
            "drum_counts": drum_counts,
            "average_velocity": float(average_velocity),
            "duration": float(duration),
            "events_per_second": float(events_per_second),
            "most_active_drum": most_active_drum,
            "velocity_range": {
                "min": float(min(e.velocity for e in events)),
                "max": float(max(e.velocity for e in events)),
                "std": float(np.std([e.velocity for e in events])),
            },
        }


class DrumPatternAnalyzer:
    """Analyzes drum patterns and rhythmic structures"""

    def __init__(self):
        self.detector = DrumDetector()

    async def analyze_patterns(self, events: List[DrumEvent], tempo_info: Dict) -> Dict:
        """
        Analyze rhythmic patterns in drum events

        Args:
            events: List of drum events
            tempo_info: Tempo and meter information

        Returns:
            Pattern analysis results
        """
        if not events:
            return {"patterns": [], "complexity": 0.0}

        tempo = tempo_info.get("tempo", 120.0)
        beat_times = tempo_info.get("beat_times", [])

        # Quantize events to beat grid
        quantized_events = await self._quantize_events(events, beat_times, tempo)

        # Find repeating patterns
        patterns = await self._find_patterns(quantized_events)

        # Calculate complexity score
        complexity = await self._calculate_complexity(events, tempo_info)

        return {
            "patterns": patterns,
            "complexity": complexity,
            "quantized_events": [e.to_dict() for e in quantized_events],
        }

    async def _quantize_events(
        self, events: List[DrumEvent], beat_times: List[float], tempo: float
    ) -> List[DrumEvent]:
        """
        Quantize drum events to nearest beat subdivision
        """
        if not beat_times:
            return events

        quantized = []
        beat_duration = 60.0 / tempo  # Duration of one beat in seconds

        for event in events:
            # Find nearest beat time
            nearest_beat_idx = min(
                range(len(beat_times)),
                key=lambda i: abs(beat_times[i] - event.timestamp),
            )

            # Quantize to 16th note grid
            subdivision = beat_duration / 4  # 16th note
            beat_time = beat_times[nearest_beat_idx]
            offset = event.timestamp - beat_time
            quantized_offset = round(offset / subdivision) * subdivision
            quantized_time = beat_time + quantized_offset

            # Create quantized event
            quantized_event = DrumEvent(
                timestamp=quantized_time,
                drum_type=event.drum_type,
                confidence=event.confidence,
                velocity=event.velocity,
                frequency=event.frequency,
                duration=event.duration,
            )
            quantized.append(quantized_event)

        return quantized

    async def _find_patterns(self, events: List[DrumEvent]) -> List[Dict]:
        """
        Find repeating rhythmic patterns
        """
        # This is a simplified pattern detection
        # A more sophisticated approach would use sequence analysis algorithms

        patterns = []

        if len(events) < 8:
            return patterns

        # Group events by measure (assuming 4/4 time)
        # This is a basic implementation
        measures = []
        current_measure = []

        for event in events:
            current_measure.append(event)
            # Simple measure detection (every 4 beats at 120 BPM ≈ 2 seconds)
            if len(current_measure) >= 4:
                measures.append(current_measure)
                current_measure = []

        # Find similar measures
        if len(measures) >= 2:
            pattern = {
                "type": "basic_pattern",
                "length": len(measures[0]),
                "repetitions": len(measures),
                "description": f"Detected {len(measures)} similar measures",
            }
            patterns.append(pattern)

        return patterns

    async def _calculate_complexity(
        self, events: List[DrumEvent], tempo_info: Dict
    ) -> float:
        """
        Calculate rhythmic complexity score (0-1)
        """
        if not events:
            return 0.0

        # Factors affecting complexity:
        # 1. Number of different drum types
        drum_types = set(e.drum_type for e in events)
        type_complexity = len(drum_types) / 8.0  # Normalize to max 8 types

        # 2. Velocity variation
        velocities = [e.velocity for e in events]
        velocity_complexity = np.std(velocities) if len(velocities) > 1 else 0.0

        # 3. Timing irregularity
        timestamps = [e.timestamp for e in events]
        intervals = np.diff(timestamps)
        timing_complexity = np.std(intervals) if len(intervals) > 1 else 0.0

        # Combine factors
        complexity = np.mean(
            np.array([type_complexity, velocity_complexity, timing_complexity])
        )
        return float(min(1.0, complexity))  # Cap at 1.0
