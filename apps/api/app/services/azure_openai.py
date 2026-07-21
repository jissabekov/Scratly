import json
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncAzureOpenAI
from app.config import get_settings
class AzureOpenAIService:
    def __init__(self,audit_writer):
        s=get_settings(); credential=DefaultAzureCredential()
        token=get_bearer_token_provider(credential,'https://cognitiveservices.azure.com/.default')
        self.client=AsyncAzureOpenAI(azure_endpoint=s.azure_openai_endpoint,azure_ad_token_provider=token,api_version='2025-04-01-preview')
        self.deployments={'analyzer':s.azure_openai_analyzer_deployment,'writer':s.azure_openai_writer_deployment,'summary':s.azure_openai_summary_deployment}; self.audit=audit_writer
    async def structured(self,deployment,prompt_name,prompt_version,model,context):
        response=await self.client.responses.parse(model=self.deployments[deployment],input=[{'role':'system','content':_prompt(prompt_name,prompt_version)},{'role':'user','content':json.dumps(context)}],text_format=model)
        # Audit stores hashes/IDs and usage, never raw student context.
        await self.audit(prompt_name=prompt_name,prompt_version=prompt_version,deployment=self.deployments[deployment],response_id=response.id,usage=response.usage)
        return response.output_parsed
def _prompt(name,version):
    with open(f'prompts/{name}/{version}/system.txt',encoding='utf-8') as f:return f.read()
