import sys
import logging
from rag.pipeline import RAGPipeline

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_rag.py \"<your query>\"")
        sys.exit(1)
        
    query = sys.argv[1]
    
    logging.basicConfig(level=logging.WARNING) # Suppress info logs for clean CLI output
    
    pipeline = RAGPipeline()
    
    if not pipeline.check_readiness():
        print("ERROR: Ollama is not available. Please ensure it is running at the configured OLLAMA_BASE_URL.")
        sys.exit(1)
        
    print(f"\n==================================================")
    print(f"QUERY: {query}")
    print(f"==================================================\n")
    
    result = pipeline.query(query)
    
    print(f"ANSWER:\n{result['answer']}\n")
    print(f"==================================================")
    print(f"SOURCES:")
    
    if not result['sources']:
        print("No sources used.")
    else:
        for s in result['sources']:
            doc = s.get('document', 'Unknown')
            page = s.get('page', 'Unknown')
            sec = s.get('section', '')
            c_type = s.get('content_type', 'text')
            
            source_line = f"- [{doc}, p. {page}]"
            if sec:
                source_line += f" (Section: {sec})"
            if c_type == 'table':
                source_line += " [TABLE]"
                
            print(source_line)
            
    print(f"==================================================")
    print(f"RETRIEVED CONTEXT SUMMARY:")
    print(f"Total chunks retrieved: {len(result['retrieval_results'])}")
    for i, res in enumerate(result['retrieval_results']):
        print(f"  {i+1}. {res.get('document_name')} (Distance: {res.get('distance', 0):.4f})")
    print(f"==================================================\n")

if __name__ == "__main__":
    main()
