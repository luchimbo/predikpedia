"""Bounded, key-free web search and public document reading; never executes page code."""

from datetime import date
from io import BytesIO
import hashlib
import ipaddress
import re
import socket
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from app.domain.research_models import ResearchDocument, fingerprint


def normalize_url(url):
    parts = urlsplit(str(url).strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("Usá un enlace público HTTP o HTTPS, sin credenciales.")
    if parts.port not in {None, 80, 443}:
        raise ValueError("El enlace no corresponde a un sitio web público.")
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", urlencode(query), ""))


def validate_public_url(url):
    url = normalize_url(url)
    host = urlsplit(url).hostname
    addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError("Solo se pueden leer sitios públicos de internet.")
    return url


class PublicSearch:
    def __init__(self, timeout=15):
        self.timeout = timeout

    def search(self, query, max_results=5):
        from ddgs import DDGS
        for backend in ("duckduckgo", "bing"):
            try:
                result = DDGS(timeout=self.timeout).text(query, backend=backend, max_results=max_results)
                if result:
                    return result
            except Exception:
                continue
        raise ValueError("Los buscadores no respondieron. Podés reintentar o agregar enlaces.")

    def _download(self, url):
        import httpx
        with httpx.Client(timeout=self.timeout, trust_env=False, follow_redirects=False,
                          headers={"User-Agent": "PredikpediaResearch/1.0"}) as client:
            for _ in range(5):
                url = validate_public_url(url)
                with client.stream("GET", url) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        url = urljoin(url, response.headers.get("location", ""))
                        continue
                    response.raise_for_status()
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 5 * 1024 * 1024:
                            raise ValueError("El documento supera el límite de 5 MB.")
                        chunks.append(chunk)
                    return url, response.headers.get("content-type", ""), b"".join(chunks)
        raise ValueError("El sitio redirigió demasiadas veces.")

    def read(self, url):
        clean = normalize_url(url)
        try:
            final_url, content_type, body = self._download(clean)
            published = ""
            if body.startswith(b"%PDF") or "application/pdf" in content_type:
                from pypdf import PdfReader
                pdf = PdfReader(BytesIO(body))
                if pdf.is_encrypted:
                    raise ValueError("El PDF está protegido.")
                if len(pdf.pages) > 100:
                    raise ValueError("El PDF supera 100 páginas; agregá un documento más específico.")
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                title = str((pdf.metadata or {}).get("/Title") or final_url)
            elif "html" in content_type or content_type.startswith("text/"):
                import trafilatura
                text = trafilatura.extract(body, include_tables=True, include_comments=False) or ""
                metadata = trafilatura.extract_metadata(body, default_url=final_url)
                title = (metadata.title if metadata else "") or final_url
                published = (metadata.date if metadata else "") or ""
                if published:
                    try:
                        date.fromisoformat(published[:10])
                        published = published[:10]
                    except ValueError:
                        published = ""
            else:
                raise ValueError("El enlace no contiene HTML ni un PDF con texto.")
            if len(text.strip()) < 80:
                raise ValueError("No se pudo leer texto suficiente. El documento puede requerir login, JavaScript u OCR.")
            if len(text) > 150000:
                raise ValueError("El texto supera el límite de lectura; agregá un documento más específico.")
            digest = hashlib.sha256(re.sub(r"\s+", " ", text).strip().encode()).hexdigest()
            return ResearchDocument(id=fingerprint([final_url, digest]), url=final_url, title=title[:300],
                                    text=text, status="read", published_at=published, content_hash=digest)
        except Exception as exc:
            # Do not record response bodies, credentials, or exception strings from remote pages.
            message = str(exc) if isinstance(exc, ValueError) else "No se pudo acceder al documento."
            return ResearchDocument(id=fingerprint([clean, "unusable"]), url=clean, error=message)
