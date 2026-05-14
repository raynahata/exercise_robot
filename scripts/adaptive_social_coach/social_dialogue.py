class SocialDialogueModule:
    """Adapter boundary for rest chat and social-partner speech behavior."""

    def build_signals(self, social_engagement=None, speech_responsiveness=None, current_mood=None, current_energy=None):
        return {
            "social_engagement": social_engagement or "medium",
            "speech_responsiveness": speech_responsiveness or social_engagement or "medium",
            "current_mood": current_mood or "neutral",
            "current_energy": current_energy if current_energy is not None else "medium",
        }

