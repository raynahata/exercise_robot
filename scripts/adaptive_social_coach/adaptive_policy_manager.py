from .models import InteractionState, PolicyAction, PolicyDecision
from .session_state_estimator import clamp


def score_to_level(score):
    if score < 0.34:
        return 1
    if score < 0.67:
        return 2
    return 3


class RuleBasedAdaptivePolicy:
    """First-milestone policy. Replace or wrap this with a bandit later."""

    def decide(self, interaction_state, session_state, user_model):
        state = InteractionState(interaction_state)
        rationale = []

        coach_score = 0.5
        social_score = user_model.baseline_chattiness
        correction_frequency = "moderate"
        message_strategy = "balanced"
        action = PolicyAction.MOTIVATIONAL_PROMPT

        if session_state.fatigue > 0.7:
            coach_score -= 0.2
            social_score -= 0.1
            correction_frequency = "low"
            message_strategy = "gentle_encouragement"
            action = PolicyAction.ENCOURAGING_COACHING
            rationale.append("fatigue_high_reduce_corrections")

        if session_state.form_quality < 0.45:
            coach_score += 0.25
            correction_frequency = "short_specific"
            action = PolicyAction.FIRM_COACHING
            rationale.append("form_declining_specific_feedback")

        if session_state.frustration > 0.65:
            coach_score -= 0.15
            social_score -= 0.05
            correction_frequency = "low"
            message_strategy = "autonomy_supportive"
            action = PolicyAction.AUTONOMY_SUPPORTIVE_CHOICE
            rationale.append("frustration_high_offer_choice")

        if state == InteractionState.REST_SOCIAL_CHAT and session_state.engagement > 0.6:
            social_score += 0.25
            action = PolicyAction.SOCIAL_CHAT
            rationale.append("engaged_during_rest_increase_social_chat")

        if state == InteractionState.ACTIVE_EXERCISE and session_state.engagement > 0.65:
            social_score -= 0.2
            action = PolicyAction.QUIET_EXERCISE_PARTNER
            rationale.append("focused_during_exercise_reduce_chattiness")

        if user_model.preferred_feedback_style == "encouraging":
            coach_score -= 0.05
        elif user_model.preferred_feedback_style == "firm":
            coach_score += 0.08

        coach_score += (user_model.correction_tolerance - 0.5) * 0.2
        social_score += (user_model.baseline_chattiness - 0.5) * 0.2

        coach_weight = round(clamp(coach_score, 0.2, 0.8), 2)
        social_weight = round(clamp(social_score, 0.2, 0.8), 2)
        total = coach_weight + social_weight
        coach_weight = round(coach_weight / total, 2)
        social_weight = round(1.0 - coach_weight, 2)

        if coach_weight >= 0.6:
            mode = "coach_leaning"
            session_flow = "coach_then_social"
        elif social_weight >= 0.6:
            mode = "social_leaning"
            session_flow = "social_then_coach"
        else:
            mode = "balanced"
            session_flow = "coach_then_social"

        coach_intensity = score_to_level(coach_weight)
        social_warmth = score_to_level(0.5 + session_state.fatigue * 0.2 + session_state.frustration * 0.2)
        social_verbosity = score_to_level(social_weight)
        if state == InteractionState.ACTIVE_EXERCISE:
            social_verbosity = min(social_verbosity, 2)

        if action == PolicyAction.FIRM_COACHING:
            robot_style = 1
        elif action in (PolicyAction.ENCOURAGING_COACHING, PolicyAction.SOCIAL_CHAT):
            robot_style = 3
        else:
            robot_style = 2 if mode == "coach_leaning" else 3

        return PolicyDecision(
            action=action.value,
            robot_style=robot_style,
            coach_intensity=coach_intensity,
            social_warmth=social_warmth,
            social_verbosity=social_verbosity,
            coach_weight=coach_weight,
            social_weight=social_weight,
            mode=mode,
            session_flow=session_flow,
            message_strategy=message_strategy,
            correction_frequency=correction_frequency,
            rationale=rationale or ["default_balanced_policy"],
        )


class ContextualBanditPolicyAdapter:
    def decide(self, interaction_state, session_state, user_model):
        raise NotImplementedError("Plug in contextual bandit policy here.")

