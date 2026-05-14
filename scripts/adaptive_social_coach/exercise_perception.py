class ExercisePerceptionModule:
    """Adapter boundary for pose tracking, rep counting, HR, and form feedback."""

    def build_signals(self, heart_rate_zone=None, movement_quality=None, form_quality=None, rep_progress=None):
        return {
            "heart_rate_zone": heart_rate_zone or "medium",
            "movement_quality": movement_quality or "medium",
            "form_quality": form_quality if form_quality is not None else movement_quality or "medium",
            "rep_progress": rep_progress if rep_progress is not None else 0.0,
        }

