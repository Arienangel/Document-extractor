import base64
import logging
import mimetypes
import tempfile
from io import BytesIO, StringIO
from pathlib import Path

import panflute as pf
import pypandoc
from fastapi import FastAPI, Header, Request, status
from fastapi.responses import PlainTextResponse
from markitdown import MarkItDown
from openai import OpenAI
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()
llm_base_url = "http://127.0.0.1:11434/v1"
llm_api_key = "sk-"
llm_model = "qwen3-vl-4B-Instruct-UD-Q4_K_XL"
with open("prompt.md", "r", encoding="utf-8") as f:
    llm_prompt = f.read()


class Markitdoen_extractor:

    def __init__(self, file_bytes: bytes, file_ext: str):
        self.client = MarkItDown(enable_plugins=True,
                                 llm_client=OpenAI(base_url=llm_base_url, api_key=llm_api_key),
                                 llm_model=llm_model,
                                 llm_prompt=llm_prompt)
        self.file_bytes = file_bytes
        self.file_ext = file_ext

    def convert_to_markdown(self) -> str:
        return self.client.convert_stream(BytesIO(self.file_bytes), file_extension=self.file_ext).markdown


class Pandoc_extractor:

    def __init__(self, file_bytes: bytes, file_ext: str):
        self.client = OpenAI(base_url=llm_base_url, api_key=llm_api_key)
        self.file_bytes = file_bytes
        self.file_ext = file_ext

    def convert_to_markdown(self) -> str:
        with tempfile.TemporaryDirectory() as media_dir:
            ast_string = pypandoc.convert_text(self.file_bytes, "json", format=self.file_ext, extra_args=[f"--extract-media={Path(media_dir)}"])
            input_stream = StringIO(ast_string)
            doc = pf.load(input_stream)
            altered_doc = doc.walk(self.get_image_description)
            output_stream = StringIO()
            pf.dump(altered_doc, output_stream)
            modified_ast_string = output_stream.getvalue()
            final_markdown = pypandoc.convert_text(modified_ast_string, "markdown", format="json")
        return final_markdown

    def get_image_description(self, elem, doc):
        if isinstance(elem, pf.Image):
            try:
                buffer = BytesIO()
                with Image.open(elem.url) as img:
                    img = img.convert("RGB")
                    img.save(buffer, format="PNG")
                    base64_img = base64.b64encode(buffer.getvalue()).decode("utf-8")
                response = self.client.chat.completions.create(
                    model=llm_model,
                    messages=[{
                        "role": "user", 
                        "content": [
                            { "type": "text", "text": llm_prompt }, 
                            { "type": "image_url", "image_url": { "url": f"data:image/png;base64,{base64_img}" } }
                        ], 
                    }],
                )
                description = response.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"Error: {str(e)}")
                description = ""

            return pf.Str(description)


@app.put("/process")
async def process_document(request: Request, x_file_content_type: str = Header(None)):
    logger.info(f"Processing document: {x_file_content_type}")
    file_ext = mimetypes.guess_extension(x_file_content_type).lstrip('.')
    file_bytes = await request.body()
    try:
        if file_ext == 'pdf':
            content = Markitdoen_extractor(file_bytes, file_ext).convert_to_markdown()
        elif file_ext in ['docx', 'epub', 'html', 'latex', 'odt', 'pptx', 'rtf', 'xlsx']:
            content = Pandoc_extractor(file_bytes, file_ext).convert_to_markdown()
        else:
            content = file_bytes.decode("utf-8")
        return {"page_content": content, "metadata": {"content_type": x_file_content_type}}
    except Exception as E:
        logger.error(f"Extraction failed for {x_file_content_type}: {str(E)}")
        return PlainTextResponse(content=f"{str(E)}", status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)
