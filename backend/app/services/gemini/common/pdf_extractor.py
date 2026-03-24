"""
PDF Structured Data Extraction Service

This service provides functionality to extract structured data from PDF documents
using Gemini's function calling capabilities.
"""

from typing import Dict, Any, List, Optional
import json
import time
import logging
import pypdf
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


# ============================================================================
# PDF Processing Functions
# ============================================================================

def extract_text_from_pdf(pdf_file_bytes: bytes) -> str:
    """
    Extracts text from a PDF file.

    Args:
        pdf_file_bytes: PDF file content as bytes

    Returns:
        Extracted text from all pages
    """
    import io
    text = ""
    pdf_file = io.BytesIO(pdf_file_bytes)
    reader = pypdf.PdfReader(pdf_file)
    for page in reader.pages:
        text += page.extract_text()
    return text


# ============================================================================
# Function Declaration Schemas
# ============================================================================

# Invoice Data Extraction Schema
extract_invoice_data_tool = types.FunctionDeclaration(
    name='extract_invoice_data',
    description='Extracts structured information from an invoice document.',
    parameters_json_schema={
        'type': 'object',
        'properties': {
            'invoice_number': {'type': 'string', 'description': 'The unique invoice number.'},
            'vendor_name': {'type': 'string', 'description': 'The name of the vendor or supplier.'},
            'vendor_address': {'type': 'string', 'description': 'The address of the vendor or supplier.'},
            'customer_name': {'type': 'string', 'description': 'The name of the customer or recipient.'},
            'customer_address': {'type': 'string', 'description': 'The address of the customer or recipient.'},
            'issue_date': {'type': 'string', 'description': 'The date the invoice was issued (e.g., YYYY-MM-DD).'},
            'due_date': {'type': 'string', 'description': 'The date the invoice is due (e.g., YYYY-MM-DD).'},
            'total_amount': {'type': 'number', 'description': 'The total amount of the invoice, including tax.'},
            'currency': {'type': 'string', 'description': 'The currency of the total amount (e.g., USD, EUR, CNY).'},
            'tax_amount': {'type': 'number', 'description': 'The total tax amount on the invoice.'},
            'subtotal_amount': {'type': 'number', 'description': 'The subtotal amount before tax.'},
            'items': {
                'type': 'array',
                'description': 'List of line items on the invoice.',
                'items': {
                    'type': 'object',
                    'properties': {
                        'description': {'type': 'string', 'description': 'Description of the item.'},
                        'quantity': {'type': 'number', 'description': 'Quantity of the item.'},
                        'unit_price': {'type': 'number', 'description': 'Unit price of the item.'},
                        'line_total': {'type': 'number', 'description': 'Total for the item line.'}
                    },
                    'required': ['description', 'quantity', 'unit_price', 'line_total']
                }
            }
        },
        'required': ['invoice_number', 'vendor_name', 'total_amount', 'issue_date', 'currency']
    }
)

# Generic Form Data Extraction Schema
extract_form_data_tool = types.FunctionDeclaration(
    name='extract_form_data',
    description='Extracts structured information from a generic form.',
    parameters_json_schema={
        'type': 'object',
        'properties': {
            'name': {'type': 'string', 'description': 'Full name provided in the form.'},
            'email': {'type': 'string', 'description': 'Email address provided.'},
            'phone_number': {'type': 'string', 'description': 'Phone number provided.'},
            'address': {'type': 'string', 'description': 'Full mailing address.'},
            'company': {'type': 'string', 'description': 'Company name.'},
            'job_title': {'type': 'string', 'description': 'Job title or position.'},
            'message': {'type': 'string', 'description': 'Any message or comments from the form.'}
        },
        'required': ['name']
    }
)

# Receipt Data Extraction Schema
extract_receipt_data_tool = types.FunctionDeclaration(
    name='extract_receipt_data',
    description='Extracts structured information from a receipt.',
    parameters_json_schema={
        'type': 'object',
        'properties': {
            'merchant_name': {'type': 'string', 'description': 'Name of the merchant or store.'},
            'merchant_address': {'type': 'string', 'description': 'Address of the merchant.'},
            'date': {'type': 'string', 'description': 'Date of the transaction.'},
            'time': {'type': 'string', 'description': 'Time of the transaction.'},
            'total_amount': {'type': 'number', 'description': 'Total amount paid.'},
            'currency': {'type': 'string', 'description': 'Currency of the transaction.'},
            'tax_amount': {'type': 'number', 'description': 'Tax amount.'},
            'payment_method': {'type': 'string', 'description': 'Payment method used (cash, card, etc.).'},
            'items': {
                'type': 'array',
                'description': 'List of purchased items.',
                'items': {
                    'type': 'object',
                    'properties': {
                        'name': {'type': 'string', 'description': 'Item name.'},
                        'quantity': {'type': 'number', 'description': 'Item quantity.'},
                        'price': {'type': 'number', 'description': 'Item price.'}
                    }
                }
            }
        },
        'required': ['merchant_name', 'total_amount']
    }
)

# Contract Data Extraction Schema
extract_contract_data_tool = types.FunctionDeclaration(
    name='extract_contract_data',
    description='Extracts structured information from a contract or agreement.',
    parameters_json_schema={
        'type': 'object',
        'properties': {
            'contract_title': {'type': 'string', 'description': 'Title or name of the contract.'},
            'contract_number': {'type': 'string', 'description': 'Contract number or reference ID.'},
            'party_a_name': {'type': 'string', 'description': 'Name of first party.'},
            'party_b_name': {'type': 'string', 'description': 'Name of second party.'},
            'effective_date': {'type': 'string', 'description': 'Date when contract becomes effective.'},
            'expiration_date': {'type': 'string', 'description': 'Date when contract expires.'},
            'contract_value': {'type': 'number', 'description': 'Total value of the contract.'},
            'currency': {'type': 'string', 'description': 'Currency of the contract value.'},
            'key_terms': {
                'type': 'array',
                'description': 'List of key terms and conditions.',
                'items': {'type': 'string'}
            }
        },
        'required': ['party_a_name', 'party_b_name']
    }
)


# Template registry
EXTRACTION_TEMPLATES = {
    'invoice': {
        'name': 'Invoice',
        'description': 'Extract structured data from invoices',
        'tool': extract_invoice_data_tool,
        'icon': '📄'
    },
    'form': {
        'name': 'Generic Form',
        'description': 'Extract data from application forms, contact forms, etc.',
        'tool': extract_form_data_tool,
        'icon': '📝'
    },
    'receipt': {
        'name': 'Receipt',
        'description': 'Extract data from purchase receipts',
        'tool': extract_receipt_data_tool,
        'icon': '🧾'
    },
    'contract': {
        'name': 'Contract',
        'description': 'Extract key information from contracts and agreements',
        'tool': extract_contract_data_tool,
        'icon': '📋'
    },
    'full-text': {
        'name': 'Full Text',
        'description': 'Extract full PDF text and return as Markdown/plain text',
        'tool': None,
        'icon': '📄'
    }
}


# ============================================================================
# PDF Extractor Service
# ============================================================================

class PDFExtractorService:
    """
    PDF Structured Data Extraction Service.

    Extracts structured data from PDF documents using Gemini function calling.
    """

    def __init__(self, *, api_key=None, use_vertex=False, project=None, location=None, http_options=None):
        """
        Initialize PDF extractor service.

        Args:
            client_factory: A callable that returns a configured Gemini client
        """
        self._api_key = api_key
        self._use_vertex = use_vertex
        self._project = project
        self._location = location
        self._http_options = http_options
        logger.info("[PDF Extractor Service] Initialized")

    async def extract_structured_data(
        self,
        pdf_bytes: bytes,
        template_type: str,
        model_id: str,
        additional_instructions: str = ""
    ) -> Dict[str, Any]:
        """
        Extract structured data from a PDF using Gemini function calling.

        Args:
            pdf_bytes: PDF file content as bytes
            template_type: Type of template to use ('invoice', 'form', 'receipt', 'contract', 'full-text')
            model_id: Model ID to use for extraction (required)
            additional_instructions: Optional additional instructions for extraction

        Returns:
            Dictionary containing extracted structured data

        Raises:
            ValueError: If template_type is not recognized or model_id is missing
            Exception: If extraction fails
        """
        # Validate template type
        if template_type not in EXTRACTION_TEMPLATES:
            raise ValueError(f"Unknown template type: {template_type}")

        logger.info(f"[PDF Extractor Service] Extraction started: template={template_type}, model={model_id}")
        logger.info(f"[PDF Extractor Service] PDF size: {len(pdf_bytes)} bytes")

        # Validate model ID
        if not model_id or not model_id.strip():
            raise ValueError("Model ID is required for PDF extraction")

        # Clean model ID (remove models/ prefix if present, as Gemini SDK handles it)
        cleaned_model_id = model_id.strip()
        if cleaned_model_id.startswith('models/'):
            cleaned_model_id = cleaned_model_id.replace('models/', '', 1)

        # Normalize common aliases that frequently 404 on v1beta
        if cleaned_model_id == 'gemini-1.5-pro-latest':
            cleaned_model_id = 'gemini-1.5-pro'
        elif cleaned_model_id == 'gemini-1.5-flash-latest':
            cleaned_model_id = 'gemini-1.5-flash'

        logger.info(f"[PDF Extractor Service] Model normalized: '{model_id}' -> '{cleaned_model_id}'")

        # Extract text from PDF (used by all modes)
        extracted_text = extract_text_from_pdf(pdf_bytes)

        if not extracted_text.strip():
            raise ValueError("No text could be extracted from the PDF")

        logger.info(f"[PDF Extractor Service] Extracted {len(extracted_text)} characters from PDF")

        template_config = EXTRACTION_TEMPLATES[template_type]

        # --- Full-text / Markdown mode: return raw text directly, no LLM round-trip ---
        if template_type == 'full-text':
            # Simple cleanup: collapse excessive blank lines
            cleaned = "\n".join([line.rstrip() for line in extracted_text.splitlines()])
            cleaned = "\n\n".join([blk.strip() for blk in cleaned.split("\n\n") if blk.strip()])

            logger.info(f"[PDF Extractor Service] Full-text extraction completed")
            return {
                'success': True,
                'template_type': template_type,
                'template_name': template_config['name'],
                'data': {
                    'markdown': cleaned
                },
                'raw_text': cleaned
            }

        # Structured templates continue with function-calling
        func_decl = template_config['tool']

        # Get client from unified pool
        client = get_client_pool().get_client(
                api_key=self._api_key,
                vertexai=self._use_vertex,
                project=self._project,
                location=self._location,
                http_options=self._http_options,
            )
        logger.info(f"[PDF Extractor Service] Using model: {cleaned_model_id}")

        # Create prompt
        prompt = f"""
Please extract the {template_config['name'].lower()} information from the following text.
If any field is not found or cannot be determined, omit it from the output.
{additional_instructions}

Document Text:
---
{extracted_text}
---
"""

        # Create tool from function declaration
        tool = types.Tool(function_declarations=[func_decl])

        # Send request to model with function calling
        try:
            response = client.models.generate_content(
                model=cleaned_model_id,
                contents=prompt,
                config=types.GenerateContentConfig(tools=[tool])
            )
        except Exception as e:
            logger.error(f"[PDF Extractor Service] Extraction failed: {e}")
            raise

        # Extract function call results from response
        if response.function_calls:
            for fn_call in response.function_calls:
                if fn_call.name == func_decl.name:
                    extracted_data = dict(fn_call.args)
                    logger.info(f"[PDF Extractor Service] Extraction successful: {len(extracted_data)} fields extracted")
                    return {
                        'success': True,
                        'template_type': template_type,
                        'template_name': template_config['name'],
                        'data': extracted_data,
                        'raw_text': extracted_text[:500] + '...' if len(extracted_text) > 500 else extracted_text
                    }

        # No function call was made
        logger.warning(f"[PDF Extractor Service] Model did not return structured data")
        return {
            'success': False,
            'error': 'Model did not return structured data',
            'model_response': response.text if response.text else 'No response',
            'raw_text': extracted_text[:500] + '...' if len(extracted_text) > 500 else extracted_text
        }

    async def extract_pdf_data(
        self,
        prompt: str,
        model: str,
        reference_images: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        统一的 PDF 数据提取接口 - 处理 PDF 数据提取和下载
        
        Args:
            prompt: Extraction instructions (used as additional_instructions)
            model: Model identifier (required)
            reference_images: Reference images dict (should contain 'pdf_bytes' or 'pdf_url')
            **kwargs: Additional parameters:
                - template_type: Template type ('invoice', 'form', 'receipt', 'contract', 'full-text')
                - pdf_bytes: PDF file content as bytes (alternative to reference_images)
                - pdf_url: PDF file URL (alternative to reference_images)
                - additional_instructions: Optional additional extraction instructions
        
        Returns:
            Dictionary containing extracted structured data
        """
        # 获取 PDF 数据
        pdf_bytes = None
        if reference_images:
            pdf_bytes = reference_images.get("pdf_bytes")
            if not pdf_bytes:
                # 如果有 URL，需要下载
                pdf_url = reference_images.get("pdf_url")
                if pdf_url:
                    import httpx
                    async with httpx.AsyncClient() as client:
                        response = await client.get(pdf_url)
                        response.raise_for_status()
                        pdf_bytes = response.content
        
        # 从 kwargs 中获取（兼容旧接口）
        if not pdf_bytes:
            pdf_bytes = kwargs.get("pdf_bytes")
        
        if not pdf_bytes:
            raise ValueError("extract_pdf_data requires 'pdf_bytes' in reference_images or kwargs")
        
        template_type = kwargs.get("template_type", "full-text")
        additional_instructions = kwargs.get("additional_instructions", prompt)

        logger.info(f"[PDF Extractor Service] PDF extraction: template={template_type}, model={model}")
        return await self.extract_structured_data(pdf_bytes, template_type, model, additional_instructions)
    
    def get_available_templates(self) -> List[Dict[str, str]]:
        """
        Get list of available extraction templates.

        Returns:
            List of template configurations
        """
        logger.info(f"[PDF Extractor Service] Retrieving templates: {len(EXTRACTION_TEMPLATES)} available")
        return [
            {
                'id': template_id,
                'name': config['name'],
                'description': config['description'],
                'icon': config['icon']
            }
            for template_id, config in EXTRACTION_TEMPLATES.items()
        ]


# ============================================================================
# Backward compatibility functions (for main.py)
# ============================================================================

async def extract_structured_data_from_pdf(
    pdf_bytes: bytes,
    template_type: str,
    api_key: str,
    model_id: str,
    additional_instructions: str = ""
) -> Dict[str, Any]:
    """
    Backward compatibility wrapper for main.py.

    This function maintains the old interface while using the new service architecture.
    """
    from ..client_pool import get_client_pool
    pool = get_client_pool()
    service = PDFExtractorService(client_factory=lambda: pool.get_client(api_key=api_key))
    return await service.extract_structured_data(
        pdf_bytes=pdf_bytes,
        template_type=template_type,
        model_id=model_id,
        additional_instructions=additional_instructions
    )


def get_available_templates() -> List[Dict[str, str]]:
    """
    Backward compatibility wrapper for main.py.

    This function maintains the old interface while using the new service architecture.
    """
    # This is a static method, so we don't need to instantiate the service
    return [
        {
            'id': template_id,
            'name': config['name'],
            'description': config['description'],
            'icon': config['icon']
        }
        for template_id, config in EXTRACTION_TEMPLATES.items()
    ]
