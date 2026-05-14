from dataclasses import asdict, dataclass, field
from enum import Enum


class InteractionState(str, Enum):
    PRE_SESSION_CHECKIN = "PRE_SESSION_CHECKIN"
    EXERCISE_DEMO = "EXERCISE_DEMO"
    ACTIVE_EXERCISE = "ACTIVE_EXERCISE"
    REAL_TIME_FEEDBACK = "REAL_TIME_FEEDBACK"
    REST_SOCIAL_CHAT = "REST_SOCIAL_CHAT"
    END_SESSION_REFLECTION = "END_SESSION_REFLECTION"
    UPDATE_USER_MODEL = "UPDATE_USER_MODEL"


class PolicyAction(str, Enum):
    FIRM_COACHING = "firm_coaching"
    ENCOURAGING_COACHING = "encouraging_coaching"
    SOCIAL_CHAT = "social_chat"
    QUIET_EXERCISE_PARTNER = "quiet_exercise_partner"
    AUTONOMY_SUPPORTIVE_CHOICE = "autonomy_supportive_choice"
    MOTIVATIONAL_PROMPT = "motivational_prompt"


@dataclass
class UserModel:
    participant_id: str = "0"
    session_number: int = 0
    baseline_chattiness: float = 0.5
    preferred_feedback_style: str = "encouraging"
    correction_tolerance: float = 0.5
    preferred_social_role: str = "exercise_partner"
    motivation_style: str = "encouraging"
    preferred_autonomy_level: float = 0.5
    history: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


@dataclass
class SessionState:
    fatigue: float = 0.5
    engagement: float = 0.5
    frustration: float = 0.2
    form_quality: float = 0.7
    rep_progress: float = 0.0
    speech_responsiveness: float = 0.5
    current_mood: str = "neutral"
    current_energy: float = 0.5
    session_number: int = 0

    def to_dict(self):
        return asdict(self)


@dataclass
class PolicyDecision:
    action: str
    robot_style: int
    coach_intensity: int
    social_warmth: int
    social_verbosity: int
    coach_weight: float
    social_weight: float
    mode: str
    session_flow: str
    message_strategy: str
    correction_frequency: str
    rationale: list

    def to_dict(self):
        return asdict(self)

