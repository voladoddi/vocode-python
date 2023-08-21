from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.action.nylas_send_email import (
    NylasSendEmail,
    NylasSendEmailActionConfig,
)
from vocode.streaming.action.twilio_schedule_appointment import (
    TwilioScheduleAppointmentAction,
    TwilioScheduleAppointmentActionConfig,
)
from vocode.streaming.models.actions import ActionConfig
from vocode.streaming.action.transfer_call import TransferCall, TransferCallActionConfig


class ActionFactory:
    def create_action(self, action_config: ActionConfig) -> BaseAction:
        if isinstance(action_config, NylasSendEmailActionConfig):
            return NylasSendEmail(action_config, should_respond=True)
        elif isinstance(action_config, TransferCallActionConfig):
            return TransferCall(action_config)
        elif isinstance(action_config, TwilioScheduleAppointmentActionConfig):
            return TwilioScheduleAppointmentAction(action_config)
        else:
            raise Exception("Invalid action type")
