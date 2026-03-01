import logging
from bs4 import BeautifulSoup
from newspaper import Article

logger = logging.getLogger(__name__)

def smart_table_extraction(soup, main_content_area=None):
    """
    Intelligently extract tables that are part of article content,
    while filtering out ads, navigation, and layout tables
    """
    
    # Find main content area if not provided
    if not main_content_area:
        content_selectors = [
            'article', 'main', '.entry-content', '.post-content', 
            '.article-content', '.content', '#content', '.single-post-content'
        ]
        for selector in content_selectors:
            main_content_area = soup.select_one(selector)
            if main_content_area:
                logger.debug(f"Found main content area: {selector}")
                break
    
    if not main_content_area:
        logger.debug("No main content area found, using full page")
        main_content_area = soup
    
    # Find all tables in main content area
    all_tables = main_content_area.find_all('table')
    logger.debug(f"Found {len(all_tables)} total tables in content area")
    
    article_tables = []
    
    for i, table in enumerate(all_tables):
        table_info = {
            "table_id": i + 1,
            "element": table,
            "is_article_content": False,
            "is_iocs": False,
            "context": "",
            "content_indicators": [],
            "skip_reasons": []
        }
        
        # === FILTERING CRITERIA ===
        
        # 1. Skip tables with obvious ad/navigation indicators
        table_classes = ' '.join(table.get('class', []))
        table_id = table.get('id', '')
        
        # Check parent elements for context
        parent_classes = []
        parent = table.parent
        for _ in range(3):  # Check up to 3 levels up
            if parent and hasattr(parent, 'get') and callable(parent.get):
                parent_classes.extend(parent.get('class', []))
            if parent:
                parent = parent.parent
        
        all_classes = table_classes + ' ' + ' '.join(parent_classes)
        
        # Skip tables that are likely part of navigation, ads, etc.
        skip_keywords = ['navigation', 'menu', 'sidebar', 'widget', 'banner', 'ad-', '-ad', 'footer', 'header', 'cookie']
        
        for keyword in skip_keywords:
            if keyword in all_classes.lower() or keyword in table_id.lower():
                table_info["skip_reasons"].append(f"Contains '{keyword}' in class/id")
                break
        
        if table_info["skip_reasons"]:
            continue
        
        # 2. Look for table context
        current = table
        context_headings = []
        
        for _ in range(5):  # Look back up to 5 siblings
            if not current:
                break
                
            current = current.find_previous_sibling()
            
            if current and current.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                heading_text = current.get_text().strip()
                context_headings.append(heading_text)
                if any(keyword in heading_text.lower() for keyword in ['ioc', 'indicator', 'hash', 'domain', 'ip', 'malware', 'threat', 'data', 'result', 'analysis']):
                    table_info["content_indicators"].append("Security/analysis heading nearby")
                    table_info["context"] = current.get_text().strip()
                break
        
        # 3. Analyze table content
        rows = table.find_all('tr')
        table_info["row_count"] = len(rows)
        
        if len(rows) == 0:
            table_info["skip_reasons"].append("Empty table")
            continue
        
        # Get sample content
        sample_cells = []
        for row in rows[:5]:  # Sample first 5 rows
            cells = row.find_all(['td', 'th'])
            for cell in cells:
                cell_text = cell.get_text(strip=True)
                if cell_text and len(cell_text) > 0:
                    sample_cells.append(cell_text)
        
        # Content pattern detection
        hash_count = 0
        domain_count = 0
        ip_count = 0
        meaningful_content = 0
        
        for cell_text in sample_cells:
            # Hash detection (32+ hex chars)
            if len(cell_text) >= 32 and all(c in '0123456789abcdef' for c in cell_text.lower()):
                hash_count += 1
                table_info["content_indicators"].append("Contains hashes")
            
            # Domain detection
            elif '.' in cell_text and len(cell_text) < 100 and not ' ' in cell_text:
                if any(tld in cell_text.lower() for tld in ['.com', '.net', '.org', '.edu', '.gov']):
                    domain_count += 1
                    table_info["content_indicators"].append("Contains domains")
            
            # IP detection
            elif cell_text.count('.') == 3 and all(part.isdigit() and 0 <= int(part) <= 255 for part in cell_text.split('.') if part.isdigit()):
                ip_count += 1
                table_info["content_indicators"].append("Contains IPs")
            
            # Meaningful text content
            elif len(cell_text) > 3 and not cell_text.lower() in ['', '&nbsp;', 'n/a', '-']:
                meaningful_content += 1
        
        # 4. Decision logic
        if hash_count > 0 or domain_count > 0 or ip_count > 0:
            table_info["is_iocs"] = True
            table_info["is_article_content"] = True
            table_info["content_indicators"].append("IOCs detected")
        
        elif meaningful_content >= 3 and len(rows) >= 2:
            table_info["is_article_content"] = True
            table_info["content_indicators"].append("Meaningful data table")
        
        elif len(rows) == 1 and meaningful_content <= 2:
            table_info["skip_reasons"].append("Looks like layout table (1 row, minimal content)")
            continue
        
        elif meaningful_content == 0:
            table_info["skip_reasons"].append("No meaningful content")
            continue
        
        else:
            # Borderline case - include if has good context
            if table_info["context"] or any('heading' in indicator for indicator in table_info["content_indicators"]):
                table_info["is_article_content"] = True
                table_info["content_indicators"].append("Good context despite minimal content")
            else:
                table_info["skip_reasons"].append("Insufficient context and content")
                continue
        
        article_tables.append(table_info)
    
    return article_tables

def improved_smart_table_extraction(soup):
    """
    Improved version that handles content outside main content areas
    """
    
    # Try multiple content area strategies
    content_strategies = [
        # Strategy 1: Traditional content areas
        {
            "name": "Traditional content selectors",
            "selectors": ['article', 'main', '.entry-content', '.post-content', '.article-content', '.content', '#content']
        },
        # Strategy 2: WordPress/CMS specific areas
        {
            "name": "WordPress content areas", 
            "selectors": ['.flex-8.font-white', '.text.border-bottom', '.wp-block-group', '.single-post-content']
        },
        # Strategy 3: Full body fallback
        {
            "name": "Full body fallback",
            "selectors": ['body']
        }
    ]
    
    best_content_area = None
    best_table_count = 0
    best_strategy = None
    
    logger.debug("Testing content area strategies...")
    
    for strategy in content_strategies:
        for selector in strategy["selectors"]:
            area = soup.select_one(selector)
            if area:
                tables_in_area = area.find_all('table')
                table_count = len(tables_in_area)
                
                # Check if any tables contain IOCs-like content
                iocs_score = 0
                for table in tables_in_area:
                    rows = table.find_all('tr')
                    for row in rows[:3]:  # Sample first 3 rows
                        cells = row.find_all(['td', 'th'])
                        for cell in cells:
                            cell_text = cell.get_text(strip=True)
                            # Score tables with hash-like content higher
                            if len(cell_text) >= 32 and all(c in '0123456789abcdef' for c in cell_text.lower()):
                                iocs_score += 10
                            elif '.' in cell_text and any(tld in cell_text.lower() for tld in ['.com', '.net', '.org']):
                                iocs_score += 5
                
                total_score = table_count + iocs_score
                logger.debug(f"{selector}: {table_count} tables, IOCs score: {iocs_score}, total: {total_score}")
                
                # Pick the area with the best combination of table count and IOCs content
                if total_score > best_table_count:
                    best_content_area = area
                    best_table_count = total_score
                    best_strategy = f"{strategy['name']} ({selector})"
                
                break  # Found this selector, move to next strategy
    
    if best_content_area is None:
        logger.debug("No content area found, using full page")
        best_content_area = soup
        best_strategy = "Full page fallback"
    
    logger.debug(f"Selected: {best_strategy} with score {best_table_count}")
    
    # Now extract tables from the best content area
    all_tables = best_content_area.find_all('table')
    logger.debug(f"Found {len(all_tables)} total tables in selected area")
    
    article_tables = []
    
    for i, table in enumerate(all_tables):
        table_info = {
            "table_id": i + 1,
            "element": table,
            "is_article_content": False,
            "is_iocs": False,
            "context": "",
            "content_indicators": [],
            "skip_reasons": [],
            "row_count": 0
        }
        
        # Look for context (nearby headings)
        current = table
        for _ in range(8):  # Look further back for context
            if not current:  # Bug fix: check if current is None
                break
                
            current = current.find_previous_sibling()
            
            if not current:  # Bug fix: check if current is None after find_previous_sibling
                break
                
            if current.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                heading_text = current.get_text().strip()
                table_info["context"] = heading_text
                if any(keyword in heading_text.lower() for keyword in ['ioc', 'indicator', 'hash', 'domain', 'malware', 'threat']):
                    table_info["content_indicators"].append("Security/analysis heading nearby")
                break
        
        # Analyze table content
        rows = table.find_all('tr')
        table_info["row_count"] = len(rows)
        
        if len(rows) == 0:
            table_info["skip_reasons"].append("Empty table")
            continue
        
        # Content analysis
        hash_count = 0
        domain_count = 0
        meaningful_content = 0
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            for cell in cells:
                cell_text = cell.get_text(strip=True)
                if len(cell_text) >= 32 and all(c in '0123456789abcdef' for c in cell_text.lower()):
                    hash_count += 1
                    table_info["content_indicators"].append("Contains hashes")
                elif '.' in cell_text and len(cell_text) < 100:
                    # More permissive domain detection - also include domains in brackets like [.]com
                    clean_text = cell_text.replace('[.]', '.').replace('(.)', '.').strip()
                    if any(tld in clean_text.lower() for tld in ['.com', '.net', '.org', '.edu', '.gov']):
                        domain_count += 1
                        table_info["content_indicators"].append("Contains domains")
                elif len(cell_text) > 3:
                    meaningful_content += 1
        
        # Decision logic - more permissive since we're in a curated content area
        if hash_count > 0 or domain_count > 0:
            table_info["is_iocs"] = True
            table_info["is_article_content"] = True
            table_info["content_indicators"].append("IOCs detected")
        elif meaningful_content >= 2 and len(rows) >= 2:
            table_info["is_article_content"] = True
            table_info["content_indicators"].append("Meaningful data table")
        else:
            table_info["skip_reasons"].append("Insufficient meaningful content")
            continue
        
        article_tables.append(table_info)
    
    return article_tables

def extract_structured_data(table_info_list, url=None):
    """
    Extract structured data from tables including IOCs
    """
    all_iocs = []
    table_summaries = []
    
    for table_info in table_info_list:
        table_element = table_info["element"]
        rows = table_element.find_all('tr')
        
        table_data = []
        for row in rows:
            cells = row.find_all(['td', 'th'])
            row_data = [cell.get_text(strip=True) for cell in cells]
            if row_data and any(cell for cell in row_data):
                table_data.append(row_data)
        
        # Create table summary
        summary = {
            "context": table_info["context"] or f"Table {table_info['table_id']}",
            "rows": len(table_data),
            "is_iocs": table_info["is_iocs"],
            "data": table_data
        }
        table_summaries.append(summary)
        
        # Extract IOCs if applicable
        if table_info["is_iocs"]:
            for row in table_data:
                if len(row) >= 1:
                    hash_value = row[0].strip()
                    # Check for hash values (32+ hex chars)
                    if len(hash_value) >= 32 and all(c in '0123456789abcdef' for c in hash_value.lower()):
                        # FIX: Use default type text or "unknown" when empty
                        type_value = ""
                        if len(row) > 1:
                            type_value = row[1].strip()
                        
                        all_iocs.append({
                            "hash": hash_value,
                            "type": type_value if type_value else "unknown",  # Fixed to use "unknown" instead of empty string
                            "context": summary["context"]
                        })
                    # Check for domains
                    elif '.' in hash_value and len(hash_value) < 100:  # Domain
                        # Clean domain - replace bracket notation [.] with actual dots
                        clean_domain = hash_value.replace('[.]', '.').replace('(.)', '.').strip()
                        if any(tld in clean_domain.lower() for tld in ['.com', '.net', '.org', '.edu', '.gov']):
                            all_iocs.append({
                                "domain": clean_domain,
                                "type": "malicious_domain",
                                "context": summary["context"]
                            })
    
    return {
        "table_summaries": table_summaries,
        "iocs": all_iocs
    }

def complete_enhanced_extraction(url, html_content):
    """
    Final implementation combining newspaper4k + smart table filtering
    """
    try:
        # Step 1: Extract main content with newspaper4k
        logger.info(f"Extracting main content with newspaper4k for {url}")
        article = Article(url)
        article.download(input_html=html_content)
        article.parse()
        
        # Step 2: Smart table extraction
        logger.info("Applying smart table filtering")
        soup = BeautifulSoup(html_content, 'html.parser')
        smart_tables = improved_smart_table_extraction(soup)
        
        # Step 3: Extract structured data from tables
        logger.info(f"Extracting structured data from {len(smart_tables)} tables")
        structured_data = extract_structured_data(smart_tables)
        all_iocs = structured_data["iocs"]
        table_summaries = structured_data["table_summaries"]
        
        # Step 4: Combine into final content
        final_content = article.text
        
        if table_summaries:
            final_content += "\n\n" + "="*50
            final_content += "\n=== STRUCTURED DATA EXTRACTED ==="
            final_content += "\n" + "="*50
            
            for table in table_summaries:
                final_content += f"\n\n### {table['context']}\n"
                
                if table["is_iocs"]:
                    final_content += f"IOCs Table ({table['rows']} entries):\n\n"
                    for row in table["data"]:
                        if len(row) >= 2:
                            # Clean up text that might have brackets to improve readability
                            row_text = row[0].replace('[.]', '.').replace('(.)', '.')
                            type_text = row[1].strip() if row[1].strip() else "unknown"
                            final_content += f"• {row_text} | {type_text}\n"
                        elif len(row) == 1:
                            row_text = row[0].replace('[.]', '.').replace('(.)', '.')
                            final_content += f"• {row_text}\n"
                else:
                    final_content += f"Data Table ({table['rows']} rows):\n\n"
                    for row in table["data"][:5]:  # Show first 5 rows
                        final_content += "| " + " | ".join(row) + " |\n"
                    if table['rows'] > 5:
                        final_content += f"... and {table['rows'] - 5} more rows\n"
        
        # Separate hash and domain IOCs for easier consumption by the front-end
        hash_iocs = [ioc for ioc in all_iocs if "hash" in ioc]
        domain_iocs = [ioc for ioc in all_iocs if "domain" in ioc]
        
        # Format domain IOCs to match hash IOCs format for consistency
        formatted_domain_iocs = []
        for domain in domain_iocs:
            formatted_domain_iocs.append({
                "domain": domain["domain"],
                "type": domain["type"],
                "context": domain["context"]
            })
        
        return {
            "title": article.title,
            "url": url,
            "content": final_content,
            "content_length": len(final_content),
            "original_length": len(article.text),
            "tables_found": len(table_summaries),
            "iocs_found": len(all_iocs),
            "structured_iocs": hash_iocs,
            "structured_domain_iocs": formatted_domain_iocs,
            "extraction_method": "newspaper4k + smart_table_filtering"
        }
        
    except Exception as e:
        logger.error(f"Error during enhanced extraction: {str(e)}")
        return {"error": str(e)} 