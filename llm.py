# LLM wrapper for Groq API
import os
import requests
import json
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class GroqLLM:
    """Wrapper for Groq API to handle natural language processing"""
    
    def __init__(self):
        self.api_key = os.getenv('GROQ_API_KEY')
        self.api_url = os.getenv('GROQ_API_URL', 'https://api.groq.com/openai/v1/chat/completions')
        
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")
    
    def _make_request(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> Dict[str, Any]:
        """Make API request to Groq"""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': 'llama-3.1-8b-instant',
            'messages': messages,
            'temperature': temperature,
            'max_tokens': 1024,
            'stream': False
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            raise Exception(f"Groq API request failed: {str(e)}")
    
    def parse_booking_query(self, query: str) -> Dict[str, Any]:
        """
        Parse natural language booking query to extract structured information
        """
        system_prompt = """You are a booking assistant that extracts structured information from natural language queries for beauty and wellness services.

IMPORTANT: Only process queries related to beauty/wellness services like manicure, pedicure, massage, facial, haircut, spa treatments, etc.

If the query is unrelated to beauty/wellness services (like random questions, gibberish, other topics), return:
{"valid_query": false, "reason": "Query not related to beauty or wellness services"}

For valid queries, extract and return:
- valid_query: true
- service: type of service (manicure, pedicure, massage, facial, haircut)
- location: area/location mentioned (REQUIRED - if not mentioned, ask user to specify Dubai area)
- preferred_date: date mentioned. IMPORTANT: 
  * If user says "next Monday", "next Friday", etc. → return "next monday", "next friday" (include "next")
  * If user says just "Monday", "Friday", etc. → return "monday", "friday" (without "next")
  * If user says "today" → return "today"
  * If user says "tomorrow" → return "tomorrow"
  * Examples: "next friday", "monday", "today", "tomorrow", "next tuesday"
- preferred_time: time mentioned or time range (morning/afternoon/evening or specific like "after 6 PM")
- duration: if specified (e.g., "90-min massage")
- budget: ONLY set if explicitly mentioned. Set to numeric value like 200 for "under 200 AED" or "budget 200". Set to -1 ONLY if user says "cheap", "low budget", "affordable", "budget-friendly" WITHOUT a specific number. If NO budget is mentioned, set to null or omit the field entirely. DO NOT invent budget values.
- budget_preference: set to "cheap" ONLY if user explicitly mentions "cheap", "low budget", "affordable", "budget-friendly"
- addons: any add-ons mentioned
- special_requests: any special requirements

CRITICAL: DO NOT set budget field unless the user explicitly mentions price, budget, "cheap", "affordable", or similar keywords. If no budget is mentioned, leave budget as null or omit it.

Return only valid JSON without any markdown formatting."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Parse this booking query: {query}"}
        ]

        try:
            response = self._make_request(messages, temperature=0.1)
            content = response['choices'][0]['message']['content'].strip()
            
            # Clean any markdown formatting
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            
            parsed_info = json.loads(content)
            return self._validate_parsed_query(parsed_info)
            
        except Exception as e:
            print(f"Error parsing query with Groq: {e}")
            return self._get_fallback_parsed_query(query)
    
    def _validate_parsed_query(self, parsed_info: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean parsed query information"""
        # Check if query is valid
        if not parsed_info.get('valid_query', True):
            return parsed_info  # Return as-is if invalid
        
        valid_services = ['manicure', 'pedicure', 'massage', 'facial', 'haircut']
        
        # Ensure required fields exist
        if 'service' not in parsed_info or parsed_info['service'].lower() not in valid_services:
            parsed_info['service'] = 'manicure'  # default
        
        # Set defaults for missing fields (but warn if location missing)
        if not parsed_info.get('location'):
            parsed_info['location'] = 'Business Bay'  # default but system should ask user
            parsed_info['location_missing'] = True
        
        parsed_info.setdefault('preferred_date', 'today')
        parsed_info.setdefault('preferred_time', 'afternoon')
        parsed_info.setdefault('valid_query', True)
        
        # Extract numeric budget from string if present
        if 'budget' in parsed_info and parsed_info['budget']:
            budget_str = str(parsed_info['budget']).lower()
            # Extract number from budget string
            import re
            numbers = re.findall(r'\d+', budget_str)
            if numbers:
                budget_value = int(numbers[0])
                # CRITICAL: Reject unrealistic budgets (< 50 AED is likely an error)
                if budget_value < 50 and budget_value != -1:
                    print(f"⚠️ Invalid budget detected: {budget_value} AED (too low), ignoring budget filter")
                    parsed_info['budget'] = None
                else:
                    parsed_info['budget'] = budget_value
            elif budget_str == '-1' or 'cheap' in budget_str or 'low' in budget_str:
                parsed_info['budget'] = -1  # Flag for cheap/affordable
                parsed_info['budget_preference'] = 'cheap'
            else:
                parsed_info['budget'] = None
        else:
            # Ensure budget is None if not set
            parsed_info['budget'] = None
        
        # Handle budget_preference field for cheap/affordable queries
        if parsed_info.get('budget_preference') == 'cheap' and not parsed_info.get('budget'):
            parsed_info['budget'] = -1  # Set flag
        
        return parsed_info
    
    def _get_fallback_parsed_query(self, query: str) -> Dict[str, Any]:
        """Fallback parsing when API fails"""
        # Simple keyword-based extraction as fallback
        query_lower = query.lower()
        
        service = 'manicure'  # default
        if 'pedicure' in query_lower:
            service = 'pedicure'
        elif 'massage' in query_lower:
            service = 'massage'
        elif 'facial' in query_lower:
            service = 'facial'
        elif 'haircut' in query_lower or 'hair' in query_lower:
            service = 'haircut'
        
        location = 'Business Bay'  # default
        if 'jlt' in query_lower or 'jumeirah lake towers' in query_lower:
            location = 'JLT'
        elif 'marina' in query_lower:
            location = 'Marina'
        elif 'downtown' in query_lower:
            location = 'Downtown'
        elif 'deira' in query_lower:
            location = 'Deira'
        
        return {
            'service': service,
            'location': location,
            'preferred_date': 'today',
            'preferred_time': 'afternoon',
            'duration': None,
            'budget': None,
            'addons': [],
            'special_requests': None
        }
    
    def generate_proposal_summary(self, proposal_data: Dict[str, Any]) -> str:
        """Generate a natural language summary of the booking proposal"""
        
        messages = [
            {
                "role": "system", 
                "content": "You are a booking assistant. Create a friendly, concise summary of the booking proposal. Include provider name, service, time, price, and location."
            },
            {
                "role": "user", 
                "content": f"Create a booking summary for this proposal: {json.dumps(proposal_data)}"
            }
        ]
        
        try:
            response = self._make_request(messages, temperature=0.3)
            return response['choices'][0]['message']['content'].strip()
        except Exception as e:
            # Fallback summary
            provider = proposal_data.get('provider', {}).get('name', 'Beauty Center')
            service = proposal_data.get('service', 'service')
            price = proposal_data.get('total_price', 0)
            
            return f"Booking proposal: {service} at {provider} for AED {price}. Please confirm to proceed."