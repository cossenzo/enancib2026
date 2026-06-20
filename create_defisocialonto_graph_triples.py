#!/usr/bin/env python3
"""
Create RDF triples for DeFiSocialOnto from graph_dataset.xlsx.

Input:
  - DeFiSocialOnto.owl: ontology exported from Protege/OWL, used only to infer the base IRI.
  - graph_dataset.xlsx: workbook with the sheets specified in the empirical graph dataset.

Output:
  - Turtle (.ttl) file containing individuals, data-property assertions, and object-property assertions.

The script intentionally does NOT create owl:imports or an optional import/traceability link.
"""

from __future__ import annotations

import argparse
import math
import re
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import XSD

DEFAULT_BASE_IRI = "http://defisocialonto.org/defisocialonto"

SHEETS_IN_ORDER = [
    "ConsumerProtectionPrinciple",
    "ConsumerProtectionMeasure",
    "Measure_Principle",
    "ActionableForesight",
    "Risk",
    "Concept",
    "LinguisticVariant",
    "Protocol",
    "Platform",
    "DiscourseUnit",
]


def is_missing(value) -> bool:
    """Return True for NaN, None, or blank-like values."""
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"nan", "none", "null"}


def clean_text(value) -> str:
    """Normalize a spreadsheet cell to stripped text."""
    if is_missing(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def split_semicolon_list(value) -> list[str]:
    """Split lists encoded as 'item1; item2; item3'."""
    text = clean_text(value)
    if not text:
        return []
    return [item.strip() for item in text.split(";") if item.strip()]


def camel_case(value: str) -> str:
    """
    Convert free text to lower camelCase for individual names.
    Example: 'ape in' -> 'apeIn'; 'GHO depeg' -> 'ghoDepeg'.
    """
    text = clean_text(value)
    if not text:
        return "Unnamed"

    tokens = re.findall(r"[A-Za-z0-9]+", text)
    if not tokens:
        return "Unnamed"

    first = tokens[0].lower()
    rest = [token[:1].upper() + token[1:] for token in tokens[1:]]
    candidate = first + "".join(rest)

    if candidate and candidate[0].isdigit():
        candidate = "n" + candidate
    return candidate


def iri_local_name(value: str) -> str:
    """
    Create a safe IRI local name for values that should be used as their own instance names.
    Existing CamelCase/PascalCase names are preserved. Values with spaces or punctuation
    are converted to PascalCase to keep the resulting Turtle easy to read in GraphDB.
    """
    text = clean_text(value)
    if not text:
        return "Unnamed"

    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_\-]*", text):
        return text

    tokens = re.findall(r"[A-Za-z0-9]+", text)
    if not tokens:
        return "Unnamed"

    candidate = "".join(token[:1].upper() + token[1:] for token in tokens)
    if candidate[0].isdigit():
        candidate = "N" + candidate
    return candidate


def extract_base_iri(ontology_path: Path) -> str:
    """Extract ontologyIRI or xml:base from the ontology file without requiring RDF/XML parsing."""
    try:
        text = ontology_path.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        return DEFAULT_BASE_IRI

    for pattern in [r'ontologyIRI="([^"]+)"', r'xml:base="([^"]+)"']:
        match = re.search(pattern, text)
        if match:
            return match.group(1).rstrip("#/")
    return DEFAULT_BASE_IRI


def principle_number_from_label(label: str) -> Optional[str]:
    """Extract the leading number from labels such as '10. Protection ...'."""
    text = clean_text(label)
    match = re.match(r"^(\d+)", text)
    return match.group(1) if match else None


def literal_date(value) -> Literal:
    """Return a date literal when possible; otherwise return a string literal."""
    if is_missing(value):
        return Literal("")
    if isinstance(value, datetime):
        return Literal(value.date().isoformat(), datatype=XSD.date)
    if isinstance(value, date):
        return Literal(value.isoformat(), datatype=XSD.date)

    text = clean_text(value)
    try:
        parsed = pd.to_datetime(text, errors="raise")
        if not pd.isna(parsed):
            return Literal(parsed.date().isoformat(), datatype=XSD.date)
    except Exception:
        pass
    return Literal(text, datatype=XSD.string)


def require_columns(df: pd.DataFrame, sheet_name: str, columns: Iterable[str]) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"Sheet '{sheet_name}' is missing required column(s): {', '.join(missing)}")


def add_string_literal(g: Graph, subject: URIRef, predicate: URIRef, value) -> None:
    text = clean_text(value)
    if text:
        g.add((subject, predicate, Literal(text, datatype=XSD.string)))


def build_graph(ontology_path: Path, dataset_path: Path) -> tuple[Graph, dict[str, int]]:
    base_iri = extract_base_iri(ontology_path)
    base_ns = Namespace(base_iri + "#")

    g = Graph()
    g.bind("defi", base_ns)
    g.bind("rdf", RDF)
    g.bind("xsd", XSD)

    xls = pd.ExcelFile(dataset_path)
    missing_sheets = [sheet for sheet in SHEETS_IN_ORDER if sheet not in xls.sheet_names]
    if missing_sheets:
        raise ValueError(f"Workbook is missing required sheet(s): {', '.join(missing_sheets)}")

    sheets = {
        sheet: pd.read_excel(dataset_path, sheet_name=sheet, dtype=str).fillna("")
        for sheet in SHEETS_IN_ORDER
    }

    counts: dict[str, int] = {sheet: 0 for sheet in SHEETS_IN_ORDER}
    counts.update({"source_instances": 0, "actor_instances": 0, "triples": 0})

    # Classes
    ConsumerProtectionPrinciple = base_ns.ConsumerProtectionPrinciple
    ConsumerProtectionMeasure = base_ns.ConsumerProtectionMeasure
    ActionableForesight = base_ns.ActionableForesight
    Risk = base_ns.Risk
    Concept = base_ns.Concept
    LinguisticVariant = base_ns.LinguisticVariant
    Protocol = base_ns.Protocol
    Platform = base_ns.Platform
    DiscourseUnit = base_ns.DiscourseUnit
    Source = base_ns.Source
    Actor = base_ns.Actor

    # Data properties
    number = base_ns.number
    description = base_ns.description
    name = base_ns.name
    rawText = base_ns.rawText
    id_prop = base_ns.id
    date_prop = base_ns.date
    url = base_ns.url
    type_prop = base_ns.type

    # Object properties
    isCoveredBy = base_ns.isCoveredBy
    isAddressedBy = base_ns.isAddressedBy
    signals = base_ns.signals
    isAssociatedWith = base_ns.isAssociatedWith
    expresses = base_ns.expresses
    refersToProtocol = base_ns.refersToProtocol
    refersToPlatform = base_ns.refersToPlatform
    hasSource = base_ns.hasSource
    isProducedBy = base_ns.isProducedBy
    contains = base_ns.contains

    # (1) ConsumerProtectionPrinciple
    df = sheets["ConsumerProtectionPrinciple"]
    require_columns(df, "ConsumerProtectionPrinciple", [
        "ConsumerProtectionPrinciple_number",
        "ConsumerProtectionPrinciple_description",
    ])
    for _, row in df.iterrows():
        n = clean_text(row["ConsumerProtectionPrinciple_number"])
        if not n:
            continue
        s = base_ns[f"Principle{n}"]
        g.add((s, RDF.type, ConsumerProtectionPrinciple))
        g.add((s, number, Literal(int(float(n)), datatype=XSD.integer)))
        add_string_literal(g, s, description, row["ConsumerProtectionPrinciple_description"])
        counts["ConsumerProtectionPrinciple"] += 1

    # (2) ConsumerProtectionMeasure
    df = sheets["ConsumerProtectionMeasure"]
    require_columns(df, "ConsumerProtectionMeasure", [
        "ConsumerProtectionMeasure_name",
        "ConsumerProtectionMeasure_description",
    ])
    for _, row in df.iterrows():
        measure_name = clean_text(row["ConsumerProtectionMeasure_name"])
        if not measure_name:
            continue
        s = base_ns[iri_local_name(measure_name)]
        g.add((s, RDF.type, ConsumerProtectionMeasure))
        add_string_literal(g, s, name, measure_name)
        add_string_literal(g, s, description, row["ConsumerProtectionMeasure_description"])
        counts["ConsumerProtectionMeasure"] += 1

    # (3) Measure_Principle
    df = sheets["Measure_Principle"]
    require_columns(df, "Measure_Principle", ["ConsumerProtectionMeasure", "ConsumerProtectionPrinciples"])
    for _, row in df.iterrows():
        measure_name = clean_text(row["ConsumerProtectionMeasure"])
        if not measure_name:
            continue
        measure = base_ns[iri_local_name(measure_name)]
        for principle_label in split_semicolon_list(row["ConsumerProtectionPrinciples"]):
            n = principle_number_from_label(principle_label)
            if n:
                g.add((measure, isCoveredBy, base_ns[f"Principle{n}"]))
        counts["Measure_Principle"] += 1

    # (4) ActionableForesight
    df = sheets["ActionableForesight"]
    require_columns(df, "ActionableForesight", [
        "ActionableForesight_name",
        "ActionableForesight_description",
    ])
    for _, row in df.iterrows():
        foresight_name = clean_text(row["ActionableForesight_name"])
        if not foresight_name:
            continue
        s = base_ns[iri_local_name(foresight_name)]
        g.add((s, RDF.type, ActionableForesight))
        add_string_literal(g, s, name, foresight_name)
        add_string_literal(g, s, description, row["ActionableForesight_description"])
        counts["ActionableForesight"] += 1

    # (5) Risk
    df = sheets["Risk"]
    require_columns(df, "Risk", [
        "Risk_name",
        "Risk_description",
        "ConsumerProtectionMeasures",
        "ActionableForesights",
    ])
    for _, row in df.iterrows():
        risk_name = clean_text(row["Risk_name"])
        if not risk_name:
            continue
        risk = base_ns[iri_local_name(risk_name)]
        g.add((risk, RDF.type, Risk))
        add_string_literal(g, risk, name, risk_name)
        add_string_literal(g, risk, description, row["Risk_description"])

        for measure_name in split_semicolon_list(row["ConsumerProtectionMeasures"]):
            g.add((risk, isAddressedBy, base_ns[iri_local_name(measure_name)]))
        for foresight_name in split_semicolon_list(row["ActionableForesights"]):
            g.add((risk, signals, base_ns[iri_local_name(foresight_name)]))
        counts["Risk"] += 1

    # (6) Concept
    df = sheets["Concept"]
    require_columns(df, "Concept", ["Concept_name", "Concept_description", "Risks"])
    for _, row in df.iterrows():
        concept_name = clean_text(row["Concept_name"])
        if not concept_name:
            continue
        concept = base_ns[camel_case(concept_name)]
        g.add((concept, RDF.type, Concept))
        add_string_literal(g, concept, name, concept_name)
        add_string_literal(g, concept, description, row["Concept_description"])
        for risk_name in split_semicolon_list(row["Risks"]):
            g.add((concept, isAssociatedWith, base_ns[iri_local_name(risk_name)]))
        counts["Concept"] += 1

    # (7) LinguisticVariant
    df = sheets["LinguisticVariant"]
    require_columns(df, "LinguisticVariant", ["LinguisticVariant_rawText", "Concept"])
    for _, row in df.iterrows():
        variant_text = clean_text(row["LinguisticVariant_rawText"])
        concept_name = clean_text(row["Concept"])
        if not variant_text:
            continue
        variant = base_ns[camel_case(variant_text)]
        g.add((variant, RDF.type, LinguisticVariant))
        add_string_literal(g, variant, rawText, variant_text)
        if concept_name:
            g.add((variant, expresses, base_ns[camel_case(concept_name)]))
        counts["LinguisticVariant"] += 1

    # (8) Protocol
    df = sheets["Protocol"]
    require_columns(df, "Protocol", ["Protocol_name"])
    for _, row in df.iterrows():
        protocol_name = clean_text(row["Protocol_name"])
        if not protocol_name:
            continue
        protocol = base_ns[iri_local_name(protocol_name)]
        g.add((protocol, RDF.type, Protocol))
        add_string_literal(g, protocol, name, protocol_name)
        counts["Protocol"] += 1

    # (9) Platform
    df = sheets["Platform"]
    require_columns(df, "Platform", ["Platform_name"])
    for _, row in df.iterrows():
        platform_name = clean_text(row["Platform_name"])
        if not platform_name:
            continue
        platform = base_ns[iri_local_name(platform_name)]
        g.add((platform, RDF.type, Platform))
        add_string_literal(g, platform, name, platform_name)
        counts["Platform"] += 1

    # (10) DiscourseUnit
    df = sheets["DiscourseUnit"]
    actor_column = "ActorType" if "ActorType" in df.columns else "Actor_Role"
    require_columns(df, "DiscourseUnit", [
        "DiscourseUnit_id",
        "DiscourseUnit_rawText",
        "DiscourseUnit_date",
        "Protocol_name",
        actor_column,
        "Source_url",
        "Source_type",
        "Platform_name",
        "LinguisticVariant_rawText",
    ])

    source_sequence = 0
    actor_sequence = 0
    role_class_map = {
        "Operator": base_ns.Operator,
        "Investor": base_ns.Investor,
        "Regulator": base_ns.Regulator,
        "SystemActor": base_ns.SystemActor,
        "UndefinedActor": Actor,
    }

    for _, row in df.iterrows():
        discourse_id = clean_text(row["DiscourseUnit_id"])
        if not discourse_id:
            continue

        discourse = base_ns[iri_local_name(discourse_id)]
        g.add((discourse, RDF.type, DiscourseUnit))
        add_string_literal(g, discourse, id_prop, discourse_id)
        add_string_literal(g, discourse, rawText, row["DiscourseUnit_rawText"])
        if not is_missing(row["DiscourseUnit_date"]):
            g.add((discourse, date_prop, literal_date(row["DiscourseUnit_date"])))

        protocol_name = clean_text(row["Protocol_name"])
        if protocol_name:
            g.add((discourse, refersToProtocol, base_ns[iri_local_name(protocol_name)]))

        platform_name = clean_text(row["Platform_name"])
        if platform_name:
            g.add((discourse, refersToPlatform, base_ns[iri_local_name(platform_name)]))

        source_sequence += 1
        source = base_ns[f"Source{source_sequence}"]
        g.add((source, RDF.type, Source))
        add_string_literal(g, source, url, row["Source_url"])
        add_string_literal(g, source, type_prop, row["Source_type"])
        g.add((discourse, hasSource, source))
        counts["source_instances"] += 1

        actor_sequence += 1
        actor = base_ns[f"Actor{actor_sequence}"]
        actor_type = clean_text(row[actor_column]) or "UndefinedActor"
        actor_class = role_class_map.get(actor_type, Actor)
        g.add((actor, RDF.type, actor_class))
        if actor_class != Actor:
            g.add((actor, RDF.type, Actor))
        g.add((discourse, isProducedBy, actor))
        counts["actor_instances"] += 1

        variant_text = clean_text(row["LinguisticVariant_rawText"])
        if variant_text:
            g.add((discourse, contains, base_ns[camel_case(variant_text)]))

        counts["DiscourseUnit"] += 1

    counts["triples"] = len(g)
    return g, counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate DeFiSocialOnto RDF triples from graph_dataset.xlsx."
    )
    parser.add_argument(
        "--ontology",
        default="DeFiSocialOnto.owl",
        help="Path to DeFiSocialOnto.owl. Used only to infer the base IRI.",
    )
    parser.add_argument(
        "--input",
        default="graph_dataset.xlsx",
        help="Path to graph_dataset.xlsx.",
    )
    parser.add_argument(
        "--output",
        default="defisocialonto_graph_dataset_instances.ttl",
        help="Output Turtle file path.",
    )
    args = parser.parse_args()

    graph, counts = build_graph(Path(args.ontology), Path(args.input))
    graph.serialize(destination=args.output, format="turtle", encoding="utf-8")

    print(f"RDF triples written: {counts['triples']}")
    for sheet in SHEETS_IN_ORDER:
        print(f"{sheet}: {counts[sheet]}")
    print(f"Source instances: {counts['source_instances']}")
    print(f"Actor instances: {counts['actor_instances']}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
