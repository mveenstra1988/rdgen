from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from vit_ai_hub.config import get_settings, load_yaml_config


@dataclass
class Finding:
    name: str
    value: str
    start: int
    end: int


@dataclass
class PiiResult:
    text: str
    original: str
    findings: list[Finding] = field(default_factory=list)
    token_map: dict[str, str] = field(default_factory=dict)
    blocked: bool = False
    action: str = "allow"

    @property
    def has_pii(self) -> bool:
        return bool(self.findings)


class PiiEngine:
    def __init__(self) -> None:
        cfg = load_yaml_config().get("pii", {})
        self.cloud_action = get_settings().vit_pii_cloud_action or cfg.get("cloud_action", "block")
        self.local_action = cfg.get("local_action", "allow")
        self.patterns: list[tuple[str, re.Pattern[str]]] = []
        for item in cfg.get("patterns", []):
            try:
                self.patterns.append((item["name"], re.compile(item["regex"])))
            except re.error:
                continue
        self.audit_path = Path(get_settings().vit_audit_log)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    def scan(self, text: str) -> list[Finding]:
        findings: list[Finding] = []
        for name, pattern in self.patterns:
            for match in pattern.finditer(text or ""):
                findings.append(
                    Finding(name=name, value=match.group(0), start=match.start(), end=match.end())
                )
        findings.sort(key=lambda f: f.start)
        return findings

    def process(self, text: str, *, destination_local: bool) -> PiiResult:
        original = text or ""
        findings = self.scan(original)
        action = self.local_action if destination_local else self.cloud_action
        if not findings:
            return PiiResult(text=original, original=original, action="allow")

        if action == "block" and not destination_local:
            result = PiiResult(
                text=original,
                original=original,
                findings=findings,
                blocked=True,
                action="block",
            )
            self._audit(result, destination_local=destination_local)
            return result

        if action == "allow" and destination_local:
            result = PiiResult(
                text=original,
                original=original,
                findings=findings,
                action="allow",
            )
            self._audit(result, destination_local=destination_local)
            return result

        # redact / tokenize
        token_map: dict[str, str] = {}
        counters: dict[str, int] = {}
        pieces: list[str] = []
        cursor = 0
        for finding in findings:
            if finding.start < cursor:
                continue
            pieces.append(original[cursor : finding.start])
            counters[finding.name] = counters.get(finding.name, 0) + 1
            token = f"⟦{finding.name.upper()}_{counters[finding.name]}⟧"
            token_map[token] = finding.value
            pieces.append(token)
            cursor = finding.end
        pieces.append(original[cursor:])
        redacted = "".join(pieces)
        result = PiiResult(
            text=redacted,
            original=original,
            findings=findings,
            token_map=token_map,
            action="redact",
        )
        self._audit(result, destination_local=destination_local)
        return result

    def rehydrate(self, text: str, token_map: dict[str, str]) -> str:
        out = text or ""
        for token, value in token_map.items():
            out = out.replace(token, value)
        return out

    def process_messages(
        self, messages: Iterable[dict[str, Any]], *, destination_local: bool
    ) -> tuple[list[dict[str, Any]], PiiResult]:
        merged_map: dict[str, str] = {}
        all_findings: list[Finding] = []
        blocked = False
        action = "allow"
        new_messages: list[dict[str, Any]] = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                # multimodal: only scan text parts
                parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        pr = self.process(part.get("text", ""), destination_local=destination_local)
                        if pr.blocked:
                            blocked = True
                        all_findings.extend(pr.findings)
                        merged_map.update(pr.token_map)
                        action = pr.action if pr.action != "allow" else action
                        parts.append({**part, "text": pr.text})
                    else:
                        parts.append(part)
                new_messages.append({**msg, "content": parts})
            else:
                pr = self.process(str(content), destination_local=destination_local)
                if pr.blocked:
                    blocked = True
                all_findings.extend(pr.findings)
                merged_map.update(pr.token_map)
                if pr.action != "allow":
                    action = pr.action
                new_messages.append({**msg, "content": pr.text})
        summary = PiiResult(
            text="",
            original="",
            findings=all_findings,
            token_map=merged_map,
            blocked=blocked,
            action="block" if blocked else action,
        )
        return new_messages, summary

    def _audit(self, result: PiiResult, *, destination_local: bool) -> None:
        entry = {
            "ts": time.time(),
            "id": str(uuid.uuid4()),
            "destination_local": destination_local,
            "action": result.action,
            "blocked": result.blocked,
            "finding_types": sorted({f.name for f in result.findings}),
            "finding_count": len(result.findings),
            # never log raw PII values
        }
        with self.audit_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


_engine: PiiEngine | None = None


def get_pii_engine() -> PiiEngine:
    global _engine
    if _engine is None:
        _engine = PiiEngine()
    return _engine