from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter
import ollama
from sentence_transformers import SentenceTransformer
from datetime import datetime
import hashlib
from typing import List, Dict, Optional

class IdeaManagementQA:
    def __init__(self):
        self.client = QdrantClient(
            url="https://93f9b8c1-c55c-45ff-9577-4209a182aec2.us-west-1-0.aws.cloud.qdrant.io",
            api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.Yd7TbZIK4aOouF9pvoxHbEUALHvtEGRHUhEMjf0o584",
            prefer_grpc=True,
            timeout=30
        )
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.collection_name = "Ideas"
        self.llm_model = "llama2"
        self._initialize_collection()

    def _initialize_collection(self):
        """Create collection if it doesn't exist"""
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )
            
    def add_idea(
        self,
        title: str,
        description: str,
        category: str = "uncategorized",
        stage: str = "concept",
        creator: str = "anonymous"
    ) -> str:
        """
        Add a new idea to the management system
        Returns:
            str: The generated idea ID
        """
        idea_id = hashlib.md5(f"{title}{datetime.now()}".encode()).hexdigest()
        full_text = f"Idea: {title}\nDetails: {description}"
        embedding = self.embedder.encode(full_text).tolist()
        
        point = PointStruct(
            id=idea_id,
            vector=embedding,
            payload={
                "title": title,
                "description": description,
                "category": category,
                "stage": stage,
                "creator": creator,
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            }
        )
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=[point]
        )
        return idea_id

    def search_ideas(self, query: str, category_filter: Optional[str] = None, 
                    stage_filter: Optional[str] = None, top_k: int = 5) -> List[Dict]:
        # Build filters
        filters = None
        if category_filter or stage_filter:
            must_conditions = []
            if category_filter:
                must_conditions.append({"key": "category", "match": {"value": category_filter}})
            if stage_filter:
                must_conditions.append({"key": "stage", "match": {"value": stage_filter}})
            filters = Filter(must=must_conditions)
        
        # Encode query and search
        query_embedding = self.embedder.encode(query).tolist()
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter=filters,
            limit=top_k,
            with_payload=True
        )
        
        # Safely parse results
        return [{
            "id": hit.id,
            "score": hit.score,
            "title": hit.payload.get("title", ""),
            "description": hit.payload.get("description", ""),
            "category": hit.payload.get("category", ""),
            "stage": hit.payload.get("stage", ""),
            "creator": hit.payload.get("creator", "")
        } for hit in results if hit.payload]

    def generate_idea_analysis(self, idea_ids: List[str]) -> str:
        ideas = []
        for idea_id in idea_ids:
            records = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[idea_id],
                with_payload=True
            )
            if records and records[0].payload:
                ideas.append(records[0].payload)
        
        if not ideas:
            return "No ideas found for analysis."
        
        prompt = """**Business Innovation Analysis Request**

**Ideas to Analyze:**
{ideas_list}

**Instructions:**
1. Perform a SWOT analysis for each idea.
2. Identify synergies between ideas.
3. Recommend next steps with timelines.
4. Estimate resources needed.
5. Highlight potential risks.

**Format:** Use Markdown with clear headings."""
        
        ideas_list = "\n\n".join(
            f"### {idea['title']}\n"
            f"- **Category:** {idea['category']}\n"
            f"- **Stage:** {idea['stage']}\n"
            f"- **Description:** {idea['description']}"
            for idea in ideas
        )
        
        response = ollama.generate(
            model=self.llm_model,
            prompt=prompt.format(ideas_list=ideas_list),
            options={'temperature': 0.5, 'num_ctx': 4096}
        )
        return response['response']

    def answer_management_question(self, question: str) -> Dict:
        relevant_ideas = self.search_ideas(question, top_k=5)
        
        if not relevant_ideas:
            return {
                "answer": "No relevant ideas found to answer your question.",
                "sources": []
            }
        
        context = "\n".join(
            f"**{idea['title']}** (Stage: {idea['stage']})\n"
            f"- {idea['description'][:200]}..."
            for idea in relevant_ideas
        )
        
        prompt = f"""**Strategic Question Answering**

**Question:** {question}

**Relevant Ideas from Database:**
{context}

**Response Requirements:**
1. Direct answer to the question.
2. Key insights from matching ideas.
3. Actionable recommendations (prioritized).
4. Risks and mitigation strategies.
5. Success metrics (KPIs)."""
        
        response = ollama.generate(
            model=self.llm_model,
            prompt=prompt,
            options={'temperature': 0.4, 'num_ctx': 4096}
        )
        
        return {
            "answer": response['response'],
            "sources": relevant_ideas
        }

if __name__ == "__main__":
    manager = IdeaManagementQA()
    
    # Add sample ideas
    idea1 = manager.add_idea(
        title="wear your mobile phones",
        description="wear your mobile phones when the mobile phone was first introduced  it was as big as a lunch box  since then  the mobile phone has undergone countless transformations  it becam...",
        category="Mobile",
        stage="prototype"
    )
    
    idea2 = manager.add_idea(
        title="Sustainable Packaging Solution",
        description="Biodegradable packaging material made from agricultural waste",
        category="Sustainability",
        stage="concept"
    )
    
    # Test analysis
    print("=== Idea Analysis ===")
    print(manager.generate_idea_analysis([idea1, idea2]))
    
    # Test Q&A
    print("\n=== Management Q&A ===")
    questions = [
        "What are our most promising AI ideas?",
        "How can we accelerate sustainability projects?",
        "Which ideas have the highest ROI potential?"
    ]
    for q in questions:
        print(f"\n**Question:** {q}")
        result = manager.answer_management_question(q)
        print(f"**Answer:**\n{result['answer']}")