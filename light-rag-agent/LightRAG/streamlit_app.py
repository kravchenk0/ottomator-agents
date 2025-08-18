"""Interactive Streamlit app for LightRAG AI Agent."""

import streamlit as st
import asyncio
import os
from typing import AsyncGenerator

# Import all the message part classes
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    UserPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    RetryPromptPart,
    ModelMessagesTypeAdapter
)

from common import RAGManager, RAGConfig, get_default_config
from rag_agent import agent, RAGDeps

async def get_agent_deps(config: RAGConfig) -> RAGDeps:
    """Creates a LightRAG instance and returns Pydantic AI agent dependencies.
    
    Args:
        config: RAG configuration
        
    Returns:
        RAGDeps instance with initialized RAG manager
    """
    try:
        rag_manager = RAGManager(config)
        await rag_manager.initialize()
        return RAGDeps(rag_manager=rag_manager)
    except Exception as e:
        st.error(f"Failed to initialize RAG: {e}")
        raise

def display_message_part(part) -> None:
    """Display a single part of a message in the Streamlit UI.
    
    Args:
        part: Message part to display
    """
    # user-prompt
    if part.part_kind == 'user-prompt':
        with st.chat_message("user"):
            st.markdown(part.content)
    # text
    elif part.part_kind == 'text':
        with st.chat_message("assistant"):
            st.markdown(part.content)

async def run_agent_with_streaming(
    user_input: str,
    agent_deps: RAGDeps,
    messages: list
) -> AsyncGenerator[str, None]:
    """Run the agent with streaming response.
    
    Args:
        user_input: User's input question
        agent_deps: Agent dependencies
        messages: Message history
        
    Yields:
        Streaming text response
    """
    try:
        async with agent.run_stream(
            user_input, deps=agent_deps, message_history=messages
        ) as result:
            async for message in result.stream_text(delta=True):  
                yield message

        # Add the new messages to the chat history
        messages.extend(result.new_messages())
        
    except Exception as e:
        yield f"Error: {str(e)}"

def create_sidebar() -> RAGConfig:
    """Create sidebar with configuration options.
    
    Returns:
        RAGConfig instance with user settings
    """
    st.sidebar.title("Configuration")
    
    working_dir = st.sidebar.text_input(
        "Working Directory",
        value="./pydantic-docs",
        help="Directory where LightRAG stores data"
    )
    
    rerank_enabled = st.sidebar.checkbox(
        "Enable Reranking",
        value=True,
        help="Enable document reranking for better results"
    )
    
    batch_size = st.sidebar.slider(
        "Batch Size",
        min_value=5,
        max_value=50,
        value=20,
        help="Number of documents to process in batches"
    )
    
    return RAGConfig(
        working_dir=working_dir,
        rerank_enabled=rerank_enabled,
        batch_size=batch_size
    )

async def main():
    """Main function with UI creation."""
    st.title("LightRAG AI Agent")
    st.markdown("Ask questions and get AI-powered answers based on your documents.")
    
    # Create sidebar configuration
    config = create_sidebar()
    
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "agent_deps" not in st.session_state:
        try:
            st.session_state.agent_deps = await get_agent_deps(config)
        except Exception as e:
            st.error(f"Failed to initialize agent: {e}")
            return
    
    # Display chat history
    for msg in st.session_state.messages:
        if isinstance(msg, (ModelRequest, ModelResponse)):
            for part in msg.parts:
                display_message_part(part)
    
    # Chat input
    user_input = st.chat_input("What do you want to know?")
    
    if user_input:
        # Display user input
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Display assistant response with streaming
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            try:
                # Stream the response
                async for message in run_agent_with_streaming(
                    user_input, 
                    st.session_state.agent_deps, 
                    st.session_state.messages
                ):
                    full_response += message
                    message_placeholder.markdown(full_response + "▌")
                
                # Final response without cursor
                message_placeholder.markdown(full_response)
                
            except Exception as e:
                st.error(f"Error generating response: {e}")
    
    # Add some helpful information in the sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Tips")
    st.sidebar.markdown("- Ask specific questions for better results")
    st.sidebar.markdown("- Use the configuration options to tune performance")
    st.sidebar.markdown("- Check the working directory for document storage")

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
