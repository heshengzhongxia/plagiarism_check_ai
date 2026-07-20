"""
文件解析服务：支持 PDF / Word / TXT 格式的文本提取
"""
import os


def extract_text_from_pdf(filepath):
    """从PDF文件提取文本"""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        raise ValueError(f"PDF解析失败: {e}")


def extract_text_from_docx(filepath):
    """从Word文件提取文本"""
    try:
        from docx import Document
        doc = Document(filepath)
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return text.strip()
    except Exception as e:
        raise ValueError(f"Word解析失败: {e}")


def extract_text(filepath, filename):
    """根据文件扩展名自动选择解析方式"""
    ext = os.path.splitext(filename)[1].lower()
    if ext == '.pdf':
        return extract_text_from_pdf(filepath)
    elif ext in ('.docx', '.doc'):
        return extract_text_from_docx(filepath)
    elif ext == '.txt':
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read().strip()
    else:
        raise ValueError(f"不支持的文件格式: {ext}，请上传 PDF / Word / TXT 文件")
