"""
Azure OpenAI Client for Foundry IQ

Provides chat completions with grounding context from agentic retrieval.
Handles reasoning model specifics (gpt-5.4-mini, o4-mini, etc.).

Auth: DefaultAzureCredential (keyless) by default.

Threadlight pilots are KEYLESS-BY-MANDATE — the key fallback below exists
only for non-threadlight reuse of this script. Do not set
AZURE_OPENAI_API_KEY in a threadlight pilot environment.
"""

import os
from typing import List, Dict, Any, Optional
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI


class AzureOpenAIClient:
    """
    Azure OpenAI client optimized for Foundry IQ integration.

    Handles:
    - Chat completions with grounding context
    - Reasoning model parameter differences
    - Streaming responses
    """

    # Reasoning models — they reject `temperature` and use `max_completion_tokens`
    # instead of `max_tokens`. Update this set when you adopt a new family.
    REASONING_MODELS = {
        "o4-mini", "o1", "o1-mini", "o1-preview", "o3-mini", "o3",
        # gpt-5.4 family — reasoning-grade chat models (May 2026)
        "gpt-5.4", "gpt-5.4-mini", "gpt-5.5",
    }

    def __init__(
        self,
        endpoint: str = None,
        api_key: str = None,
        deployment: str = None,
        # Pin a Foundry-supported preview that exposes the responses API +
        # gpt-5.x routing. Bump as new previews land; do not let callers
        # silently inherit a stale default that drops chat features.
        api_version: str = "2025-04-01-preview"
    ):
        self.endpoint = endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT")
        self.deployment = deployment or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4-mini")
        self.api_version = api_version

        if not self.endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT is required")

        key = api_key or os.environ.get("AZURE_OPENAI_API_KEY")
        if key:
            self.client = AzureOpenAI(
                azure_endpoint=self.endpoint,
                api_key=key,
                api_version=self.api_version,
            )
        else:
            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(
                credential, "https://cognitiveservices.azure.com/.default"
            )
            self.client = AzureOpenAI(
                azure_endpoint=self.endpoint,
                azure_ad_token_provider=token_provider,
                api_version=self.api_version,
            )

    def _is_reasoning_model(self, model: str = None) -> bool:
        """Check if the model is a reasoning model with parameter restrictions."""
        model_name = model or self.deployment
        return any(rm in model_name.lower() for rm in self.REASONING_MODELS)

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        model: str = None
    ) -> str:
        """
        Generate a chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: Optional system prompt to prepend
            temperature: Sampling temperature (ignored for reasoning models)
            max_tokens: Maximum tokens in response
            model: Optional model override

        Returns:
            Generated response text
        """
        deployment = model or self.deployment

        # Build messages list
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        # Build completion params
        params = {
            "model": deployment,
            "messages": full_messages,
        }

        # Handle reasoning model differences
        if self._is_reasoning_model(deployment):
            # Reasoning models use max_completion_tokens, not max_tokens
            params["max_completion_tokens"] = max_tokens
            # Don't set temperature - reasoning models only support default
        else:
            params["max_tokens"] = max_tokens
            params["temperature"] = temperature

        response = self.client.chat.completions.create(**params)

        # Handle potential None content from reasoning models
        content = response.choices[0].message.content
        return content if content else ""

    def chat_with_context(
        self,
        query: str,
        context: str,
        system_prompt: str = None,
        conversation_history: List[Dict[str, str]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """
        Generate a response grounded in retrieved context.

        Args:
            query: User query
            context: Retrieved context to ground the response
            system_prompt: Optional custom system prompt
            conversation_history: Previous messages for multi-turn
            temperature: Sampling temperature
            max_tokens: Maximum tokens

        Returns:
            Generated response grounded in context
        """
        default_system = """You are PolicyBot, a helpful assistant that answers questions based on company policy documents.

IMPORTANT INSTRUCTIONS:
1. ONLY answer based on the provided context
2. If the context doesn't contain the answer, say "I couldn't find that information in our policy documents. Please contact HR for assistance."
3. Always cite your sources using the format: [source_file]
4. Be concise but complete
5. Never make up information"""

        system = system_prompt or default_system

        # Build the grounded prompt
        grounded_query = f"""Context from policy documents:
---
{context}
---

User Question: {query}

Based ONLY on the context above, provide a helpful answer with citations."""

        # IMPORTANT: don't mutate caller's list. The previous form
        # `messages = conversation_history or []; messages.append(...)`
        # appended into the SAME object every call when the caller passed
        # in their own history — creating exponential context growth and
        # turning the bot's "history" into a hall-of-mirrors of repeated
        # grounded queries. Always copy to a fresh list.
        messages = list(conversation_history) if conversation_history else []
        messages.append({"role": "user", "content": grounded_query})

        return self.chat_completion(
            messages=messages,
            system_prompt=system,
            temperature=temperature,
            max_tokens=max_tokens
        )

    def generate_embedding(
        self,
        text: str,
        model: str = "text-embedding-3-small"
    ) -> List[float]:
        """
        Generate an embedding for text.

        Args:
            text: Text to embed
            model: Embedding model deployment name

        Returns:
            Embedding vector
        """
        response = self.client.embeddings.create(
            input=text[:8000],  # Limit input
            model=model
        )
        return response.data[0].embedding


class PolicyBot:
    """
    High-level PolicyBot that combines retrieval and generation.

    Integrates Knowledge Agent retrieval with Azure OpenAI for
    grounded Q&A over policy documents.
    """

    def __init__(
        self,
        openai_client: AzureOpenAIClient = None,
        retriever = None,
        system_prompt: str = None
    ):
        from .knowledge_agent_manager import KnowledgeAgentRetriever

        self.openai = openai_client or AzureOpenAIClient()
        self.retriever = retriever or KnowledgeAgentRetriever()
        self.conversation_history: List[Dict[str, str]] = []

        self.system_prompt = system_prompt or """You are PolicyBot, a helpful HR assistant that answers questions about company policies.

IMPORTANT:
1. Answer ONLY based on the retrieved policy documents
2. Always cite sources using [filename] format
3. If information isn't in the documents, say so clearly
4. Be helpful, concise, and accurate"""

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
        self.retriever.clear_history()

    def ask(self, query: str) -> Dict[str, Any]:
        """
        Ask a question and get a grounded response.

        Args:
            query: User question

        Returns:
            Dict with 'answer', 'sources', and 'raw_context'
        """
        # Retrieve relevant context
        retrieval_result = self.retriever.retrieve(query)

        # Format context with citations
        context = self.retriever.format_citations(retrieval_result)

        # Generate grounded response
        response = self.openai.chat_with_context(
            query=query,
            context=context,
            system_prompt=self.system_prompt,
            conversation_history=self.conversation_history
        )

        # Update conversation history
        self.conversation_history.append({"role": "user", "content": query})
        self.conversation_history.append({"role": "assistant", "content": response})

        # Extract source files from retrieval
        sources = []
        if "citations" in retrieval_result:
            for citation in retrieval_result["citations"]:
                source = citation.get("sourceFile", citation.get("title", "unknown"))
                if source not in sources:
                    sources.append(source)

        return {
            "answer": response,
            "sources": sources,
            "raw_context": context
        }


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    # Test basic completion
    client = AzureOpenAIClient()

    response = client.chat_completion(
        messages=[{"role": "user", "content": "What is the capital of France?"}],
        max_tokens=100
    )
    print("Basic completion:", response)

    # Test with context
    context = """According to the PTO Policy document:
- New employees (0-2 years): 15 days per year
- Employees with 2-5 years tenure: 20 days per year
- Employees with 5+ years tenure: 25 days per year"""

    response = client.chat_with_context(
        query="How many vacation days do I get as a new employee?",
        context=context
    )
    print("\nGrounded response:", response)
