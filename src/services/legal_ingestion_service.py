
import asyncio
import logging
import json
import uuid
import os
import time
from typing import List, Dict, Any
# ...
from llama_parse import LlamaParse
from services.graph_service import graph_service
from utils.llm_client import LlmClient
from config import Config
from llama_index.core.node_parser import SentenceSplitter

logger = logging.getLogger(__name__)


class LegalIngestionService:
    def __init__(self):
        self.llm_client = LlmClient()
        self.parser = LlamaParse(
            result_type="markdown",
            api_key=Config.llama_cloud.API_KEY,
            verbose=True
        )

    async def ingest_document(self, file_path: str, file_id: str):
        """
        Orchestrates the ingestion: Parse -> Extract Graph -> Store in Neo4j.
        """
        logger.info(f"Starting Legal Ingestion for {file_id}")
        
        if not Config.llama_cloud.API_KEY:
            logger.error("LLAMA_CLOUD_API_KEY is missing. Skipping LlamaParse.")
            return


        # 0. Check if file already exists
        check_query = "MATCH (f:File {id: $file_id}) RETURN f"
        existing = graph_service.execute_query(check_query, {"file_id": file_id})
        if existing:
            logger.info(f"File {file_id} already ingested. Skipping.")
            return "Already ingested."

        try:
            # 1. Parse Document
            docs = await self.parser.aload_data(file_path)
            full_text = "\n".join([doc.text for doc in docs])
            
            logger.info(f"LlamaParse extracted {len(full_text)} chars.")

            # 2. Extract Graph (Parallel)
            chunks = self._chunk_text_for_graph(full_text)
            all_nodes = []
            all_edges = []
            
            # Helper for async processing
            async def process_chunk(chunk, chunk_index):
                try:
                    # No sleep needed for OpenAI/Paid
                    graph_json_str = await self._extract_async(chunk) 
                    cleaned_json = self._clean_json(graph_json_str)
                    graph_data = json.loads(cleaned_json)
                    return graph_data
                except Exception as e:
                    logger.error(f"Error processing chunk {chunk_index}: {e}")
                    return None

            # Run in parallel with Semaphore
            sem = asyncio.Semaphore(5) # 5 concurrent requests
            async def protected_process(chunk, i):
                async with sem:
                    return await process_chunk(chunk, i)

            results = await asyncio.gather(*[protected_process(c, i) for i, c in enumerate(chunks)])
            
            for res in results:
                if res:
                    if "nodes" in res: all_nodes.extend(res["nodes"])
                    if "edges" in res: all_edges.extend(res["edges"])

            # 3. Store in Neo4j (Add File Node too)
            self._persist_to_neo4j(all_nodes, all_edges, file_id)
            
            # Create File Node to mark completion
            graph_service.execute_query(
                "MERGE (f:File {id: $file_id}) SET f.ingested_at = timestamp()", 
                {"file_id": file_id}
            )
            
            return full_text 

        except Exception as e:
            logger.error(f"Legal Ingestion failed: {e}", exc_info=True)
            raise e

    def _chunk_text_for_graph(self, text: str, chunk_size=3000) -> List[str]:
        splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=200)
        return splitter.split_text(text)

    def _persist_to_neo4j(self, nodes: List[Dict], edges: List[Dict], file_id: str):
        logger.info(f"Persisting {len(nodes)} nodes and {len(edges)} edges to Neo4j")
        
        # Merge Nodes
        ALLOWED_LABELS = {"Case", "Ruling", "Statute", "Section", "LegalConcept", "Condition", "Judge", "LegalSystem"}
        for node in nodes:
            label = node.get('label')
            if not label or label not in ALLOWED_LABELS:
                logger.warning(f"Skipping node with invalid or missing label: {label}")
                continue

            query = f"""
            MERGE (n:{label} {{id: $id}})
            SET n.text = $text, n.file_id = $file_id
            """
            graph_service.execute_query(query, {
                "id": self._make_global_id(node['id'], file_id), 
                "text": node.get('text', ''),
                "file_id": file_id
            })

        # Merge Edges
        ALLOWED_RELATIONS = {"ESTABLISHED", "DEFINES", "HAS_EXCEPTION", "SUPPORTS", "CONTRADICTS", "ALLOWS", "REJECTS"}
        for edge in edges:
            relation = edge.get('relation')
            normalized_relation = relation.upper().replace(" ", "_") if relation else None

            if not normalized_relation or normalized_relation not in ALLOWED_RELATIONS:
                logger.warning(f"Skipping edge with invalid or missing relation: {relation}")
                continue

            source_id = self._make_global_id(edge['source'], file_id)
            target_id = self._make_global_id(edge['target'], file_id)
            
            query = f"""
            MATCH (s {{id: $source_id}}), (t {{id: $target_id}})
            MERGE (s)-[r:{normalized_relation}]->(t)
            """
            graph_service.execute_query(query, {
                "source_id": source_id,
                "target_id": target_id
            })



    async def _extract_async(self, text: str) -> str:
        """
        Wrapper to run sync LlmClient method in a thread pool.
        """
        return await asyncio.to_thread(self.llm_client.extract_legal_graph_triplets, text)

    def _clean_json(self, response: str) -> str:

        """
        Cleans the response from LLM to extract valid JSON.
        Removes markdown code blocks (```json ... ```).
        """
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]
            
        if response.endswith("```"):
            response = response[:-3]
            
        return response.strip()

    def _make_global_id(self, local_id: str, file_id: str) -> str:

        # Create a unique ID to prevent collisions between chunks unless intended
        # Ideally we use Entity Resolution (e.g. Node Name) instead of chunk-IDs
        # For now, append file_id to assume nodes are unique to this ingestion run unless names match
        # To improve: extracting 'name' property and merging on 'name' is better.
        # But looking at prototype, 'id' was abstract 'N1'.
        return f"{file_id}_{local_id}"

legal_ingestion_service = LegalIngestionService()
