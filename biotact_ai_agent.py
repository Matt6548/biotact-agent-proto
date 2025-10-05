"""
biotact_ai_agent.py
====================

This module implements a prototype AI‑powered marketing agent for Biotact
Deutschland.  The goal of the prototype is to demonstrate how a modular
architecture can ingest reference material (brand principles, product
information and ecosystem guidelines) and automatically assemble a
content plan for a specified period.  The agent is designed with
extensibility in mind – future versions could integrate with large
language models (LLMs), image generators or bespoke analytics tools to
generate podcast scripts, AR filters or personalised email campaigns.

At the time of writing this prototype the environment does not provide
access to external APIs (e.g. OpenAI’s API) or third‑party libraries.
Consequently, the agent relies on heuristic rules to build a content
plan.  It uses a simple date scheduler, incorporates key health
awareness days from publicly available calendars and aligns each
campaign with the benefits of Biotact products.  The agent reads the
source documents that accompany the test assignment and extracts
product names and basic attributes.  If an LLM becomes available, the
``LLMClient`` class can be extended to call the model and
generate richer copy.

Usage example::

    from datetime import date
    from biotact_ai_agent import BiotactMarketingAgent

    agent = BiotactMarketingAgent('data')
    plan = agent.generate_q4_2025_plan()
    for entry in plan:
        print(entry)

The resulting plan is a list of dictionaries with keys such as
``date``, ``channel``, ``title``, ``description`` and ``target``.

Author: AI prototype for Biotact Deutschland GmbH
Date: 2025‑10‑03
"""

from __future__ import annotations

import os
import re
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple


def read_text_file(path: str) -> str:
    """Load a UTF‑8 encoded text file and return its contents.

    Parameters
    ----------
    path : str
        Absolute or relative path to the text file.

    Returns
    -------
    str
        Contents of the file as a single string.
    """
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@dataclass
class Product:
    """Representation of a single Biotact product.

    Attributes
    ----------
    name : str
        The commercial name of the product (e.g. ``DERMACOMPLEX``).
    tagline : str
        A short slogan summarising the product’s purpose.
    benefits : List[str]
        A list of bullet points highlighting the product’s advantages.
    target_groups : List[str]
        Demographic or behavioural groups for which the product is most
        appropriate (e.g. ``children 4+``, ``adults``).
    notes : str
        Additional raw text extracted from the document.
    """

    name: str
    tagline: str
    benefits: List[str] = field(default_factory=list)
    target_groups: List[str] = field(default_factory=list)
    notes: str = ""


class DocumentParser:
    """Parse Biotact reference documents and extract structured data.

    This class reads plain text files that were derived from the
    original DOCX documents (see the extraction script in the notebook).
    It includes heuristic methods to identify product names and their
    descriptive paragraphs.  The parsing logic is simple and may be
    refined in future versions.
    """

    # A product header consists of uppercase letters (Latin or Cyrillic) and
    # optional digits/spaces, must contain at least one letter to avoid
    # misinterpreting numeric dosage lines (e.g. "2000") as product names.
    PRODUCT_HEADER_RE = re.compile(r"^([A-ZА-Я][A-ZА-Я0-9 ]*)®?\s*$")

    def __init__(self, brand_path: str, products_path: str, ecosystem_path: str):
        self.brand_text = read_text_file(brand_path)
        self.products_text = read_text_file(products_path)
        self.ecosystem_text = read_text_file(ecosystem_path)

    def parse_products(self) -> Dict[str, Product]:
        """Return a mapping from product names to ``Product`` objects.

        The parser scans the products document line by line.  When it
        encounters an uppercase line ending with a registered trademark
        symbol (®) it treats this as the start of a new product.  Lines
        immediately following the header are used to populate the
        tagline and subsequent bullet points or paragraphs are grouped
        into benefits.  This strategy does not guarantee perfect
        segmentation but provides a useful starting point for the agent.
        """
        lines = self.products_text.split("\n")
        products: Dict[str, Product] = {}
        current: Optional[Product] = None
        for line in lines:
            header_match = self.PRODUCT_HEADER_RE.match(line.strip())
            if header_match and len(header_match.group(1).strip()) > 3:
                # Commit previous product
                if current is not None:
                    products[current.name] = current
                name = header_match.group(1).strip()
                current = Product(name=name, tagline="")
                continue
            if current is None:
                continue
            # If tagline not set and line contains text, use as tagline
            if not current.tagline and line.strip():
                current.tagline = line.strip()
                continue
            # Collect bullet points starting with unicode checkmarks
            if line.strip().startswith("✅") or line.strip().startswith("✔"):
                # Remove leading symbols and whitespace
                benefit = line.strip().lstrip("✅✔ ")
                if benefit:
                    current.benefits.append(benefit)
                continue
            # Identify target group patterns
            if "дет" in line.lower() or "взрос" in line.lower():
                # Rough heuristic: look for age ranges or demographic hints
                current.target_groups.append(line.strip())
            # Append all lines to notes
            current.notes += line.strip() + " "
        # Commit last product
        if current is not None:
            products[current.name] = current
        return products

    def parse_ecosystem(self) -> Dict[str, str]:
        """Extract simple facts from the media ecosystem description.

        The ecosystem document outlines internal production roles,
        marketing channels and rationale for building an in‑house studio.
        For this prototype we simply return the entire text keyed by
        section names.  Future iterations could perform finer‑grained
        extraction.
        """
        return {
            "ecosystem": self.ecosystem_text,
            "brand": self.brand_text,
            "products": self.products_text,
        }


class LLMClient:
    """Placeholder class representing a Large Language Model interface.

    In the current environment we cannot call an external LLM.  This
    class therefore exposes a ``generate`` method that accepts a
    prompt and returns a synthetic response.  If in the future a
    connection to an API becomes available, the implementation of
    ``generate`` can be replaced with a real call to OpenAI, Grok or
    another provider.  Keeping this logic behind a class boundary
    enables easy swapping of the model backend without changing the
    overall agent design.
    """

    def __init__(self):
        # Hard‑coded responses could be loaded from templates or fine tuned
        self.default_response = (
            "[LLM placeholder] Real model responses would appear here.\n"
            "This placeholder acknowledges that the prototype environment does not"
            " provide a live LLM."
        )

    def generate(self, prompt: str) -> str:
        """Return a synthetic LLM response.

        Parameters
        ----------
        prompt : str
            The user or system prompt to which the model should respond.

        Returns
        -------
        str
            A placeholder string containing the prompt for transparency.
        """
        # In a real implementation you would call openai.ChatCompletion.create
        # or similar here.  For now we simply echo the prompt.
        response = self.default_response + "\n\nPrompt excerpt:\n" + prompt[:500]
        return response


@dataclass
class ContentEntry:
    """Structure representing a single content plan entry."""

    date: date
    channel: str
    title: str
    description: str
    product: Optional[str] = None
    target: Optional[str] = None
    image_prompt: Optional[str] = None

    def to_dict(self) -> Dict[str, str]:
        """Convert the entry into a serialisable dictionary."""
        return {
            "date": self.date.isoformat(),
            "channel": self.channel,
            "title": self.title,
            "description": self.description,
            "product": self.product or "",
            "target": self.target or "",
            "image_prompt": self.image_prompt or "",
        }


class BiotactMarketingAgent:
    """High level orchestrator that builds a marketing plan.

    The agent holds references to the parsed product catalogue and brand
    principles.  It exposes methods for generating a quarter’s content
    plan, leveraging simple heuristics and the ``LLMClient`` where
    appropriate.  The plan is assembled into a list of ``ContentEntry``
    objects which can be exported to JSON or iterated over directly.
    """

    HEALTH_DAYS: Dict[str, List[Tuple[int, str]]] = {
        "October": [
            (1, "International Day of Older Persons"),
            (10, "World Mental Health Day"),
            (10, "World Sight Day"),
            (11, "World Obesity Day"),
            (16, "World Food Day"),
            (24, "World Polio Day"),
        ],
        "November": [
            (8, "World Radiology Day"),
            (14, "World Diabetes Day"),
            (18, "Start of World Antibiotic Awareness Week"),
            (25, "International Day for the Elimination of Violence Against Women"),
        ],
        "December": [
            (1, "World AIDS Day"),
            (3, "International Day of Persons with Disabilities"),
            (12, "Universal Health Coverage Day"),
        ],
    }

    CHANNELS: List[str] = [
        "Instagram", "YouTube", "Telegram", "Blog", "Podcast", "Email"
    ]

    def __init__(self, data_dir: str):
        """Initialise the agent by parsing data and instantiating dependencies.

        Parameters
        ----------
        data_dir : str
            Directory containing the extracted text files from the source
            documents.  The directory must include:
              - ``Biotact Media Ecosystem Plan.docx.txt``
              - ``Инфо о бренде 2025 (RU).docx.txt``
              - ``Инфо о продуктах 2025 (RU).docx.txt``
        """
        brand_path = os.path.join(data_dir, "Инфо о бренде 2025 (RU).docx.txt")
        products_path = os.path.join(data_dir, "Инфо о продуктах 2025 (RU).docx.txt")
        ecosystem_path = os.path.join(data_dir, "Biotact Media Ecosystem Plan.docx.txt")
        self.parser = DocumentParser(brand_path, products_path, ecosystem_path)
        self.products = self.parser.parse_products()
        self.llm = LLMClient()

    def _create_base_schedule(self, start: date, end: date) -> List[date]:
        """Generate a list of dates between ``start`` and ``end`` inclusive.

        Parameters
        ----------
        start : date
            Starting day of the schedule.
        end : date
            Last day of the schedule.

        Returns
        -------
        List[date]
            All dates in the interval [start, end].
        """
        days = []
        current = start
        while current <= end:
            days.append(current)
            current += timedelta(days=1)
        return days

    def _pick_channel(self, day: date) -> str:
        """Select an appropriate channel based on the day of the week.

        Weekends favour longer‑form content such as YouTube videos or
        podcast episodes, whereas weekdays can be used for social media
        posts, blog entries or email campaigns.  The mapping is simple
        but can be replaced by more sophisticated logic or an ML model.
        """
        weekday = day.weekday()  # 0=Monday
        if weekday >= 5:
            # Saturday or Sunday
            return "YouTube" if weekday == 5 else "Podcast"
        # Cycle through available channels on weekdays
        return self.CHANNELS[weekday % len(self.CHANNELS)]

    def _select_product_for_day(self, day: date) -> Optional[Product]:
        """Heuristically choose a product to highlight on a given day.

        The algorithm cycles through the list of products, aligning
        products with related health awareness days if possible.  For
        example, on World Sight Day the OPHTALMOCOMPLEX will be
        prioritised.  This logic is simplistic but illustrates how
        domain knowledge influences scheduling.
        """
        # Check for a matching health day
        month_name = day.strftime("%B")
        if month_name in self.HEALTH_DAYS:
            for event_day, event_name in self.HEALTH_DAYS[month_name]:
                if day.day == event_day:
                    # Match product by keyword in event name
                    if "Sight" in event_name or "Vision" in event_name:
                        return self.products.get("OPHTALMOCOMPLEX", None)
                    if "Mental" in event_name:
                        return self.products.get("NEUROCOMPLEX", None)
                    if "Food" in event_name:
                        return self.products.get("DERMACOMPLEX", None)
                    if "Diabetes" in event_name:
                        return self.products.get("GLUCOCOMPLEX", None)
                    # fallback: choose any product
                    break
        # Cycle through products by date
        names = sorted(self.products.keys())
        if not names:
            return None
        index = (day.toordinal()) % len(names)
        return self.products[names[index]]

    def _compose_title_and_description(self, prod: Product, day: date, channel: str, event: Optional[str]) -> Tuple[str, str, str]:
        """Create a title, description and image prompt for a content entry.

        The message draws upon the product’s tagline and benefits.  If a
        health awareness event is associated with the date, the title
        will reference it to improve relevance.  For longer‐form
        channels the description is expanded using the ``LLMClient``
        placeholder.
        """
        # Build a base title
        title_parts = []
        if event:
            title_parts.append(event)
        if prod:
            title_parts.append(prod.name.title())
        else:
            title_parts.append("Biotact")
        title = " – ".join(title_parts)

        # Compose a brief description from benefits
        benefits = ", ".join(prod.benefits[:3]) if prod and prod.benefits else ""
        description = f"Обсуждаем преимущества {prod.name}: {benefits}." if prod else "Общий пост о здоровье и гармонии."

        # For longer channels fetch a placeholder LLM expansion
        if channel in {"YouTube", "Podcast", "Blog", "Email"}:
            prompt = (
                f"Вы маркетолог компании Biotact. Создайте развёрнутый текст для канала {channel} "
                f"о продукте {prod.name if prod else 'Biotact'} на {day.strftime('%d %B %Y')}. Включите факты "
                f"о бренде, информацию из списка преимуществ и призыв к действию."
            )
            llm_output = self.llm.generate(prompt)
            description = llm_output

        # Image prompt summarises the theme for generative art
        image_prompt = None
        if prod:
            # Use the tagline and first benefit as the basis for image generation
            key_words = prod.tagline + " " + (prod.benefits[0] if prod.benefits else "")
            image_prompt = (
                f"An elegant, modern illustration representing {prod.name}: {key_words}. "
                "Use soft colours and incorporate elements of nature and science."
            )
        return title, description, image_prompt

    def generate_q4_2025_plan(self) -> List[ContentEntry]:
        """Assemble a content plan for Q4 2025 (October–December).

        Returns
        -------
        List[ContentEntry]
            A list of scheduled posts across different channels.  Each
            entry contains the date, selected channel, product (if any),
            event (if applicable), description and a prompt for image
            generation.
        """
        start = date(2025, 10, 1)
        end = date(2025, 12, 31)
        days = self._create_base_schedule(start, end)
        plan: List[ContentEntry] = []
        for day in days:
            # Skip a few days per week to avoid content fatigue (e.g. only schedule every 3rd day)
            if day.day % 3 != 0:
                continue
            channel = self._pick_channel(day)
            prod = self._select_product_for_day(day)
            # Identify any health awareness event on this day
            month_name = day.strftime("%B")
            event_name = None
            if month_name in self.HEALTH_DAYS:
                for event_day, name in self.HEALTH_DAYS[month_name]:
                    if event_day == day.day:
                        event_name = name
                        break
            title, description, image_prompt = self._compose_title_and_description(prod, day, channel, event_name)
            target = ", ".join(prod.target_groups[:2]) if prod and prod.target_groups else "Здоровые семьи"
            entry = ContentEntry(
                date=day,
                channel=channel,
                title=title,
                description=description,
                product=prod.name if prod else None,
                target=target,
                image_prompt=image_prompt,
            )
            plan.append(entry)
        return plan

    def export_plan_to_json(self, plan: Sequence[ContentEntry], path: str) -> None:
        """Write the content plan to a JSON file.

        Parameters
        ----------
        plan : Sequence[ContentEntry]
            The content plan to serialise.
        path : str
            Destination path for the JSON file.
        """
        with open(path, "w", encoding="utf-8") as f:
            json.dump([entry.to_dict() for entry in plan], f, ensure_ascii=False, indent=2)


def main():  # pragma: no cover
    """Entry point for manual execution.

    When run as a script this function generates the plan and writes
    it to ``q4_2025_plan.json`` in the current directory.  It also
    prints a short summary to the console.
    """
    data_dir = os.path.dirname(__file__)
    agent = BiotactMarketingAgent(data_dir)
    plan = agent.generate_q4_2025_plan()
    out_path = os.path.join(data_dir, "q4_2025_plan.json")
    agent.export_plan_to_json(plan, out_path)
    print(f"Generated {len(plan)} content entries and saved to {out_path}.")
    for entry in plan[:5]:
        print(entry.to_dict())


if __name__ == "__main__":  # pragma: no cover
    main()