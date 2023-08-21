'''
class SpellerAgentConfig(AgentConfig, type="agent_speller"):
    pass


class SpellerAgent(BaseAgent):
    def __init__(self, agent_config: SpellerAgentConfig):
        super().__init__(agent_config=agent_config)

    async def respond(
        self,
        human_input,
        conversation_id: str,
        is_interrupt: bool = False,
    ) -> Tuple[Optional[str], bool]:
        return "".join(c + " " for c in human_input), False


class SpellerAgentFactory(AgentFactory):
    def create_agent(self, agent_config: AgentConfig) -> BaseAgent:
        return SpellerAgent(agent_config=agent_config)
'''

