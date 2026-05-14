from .models import SessionState


def clamp(value, min_value=0.0, max_value=1.0):
    return max(min_value, min(max_value, value))


def level_to_score(value, default=0.5):
    mapping = {
        "low": 0.2,
        "medium": 0.5,
        "moderate": 0.5,
        "high": 0.8,
    }
    if isinstance(value, (int, float)):
        return clamp(float(value))
    return mapping.get(str(value).lower(), default)


class SessionStateEstimator:
    """Converts live or placeholder signals into a common session state."""

    def estimate(self, signals, user_model=None):
        signals = signals or {}
        heart_rate_zone = level_to_score(signals.get("heart_rate_zone", "medium"))
        movement_quality = level_to_score(signals.get("movement_quality", "medium"))
        social_engagement = level_to_score(signals.get("social_engagement", "medium"))

        fatigue = level_to_score(signals.get("fatigue", heart_rate_zone))
        form_quality = level_to_score(signals.get("form_quality", movement_quality))
        engagement = level_to_score(signals.get("engagement", social_engagement))
        speech_responsiveness = level_to_score(
            signals.get("speech_responsiveness", social_engagement)
        )
        current_energy = level_to_score(signals.get("current_energy", 1.0 - fatigue))
        frustration = level_to_score(signals.get("frustration", 0.2))

        if form_quality < 0.35 and fatigue > 0.65:
            frustration = max(frustration, 0.55)

        return SessionState(
            fatigue=fatigue,
            engagement=engagement,
            frustration=frustration,
            form_quality=form_quality,
            rep_progress=level_to_score(signals.get("rep_progress", 0.0)),
            speech_responsiveness=speech_responsiveness,
            current_mood=str(signals.get("current_mood", "neutral")),
            current_energy=current_energy,
            session_number=getattr(user_model, "session_number", 0),
        )

