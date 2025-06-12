# qdrant_upsert_metadata.py
import pandas as pd
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
import time
from tqdm import tqdm  # For progress bars

# Configuration - UPDATE THESE VALUES
QDRANT_URL = "https://93f9b8c1-c55c-45ff-9577-4209a182aec2.us-west-1-0.aws.cloud.qdrant.io"
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.Yd7TbZIK4aOouF9pvoxHbEUALHvtEGRHUhEMjf0o584"  # Replace with your actual API key
COLLECTION_NAME = "Ideas"
EMBEDDING_DIM = 384  # Must match your embedding dimension
BATCH_SIZE = 100  # Reduced for more frequent commits

def initialize_client():
    """Initialize and verify Qdrant connection"""
    try:
        client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            timeout=30  # Increased timeout
        )
        # Test connection
        client.get_collections()
        return client
    except Exception as e:
        print(f"Connection failed: {str(e)}")
        raise

def safe_recreate_collection(client):
    """Safely handle collection creation with retries"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # First try deleting if exists
            try:
                client.delete_collection(COLLECTION_NAME)
                time.sleep(1)  # Brief pause
            except:
                pass  # Collection didn't exist
            
            # Create new collection
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=EMBEDDING_DIM,
                    distance=Distance.COSINE
                )
            )
            return True
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {str(e)}")
            time.sleep(2)  # Wait before retry
    return False

def upsert_data(client, metadata_path: str, embeddings_path: str):
    """Main upsert function with progress tracking"""
    try:
        print("Loading data...")
        metadata_df = pd.read_csv(metadata_path)
        embeddings_df = pd.read_csv(embeddings_path)
        
        assert len(metadata_df) == len(embeddings_df), "Mismatched row counts!"
        print(f"Found {len(metadata_df)} records to upsert")
        
        if not safe_recreate_collection(client):
            raise Exception("Failed to initialize collection after multiple attempts")
        
        print("Uploading data...")
        points = []
        successful_uploads = 0
        
        with tqdm(total=len(metadata_df)) as pbar:
            for idx, (meta_row, emb_row) in enumerate(zip(metadata_df.itertuples(), embeddings_df.values)):
                points.append(PointStruct(
                    id=idx,
                    vector=emb_row.tolist(),
                    payload={
                        "title": meta_row.title,
                        "text": meta_row.texto,
                        "original_id": idx
                    }
                ))
                
                if len(points) >= BATCH_SIZE:
                    try:
                        client.upsert(
                            collection_name=COLLECTION_NAME,
                            points=points,
                            wait=True
                        )
                        successful_uploads += len(points)
                        points = []
                        pbar.update(BATCH_SIZE)
                    except Exception as e:
                        print(f"\nBatch upload failed: {str(e)}")
                        raise
            
            # Final batch
            if points:
                client.upsert(
                    collection_name=COLLECTION_NAME,
                    points=points,
                    wait=True
                )
                successful_uploads += len(points)
                pbar.update(len(points))
        
        print(f"\nSuccessfully uploaded {successful_uploads}/{len(metadata_df)} records")
        print(f"Collection status: {client.get_collection(COLLECTION_NAME).status}")
        
    except Exception as e:
        print(f"\nError during upsert: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        qdrant_client = initialize_client()
        upsert_data(
            client=qdrant_client,
            metadata_path="metadata_train.csv",
            embeddings_path="embedding_train.csv"
        )
    except Exception as e:
        print(f"Fatal error: {str(e)}")