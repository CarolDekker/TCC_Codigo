import pandas as pd
from qdrant_client import QdrantClient
from qdrant_client.http import models
from tqdm import tqdm
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_qdrant_client():
    """Initialize and return Qdrant client with error handling"""
    try:
        client = QdrantClient(
            url="https://93f9b8c1-c55c-45ff-9577-4209a182aec2.us-west-1-0.aws.cloud.qdrant.io",
            api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.Yd7TbZIK4aOouF9pvoxHbEUALHvtEGRHUhEMjf0o584",
            timeout=100
        )
        # Test connection
        client.get_collections()
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Qdrant client: {str(e)}")
        raise

def create_collection_if_not_exists(client, collection_name, vector_size=384):
    """Create collection if it doesn't exist"""
    try:
        collections = client.get_collections()
        collection_names = [collection.name for collection in collections.collections]
        
        if collection_name not in collection_names:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,  # Based on your CSV which has 384 columns (0-383)
                    distance=models.Distance.COSINE  # Common choice for embeddings
                )
            )
            logger.info(f"Created collection: {collection_name}")
        else:
            logger.info(f"Collection {collection_name} already exists")
    except Exception as e:
        logger.error(f"Failed to create collection: {str(e)}")
        raise

def process_dataframe(df):
    """Process dataframe and convert to list of PointStruct"""
    points = []
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Processing rows"):
        try:
            point = models.PointStruct(
                id=idx,
                vector=row.values.tolist(),
                payload={}  # Add payload if needed
            )
            points.append(point)
        except Exception as e:
            logger.warning(f"Error processing row {idx}: {str(e)}")
            continue
    return points

def main():
    try:
        # Initialize client
        client = initialize_qdrant_client()
        
        # Create collection if it doesn't exist
        collection_name = "Ideas"
        create_collection_if_not_exists(client, collection_name)
        
        # Read CSV in chunks if large
        chunksize = 1000  # Adjust based on your memory constraints
        
        for chunk in tqdm(pd.read_csv('embedding_train.csv', sep=',', chunksize=chunksize), desc="Processing chunks"):
            # Convert numeric columns to float (handles commas if present)
            chunk = chunk.apply(lambda x: pd.to_numeric(x.astype(str).str.replace(',', '.'), errors='coerce'))
            
            # Drop rows with NA values that resulted from conversion
            chunk = chunk.dropna()
            
            # Process chunk
            points = process_dataframe(chunk)
            
            # Upsert to Qdrant
            try:
                client.upsert(
                    collection_name=collection_name,
                    points=points,
                    wait=True
                )
                logger.info(f"Successfully upserted {len(points)} points")
            except Exception as e:
                logger.error(f"Failed to upsert batch: {str(e)}")
                
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()