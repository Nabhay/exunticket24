from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

SERVICE_ACCOUNT_FILE = 'creds.json'

SCOPES = ['https://www.googleapis.com/auth/drive.readonly', 
          'https://www.googleapis.com/auth/documents.readonly',
          'https://www.googleapis.com/auth/spreadsheets.readonly']

# Authenticate with service account
credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=credentials)
docs_service = build('docs', 'v1', credentials=credentials)
sheets_service = build('sheets', 'v4', credentials=credentials)

# List all Google Docs and Sheets in a folder
def list_google_docs_and_sheets_in_folder(service, folder_id):
    try:
        query = f"'{folder_id}' in parents and (mimeType='application/vnd.google-apps.document' or mimeType='application/vnd.google-apps.spreadsheet')"
        results = service.files().list(
            q=query,
            pageSize=100,
            fields="nextPageToken, files(id, name, mimeType)"
        ).execute()
        items = results.get('files', [])
        return items
    except Exception as e:
        return []

# Get content of Google Doc and convert it to Markdown
def get_google_doc_content(doc_id, docs_service):
    try:
        document = docs_service.documents().get(documentId=doc_id).execute()
        return document
    except Exception as e:
        return {}

# Convert Google Doc to markdown
def convert_to_markdown(doc_content):
    markdown = ''
    if not doc_content:
        return markdown
    
    for element in doc_content.get('body', {}).get('content', []):
        if 'paragraph' in element:
            markdown += convert_paragraph_to_markdown(element['paragraph'])
        elif 'table' in element:
            markdown += convert_table_to_markdown(element['table']) + '\n'
    
    return markdown

def convert_table_to_markdown(table):
    markdown = ""
    rows = table['tableRows']
    
    # Extract table content and convert to Markdown
    for row_idx, row in enumerate(rows):
        row_data = []
        for cell in row['tableCells']:
            cell_content = ''
            for content in cell['content']:
                if 'paragraph' in content:
                    for element in content['paragraph']['elements']:
                        if 'textRun' in element:
                            cell_content += convert_text_run_to_markdown(element['textRun'])
            row_data.append(cell_content)
        
        # Add table row to markdown
        markdown += "| " + " | ".join(row_data) + " |\n"
        
        # Add header separator after the first row
        if row_idx == 0:
            markdown += "| " + " | ".join(['---'] * len(row_data)) + " |\n"
    
    return markdown

def convert_text_run_to_markdown(text_run):
    text = text_run['content']
    text_style = text_run.get('textStyle', {})
    
    # Apply bold
    if text_style.get('bold'):
        text = f"**{text.strip()}**"
    
    # Apply italics
    if text_style.get('italic'):
        text = f"*{text.strip()}*"
    
    # Apply underline (note: Markdown doesn't natively support underlines)
    if text_style.get('underline'):
        text = f"_{text.strip()}_"
    
    # Apply strikethrough
    if text_style.get('strikethrough'):
        text = f"~~{text.strip()}~~"
    
    # Apply links
    if 'link' in text_style:
        link_url = text_style['link'].get('url', '')
        text = f"[{text.strip()}]({link_url})"
    
    return text


def convert_paragraph_to_markdown(paragraph):
    markdown = ''
    
    # Handle headings by checking paragraph style
    if 'paragraphStyle' in paragraph:
        heading = paragraph['paragraphStyle'].get('namedStyleType', '')
        if heading == 'HEADING_1':
            markdown += "# "
        elif heading == 'HEADING_2':
            markdown += "## "
        elif heading == 'HEADING_3':
            markdown += "### "
        elif heading == 'HEADING_4':
            markdown += "#### "
        elif heading == 'HEADING_5':
            markdown += "##### "
        elif heading == 'HEADING_6':
            markdown += "###### "
    
    # Handle lists (ordered/unordered)
    if 'bullet' in paragraph:
        bullet = paragraph['bullet']
        if 'listId' in bullet:
            # Indent levels determine if it's an unordered or ordered list
            indent_level = bullet.get('nestingLevel', 0)
            marker = "-" if indent_level == 0 else "1."
            markdown += " " * (indent_level * 2) + f"{marker} "
    # Convert text elements inside the paragraph
    for element in paragraph['elements']:
        if 'textRun' in element:
            markdown += convert_text_run_to_markdown(element['textRun'])
    markdown += '\n\n'
    return markdown

# Get content of Google Sheet and return JSON
def get_google_sheet_content(sheet_id, sheets_service):
    try:
        sheet = sheets_service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        return sheet
    except Exception as e:
        return {}

# Main function to process all Google Docs and Sheets in the folder
def process_docs_and_sheets_in_folder(folder_id):
    data = ''
    files = list_google_docs_and_sheets_in_folder(drive_service, folder_id)
    
    for file in files:
        file_id = file['id']
        file_name = file['name']
        file_type = file['mimeType']
        
        # Process Google Docs
        if file_type == 'application/vnd.google-apps.document':
            doc_content = get_google_doc_content(file_id, docs_service)
            if doc_content:
                markdown_content = convert_to_markdown(doc_content)
                data += markdown_content + '\n'
        
        # Process Google Sheets
        elif file_type == 'application/vnd.google-apps.spreadsheet':
            sheet_content = get_google_sheet_content(file_id, sheets_service)
            if sheet_content:
                data += str(sheet_content) + '\n'
    
    return data