"""
Audio Source Separation Module
Advanced drum source separation and enhancement for automatic drum transcription
"""

import logging
from pathlib import Path
from typing import Dict, Optional

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

# Import audio processing libraries with error handling
try:
    import librosa
    import scipy.ndimage
    import soundfile as sf
    from scipy import signal
    from sklearn.decomposition import NMF, FastICA

    AUDIO_LIBS_AVAILABLE = True
except ImportError as e:
    AUDIO_LIBS_AVAILABLE = False
    librosa = None
    sf = None
    signal = None
    FastICA = None
    NMF = None
    scipy = None
    logger = logging.getLogger(__name__)
    logger.warning(f"Audio processing libraries not available: {e}")

from app.modules.media.models import AudioFile
from app.modules.media.repository import AudioFileRepository

logger = logging.getLogger(__name__)


class SeparationConfig:
    """Configuration for audio source separation"""

    def __init__(
        self,
        n_fft: int = 2048,
        hop_length: int = 512,
        window: str = "hann",
        n_components: int = 8,
        max_iterations: int = 200,
        tolerance: float = 1e-4,
        mask_smoothing: bool = True,
        smoothing_sigma: float = 1.0,
    ):
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.window = window
        self.n_components = n_components
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self.mask_smoothing = mask_smoothing
        self.smoothing_sigma = smoothing_sigma

        # Frequency ranges for drum types (Hz)
        self.frequency_ranges = {
            "kick": (20, 120),
            "snare": (150, 600),
            "hihat": (4000, 16000),
            "cymbals": (3000, 20000),
            "toms": (80, 400),
        }


class DrumSourceSeparator:
    """Advanced audio source separation system for drum isolation"""

    def __init__(self, config: Optional[SeparationConfig] = None):
        self.config = config or SeparationConfig()
        self.audio_repository = AudioFileRepository()

        if not AUDIO_LIBS_AVAILABLE:
            logger.warning("Audio processing libraries not available")

    async def separate_drum_sources(
        self,
        db: AsyncSession,
        audio_file: AudioFile,
        method: str = "nmf",
        save_separated: bool = True,
    ) -> Dict[str, str]:
        """
        Separate drum sources from mixed audio

        Args:
            db: Database session
            audio_file: AudioFile model instance
            method: Separation method ('nmf', 'ica', 'spectral')
            save_separated: Whether to save separated sources to disk

        Returns:
            Dictionary mapping source names to file paths
        """
        if not AUDIO_LIBS_AVAILABLE:
            raise RuntimeError("Audio processing libraries not available")

        try:
            # Load audio data
            audio_path = str(audio_file.storage_path)
            if librosa is None:
                raise RuntimeError("librosa not available")
            y, sr = librosa.load(audio_path, sr=None)

            logger.info(f"Loaded audio for separation: {len(y)} samples at {sr}Hz")

            # Apply source separation based on method
            if method == "nmf":
                separated_sources = await self._separate_nmf(y, int(sr))
            elif method == "ica":
                separated_sources = await self._separate_ica(y, int(sr))
            elif method == "spectral":
                separated_sources = await self._separate_spectral_masking(y, int(sr))
            else:
                raise ValueError(f"Unknown separation method: {method}")

            # Save separated sources if requested
            separated_paths = {}
            if save_separated:
                separated_paths = await self._save_separated_sources(
                    separated_sources, audio_file, int(sr)
                )

            logger.info(f"Successfully separated {len(separated_sources)} sources")
            return separated_paths

        except Exception as e:
            logger.error(f"Source separation failed: {e}")
            raise

    async def _separate_nmf(self, y: np.ndarray, sr: int) -> Dict[str, np.ndarray]:
        """
        Non-negative Matrix Factorization based source separation

        Args:
            y: Audio time series
            sr: Sample rate

        Returns:
            Dictionary of separated sources
        """
        if librosa is None or NMF is None:
            raise RuntimeError("Required audio libraries not available")

        # Compute magnitude spectrogram
        stft = librosa.stft(
            y,
            n_fft=self.config.n_fft,
            hop_length=self.config.hop_length,
            window=self.config.window,
        )
        magnitude = np.abs(stft)

        # Apply NMF to magnitude spectrogram
        nmf = NMF(
            n_components=int(self.config.n_components),  # type: ignore
            max_iter=self.config.max_iterations,
            random_state=42,
        )

        # Reshape for NMF (features x samples)
        magnitude_flat = magnitude.reshape(magnitude.shape[0], -1)
        W = nmf.fit_transform(magnitude_flat)  # Basis functions
        H = nmf.components_  # Activation coefficients

        # Reconstruct individual sources
        separated_sources = {}

        for i in range(self.config.n_components):
            # Reconstruct this component
            source_magnitude = np.outer(W[:, i], H[i, :])
            source_magnitude = source_magnitude.reshape(magnitude.shape)

            # Create soft mask
            mask = source_magnitude / (magnitude + 1e-10)
            mask = np.minimum(mask, 1.0)

            # Apply mask to original STFT
            masked_stft = stft * mask

            # Convert back to time domain
            source_audio = librosa.istft(
                masked_stft,
                hop_length=self.config.hop_length,
            )

            # Classify source based on spectral characteristics
            source_name = await self._classify_separated_source(source_magnitude, sr, i)

            separated_sources[source_name] = source_audio

        return separated_sources

    async def _separate_ica(self, y: np.ndarray, sr: int) -> Dict[str, np.ndarray]:
        """
        Independent Component Analysis based source separation

        Args:
            y: Audio time series (should be stereo for ICA)
            sr: Sample rate

        Returns:
            Dictionary of separated sources
        """
        if FastICA is None:
            raise RuntimeError("FastICA not available")

        # ICA works best with stereo input
        if y.ndim == 1:
            # Create pseudo-stereo by time-shifting
            y_shifted = np.roll(y, sr // 100)  # 10ms shift
            y_stereo = np.vstack([y, y_shifted])
        else:
            y_stereo = y

        # Apply ICA
        ica = FastICA(
            n_components=min(self.config.n_components, y_stereo.shape[0]),
            max_iter=self.config.max_iterations,
            tol=self.config.tolerance,
            random_state=42,
        )

        # Fit ICA on overlapping windows for better separation
        window_size = sr * 2  # 2 second windows
        hop_size = window_size // 2

        separated_components = []

        for start in range(0, len(y) - window_size, hop_size):
            end = start + window_size
            window_data = y_stereo[:, start:end]

            try:
                if window_data is not None and hasattr(window_data, "T"):
                    components = ica.fit_transform(window_data.T)
                    if components is not None and hasattr(components, "T"):
                        components = components.T
                else:
                    components = ica.fit_transform(window_data)
                separated_components.append(components)
            except Exception as e:
                logger.warning(f"ICA failed for window {start}-{end}: {e}")
                continue

        if not separated_components:
            raise RuntimeError("ICA separation failed for all windows")

        # Combine components from all windows
        combined_components = {}
        n_components = separated_components[0].shape[0]

        for i in range(n_components):
            component_windows = [comp[i] for comp in separated_components]

            # Simple overlap-add reconstruction
            full_length = len(y)
            combined = np.zeros(full_length)

            for j, window in enumerate(component_windows):
                start = j * hop_size
                end = min(start + len(window), full_length)
                combined[start:end] += window[: end - start]

            source_name = f"ica_component_{i}"
            combined_components[source_name] = combined

        return combined_components

    async def _separate_spectral_masking(
        self, y: np.ndarray, sr: int
    ) -> Dict[str, np.ndarray]:
        """
        Frequency-based spectral masking for drum separation

        Args:
            y: Audio time series
            sr: Sample rate

        Returns:
            Dictionary of separated drum sources
        """
        if librosa is None or scipy is None:
            raise RuntimeError("Required audio libraries not available")

        # Compute STFT
        stft = librosa.stft(
            y, n_fft=self.config.n_fft, hop_length=self.config.hop_length
        )
        magnitude = np.abs(stft)

        # Create frequency bins
        freqs = librosa.fft_frequencies(sr=sr, n_fft=self.config.n_fft)

        separated_sources = {}

        # Separate by frequency bands
        for drum_type, (low_freq, high_freq) in self.config.frequency_ranges.items():
            # Create frequency mask
            freq_mask = (freqs >= low_freq) & (freqs <= high_freq)

            # Apply frequency mask
            masked_magnitude = magnitude.copy()
            masked_magnitude[~freq_mask] *= 0.1  # Attenuate other frequencies

            # Apply temporal masking based on energy
            temporal_mask = await self._create_temporal_mask(
                masked_magnitude, drum_type
            )

            # Combine masks
            final_mask = temporal_mask
            if self.config.mask_smoothing and hasattr(scipy, "ndimage"):
                final_mask = scipy.ndimage.gaussian_filter(
                    final_mask, sigma=self.config.smoothing_sigma
                )

            # Apply mask to STFT
            masked_stft = stft * final_mask

            # Convert back to time domain
            separated_audio = librosa.istft(
                masked_stft, hop_length=self.config.hop_length
            )

            separated_sources[drum_type] = separated_audio

        return separated_sources

    async def _create_temporal_mask(
        self, magnitude: np.ndarray, drum_type: str
    ) -> np.ndarray:
        """
        Create temporal mask based on drum type characteristics

        Args:
            magnitude: Magnitude spectrogram
            drum_type: Type of drum to isolate

        Returns:
            Temporal mask array
        """
        if librosa is None:
            raise RuntimeError("librosa not available")

        # Calculate energy over frequency bands
        energy = np.sum(magnitude, axis=0)

        # Different masking strategies for different drum types
        if drum_type in ["kick", "snare"]:
            # For transient drums, use onset-based masking
            onset_frames = librosa.onset.onset_detect(
                onset_envelope=energy, units="frames"
            )

            # Create mask around onsets
            mask = np.zeros_like(energy)
            for onset in onset_frames:
                start = max(0, onset - 2)
                end = min(len(mask), onset + 10)  # Longer decay for kick/snare
                mask[start:end] = 1.0

        else:
            # For sustained drums (hi-hat, cymbals), use energy-based masking
            threshold = np.mean(energy) + np.std(energy)
            mask = (energy > threshold).astype(float)

        # Smooth the mask
        if mask.ndim == 1:
            mask = np.tile(mask, (magnitude.shape[0], 1))

        return mask

    async def _classify_separated_source(
        self, magnitude: np.ndarray, sr: int, component_idx: int
    ) -> str:
        """
        Classify separated audio source based on spectral characteristics

        Args:
            magnitude: Magnitude spectrogram of the source
            sr: Sample rate
            component_idx: Index of the component

        Returns:
            Predicted source name
        """
        if librosa is None:
            raise RuntimeError("librosa not available")

        # Calculate spectral features
        freqs = librosa.fft_frequencies(sr=sr, n_fft=self.config.n_fft)

        # Energy distribution across frequency bands
        total_energy = np.sum(magnitude)
        if total_energy == 0:
            return f"silent_component_{component_idx}"

        band_energies = {}
        for drum_type, (low_freq, high_freq) in self.config.frequency_ranges.items():
            freq_mask = (freqs >= low_freq) & (freqs <= high_freq)
            band_energy = np.sum(magnitude[freq_mask, :])
            band_energies[drum_type] = band_energy / total_energy

        # Find dominant frequency band
        dominant_band = max(band_energies.keys(), key=lambda k: band_energies[k])

        # Calculate spectral centroid
        spectral_centroid = np.sum(freqs[:, None] * magnitude, axis=0)
        spectral_centroid = np.sum(spectral_centroid) / total_energy

        # Classify based on dominant frequency and spectral characteristics
        if dominant_band == "kick" and spectral_centroid < 200:
            return "kick_drum"
        elif dominant_band == "snare" and 150 < spectral_centroid < 500:
            return "snare_drum"
        elif dominant_band == "hihat" and spectral_centroid > 5000:
            return "hihat"
        elif dominant_band == "cymbals" and spectral_centroid > 3000:
            return "cymbals"
        elif dominant_band == "toms":
            return "toms"
        else:
            return f"{dominant_band}_component_{component_idx}"

    async def _save_separated_sources(
        self, sources: Dict[str, np.ndarray], original_audio_file: AudioFile, sr: int
    ) -> Dict[str, str]:
        """
        Save separated sources to disk

        Args:
            sources: Dictionary of separated audio sources
            original_audio_file: Original audio file record
            sr: Sample rate

        Returns:
            Dictionary mapping source names to file paths
        """
        try:
            # Create output directory
            base_dir = Path("uploads") / "separated" / str(original_audio_file.id)
            base_dir.mkdir(parents=True, exist_ok=True)

            saved_paths = {}

            for source_name, audio_data in sources.items():
                # Skip empty sources
                if np.max(np.abs(audio_data)) < 1e-6:
                    continue

                # Generate filename
                filename = f"{source_name}.wav"
                filepath = base_dir / filename

                # Normalize audio to prevent clipping
                if np.max(np.abs(audio_data)) > 0:
                    audio_data = audio_data / np.max(np.abs(audio_data)) * 0.95

                # Save audio file
                if sf is None:
                    raise RuntimeError("soundfile not available")
                sf.write(str(filepath), audio_data, sr, subtype="PCM_16")

                saved_paths[source_name] = str(filepath)

                logger.debug(f"Saved separated source: {filepath}")

            return saved_paths

        except Exception as e:
            logger.error(f"Failed to save separated sources: {e}")
            return {}

    async def enhance_drum_track(
        self, audio_path: str, drum_type: str = "all"
    ) -> np.ndarray:
        """
        Enhance specific drum elements in audio

        Args:
            audio_path: Path to audio file
            drum_type: Type of drum to enhance ('kick', 'snare', 'hihat', 'all')

        Returns:
            Enhanced audio array
        """
        if not AUDIO_LIBS_AVAILABLE:
            raise RuntimeError("Audio processing libraries not available")

        try:
            # Load audio
            if librosa is None:
                raise RuntimeError("librosa not available")
            y, sr = librosa.load(audio_path, sr=None)

            # Apply enhancement based on drum type
            if drum_type == "kick":
                enhanced = await self._enhance_kick_drum(y, int(sr))
            elif drum_type == "snare":
                enhanced = await self._enhance_snare_drum(y, int(sr))
            elif drum_type == "hihat":
                enhanced = await self._enhance_hihat(y, int(sr))
            else:
                enhanced = await self._enhance_all_drums(y, int(sr))

            return enhanced

        except Exception as e:
            logger.error(f"Drum enhancement failed: {e}")
            return np.array([])

    async def _enhance_kick_drum(self, y: np.ndarray, sr: int) -> np.ndarray:
        """
        Enhance kick drum frequencies
        """
        if signal is None:
            return y

        # Apply low-pass filter and boost low frequencies
        nyquist = sr / 2
        low_cutoff = 150 / nyquist

        try:
            butter_result = signal.butter(4, low_cutoff, btype="low")
            if butter_result is not None and len(butter_result) == 2:
                b, a = butter_result
                kick_enhanced = signal.filtfilt(b, a, y)
            else:
                return y
        except Exception:
            return y

        # Apply compression to even out dynamics
        kick_enhanced = await self._apply_compression(kick_enhanced, ratio=3.0)

        # Mix with original
        return 0.7 * y + 0.3 * kick_enhanced

    async def _enhance_snare_drum(self, y: np.ndarray, sr: int) -> np.ndarray:
        """
        Enhance snare drum frequencies
        """
        if signal is None:
            return y

        # Band-pass filter for snare frequencies
        nyquist = sr / 2
        low_cutoff = 100 / nyquist
        high_cutoff = 600 / nyquist

        try:
            butter_result = signal.butter(4, [low_cutoff, high_cutoff], btype="band")
            if butter_result is not None and len(butter_result) == 2:
                b, a = butter_result
                snare_enhanced = signal.filtfilt(b, a, y)

                # Add some high-frequency content for snap
                butter_high_result = signal.butter(2, 3000 / nyquist, btype="high")
                if butter_high_result is not None and len(butter_high_result) == 2:
                    b_high, a_high = butter_high_result
                    snare_high = signal.filtfilt(b_high, a_high, y) * 0.3
                    snare_enhanced += snare_high
            else:
                return y
        except Exception:
            return y

        # Mix with original
        return 0.8 * y + 0.2 * snare_enhanced

    async def _enhance_hihat(self, y: np.ndarray, sr: int) -> np.ndarray:
        """
        Enhance hi-hat frequencies
        """
        if signal is None:
            return y

        # High-pass filter for hi-hat
        nyquist = sr / 2
        high_cutoff = 4000 / nyquist

        try:
            butter_result = signal.butter(4, high_cutoff, btype="high")
            if butter_result is not None and len(butter_result) == 2:
                b, a = butter_result
                hihat_enhanced = signal.filtfilt(b, a, y)
            else:
                return y
        except Exception:
            return y

        # Apply light compression
        hihat_enhanced = await self._apply_compression(hihat_enhanced, ratio=2.0)

        # Mix with original
        return 0.85 * y + 0.15 * hihat_enhanced

    async def _enhance_all_drums(self, y: np.ndarray, sr: int) -> np.ndarray:
        """
        Enhance all drum elements
        """
        # Multi-band enhancement
        kick_enhanced = await self._enhance_kick_drum(y, sr)
        snare_enhanced = await self._enhance_snare_drum(y, sr)
        hihat_enhanced = await self._enhance_hihat(y, sr)

        # Combine enhancements
        enhanced = (kick_enhanced + snare_enhanced + hihat_enhanced) / 3

        return enhanced

    async def _apply_compression(
        self, audio: np.ndarray, ratio: float = 3.0, threshold: float = 0.1
    ) -> np.ndarray:
        """
        Apply dynamic range compression

        Args:
            audio: Input audio
            ratio: Compression ratio
            threshold: Compression threshold

        Returns:
            Compressed audio
        """
        # Simple compression algorithm
        output = audio.copy()

        # Find samples above threshold
        above_threshold = np.abs(output) > threshold

        # Apply compression to samples above threshold
        output[above_threshold] = np.sign(output[above_threshold]) * (
            threshold + (np.abs(output[above_threshold]) - threshold) / ratio
        )

        return output

    async def remove_vocals(self, y: np.ndarray, sr: int) -> np.ndarray:
        """
        Remove vocals using center channel extraction (works for stereo)

        Args:
            y: Audio time series (stereo)
            sr: Sample rate

        Returns:
            Audio with vocals reduced
        """
        if y.ndim == 1:
            return y  # Can't remove vocals from mono

        # Simple vocal removal: subtract left and right channels
        if y.shape[0] == 2:
            vocal_removed = y[0] - y[1]
        else:
            vocal_removed = y

        return vocal_removed

    async def isolate_drums_by_harmonics(self, y: np.ndarray, sr: int) -> np.ndarray:
        """
        Isolate drums by removing harmonic content

        Args:
            y: Audio time series
            sr: Sample rate

        Returns:
            Audio with harmonic content reduced
        """
        if not AUDIO_LIBS_AVAILABLE or librosa is None:
            return y

        # Separate harmonic and percussive components
        stft = librosa.stft(y, hop_length=self.config.hop_length)
        harmonic, percussive = librosa.decompose.hpss(stft, margin=3.0)

        # Return percussive component (drums)
        drums_isolated = librosa.istft(percussive, hop_length=self.config.hop_length)

        return drums_isolated

    async def get_separation_quality_metrics(
        self, original: np.ndarray, separated_sources: Dict[str, np.ndarray]
    ) -> Dict[str, float]:
        """
        Calculate quality metrics for source separation

        Args:
            original: Original mixed audio
            separated_sources: Dictionary of separated sources

        Returns:
            Dictionary of quality metrics
        """
        metrics = {}

        # Reconstruction error
        if separated_sources:
            reconstructed = np.zeros_like(original)
            for source in separated_sources.values():
                if hasattr(source, "__len__") and len(source) > 0:
                    min_len = min(len(reconstructed), len(source))
                    reconstructed[:min_len] += source[:min_len]

            # Pad/trim to match original length
            min_length = min(len(original), len(reconstructed))
            orig_trimmed = original[:min_length]
            recon_trimmed = reconstructed[:min_length]

            # Signal-to-Distortion Ratio (SDR)
            noise = orig_trimmed - recon_trimmed
            signal_power = np.mean(orig_trimmed**2)
            noise_power = np.mean(noise**2)

            if noise_power > 0:
                sdr = 10 * np.log10(signal_power / noise_power)
                metrics["sdr_db"] = float(sdr)

            # Reconstruction error
            metrics["reconstruction_error"] = float(np.mean(noise**2))

        # Source diversity (how different the sources are)
        if hasattr(separated_sources, "__len__") and len(separated_sources) > 1:
            source_arrays = list(separated_sources.values())
            correlations = []

            for i, s1 in enumerate(source_arrays):
                for s2 in source_arrays[i + 1 :]:
                    if len(s1) > 0 and len(s2) > 0:
                        min_len = min(len(s1), len(s2))
                        corr = np.corrcoef(s1[:min_len], s2[:min_len])[0, 1]
                        if not np.isnan(corr):
                            correlations.append(abs(corr))

            if correlations:
                metrics["source_diversity"] = float(1.0 - np.mean(correlations))
            else:
                metrics["source_diversity"] = 0.0

        return metrics


class AudioStemExporter:
    """Export separated audio sources as stems for DAW import"""

    def __init__(self):
        self.separator = DrumSourceSeparator()

    async def create_drum_stems(
        self,
        db: AsyncSession,
        audio_file: AudioFile,
        export_format: str = "wav",
        bit_depth: int = 24,
        normalize: bool = True,
    ) -> Dict[str, str]:
        """
        Create professional drum stems for DAW import

        Args:
            db: Database session
            audio_file: Audio file to process
            export_format: Export format ('wav', 'flac', 'aiff')
            bit_depth: Bit depth for export (16, 24, 32)
            normalize: Whether to normalize stems

        Returns:
            Dictionary mapping stem names to file paths
        """
        try:
            # Separate sources
            separated_sources = await self.separator.separate_drum_sources(
                db, audio_file, method="spectral", save_separated=False
            )

            # Create stem directory
            stem_dir = Path("uploads") / "stems" / str(audio_file.id)
            stem_dir.mkdir(parents=True, exist_ok=True)

            # Load original audio for reference
            if librosa is None:
                raise RuntimeError("librosa not available")
            y, sr = librosa.load(str(audio_file.storage_path), sr=None)

            stem_paths = {}

            # Group sources into standard stems
            stem_groups = {
                "kick": ["kick_drum", "kick"],
                "snare": ["snare_drum", "snare"],
                "hihat": ["hihat"],
                "cymbals": ["cymbals", "crash"],
                "toms": ["toms", "tom_low", "tom_mid", "tom_high"],
                "percussion": ["percussion", "misc"],
            }

            for stem_name, source_names in stem_groups.items():
                # Combine matching sources
                stem_audio = np.zeros_like(y)

                for source_name in source_names:
                    for sep_name, sep_audio in separated_sources.items():
                        if any(s in sep_name.lower() for s in source_names):
                            # Align lengths
                            min_len = min(len(stem_audio), len(sep_audio))
                            stem_audio[:min_len] += sep_audio[:min_len]

                # Skip empty stems
                if np.max(np.abs(stem_audio)) < 1e-6:
                    continue

                # Normalize if requested
                if normalize:
                    stem_audio = stem_audio / np.max(np.abs(stem_audio)) * 0.95

                # Export stem
                stem_filename = f"{stem_name}.{export_format}"
                stem_path = stem_dir / stem_filename

                # Determine subtype based on bit depth and format
                if export_format.lower() == "wav":
                    subtype = f"PCM_{bit_depth}"
                elif export_format.lower() == "flac":
                    subtype = f"PCM_{bit_depth}"
                else:
                    subtype = "PCM_24"

                if sf is None:
                    raise RuntimeError("soundfile not available")
                sf.write(str(stem_path), stem_audio, int(sr), subtype=subtype)
                stem_paths[stem_name] = str(stem_path)

            return stem_paths

        except Exception as e:
            logger.error(f"Stem export failed: {e}")
            return {}
