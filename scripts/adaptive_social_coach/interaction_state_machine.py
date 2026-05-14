from .models import InteractionState


class InteractionStateMachine:
    def __init__(self):
        self.state = InteractionState.PRE_SESSION_CHECKIN

    def transition(self, event):
        event = str(event)
        transitions = {
            (InteractionState.PRE_SESSION_CHECKIN, "checkin_complete"): InteractionState.EXERCISE_DEMO,
            (InteractionState.EXERCISE_DEMO, "demo_complete"): InteractionState.ACTIVE_EXERCISE,
            (InteractionState.ACTIVE_EXERCISE, "rep_feedback_needed"): InteractionState.REAL_TIME_FEEDBACK,
            (InteractionState.REAL_TIME_FEEDBACK, "feedback_complete"): InteractionState.ACTIVE_EXERCISE,
            (InteractionState.ACTIVE_EXERCISE, "set_complete"): InteractionState.REST_SOCIAL_CHAT,
            (InteractionState.REST_SOCIAL_CHAT, "rest_complete"): InteractionState.EXERCISE_DEMO,
            (InteractionState.REST_SOCIAL_CHAT, "session_complete"): InteractionState.END_SESSION_REFLECTION,
            (InteractionState.END_SESSION_REFLECTION, "reflection_complete"): InteractionState.UPDATE_USER_MODEL,
        }
        self.state = transitions.get((self.state, event), self.state)
        return self.state

