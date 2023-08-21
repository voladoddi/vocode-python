import logging
import os
from fastapi import FastAPI
from vocode.streaming.models.telephony import TwilioConfig
from vocode.streaming.action.factory import ActionFactory, ActionConfig, BaseAction
from pyngrok import ngrok
from vocode.streaming.telephony.config_manager.redis_config_manager import (
    RedisConfigManager,
)
from vocode.streaming.utils import events_manager
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage
from vocode.streaming.telephony.server.base import (
    TwilioInboundCallConfig,
    TelephonyServer,
)

from typing import Type
from pydantic import BaseModel, Field
import os
from vocode.streaming.action.base_action import BaseAction
from vocode.streaming.models.actions import (
    ActionConfig
)

# from vocode.streaming.action.twilio_schedule_appointment import (
#    TwilioScheduleAppointmentAction, TwilioScheduleAppointmentActionConfig
# )
# from vocode.streaming.agent.my_agent import MyAgentFactory
import sys

# if running from python, this will load the local .env
# docker-compose will load the .env file by itself
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(docs_url=None)

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

config_manager = RedisConfigManager()

BASE_URL = os.getenv("TELEPHONY_SERVER_BASE_URL")

if not BASE_URL:
    ngrok_auth = os.environ.get("NGROK_AUTH_TOKEN")
    if ngrok_auth is not None:
        ngrok.set_auth_token(ngrok_auth)
    port = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else 3000

    # Open a ngrok tunnel to the dev server
    BASE_URL = ngrok.connect(port).public_url.replace("https://", "")
    logger.info('ngrok tunnel "{}" -> "http://127.0.0.1:{}"'.format(BASE_URL, port))

if not BASE_URL:
    raise ValueError("BASE_URL must be set in environment if not using pyngrok")

# ---------------------- PROMPT ------------------------------
PROMPT_PREAMBLE = """
Hi there...we're going to have a conversation, 
for which I need you to assume the role of a receptionist at the insurance call center.

As a person who's chatting with you, my goal is to set up an appointment with a doctor...
In the course of our conversation, you have to confirm what I'm calling for right in the beginning of our conversation... 
if I don't give you a concrete reason insist twice or thrice, and if I still don't give a clear reason end with "Sorry I cannot help, goodbye".

If I give you a reason, assess whether it is relevant - that is, the only reason you'll accept is that I'm talking to you to get an appointment set up... 
anything else is irrelevant to which you'll also respond with "Sorry I cannot help, goodbye".

If I confirm that I'm calling about setting up an appointment with a doctor,
paraphrase my response back to me, and say "I can help you with that" and proceed to ask me about other details.


Once I confirm that I'm calling for setting up a doctor's appointment, 
make sure that you have all the details as mentioned above. 
These are the mandatory details to collect:
- my name and date of birth
- my insurance details : payer ID and name
- my address
- my preferred phone contact number
- chief medical complaint/reason I'm calling to see a doctor. Remember, 
"Annual health checkup" or "general check up" or "following up from last appointment" is a perfectly good reason to continue.
- if I have a referral by my general doctor to see a particular doctor, and note their name down.

If any of the details is missing, make sure you ask them again.
Provide me with at least three doctor names, appointment dates and times options.
I will choose one or ask for other dates.
If I ask another date, mention that I have to call back to ask for a date that is more than one week out.

Before ending our call, once you have a confirmed appointment date and time from me, 
read back the confirmed name of the doctor, appointment date and time to me, \
for e.g. "You will be meeting with Doctor Smith on August 27th at 2pm" \
Spell out the "doctor" word don't shorten it to "Dr." 
Then end the call with "goodbye", and stop responding to anything else after I say goodbye
"""

# ------------------ DEFINING MY AGENT ---------------------------
from vocode.streaming.agent.factory import AgentFactory

import logging
import typing
from typing import Any, Dict, List, Optional

from vocode import getenv
from vocode.streaming.action.factory import ActionFactory
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.agent.utils import (
    format_openai_chat_messages_from_transcript,
    collate_response_async,
    openai_get_tokens,
    vector_db_result_to_openai_chat_message,
)
from vocode.streaming.agent import ChatGPTAgent



class MyAgentFactory(AgentFactory):
    def __init__(self, action_factory: ActionFactory):
        self.agent_config = ChatGPTAgentConfig
        self.action_factory = action_factory

    def create_agent(
        self, agent_config: ChatGPTAgentConfig, logger: Optional[logging.Logger] = logger
    ) -> ChatGPTAgent:
        return ChatGPTAgent(
            agent_config=typing.cast(ChatGPTAgent, agent_config),
            action_factory=self.action_factory,
            logger=logger
        )
    
# ---- STEP 1 ------- ACTION DEFINITION
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

from aenum import Enum, extend_enum
extend_enum(ActionType, 'TWILIO_SCHEDULE_APPOINTMENT', "action_twilio_schedule_appointment")

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
    description: str = "\
    Sends an SMS using Twilio API client.\
    The input to this action is a pipe separated list of the recipient phone number, doctor's name, date and time.\
    But always include the pipe character even if the number, name, date and time are not included and just leave it blank.\
    \
    The subject should only be included if it is a new email thread.\
    If there is no message id, the email will be sent as a new email.\
    Otherwise, it will be sent as a reply to the given message. Make sure to include the previous message_id\
    if you are replying to an email.\
    \
    For example, `+12134469407|Doctor Patel|August 27th 2023|2pm` would send an SMS\
    to +12134469407 with the provided Doctor's name, appointment date and time."

    parameters_type: Type[TwilioScheduleAppointmentParameters] = TwilioScheduleAppointmentParameters
    response_type: Type[TwilioScheduleAppointmentResponse] = TwilioScheduleAppointmentResponse

    async def run(
        self, action_input: ActionInput[TwilioScheduleAppointmentParameters]
    ) -> ActionOutput[TwilioScheduleAppointmentResponse]:
        from twilio.rest import Client

        recipient_phone, doctor_name, appt_date, appt_time = action_input.params.split("|")

        account_sid = os.environ['TWILIO_ACCOUNT_SID']
        auth_token = os.environ['TWILIO_AUTH_TOKEN']
        sender_twilio_number = os.environ['OUTBOUND_CALLER_NUMBER']
        client = Client(account_sid, auth_token)

        # Create the SMS
        message = client.messages.create(
            body=f"Your appointment is with {doctor_name} on {appt_date} at {appt_time}",
            from_=sender_twilio_number,
            to=recipient_phone #action_input.params.recipient_number.strip()
        )

        print(message.sid["body"])

        return ActionOutput(
            action_type=self.action_config.type,
            response=TwilioScheduleAppointmentResponse(success=True),
        )


# ---- STEP 2 ------- INTEGRATE WITH AGENT
events_manager_instance = events_manager.EventsManager()
ChatGPTAgentConfig.actions = [TwilioScheduleAppointmentActionConfig]
class TwilioScheduleAppointmentFactory(ActionFactory):
    def create_action(self, action_config: ActionConfig) -> BaseAction:
        if isinstance(action_config, TwilioScheduleAppointmentActionConfig):
            return TwilioScheduleAppointmentAction(action_config, should_respond=True)
        else:
            raise Exception("Invalid action type")

telephony_server = TelephonyServer(
    base_url=BASE_URL,
    config_manager=config_manager,
    inbound_call_configs=[
        TwilioInboundCallConfig(
            url="/inbound_call",
            agent_config=ChatGPTAgentConfig(
                initial_message=BaseMessage(
                    text="Hi, you've reached the reception desk for ABC insurance. how can I help you today?"
                ),
                prompt_preamble=PROMPT_PREAMBLE,
                generate_responses=True,
            ),
            twilio_config=TwilioConfig(
                account_sid=os.environ["TWILIO_ACCOUNT_SID"],
                auth_token=os.environ["TWILIO_AUTH_TOKEN"],
            ),
        )
    ],
    agent_factory=MyAgentFactory(
        action_factory=TwilioScheduleAppointmentFactory
    ),
    logger=logger,
    events_manager=events_manager_instance,
)

app.include_router(telephony_server.get_router())
