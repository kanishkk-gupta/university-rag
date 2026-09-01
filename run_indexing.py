import logging
import sys
from vectorstore.indexer import run_indexing

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    logger = logging.getLogger("indexing")
    logger.info("=" * 60)
    logger.info("BMU University RAG — Vector Indexing Pipeline")
    logger.info("=" * 60)
    
    run_indexing()
    
    logger.info("=" * 60)
    logger.info("INDEXING COMPLETE")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
