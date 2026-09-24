"""Summarizer selection: heuristic by default, optional LLM.

The engine builds one summarizer per run and calls :meth:`Summarizer.summarize` for
every artifact. When an LLM config is present the LLM is tried first, always falling
back to the deterministic heuristic on any error so a snapshot never fails because of
a summariser problem.
"""

from __future__ import annotations

from dev_vigilante.artifact import Artifact
from dev_vigilante.summarizers import heuristic


class Summarizer:
    def __init__(self, llm_config: dict | None = None):
        self.llm_config = llm_config

    def summarize(self, artifact: Artifact) -> str:
        base = heuristic.summarize(artifact)
        if not self.llm_config:
            return base

        try:
            from dev_vigilante.summarizers import llm

            text = llm.summarize(artifact, base, self.llm_config)
            return (text or base).strip()
        except Exception:
            # Never let a remote failure break a snapshot.
            try:
                import frappe

                frappe.log_error(title="Dev Vigilante LLM summarizer", message=frappe.get_traceback())
            except Exception:
                pass
            return base


def get_summarizer(llm_config: dict | None = None) -> Summarizer:
    return Summarizer(llm_config)
