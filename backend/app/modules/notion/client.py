import re
from typing import Any

from notion_client import AsyncClient


class NotionClientWrapper:
    def __init__(self, api_key: str, notion_url: str | None = None):
        kwargs: dict[str, Any] = {"auth": api_key}
        if notion_url:
            kwargs["base_url"] = notion_url
        self.client = AsyncClient(**kwargs)

    async def validate_key(self) -> str:
        """Verify the API key works by calling /v1/users/me.

        Returns the workspace name (bot name) from the response.
        """
        response = await self.client.users.me()
        bot = response.get("bot", {})
        if isinstance(bot, dict):
            owner = bot.get("owner", {})
            if isinstance(owner, dict):
                workspace = owner.get("workspace_name")
                if workspace:
                    return workspace
        return bot.get("name", "Notion Workspace") if isinstance(bot, dict) else "Notion"

    async def search(self, query: str = "") -> list[dict]:
        """Search pages and databases in Notion."""
        response = await self.client.search(query=query)
        results = []
        for item in response.get("results", []):
            title = self._extract_title(item)
            results.append(
                {
                    "id": item["id"],
                    "title": title,
                    "object": item["object"],
                }
            )
        return results

    async def create_page(
        self,
        parent_page_id: str,
        title: str,
        content_markdown: str,
    ) -> str:
        """Create a page with markdown content. Returns page_id."""
        blocks = self._md_to_notion_blocks(content_markdown)
        response = await self.client.pages.create(
            parent={"page_id": parent_page_id},
            properties={
                "title": {"title": [{"text": {"content": title}}]}
            },
            children=blocks[:100] if blocks else [],
        )
        page_id = response["id"]
        for i in range(100, len(blocks), 100):
            await self.client.blocks.children.append(
                block_id=page_id,
                children=blocks[i : i + 100],
            )
        return page_id

    async def update_page(self, page_id: str, content_markdown: str) -> None:
        """Replace all content of an existing page."""
        existing = await self.client.blocks.children.list(block_id=page_id)
        for block in existing.get("results", []):
            await self.client.blocks.delete(block_id=block["id"])

        blocks = self._md_to_notion_blocks(content_markdown)
        for i in range(0, len(blocks), 100):
            await self.client.blocks.children.append(
                block_id=page_id,
                children=blocks[i : i + 100],
            )

    def _extract_title(self, item: dict) -> str:
        if item["object"] == "database":
            title_field = item.get("title", [])
        else:
            props = item.get("properties", {})
            title_field = props.get("title", {}).get("title", [])
        if not title_field:
            return "(sin título)"
        return "".join(t.get("plain_text", "") for t in title_field)

    # ------------------------------------------------------------------
    # Markdown -> Notion blocks converter
    # ------------------------------------------------------------------

    def _md_to_notion_blocks(self, md: str) -> list[dict]:
        """Convert Markdown to a list of Notion block objects.

        Supports: headers, bold/italic, paragraphs, tables, blockquotes
        (callouts), fenced code blocks, and bullet / numbered lists.
        """
        lines = md.split("\n")
        blocks: list[dict] = []
        i = 0
        n = len(lines)

        while i < n:
            line = lines[i]

            # Code blocks
            if line.strip().startswith("```"):
                lang = line.strip()[3:].strip()
                code_lines = []
                i += 1
                while i < n and not lines[i].strip().startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                i += 1  # skip closing fence
                blocks.append(
                    {
                        "type": "code",
                        "code": {
                            "rich_text": [
                                {"type": "text", "text": {"content": "\n".join(code_lines)}}
                            ],
                            "language": lang or "plain text",
                        },
                    }
                )
                continue

            # Tables
            if line.strip().startswith("|") and i + 1 < n and re.match(
                r"^\s*\|?[\s:|-]+\|?\s*$", lines[i + 1]
            ):
                table_rows = []
                while i < n and lines[i].strip().startswith("|"):
                    cells = self._parse_table_row(lines[i])
                    table_rows.append(cells)
                    i += 1
                # first row is header, skip separator row
                header = table_rows[0]
                body = table_rows[2:] if len(table_rows) >= 3 else table_rows[1:]
                children = []
                for r in [header] + body:
                    row_cells = [
                        self._rich_text(self._clean_inline(c))
                        for c in r
                    ]
                    children.append(
                        {
                            "type": "table_row",
                            "table_row": {"cells": row_cells},
                        }
                    )
                blocks.append(
                    {
                        "type": "table",
                        "table": {
                            "table_width": len(header),
                            "has_column_header": True,
                            "has_row_header": False,
                            "children": children,
                        },
                    }
                )
                continue

            # Headers
            if line.startswith("### "):
                blocks.append(self._heading("heading_3", line[4:]))
                i += 1
                continue
            if line.startswith("## "):
                blocks.append(self._heading("heading_2", line[3:]))
                i += 1
                continue
            if line.startswith("# "):
                blocks.append(self._heading("heading_1", line[2:]))
                i += 1
                continue

            # Blockquote -> callout
            if line.strip().startswith(">"):
                quote_text = line.strip()[1:].strip()
                blocks.append(self._callout(quote_text))
                i += 1
                continue

            # Bullet list
            if re.match(r"^\s*[-*]\s+", line):
                items = []
                while i < n and re.match(r"^\s*[-*]\s+", lines[i]):
                    items.append(self._clean_inline(re.sub(r"^\s*[-*]\s+", "", lines[i])))
                    i += 1
                for it in items:
                    blocks.append(
                        {
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {"rich_text": self._rich_text(it)},
                        }
                    )
                continue

            # Numbered list
            if re.match(r"^\s*\d+\.\s+", line):
                items = []
                while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                    items.append(self._clean_inline(re.sub(r"^\s*\d+\.\s+", "", lines[i])))
                    i += 1
                for it in items:
                    blocks.append(
                        {
                            "type": "numbered_list_item",
                            "numbered_list_item": {"rich_text": self._rich_text(it)},
                        }
                    )
                continue

            # Empty line
            if not line.strip():
                i += 1
                continue

            # Paragraph
            blocks.append(
                {
                    "type": "paragraph",
                    "paragraph": {"rich_text": self._rich_text(self._clean_inline(line))},
                }
            )
            i += 1

        return blocks

    def _heading(self, block_type: str, text: str) -> dict:
        return {
            "type": block_type,
            block_type: {
                "rich_text": self._rich_text(self._clean_inline(text)),
            },
        }

    def _callout(self, text: str) -> dict:
        return {
            "type": "callout",
            "callout": {
                "rich_text": self._rich_text(self._clean_inline(text)),
                "icon": {"type": "emoji", "emoji": "💡"},
            },
        }

    def _rich_text(self, text: str) -> list[dict]:
        """Build a list of rich_text objects with bold/italic annotations."""
        return self._parse_inline(text)

    def _parse_inline(self, text: str) -> list[dict]:
        """Parse inline **bold** and *italic* into Notion rich_text segments."""
        segments: list[dict] = []
        pattern = re.compile(r"(\*\*([^*]+)\*\*|\*([^*]+)\*|_([^_]+)_)")
        last = 0
        for m in pattern.finditer(text):
            if m.start() > last:
                segments.append(self._text_segment(text[last : m.start()]))
            if m.group(2) is not None:  # **bold**
                segments.append(self._text_segment(m.group(2), bold=True))
            elif m.group(3) is not None:  # *italic*
                segments.append(self._text_segment(m.group(3), italic=True))
            elif m.group(4) is not None:  # _italic_
                segments.append(self._text_segment(m.group(4), italic=True))
            last = m.end()
        if last < len(text):
            segments.append(self._text_segment(text[last:]))
        return segments or [self._text_segment("")]

    @staticmethod
    def _text_segment(content: str, bold: bool = False, italic: bool = False) -> dict:
        annotation = {}
        if bold:
            annotation["bold"] = True
        if italic:
            annotation["italic"] = True
        return {
            "type": "text",
            "text": {"content": content},
            "annotations": annotation,
        }

    @staticmethod
    def _clean_inline(text: str) -> str:
        """Strip accidental markdown chars that Notion doesn't render."""
        text = text.replace("**", "").replace("*", "").replace("_", "")
        return text.strip()

    @staticmethod
    def _parse_table_row(line: str) -> list[str]:
        line = line.strip().strip("|")
        return [c.strip() for c in line.split("|")]
