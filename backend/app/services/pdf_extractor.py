"""
PDF Structured Data Extraction Module

This module provides functionality to extract structured data from PDF documents
using Gemini's function calling capabilities.
"""

from typing import Dict, Any, List, Optional
import json
import time
import pypdf
import google.generativeai as genai
import google.ai.generativelanguage as glm


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
extract_invoice_data_tool = glm.FunctionDeclaration(
    name='extract_invoice_data',
    description='Extracts structured information from an invoice document.',
    parameters=glm.Schema(
        type=glm.Type.OBJECT,
        properties={
            'invoice_number': glm.Schema(type=glm.Type.STRING, description='The unique invoice number.'),
            'vendor_name': glm.Schema(type=glm.Type.STRING, description='The name of the vendor or supplier.'),
            'vendor_address': glm.Schema(type=glm.Type.STRING, description='The address of the vendor or supplier.'),
            'customer_name': glm.Schema(type=glm.Type.STRING, description='The name of the customer or recipient.'),
            'customer_address': glm.Schema(type=glm.Type.STRING, description='The address of the customer or recipient.'),
            'issue_date': glm.Schema(type=glm.Type.STRING, description='The date the invoice was issued (e.g., YYYY-MM-DD).'),
            'due_date': glm.Schema(type=glm.Type.STRING, description='The date the invoice is due (e.g., YYYY-MM-DD).'),
            'total_amount': glm.Schema(type=glm.Type.NUMBER, description='The total amount of the invoice, including tax.'),
            'currency': glm.Schema(type=glm.Type.STRING, description='The currency of the total amount (e.g., USD, EUR, CNY).'),
            'tax_amount': glm.Schema(type=glm.Type.NUMBER, description='The total tax amount on the invoice.'),
            'subtotal_amount': glm.Schema(type=glm.Type.NUMBER, description='The subtotal amount before tax.'),
            'items': glm.Schema(
                type=glm.Type.ARRAY,
                items=glm.Schema(
                    type=glm.Type.OBJECT,
                    properties={
                        'description': glm.Schema(type=glm.Type.STRING, description='Description of the item.'),
                        'quantity': glm.Schema(type=glm.Type.NUMBER, description='Quantity of the item.'),
                        'unit_price': glm.Schema(type=glm.Type.NUMBER, description='Unit price of the item.'),
                        'line_total': glm.Schema(type=glm.Type.NUMBER, description='Total for the item line.')
                    },
                    required=['description', 'quantity', 'unit_price', 'line_total']
                ),
                description='List of line items on the invoice.'
            )
        },
        required=['invoice_number', 'vendor_name', 'total_amount', 'issue_date', 'currency']
    )
)

# Generic Form Data Extraction Schema
extract_form_data_tool = glm.FunctionDeclaration(
    name='extract_form_data',
    description='Extracts structured information from a generic form.',
    parameters=glm.Schema(
        type=glm.Type.OBJECT,
        properties={
            'name': glm.Schema(type=glm.Type.STRING, description='Full name provided in the form.'),
            'email': glm.Schema(type=glm.Type.STRING, description='Email address provided.'),
            'phone_number': glm.Schema(type=glm.Type.STRING, description='Phone number provided.'),
            'address': glm.Schema(type=glm.Type.STRING, description='Full mailing address.'),
            'company': glm.Schema(type=glm.Type.STRING, description='Company name.'),
            'job_title': glm.Schema(type=glm.Type.STRING, description='Job title or position.'),
            'message': glm.Schema(type=glm.Type.STRING, description='Any message or comments from the form.')
        },
        required=['name']
    )
)

# Receipt Data Extraction Schema
extract_receipt_data_tool = glm.FunctionDeclaration(
    name='extract_receipt_data',
    description='Extracts structured information from a receipt.',
    parameters=glm.Schema(
        type=glm.Type.OBJECT,
        properties={
            'merchant_name': glm.Schema(type=glm.Type.STRING, description='Name of the merchant or store.'),
            'merchant_address': glm.Schema(type=glm.Type.STRING, description='Address of the merchant.'),
            'date': glm.Schema(type=glm.Type.STRING, description='Date of the transaction.'),
            'time': glm.Schema(type=glm.Type.STRING, description='Time of the transaction.'),
            'total_amount': glm.Schema(type=glm.Type.NUMBER, description='Total amount paid.'),
            'currency': glm.Schema(type=glm.Type.STRING, description='Currency of the transaction.'),
            'tax_amount': glm.Schema(type=glm.Type.NUMBER, description='Tax amount.'),
            'payment_method': glm.Schema(type=glm.Type.STRING, description='Payment method used (cash, card, etc.).'),
            'items': glm.Schema(
                type=glm.Type.ARRAY,
                items=glm.Schema(
                    type=glm.Type.OBJECT,
                    properties={
                        'name': glm.Schema(type=glm.Type.STRING, description='Item name.'),
                        'quantity': glm.Schema(type=glm.Type.NUMBER, description='Item quantity.'),
                        'price': glm.Schema(type=glm.Type.NUMBER, description='Item price.')
                    }
                ),
                description='List of purchased items.'
            )
        },
        required=['merchant_name', 'total_amount']
    )
)

# Contract Data Extraction Schema
extract_contract_data_tool = glm.FunctionDeclaration(
    name='extract_contract_data',
    description='Extracts structured information from a contract or agreement.',
    parameters=glm.Schema(
        type=glm.Type.OBJECT,
        properties={
            'contract_title': glm.Schema(type=glm.Type.STRING, description='Title or name of the contract.'),
            'contract_number': glm.Schema(type=glm.Type.STRING, description='Contract number or reference ID.'),
            'party_a_name': glm.Schema(type=glm.Type.STRING, description='Name of first party.'),
            'party_b_name': glm.Schema(type=glm.Type.STRING, description='Name of second party.'),
            'effective_date': glm.Schema(type=glm.Type.STRING, description='Date when contract becomes effective.'),
            'expiration_date': glm.Schema(type=glm.Type.STRING, description='Date when contract expires.'),
            'contract_value': glm.Schema(type=glm.Type.NUMBER, description='Total value of the contract.'),
            'currency': glm.Schema(type=glm.Type.STRING, description='Currency of the contract value.'),
            'key_terms': glm.Schema(
                type=glm.Type.ARRAY,
                items=glm.Schema(type=glm.Type.STRING),
                description='List of key terms and conditions.'
            )
        },
        required=['party_a_name', 'party_b_name']
    )
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
# Main Extraction Function
# ============================================================================

async def extract_structured_data_from_pdf(
    pdf_bytes: bytes,
    template_type: str,
    api_key: str,
    model_id: str,
    additional_instructions: str = ""
) -> Dict[str, Any]:
    """
    Extract structured data from a PDF using Gemini function calling.

    Args:
        pdf_bytes: PDF file content as bytes
        template_type: Type of template to use ('invoice', 'form', 'receipt', 'contract')
        api_key: Google AI API key
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

    # 打印函数入口信息
    print(f"[PDF Extractor] ========== 提取函数调用 ==========")
    print(f"[PDF Extractor] 接收到的参数:")
    print(f"  - model_id: '{model_id}'")
    print(f"  - model_id类型: {type(model_id).__name__}")
    print(f"  - template_type: '{template_type}'")
    
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

    print(f"[PDF Extractor] 模型ID清理:")
    print(f"  - 原始: '{model_id}'")
    print(f"  - 清理后: '{cleaned_model_id}'")

    # Extract text from PDF (used by all modes)
    extracted_text = extract_text_from_pdf(pdf_bytes)

    if not extracted_text.strip():
        raise ValueError("No text could be extracted from the PDF")

    template_config = EXTRACTION_TEMPLATES[template_type]

    # --- Full-text / Markdown mode: return raw text directly, no LLM round-trip ---
    if template_type == 'full-text':
        # Simple cleanup: collapse excessive blank lines
        cleaned = "\n".join([line.rstrip() for line in extracted_text.splitlines()])
        cleaned = "\n\n".join([blk.strip() for blk in cleaned.split("\n\n") if blk.strip()])

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
    tool = template_config['tool']

    # Configure Gemini
    genai.configure(api_key=api_key)

    # Initialize model with function calling - use provided model ID
    print(f"[PDF Extractor] 准备初始化GenerativeModel")
    print(f"  - 将使用的model_name: '{cleaned_model_id}'")
    
    try:
        model = genai.GenerativeModel(
            model_name=cleaned_model_id,
            tools=[tool]
        )
        print(f"[PDF Extractor] ✓ GenerativeModel初始化成功")
        print(f"[PDF Extractor] ==========================================")
    except Exception as model_err:
        print(f"[PDF Extractor] ✗ GenerativeModel初始化失败!")
        print(f"  - 错误: {str(model_err)}")
        print(f"  - 使用的model_id: '{cleaned_model_id}'")
        print(f"[PDF Extractor] ==========================================")
        raise

    # Create chat session (enable auto function calling to simplify parsing)
    chat = model.start_chat(enable_automatic_function_calling=True)

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

    # Send message to model
    response = chat.send_message(prompt)

    # --- Extract function call results (compatible with old/new SDK) ---
    # Newer SDK: function calls live in candidates[].content.parts[].function_call
    # Older SDK: response.tool_calls is populated.
    def iter_function_calls(resp):
        # Old style
        if getattr(resp, "tool_calls", None):
            for tc in resp.tool_calls:
                yield tc.function
        # New style (GenerateContentResponse)
        if getattr(resp, "candidates", None):
            for cand in resp.candidates:
                if not getattr(cand, "content", None):
                    continue
                parts = getattr(cand.content, "parts", []) or []
                for part in parts:
                    fc = getattr(part, "function_call", None)
                    if fc:
                        yield fc

    for fn_call in iter_function_calls(response):
        if fn_call.name == tool.name:
            extracted_data = dict(fn_call.args)
            return {
                'success': True,
                'template_type': template_type,
                'template_name': template_config['name'],
                'data': extracted_data,
                'raw_text': extracted_text[:500] + '...' if len(extracted_text) > 500 else extracted_text
            }

    # No function call was made
    return {
        'success': False,
        'error': 'Model did not return structured data',
        'model_response': getattr(response, "text", None) or 'No response',
        'raw_text': extracted_text[:500] + '...' if len(extracted_text) > 500 else extracted_text
    }


def get_available_templates() -> List[Dict[str, str]]:
    """
    Get list of available extraction templates.

    Returns:
        List of template configurations
    """
    return [
        {
            'id': template_id,
            'name': config['name'],
            'description': config['description'],
            'icon': config['icon']
        }
        for template_id, config in EXTRACTION_TEMPLATES.items()
    ]
