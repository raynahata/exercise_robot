import json
import os
from datetime import datetime

from .models import UserModel


class UserModelManager:
    """Loads and updates long-term participant preferences."""

    def __init__(self, storage_dir):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def path_for(self, participant_id):
        return os.path.join(self.storage_dir, "participant_{}_user_model.json".format(participant_id))

    def load(self, participant_id, defaults=None):
        path = self.path_for(participant_id)
        if os.path.exists(path):
            with open(path, "r") as model_file:
                data = json.load(model_file)
            data.setdefault("participant_id", str(participant_id))
            return UserModel(**data)

        model = UserModel(participant_id=str(participant_id))
        if defaults:
            for key, value in defaults.items():
                if hasattr(model, key):
                    setattr(model, key, value)
        return model

    def save(self, model):
        with open(self.path_for(model.participant_id), "w") as model_file:
            json.dump(model.to_dict(), model_file, indent=2, sort_keys=True)

    def update_from_session(self, model, session_state, reward_signals=None):
        reward_signals = reward_signals or {}
        rating = reward_signals.get("user_rating")
        explicit_feedback = reward_signals.get("explicit_feedback", "")

        model.session_number += 1
        if session_state.speech_responsiveness > 0.65 and session_state.engagement > 0.6:
            model.baseline_chattiness = min(1.0, model.baseline_chattiness + 0.05)
        elif session_state.speech_responsiveness < 0.35:
            model.baseline_chattiness = max(0.0, model.baseline_chattiness - 0.05)

        if session_state.frustration > 0.65:
            model.correction_tolerance = max(0.0, model.correction_tolerance - 0.08)
            model.preferred_autonomy_level = min(1.0, model.preferred_autonomy_level + 0.08)
        elif session_state.form_quality > 0.75 and rating and rating >= 4:
            model.correction_tolerance = min(1.0, model.correction_tolerance + 0.04)

        if "direct" in explicit_feedback.lower():
            model.preferred_feedback_style = "firm"
        elif "gentle" in explicit_feedback.lower() or "encouraging" in explicit_feedback.lower():
            model.preferred_feedback_style = "encouraging"

        model.history.append({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_state": session_state.to_dict(),
            "reward_signals": reward_signals,
        })
        model.history = model.history[-20:]
        self.save(model)
        return model

