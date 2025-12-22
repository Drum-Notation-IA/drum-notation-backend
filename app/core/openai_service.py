"""
OpenAI Service for Intelligent Music Analysis
Provides AI-powered analysis for drum patterns, notation generation, and musical insights
"""

import logging
import os
from typing import Dict, List, Optional, Tuple, Union

import openai
from openai import AsyncOpenAI

from app.modules.audio_processing.detection import DrumEvent

logger = logging.getLogger(__name__)


class OpenAIService:
    """OpenAI service for intelligent music analysis and content generation"""

    def __init__(self):
        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OpenAI API key not found. AI features will be disabled.")
            self.client = None
            self.enabled = False
        else:
            self.client = AsyncOpenAI(api_key=api_key)
            self.enabled = True
            logger.info("OpenAI service initialized successfully")

        # Configuration
        self.model = os.getenv("OPENAI_MODEL", "gpt-4")
        self.max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "1500"))
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))

    async def analyze_drum_pattern(
        self,
        drum_events: List[DrumEvent],
        tempo: float,
        time_signature: str = "4/4",
        duration: float = 0.0,
    ) -> Dict[str, Union[str, float, List[str]]]:
        """
        Analyze drum pattern and provide intelligent insights

        Args:
            drum_events: List of detected drum events
            tempo: Detected tempo in BPM
            time_signature: Time signature (e.g., "4/4")
            duration: Total duration in seconds

        Returns:
            Dictionary containing analysis results
        """
        if not self.enabled:
            return self._get_fallback_analysis()

        try:
            # Prepare drum pattern summary
            pattern_summary = self._summarize_drum_pattern(
                drum_events, tempo, time_signature, duration
            )

            # Create analysis prompt
            prompt = self._create_pattern_analysis_prompt(pattern_summary)

            # Get AI analysis
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert drummer, music teacher, and rhythm analyst. Provide detailed, educational, and practical insights about drum patterns.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            # Parse and structure the response
            analysis_text = response.choices[0].message.content
            structured_analysis = self._parse_analysis_response(analysis_text)

            return structured_analysis

        except Exception as e:
            logger.error(f"OpenAI pattern analysis failed: {e}")
            return self._get_fallback_analysis()

    async def generate_pattern_variations(
        self,
        drum_events: List[DrumEvent],
        tempo: float,
        difficulty_level: str = "intermediate",
    ) -> Dict[str, List[str]]:
        """
        Generate practice variations of the detected drum pattern

        Args:
            drum_events: Original drum events
            tempo: Tempo in BPM
            difficulty_level: Target difficulty (beginner, intermediate, advanced)

        Returns:
            Dictionary with different types of variations
        """
        if not self.enabled:
            return self._get_fallback_variations()

        try:
            pattern_description = self._describe_pattern_for_ai(drum_events, tempo)

            prompt = f"""
            Based on this drum pattern:
            {pattern_description}

            Generate practice variations for a {difficulty_level} drummer:

            1. SIMPLIFIED VERSIONS (3 variations):
            - Easier versions for practice building up to the original

            2. COMPLEXITY VARIATIONS (3 variations):
            - Add fills, ghost notes, or accents

            3. STYLE ADAPTATIONS (3 variations):
            - Same basic pattern in different musical styles

            4. TECHNICAL EXERCISES (3 variations):
            - Focused exercises to master specific techniques

            Format each variation as a clear, concise description that a drummer can follow.
            """

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional drum instructor creating practice exercises. Be specific, practical, and pedagogically sound.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )

            variations_text = response.choices[0].message.content
            structured_variations = self._parse_variations_response(variations_text)

            return structured_variations

        except Exception as e:
            logger.error(f"OpenAI variation generation failed: {e}")
            return self._get_fallback_variations()

    async def classify_musical_style(
        self,
        drum_events: List[DrumEvent],
        tempo: float,
        audio_features: Optional[Dict] = None,
    ) -> Dict[str, Union[str, float, List[Tuple[str, float]]]]:
        """
        Classify the musical style/genre of the drum pattern

        Args:
            drum_events: Detected drum events
            tempo: Tempo in BPM
            audio_features: Additional audio features if available

        Returns:
            Style classification with confidence scores
        """
        if not self.enabled:
            return self._get_fallback_style_classification()

        try:
            # Analyze pattern characteristics
            pattern_analysis = self._analyze_pattern_characteristics(drum_events, tempo)

            # Include audio features if available
            audio_info = ""
            if audio_features:
                audio_info = f"\nAudio characteristics: {audio_features}"

            prompt = f"""
            Analyze this drum pattern and classify its musical style:

            Pattern Analysis:
            {pattern_analysis}
            {audio_info}

            Provide:
            1. PRIMARY GENRE (most likely): [Genre name] - [confidence %]
            2. SECONDARY GENRES (2-3 possibilities): [Genre] - [confidence %]
            3. STYLE CHARACTERISTICS: Key elements that indicate this style
            4. HISTORICAL CONTEXT: Brief background about this drumming style
            5. NOTABLE DRUMMERS: Who is known for this style

            Consider genres like: Rock, Jazz, Blues, Funk, Latin, Reggae, Hip-Hop, Electronic, Folk, Country, Metal, Progressive, etc.
            """

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a music historian and genre expert specializing in percussion and rhythm analysis.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=0.3,  # Lower temperature for more consistent classification
            )

            classification_text = response.choices[0].message.content
            structured_classification = self._parse_style_classification(
                classification_text
            )

            return structured_classification

        except Exception as e:
            logger.error(f"OpenAI style classification failed: {e}")
            return self._get_fallback_style_classification()

    async def generate_practice_instructions(
        self, drum_events: List[DrumEvent], tempo: float, difficulty_assessment: str
    ) -> Dict[str, List[str]]:
        """
        Generate step-by-step practice instructions for the drum pattern

        Args:
            drum_events: Drum events to practice
            tempo: Target tempo
            difficulty_assessment: Assessed difficulty level

        Returns:
            Structured practice instructions
        """
        if not self.enabled:
            return self._get_fallback_practice_instructions()

        try:
            pattern_description = self._describe_pattern_for_ai(drum_events, tempo)

            prompt = f"""
            Create comprehensive practice instructions for this drum pattern:

            Pattern: {pattern_description}
            Assessed Difficulty: {difficulty_assessment}
            Target Tempo: {tempo} BPM

            Provide structured practice instructions:

            1. PREPARATION (2-3 steps):
            - Setup and warm-up recommendations

            2. LEARNING PHASES (4-5 progressive steps):
            - Start slow, build complexity gradually
            - Include specific tempo recommendations for each phase

            3. TECHNIQUE FOCUS (3-4 key points):
            - Specific technical aspects to watch for

            4. COMMON MISTAKES (3-4 items):
            - What to avoid and how to correct

            5. MASTERY GOALS (2-3 objectives):
            - How to know when you've mastered it

            Make instructions clear, encouraging, and suitable for the difficulty level.
            """

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an experienced drum teacher creating lesson plans. Be encouraging, specific, and pedagogically sound.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=0.7,
            )

            instructions_text = response.choices[0].message.content
            structured_instructions = self._parse_practice_instructions(
                instructions_text
            )

            return structured_instructions

        except Exception as e:
            logger.error(f"OpenAI practice instruction generation failed: {e}")
            return self._get_fallback_practice_instructions()

    async def explain_musical_concepts(
        self, drum_events: List[DrumEvent], concepts_to_explain: List[str]
    ) -> Dict[str, str]:
        """
        Explain musical concepts present in the drum pattern

        Args:
            drum_events: Drum events to analyze
            concepts_to_explain: List of concepts to focus on

        Returns:
            Dictionary mapping concepts to explanations
        """
        if not self.enabled:
            return {
                concept: f"AI explanation not available for {concept}"
                for concept in concepts_to_explain
            }

        try:
            pattern_context = self._describe_pattern_for_ai(drum_events, None)
            concepts_list = ", ".join(concepts_to_explain)

            prompt = f"""
            Using this drum pattern as context:
            {pattern_context}

            Explain these musical concepts in relation to the pattern:
            {concepts_list}

            For each concept:
            1. Define it clearly
            2. Show how it applies to this specific pattern
            3. Provide practical examples
            4. Suggest how to practice/develop this concept

            Make explanations educational but accessible.
            """

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a music theory expert and educator explaining concepts with practical drum examples.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=0.6,
            )

            explanations_text = response.choices[0].message.content
            concept_explanations = self._parse_concept_explanations(
                explanations_text, concepts_to_explain
            )

            return concept_explanations

        except Exception as e:
            logger.error(f"OpenAI concept explanation failed: {e}")
            return {
                concept: f"Error generating explanation for {concept}"
                for concept in concepts_to_explain
            }

    # Helper methods for data processing

    def _summarize_drum_pattern(
        self,
        drum_events: List[DrumEvent],
        tempo: float,
        time_signature: str,
        duration: float,
    ) -> str:
        """Create a concise summary of the drum pattern for AI analysis"""
        if not drum_events:
            return "No drum events detected"

        # Count drum types
        drum_counts = {}
        for event in drum_events:
            drum_counts[event.drum_type] = drum_counts.get(event.drum_type, 0) + 1

        # Calculate pattern density
        events_per_second = len(drum_events) / max(duration, 1)

        summary = f"""
        Tempo: {tempo:.1f} BPM
        Time Signature: {time_signature}
        Duration: {duration:.1f} seconds
        Total Events: {len(drum_events)}
        Events per second: {events_per_second:.2f}

        Drum distribution:
        """

        for drum_type, count in sorted(drum_counts.items()):
            percentage = (count / len(drum_events)) * 100
            summary += f"- {drum_type}: {count} hits ({percentage:.1f}%)\n"

        return summary

    def _create_pattern_analysis_prompt(self, pattern_summary: str) -> str:
        """Create a comprehensive analysis prompt"""
        return f"""
        Analyze this drum pattern and provide insights:

        {pattern_summary}

        Please provide:

        1. PATTERN NAME: What would you call this drum pattern?
        2. DIFFICULTY LEVEL: Rate from 1-10 with explanation
        3. MUSICAL STYLE: Primary genre/style classification
        4. KEY CHARACTERISTICS: What makes this pattern distinctive?
        5. TECHNICAL ELEMENTS: Notable techniques or challenges
        6. LEARNING FOCUS: What should a drummer focus on when learning this?
        7. MUSICAL CONTEXT: Where might this pattern be used?
        8. PRACTICE SUGGESTIONS: How to approach learning this pattern

        Be specific, educational, and encouraging in your analysis.
        """

    def _describe_pattern_for_ai(
        self, drum_events: List[DrumEvent], tempo: Optional[float]
    ) -> str:
        """Create a readable description of the drum pattern for AI processing"""
        if not drum_events:
            return "Empty drum pattern"

        description = []
        if tempo:
            description.append(f"Tempo: {tempo:.1f} BPM")

        description.append(f"Pattern with {len(drum_events)} drum hits:")

        # Group events by time segments for readability
        time_segments = {}
        for event in drum_events:
            segment = int(event.timestamp)
            if segment not in time_segments:
                time_segments[segment] = []
            time_segments[segment].append(event)

        for segment in sorted(time_segments.keys()):
            events = time_segments[segment]
            segment_desc = f"At {segment}s: "
            event_descriptions = []
            for event in events:
                event_descriptions.append(f"{event.drum_type}({event.velocity:.2f})")
            segment_desc += ", ".join(event_descriptions)
            description.append(segment_desc)

        return "\n".join(description)

    def _analyze_pattern_characteristics(
        self, drum_events: List[DrumEvent], tempo: float
    ) -> str:
        """Analyze pattern characteristics for style classification"""
        if not drum_events:
            return "No pattern to analyze"

        characteristics = []
        characteristics.append(f"Tempo: {tempo:.1f} BPM")

        # Analyze tempo characteristics
        if tempo < 70:
            characteristics.append("Slow tempo (ballad/slow song)")
        elif tempo < 100:
            characteristics.append("Moderate tempo")
        elif tempo < 140:
            characteristics.append("Medium-fast tempo")
        elif tempo < 180:
            characteristics.append("Fast tempo")
        else:
            characteristics.append("Very fast tempo")

        # Analyze drum usage patterns
        drum_usage = {}
        total_velocity = 0
        for event in drum_events:
            drum_usage[event.drum_type] = drum_usage.get(event.drum_type, 0) + 1
            total_velocity += event.velocity

        avg_velocity = total_velocity / len(drum_events)
        characteristics.append(f"Average hit velocity: {avg_velocity:.2f}")

        # Analyze pattern complexity
        unique_drums = len(drum_usage)
        characteristics.append(f"Uses {unique_drums} different drum types")

        return "\n".join(characteristics)

    # Response parsing methods

    def _parse_analysis_response(
        self, response_text: str
    ) -> Dict[str, Union[str, float, List[str]]]:
        """Parse AI analysis response into structured data"""
        # This is a simplified parser - you could make it more sophisticated
        return {
            "analysis": response_text,
            "ai_generated": True,
            "confidence": 0.8,
            "summary": response_text[:200] + "..."
            if len(response_text) > 200
            else response_text,
        }

    def _parse_variations_response(self, response_text: str) -> Dict[str, List[str]]:
        """Parse variations response into structured format"""
        # Simplified parsing - could be enhanced with more sophisticated text processing
        sections = response_text.split("\n\n")
        return {
            "simplified": [s.strip() for s in sections[:3] if s.strip()],
            "complex": [s.strip() for s in sections[3:6] if s.strip()],
            "styles": [s.strip() for s in sections[6:9] if s.strip()],
            "exercises": [s.strip() for s in sections[9:12] if s.strip()],
            "raw_response": response_text,
        }

    def _parse_style_classification(
        self, response_text: str
    ) -> Dict[str, Union[str, float, List[Tuple[str, float]]]]:
        """Parse style classification response"""
        return {
            "primary_genre": "Unknown",
            "confidence": 0.7,
            "secondary_genres": [],
            "characteristics": response_text,
            "full_analysis": response_text,
        }

    def _parse_practice_instructions(self, response_text: str) -> Dict[str, List[str]]:
        """Parse practice instructions into structured format"""
        sections = response_text.split("\n\n")
        return {
            "preparation": [s.strip() for s in sections[:3] if s.strip()],
            "learning_phases": [s.strip() for s in sections[3:8] if s.strip()],
            "technique_focus": [s.strip() for s in sections[8:12] if s.strip()],
            "common_mistakes": [s.strip() for s in sections[12:16] if s.strip()],
            "mastery_goals": [s.strip() for s in sections[16:] if s.strip()],
            "full_instructions": response_text,
        }

    def _parse_concept_explanations(
        self, response_text: str, concepts: List[str]
    ) -> Dict[str, str]:
        """Parse concept explanations into a dictionary"""
        explanations = {}
        sections = response_text.split("\n\n")

        for i, concept in enumerate(concepts):
            if i < len(sections):
                explanations[concept] = sections[i].strip()
            else:
                explanations[concept] = "Explanation not available"

        return explanations

    # Fallback methods when OpenAI is not available

    def _get_fallback_analysis(self) -> Dict[str, Union[str, float, List[str]]]:
        """Provide basic analysis when AI is not available"""
        return {
            "analysis": "AI analysis not available. Please configure OpenAI API key for intelligent insights.",
            "ai_generated": False,
            "confidence": 0.0,
            "summary": "Basic analysis only - enable OpenAI for detailed insights",
        }

    def _get_fallback_variations(self) -> Dict[str, List[str]]:
        """Provide basic variations when AI is not available"""
        return {
            "simplified": [
                "Practice at slower tempo",
                "Use only kick and snare",
                "Remove fills",
            ],
            "complex": [
                "Add ghost notes",
                "Include hi-hat variations",
                "Add crash accents",
            ],
            "styles": [
                "Try in different time signatures",
                "Apply swing feel",
                "Add Latin percussion",
            ],
            "exercises": [
                "Practice each limb separately",
                "Use metronome",
                "Record yourself playing",
            ],
            "note": "AI-generated variations not available",
        }

    def _get_fallback_style_classification(
        self,
    ) -> Dict[str, Union[str, float, List[Tuple[str, float]]]]:
        """Basic style classification fallback"""
        return {
            "primary_genre": "Unknown",
            "confidence": 0.0,
            "secondary_genres": [],
            "characteristics": "AI style classification not available",
            "full_analysis": "Configure OpenAI API key for intelligent style analysis",
        }

    def _get_fallback_practice_instructions(self) -> Dict[str, List[str]]:
        """Basic practice instructions fallback"""
        return {
            "preparation": [
                "Warm up with simple beats",
                "Set up metronome",
                "Check drum tuning",
            ],
            "learning_phases": [
                "Start slow",
                "Master basic pattern",
                "Gradually increase tempo",
                "Add dynamics",
            ],
            "technique_focus": [
                "Keep steady tempo",
                "Maintain proper posture",
                "Practice limb independence",
            ],
            "common_mistakes": [
                "Rushing tempo",
                "Poor stick technique",
                "Lack of consistency",
            ],
            "mastery_goals": [
                "Play cleanly at target tempo",
                "Maintain groove",
                "Add personal style",
            ],
            "note": "AI-generated instructions not available",
        }

    def is_enabled(self) -> bool:
        """Check if OpenAI service is enabled and configured"""
        return self.enabled

    def get_status(self) -> Dict[str, Union[bool, str]]:
        """Get service status information"""
        return {
            "enabled": self.enabled,
            "model": self.model if self.enabled else "N/A",
            "api_key_configured": bool(os.getenv("OPENAI_API_KEY")),
            "status": "Ready" if self.enabled else "API key required",
        }
