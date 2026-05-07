"""
Document Indexer for Foundry IQ

Indexes documents into Azure AI Search with text chunking and embeddings
for vector search and agentic retrieval.
"""

import os
import uuid
import hashlib
from typing import List, Dict, Any, Optional
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from openai import AzureOpenAI


class DocumentIndexer:
    """Indexes documents into Azure AI Search with embeddings."""

    def __init__(
        self,
        search_endpoint: str = None,
        search_key: str = None,
        index_name: str = "policy-documents",
        openai_endpoint: str = None,
        openai_key: str = None,
        embedding_deployment: str = "text-embedding-ada-002",
    ):
        self.search_endpoint = search_endpoint or os.environ.get("AI_SEARCH_ENDPOINT")
        self.search_key = search_key or os.environ.get("AI_SEARCH_KEY")
        self.index_name = index_name
        self.openai_endpoint = openai_endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT")
        self.openai_key = openai_key or os.environ.get("AZURE_OPENAI_API_KEY")
        self.embedding_deployment = embedding_deployment

        if not all([self.search_endpoint, self.search_key]):
            raise ValueError("AI_SEARCH_ENDPOINT and AI_SEARCH_KEY are required")

        self.search_client = SearchClient(
            endpoint=self.search_endpoint,
            index_name=self.index_name,
            credential=AzureKeyCredential(self.search_key)
        )

        # Azure OpenAI client for embeddings (optional - can use without embeddings)
        self.openai_client = None
        if self.openai_endpoint and self.openai_key:
            self.openai_client = AzureOpenAI(
                azure_endpoint=self.openai_endpoint,
                api_key=self.openai_key,
                api_version="2024-12-01-preview"
            )

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 1000,
        overlap: int = 200
    ) -> List[str]:
        """
        Split text into overlapping chunks.

        Args:
            text: Text to chunk
            chunk_size: Maximum characters per chunk
            overlap: Number of characters to overlap between chunks

        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence end near chunk boundary
                for sep in ['. ', '.\n', '! ', '? ', '\n\n']:
                    last_sep = text.rfind(sep, start, end)
                    if last_sep > start + chunk_size // 2:
                        end = last_sep + len(sep)
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - overlap

        return chunks

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding vector for text using Azure OpenAI.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if embeddings not configured
        """
        if not self.openai_client:
            return None

        try:
            response = self.openai_client.embeddings.create(
                input=text[:8000],  # Limit input length
                model=self.embedding_deployment
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Warning: Could not generate embedding: {e}")
            return None

    def generate_doc_id(self, source_file: str, chunk_id: int) -> str:
        """Generate a unique document ID."""
        unique_str = f"{source_file}-{chunk_id}"
        return hashlib.md5(unique_str.encode()).hexdigest()

    def index_document(
        self,
        content: str,
        title: str,
        category: str,
        source_file: str,
        chunk_size: int = 1000,
        overlap: int = 200,
        generate_embeddings: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Index a document by chunking and uploading to Azure AI Search.

        Args:
            content: Document content
            title: Document title
            category: Document category (e.g., 'hr', 'policy', 'procedure')
            source_file: Source filename
            chunk_size: Size of text chunks
            overlap: Overlap between chunks
            generate_embeddings: Whether to generate vector embeddings

        Returns:
            List of indexed document chunks
        """
        chunks = self.chunk_text(content, chunk_size, overlap)
        documents = []

        for i, chunk in enumerate(chunks):
            doc = {
                "id": self.generate_doc_id(source_file, i),
                "title": title,
                "content": chunk,
                "category": category,
                "source_file": source_file,
                "chunk_id": i,
            }

            if generate_embeddings:
                embedding = self.generate_embedding(chunk)
                if embedding:
                    doc["content_vector"] = embedding

            documents.append(doc)

        # Upload in batches of 100
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            result = self.search_client.upload_documents(documents=batch)
            succeeded = sum(1 for r in result if r.succeeded)
            print(f"Indexed {succeeded}/{len(batch)} chunks for '{source_file}'")

        return documents

    def index_policy_documents(
        self,
        documents: List[Dict[str, str]],
        generate_embeddings: bool = True
    ) -> int:
        """
        Index multiple policy documents.

        Args:
            documents: List of dicts with keys: content, title, category, source_file
            generate_embeddings: Whether to generate vector embeddings

        Returns:
            Total number of chunks indexed
        """
        total_chunks = 0

        for doc in documents:
            chunks = self.index_document(
                content=doc["content"],
                title=doc["title"],
                category=doc["category"],
                source_file=doc["source_file"],
                generate_embeddings=generate_embeddings
            )
            total_chunks += len(chunks)

        print(f"Total chunks indexed: {total_chunks}")
        return total_chunks

    def delete_document(self, source_file: str) -> None:
        """Delete all chunks for a source file."""
        # Search for all chunks from this file
        results = self.search_client.search(
            search_text="*",
            filter=f"source_file eq '{source_file}'",
            select=["id"]
        )

        doc_ids = [{"id": doc["id"]} for doc in results]
        if doc_ids:
            result = self.search_client.delete_documents(documents=doc_ids)
            succeeded = sum(1 for r in result if r.succeeded)
            print(f"Deleted {succeeded} chunks for '{source_file}'")
        else:
            print(f"No documents found for '{source_file}'")

    def search(
        self,
        query: str,
        top: int = 5,
        use_vector: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Search the index.

        Args:
            query: Search query
            top: Number of results to return
            use_vector: Whether to use vector search

        Returns:
            List of search results
        """
        search_kwargs = {
            "search_text": query,
            "select": ["id", "title", "content", "category", "source_file", "chunk_id"],
            "top": top
        }

        if use_vector and self.openai_client:
            embedding = self.generate_embedding(query)
            if embedding:
                from azure.search.documents.models import VectorizedQuery
                search_kwargs["vector_queries"] = [
                    VectorizedQuery(
                        vector=embedding,
                        k_nearest_neighbors=top,
                        fields="content_vector"
                    )
                ]

        results = list(self.search_client.search(**search_kwargs))
        return results


# Sample policy documents for testing
SAMPLE_POLICIES = [
    {
        "title": "PTO Policy",
        "category": "hr",
        "source_file": "pto_policy.md",
        "content": """# Paid Time Off (PTO) Policy

## Overview
All full-time employees are entitled to paid time off (PTO) based on their tenure with the company.

## PTO Accrual
- New employees (0-2 years): 15 days per year
- Employees with 2-5 years tenure: 20 days per year
- Employees with 5+ years tenure: 25 days per year

## Requesting PTO
1. Submit PTO requests at least 2 weeks in advance for planned absences
2. Emergency/sick leave can be requested same-day
3. Requests should be submitted through the HR portal
4. Manager approval is required for all PTO requests

## PTO Carryover
- Up to 5 unused PTO days may be carried over to the next year
- Carryover days must be used within Q1 of the new year
- Unused carryover days after Q1 will be forfeited

## Holiday Schedule
The company observes the following paid holidays:
- New Year's Day
- Martin Luther King Jr. Day
- Presidents' Day
- Memorial Day
- Independence Day
- Labor Day
- Thanksgiving Day and day after
- Christmas Day

## Contact
For questions about PTO policy, contact HR at hr@company.com"""
    },
    {
        "title": "Remote Work Policy",
        "category": "hr",
        "source_file": "remote_work_policy.md",
        "content": """# Remote Work Policy

## Eligibility
Remote work arrangements are available to employees whose job responsibilities can be effectively performed outside the office.

## Requirements
1. Employees must maintain a dedicated workspace
2. Reliable high-speed internet connection required
3. Must be available during core business hours (10am-3pm local time)
4. Regular video meetings with cameras on
5. Response time to messages within 2 hours during business hours

## International Remote Work
- Working from another country requires pre-approval from HR and Legal
- Tax implications must be reviewed before approval
- Maximum duration: 30 days per year
- Cannot work remotely from countries under US sanctions

## Equipment
- Company provides laptop and necessary software
- Employees may request ergonomic equipment (up to $500 reimbursement)
- IT support available remotely during business hours

## Performance Expectations
- Remote employees are held to the same performance standards
- Regular check-ins with manager required (weekly minimum)
- Participation in team meetings is mandatory

## Combining Remote Work with PTO
- You may work remotely during PTO if traveling domestically
- International travel during PTO should not include work activities
- If you wish to extend a trip with remote work days, request approval 2 weeks in advance

## Contact
For remote work policy questions, contact HR at hr@company.com"""
    },
    {
        "title": "Expense Reimbursement Policy",
        "category": "finance",
        "source_file": "expense_policy.md",
        "content": """# Expense Reimbursement Policy

## Overview
This policy outlines the procedures for expense reimbursement for business-related costs.

## Expense Categories

### Travel Expenses
- Airfare: Economy class for flights under 6 hours
- Hotels: Up to $200/night (higher limits for major cities with approval)
- Meals: Up to $75/day
- Ground transportation: Reasonable costs for taxis, rideshare, or rental cars

### Office Supplies
- Pre-approved purchases up to $100 do not require manager approval
- Purchases over $100 require manager pre-approval

### Professional Development
- Conferences and training: Up to $2,500/year with manager approval
- Books and subscriptions: Up to $500/year

## Approval Requirements

| Amount | Approval Required |
|--------|-------------------|
| Under $100 | No approval needed |
| $100 - $500 | Manager approval |
| $500 - $2,500 | Manager + Director approval |
| $2,500 - $5,000 | VP approval |
| Over $5,000 | CFO approval |

## International Travel
- International travel requires VP approval regardless of amount
- Per diem rates follow US State Department guidelines
- Currency conversion at expense report date

## Submission Process
1. Submit expenses within 30 days of incurrence
2. Attach all receipts (photo or scan acceptable)
3. Include business purpose for each expense
4. Use the expense management system

## Reimbursement Timeline
- Approved expenses are reimbursed within 10 business days
- Direct deposit to payroll account

## Q4 Budget Freeze
During Q4 budget freeze (typically October-December):
- All non-essential travel must be pre-approved by VP
- Conference attendance limited to speakers only
- Expense reports should be submitted weekly

## Contact
For expense policy questions, contact finance@company.com"""
    },
    {
        "title": "Code of Conduct",
        "category": "compliance",
        "source_file": "code_of_conduct.md",
        "content": """# Code of Conduct

## Our Values
- Integrity in all business dealings
- Respect for colleagues and partners
- Commitment to diversity and inclusion
- Excellence in everything we do

## Professional Behavior
All employees are expected to:
- Treat others with respect and dignity
- Maintain confidentiality of company information
- Avoid conflicts of interest
- Report concerns through appropriate channels

## Anti-Harassment Policy
The company maintains a zero-tolerance policy for harassment based on:
- Race, color, or national origin
- Gender, gender identity, or sexual orientation
- Religion or disability
- Age or any other protected characteristic

## Reporting Concerns
If you observe violations of this code:
1. Report to your manager or HR
2. Use the anonymous ethics hotline: 1-800-ETHICS
3. Email: ethics@company.com

All reports are investigated confidentially.

## Consequences
Violations of this code may result in:
- Verbal or written warning
- Performance improvement plan
- Suspension
- Termination of employment

## Acknowledgment
All employees must acknowledge receipt and understanding of this code annually.

## Contact
For questions about the code of conduct, contact ethics@company.com"""
    }
]


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    # Initialize indexer
    indexer = DocumentIndexer(index_name="policy-documents")

    # Index sample policy documents (without embeddings for faster testing)
    total = indexer.index_policy_documents(
        SAMPLE_POLICIES,
        generate_embeddings=False  # Set to True if you have embedding model deployed
    )
    print(f"Indexed {total} total chunks")

    # Test search
    results = indexer.search("How many PTO days do new employees get?", top=3)
    for r in results:
        print(f"\n--- {r['title']} ({r['source_file']}) ---")
        print(r['content'][:200] + "...")
