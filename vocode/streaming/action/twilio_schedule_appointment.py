from typing import Type
from pydantic import BaseModel, Field
import os
from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)


class TwilioScheduleAppointmentActionConfig(ActionConfig, type=ActionType.TWILIO_SCHEDULE_APPOINTMENT):
    pass


class TwilioScheduleAppointmentParameters(BaseModel):
    recipient_number: str = Field(..., description="The contact number of the patient.")
    body: str = Field(..., description="Body of the SMS containing doctor's name,\
                      date and time of appointment with the doctor that\
                      was confirmed and chosen by patient")


class TwilioScheduleAppointmentResponse(BaseModel):
    success: bool


class TwilioScheduleAppointmentAction(
    BaseAction[
        TwilioScheduleAppointmentActionConfig, TwilioScheduleAppointmentParameters, TwilioScheduleAppointmentResponse
    ]
):
    description: str = "Sends an SMS using Twilio API to the preferred contact number provided by the patient\
        once the patient confirms the selected date and time for doctor's appointment with the doctor's name, date and time"
    parameters_type: Type[TwilioScheduleAppointmentParameters] = TwilioScheduleAppointmentParameters
    response_type: Type[TwilioScheduleAppointmentResponse] = TwilioScheduleAppointmentResponse

    async def run(
        self, action_input: ActionInput[TwilioScheduleAppointmentParameters]
    ) -> ActionOutput[TwilioScheduleAppointmentResponse]:
        from twilio.rest import Client

        account_sid = os.environ['TWILIO_ACCOUNT_SID']
        auth_token = os.environ['TWILIO_AUTH_TOKEN']
        sender_twilio_number = os.environ['OUTBOUND_CALLER_NUMBER']
        client = Client(account_sid, auth_token)

        # Create the email draft
        message = client.messages.create(
            body=action_input.params.body,
            from_=sender_twilio_number,
            to=action_input.params.recipient_number.strip()
        )   #'+12134469407'

        print(message.sid["body"])

        return ActionOutput(
            action_type=self.action_config.type,
            response=TwilioScheduleAppointmentResponse(success=True),
        )
