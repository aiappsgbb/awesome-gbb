"""
Azure AI Search Index Manager

Creates and manages search indexes with vector search and semantic configuration
for Foundry IQ agentic retrieval.
"""

import os
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SearchableField,
    SimpleField,
)


class SearchIndexManager:
    """Manages Azure AI Search indexes for Foundry IQ."""

    def __init__(
        self,
        endpoint: str = None,
        api_key: str = None,
    ):
        self.endpoint = endpoint or os.environ.get("AI_SEARCH_ENDPOINT")
        self.api_key = api_key or os.environ.get("AI_SEARCH_KEY")

        if not self.endpoint or not self.api_key:
            raise ValueError("AI_SEARCH_ENDPOINT and AI_SEARCH_KEY are required")

        self.credential = AzureKeyCredential(self.api_key)
        self.client = SearchIndexClient(
            endpoint=self.endpoint,
            credential=self.credential
        )

    def create_policy_index(
        self,
        index_name: str = "policy-documents",
        vector_dimensions: int = 1536  # OpenAI ada-002 dimensions
    ) -> SearchIndex:
        """
        Create a search index optimized for policy documents with vector search.

        Args:
            index_name: Name of the index to create
            vector_dimensions: Dimensions of the embedding vectors

        Returns:
            Created SearchIndex object
        """
        # Define fields
        fields = [
            SimpleField(
                name="id",
                type=SearchFieldDataType.String,
                key=True,
                filterable=True
            ),
            SearchableField(
                name="title",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=True,
                sortable=True
            ),
            SearchableField(
                name="content",
                type=SearchFieldDataType.String,
                searchable=True
            ),
            SearchableField(
                name="category",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=True,
                facetable=True
            ),
            SimpleField(
                name="source_file",
                type=SearchFieldDataType.String,
                filterable=True
            ),
            SimpleField(
                name="chunk_id",
                type=SearchFieldDataType.Int32,
                filterable=True,
                sortable=True
            ),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=vector_dimensions,
                vector_search_profile_name="vector-profile"
            ),
        ]

        # Vector search configuration
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="hnsw-algorithm",
                    parameters={
                        "m": 4,
                        "efConstruction": 400,
                        "efSearch": 500,
                        "metric": "cosine"
                    }
                )
            ],
            profiles=[
                VectorSearchProfile(
                    name="vector-profile",
                    algorithm_configuration_name="hnsw-algorithm"
                )
            ]
        )

        # Semantic search configuration
        semantic_config = SemanticConfiguration(
            name="semantic-config",
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="title"),
                content_fields=[SemanticField(field_name="content")],
                keywords_fields=[SemanticField(field_name="category")]
            )
        )

        semantic_search = SemanticSearch(
            configurations=[semantic_config]
        )

        # Create the index
        index = SearchIndex(
            name=index_name,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search
        )

        result = self.client.create_or_update_index(index)
        print(f"Index '{result.name}' created/updated successfully")
        return result

    def delete_index(self, index_name: str) -> None:
        """Delete an index by name."""
        self.client.delete_index(index_name)
        print(f"Index '{index_name}' deleted successfully")

    def list_indexes(self) -> list:
        """List all indexes in the search service."""
        indexes = list(self.client.list_indexes())
        return [idx.name for idx in indexes]

    def get_index(self, index_name: str) -> SearchIndex:
        """Get an index by name."""
        return self.client.get_index(index_name)


if __name__ == "__main__":
    # Example usage
    from dotenv import load_dotenv
    load_dotenv()

    manager = SearchIndexManager()

    # List existing indexes
    print("Existing indexes:", manager.list_indexes())

    # Create policy documents index
    index = manager.create_policy_index("policy-documents")
    print(f"Created index with {len(index.fields)} fields")
