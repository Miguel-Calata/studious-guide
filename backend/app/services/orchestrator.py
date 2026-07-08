from app.modules.ai_gateway.interfaces import AIGatewayClient
from app.modules.ai_gateway.openrouter_client import OpenRouterClient


class PipelineOrchestrator:
    def __init__(
        self,
        ai_client: AIGatewayClient | None = None,
    ):
        self.ai = ai_client or OpenRouterClient()

    async def extract_all(self, project_id: str) -> None:
        pass

    async def generate_all_sections(self, project_id: str) -> None:
        pass
