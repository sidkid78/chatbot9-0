import logging
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from llama_index.core.chat_engine.types import BaseChatEngine, NodeWithScore
from llama_index.core.llms import MessageRole

from app.api.routers.events import EventCallbackHandler
from app.api.routers.models import ChatData, Message, Result, SourceNodes
from app.api.routers.vercel_response import VercelStreamResponse
from app.engine import get_chat_engine
from app.engine.query_filter import generate_filters
from ..engine.service import LLamaCloudFileService

chat_router = APIRouter()

logger = logging.getLogger('uvicorn')

async def process_chat_request(
    chat_engine: BaseChatEngine,
    data: ChatData,
    event_handler: EventCallbackHandler | None = None
):
    last_message_content = data.get_last_message_content()
    messages = data.get_history_messages()
    return await chat_engine.astream_chat(last_message_content, messages)

@chat_router.post('')
async def chat(
    request: Request,
    data: ChatData,
    background_tasks: BackgroundTasks,
):
    try:
        doc_ids = data.get_chat_document_ids()
        filters = generate_filters(doc_ids)
        params = data.data or {}
        logger.info(f'Creating chat engine with filters: {str(filters)}')
        
        event_handler = EventCallbackHandler()
        chat_engine = get_chat_engine(
            filters=filters,
            params=params,
            event_handlers=[event_handler]
        )
        
        response = await process_chat_request(chat_engine, data, event_handler)
        process_response_nodes(response.source_nodes, background_tasks)

        return VercelStreamResponse(request, event_handler, response, data)
    except Exception as e:
        logger.exception('Error in chat engine', exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Error in chat engine: {e}'
        ) from e

@chat_router.post('/request')
async def chat_request(
    data: ChatData,
    chat_engine: BaseChatEngine = Depends(get_chat_engine)
) -> Result:
    response = await process_chat_request(chat_engine, data)
    return Result(
        result=Message(role=MessageRole.ASSISTANT, content=response.response),
        nodes=SourceNodes.from_source_nodes(response.source_nodes)
    )

def process_response_nodes(
    nodes: List[NodeWithScore],
    background_tasks: BackgroundTasks,
):
    try:
        LLamaCloudFileService.download_files_from_nodes(nodes, background_tasks)
    except ImportError:
        logger.debug('LlamaCloud is not configured. Skipping post processing of nodes')
