import frappe
from frappe.model.document import Document


class VigilanteSettings(Document):
    def get_scope(self):
        """Return the module include/exclude scope as clean lists."""
        include = _split_csv(self.include_modules)
        exclude = _split_csv(self.exclude_modules)
        return {
            "include_modules": include,
            "exclude_modules": exclude,
            "include_standard_apps": bool(self.include_standard_apps),
            "include_raw_source": bool(self.include_raw_source),
        }

    def get_llm_config(self):
        """Return LLM config, or None when heuristic summaries should be used."""
        if not self.enable_llm_summaries:
            return None
        api_key = self.get_password("llm_api_key", raise_exception=False)
        if not api_key:
            return None
        return {
            "provider": self.llm_provider or "Anthropic",
            "model": self.llm_model or "",
            "api_key": api_key,
        }


def _split_csv(value):
    if not value:
        return []
    return [part.strip() for part in value.replace("\n", ",").split(",") if part.strip()]


def get_settings():
    """Convenience accessor used across the app."""
    return frappe.get_single("Vigilante Settings")
