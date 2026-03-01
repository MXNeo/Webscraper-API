import logging
import requests
import json
from table_extraction import complete_enhanced_extraction

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_ioc_extraction(url):
    """Test IOC extraction from a security blog URL"""
    logger.info(f"Testing IOC extraction from URL: {url}")
    
    # Headers to avoid binary content issues
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',  # Removed 'br' to avoid Brotli compression issues
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    try:
        # Fetch the page content
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        html_content = response.text
        
        # Check for binary content
        if any(ord(c) < 32 and c not in '\r\n\t' for c in html_content[:100]):
            logger.error(f"Received binary content instead of HTML. First 100 chars: {repr(html_content[:100])}")
            return
        
        # Run the enhanced extraction
        results = complete_enhanced_extraction(url, html_content)
        
        # Check if extraction succeeded
        if "error" in results:
            logger.error(f"Extraction failed: {results['error']}")
            return
        
        logger.info(f"Extraction successful:")
        logger.info(f"- Title: {results['title']}")
        logger.info(f"- Content length: {results['content_length']} characters")
        logger.info(f"- Tables found: {results['tables_found']}")
        logger.info(f"- IOCs found: {results['iocs_found']}")
        
        # Print structured IOCs
        if results['iocs_found'] > 0:
            logger.info("\n==================================================")
            logger.info("📊 STRUCTURED IOCs SUMMARY:")
            logger.info("==================================================")
            print(json.dumps(results['structured_iocs'], indent=2))
            
            # Categorize IOCs by type
            ioc_types = {}
            for ioc in results['structured_iocs']:
                if 'hash' in ioc:
                    ioc_type = ioc.get('type', 'unknown')
                    ioc_types[ioc_type] = ioc_types.get(ioc_type, 0) + 1
                elif 'domain' in ioc:
                    ioc_types['domains'] = ioc_types.get('domains', 0) + 1
            
            logger.info("\nIOC Type Distribution:")
            for ioc_type, count in ioc_types.items():
                logger.info(f"  {ioc_type}: {count}")
        
        # Print preview of content
        logger.info("\n==================================================")
        logger.info("📝 CONTENT PREVIEW (Final 1000 characters):")
        logger.info("==================================================")
        print(results['content'][-1000:])
        
        return results
        
    except Exception as e:
        logger.error(f"Error testing IOC extraction: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Test URL with IOCs - from CheckPoint Research or similar security blogs
    test_url = "https://research.checkpoint.com/2025/stealth-falcon-zero-day/"
    
    # You can add more test URLs here
    test_urls = [
        test_url,
        # Add more URLs as needed
    ]
    
    for url in test_urls:
        results = test_ioc_extraction(url)
        print("\n" + "="*70) 