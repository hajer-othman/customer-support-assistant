"""Lecture et découpage des documents de politique en chunks.

Un chunk = une section `##` d'un fichier. Les fichiers sont nommés `sujet.langue.md`
(par exemple `returns.fr.md`) et rangés dans `backend/data/policies/`.
"""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

# backend/app/rag/chunking.py -> parents[2] = backend/
POLICIES_DIR = Path(__file__).resolve().parents[2] / "data" / "policies"
LANGUAGES = {"fr", "en"}


@dataclass(frozen=True)
class Chunk:
    document_name: str
    language: str
    section_title: str
    content: str  # le texte de la section, sans en-tête (affiché et envoyé à la génération)
    embedding_text: str  # en-tête + texte : c'est lui qui est vectorisé
    content_hash: str  # empreinte de embedding_text

    @property
    def key(self) -> tuple[str, str, str]:
        """Identifiant d'un chunk : correspond à la contrainte d'unicité de la table."""
        return (self.document_name, self.language, self.section_title)


def build_embedding_text(
    document_name: str, language: str, section_title: str, content: str
) -> str:
    """Ajoute l'en-tête (document, langue, section) avant le texte de la section."""
    return f"Document: {document_name} ({language})\nSection: {section_title}\n\n{content}"


def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_filename(path: Path) -> tuple[str, str]:
    """`returns.fr.md` -> ("returns", "fr")."""
    document_name, _, language = path.stem.rpartition(".")
    if not document_name or language not in LANGUAGES:
        raise ValueError(f"Nom de fichier invalide : {path.name} (attendu : sujet.fr.md ou sujet.en.md)")
    return document_name, language


def split_sections(text: str) -> list[tuple[str, str]]:
    """Découpe un fichier en sections `##` : renvoie une liste de (titre, contenu).

    Le titre `#` du début du fichier n'est pas une section : il est ignoré.
    """
    sections = []
    for part in re.split(r"^## ", text, flags=re.MULTILINE)[1:]:
        title, _, body = part.partition("\n")
        sections.append((title.strip(), body.strip()))
    return sections


def load_chunks(policies_dir: Path = POLICIES_DIR) -> list[Chunk]:
    """Lit tous les fichiers `*.md` du dossier et renvoie la liste des chunks."""
    chunks: list[Chunk] = []
    seen: set[tuple[str, str, str]] = set()

    for path in sorted(policies_dir.glob("*.md")):
        document_name, language = parse_filename(path)
        # read_text convertit les fins de ligne Windows (CRLF) en \n : l'empreinte reste stable
        text = path.read_text(encoding="utf-8")

        for title, content in split_sections(text):
            if not title or not content:
                raise ValueError(f"Section vide ou sans titre dans {path.name} : {title!r}")
            embedding_text = build_embedding_text(document_name, language, title, content)
            chunk = Chunk(
                document_name=document_name,
                language=language,
                section_title=title,
                content=content,
                embedding_text=embedding_text,
                content_hash=compute_hash(embedding_text),
            )
            if chunk.key in seen:
                raise ValueError(f"Titre de section en double dans {path.name} : {title!r}")
            seen.add(chunk.key)
            chunks.append(chunk)

    return chunks