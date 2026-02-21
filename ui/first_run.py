"""First-run setup wizard."""

import logging
import threading

import flet as ft

log = logging.getLogger(__name__)

SUGGESTED_MODELS = {
    "main": [
        "anthropic/claude-sonnet-4.6",
        "anthropic/claude-sonnet-4.5",
        "anthropic/claude-opus-4",
        "google/gemini-2.5-pro-preview",
    ],
    "code": [
        "anthropic/claude-sonnet-4.6",
        "anthropic/claude-sonnet-4.5",
        "anthropic/claude-opus-4",
        "openai/o3",
    ],
    "light": [
        "google/gemini-2.5-flash",
        "google/gemini-2.5-pro-preview",
        "openai/o3-mini",
        "anthropic/claude-sonnet-4",
    ],
}


def _make_model_row(label: str, field: ft.TextField, suggestions: list, page_ref: list):
    """Create a model field with clickable suggestion chips."""
    def _pick(val):
        field.value = val
        if page_ref[0]:
            page_ref[0].update()

    chips = ft.Row(
        controls=[
            ft.TextButton(
                m.split("/")[-1],
                on_click=lambda _e, mv=m: _pick(mv),
                style=ft.ButtonStyle(padding=ft.padding.symmetric(horizontal=6, vertical=0)),
            )
            for m in suggestions
        ],
        wrap=True, spacing=2, run_spacing=2,
    )
    return ft.Column(spacing=4, controls=[
        ft.Text(label, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE70),
        field,
        chips,
    ])


def run_first_run_wizard(
    models: list, settings_defaults: dict, save_fn,
) -> bool:
    """Show a setup wizard. Returns True if user completed setup."""
    _completed = [False]

    def _wizard(page: ft.Page):
        page.title = "Ouroboros \u2014 Setup"
        page.theme_mode = ft.ThemeMode.DARK
        page.window.width = 640
        page.window.height = 700
        page.padding = 0
        page.spacing = 0

        page_ref = [page]
        step = [0]
        status_text = ft.Text("", size=13)

        api_key_input = ft.TextField(
            label="OpenRouter API Key", password=True, can_reveal_password=True,
            width=480, hint_text="sk-or-...",
        )
        openai_key_input = ft.TextField(
            label="OpenAI API Key (for web search)", password=True,
            can_reveal_password=True, width=480, hint_text="sk-... (optional)",
        )
        anthropic_key_input = ft.TextField(
            label="Anthropic API Key", password=True,
            can_reveal_password=True, width=480, hint_text="sk-ant-... (optional)",
        )

        model_main_field = ft.TextField(
            label="Main Model", width=480,
            value="anthropic/claude-sonnet-4.6",
            hint_text="e.g. anthropic/claude-sonnet-4.6",
        )
        model_code_field = ft.TextField(
            label="Code Model", width=480,
            value="anthropic/claude-sonnet-4.6",
            hint_text="e.g. anthropic/claude-sonnet-4.6",
        )
        model_light_field = ft.TextField(
            label="Light Model (dedup, safety)", width=480,
            value="google/gemini-2.5-flash",
            hint_text="e.g. google/gemini-2.5-flash",
        )

        def _go_step(n):
            step[0] = n
            for i, s in enumerate(step_views):
                s.visible = (i == n)
            page.update()

        def _on_test_key(_e):
            key = api_key_input.value.strip()
            if not key:
                status_text.value = "Please enter an API key."
                status_text.color = ft.Colors.RED_300
                page.update()
                return
            status_text.value = "Testing connection..."
            status_text.color = ft.Colors.AMBER_300
            page.update()

            def _test():
                try:
                    import requests
                    r = requests.get(
                        "https://openrouter.ai/api/v1/models",
                        headers={"Authorization": f"Bearer {key}"},
                        timeout=10,
                    )
                    if r.status_code == 200:
                        status_text.value = "Connection successful!"
                        status_text.color = ft.Colors.GREEN_300
                    else:
                        status_text.value = f"API returned {r.status_code}. Check your key."
                        status_text.color = ft.Colors.RED_300
                except Exception as exc:
                    status_text.value = f"Connection failed: {exc}"
                    status_text.color = ft.Colors.RED_300
                page.update()

            threading.Thread(target=_test, daemon=True).start()

        def _on_finish(_e):
            try:
                s = dict(settings_defaults)
                s["OPENROUTER_API_KEY"] = api_key_input.value.strip()
                s["OPENAI_API_KEY"] = openai_key_input.value.strip()
                s["ANTHROPIC_API_KEY"] = anthropic_key_input.value.strip()
                s["OUROBOROS_MODEL"] = model_main_field.value.strip()
                s["OUROBOROS_MODEL_CODE"] = model_code_field.value.strip()
                s["OUROBOROS_MODEL_LIGHT"] = model_light_field.value.strip()
                save_fn(s)
                _completed[0] = True
            except Exception as exc:
                log.error("Wizard save failed: %s", exc, exc_info=True)
                _completed[0] = True
            page.window.destroy()

        # Step 0: Welcome
        step0 = ft.Column(
            visible=True, spacing=20,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text("O", size=64, weight=ft.FontWeight.BOLD, color=ft.Colors.TEAL_200),
                ft.Text("Welcome to Ouroboros", size=24, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "A self-creating agent running locally on your Mac.\n"
                    "Let\u2019s get you set up in a few steps.",
                    size=14, color=ft.Colors.WHITE70, text_align=ft.TextAlign.CENTER,
                ),
                ft.FilledButton("Get Started", on_click=lambda _: _go_step(1)),
            ],
        )

        # Step 1: API Keys
        step1 = ft.Column(
            visible=False, spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text("Step 1: API Keys", size=20, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Ouroboros uses OpenRouter for LLM access.\nGet a key at openrouter.ai",
                    size=13, color=ft.Colors.WHITE70, text_align=ft.TextAlign.CENTER,
                ),
                api_key_input,
                ft.OutlinedButton("Test Connection", on_click=_on_test_key),
                status_text,
                openai_key_input,
                anthropic_key_input,
                ft.Text("OpenAI key enables web search. Anthropic key is optional.", size=11, color=ft.Colors.WHITE38),
                ft.Row([
                    ft.TextButton("Back", on_click=lambda _: _go_step(0)),
                    ft.FilledButton("Next", on_click=lambda _: _go_step(2)),
                ], alignment=ft.MainAxisAlignment.CENTER),
            ],
        )

        # Step 2: Models
        step2 = ft.Column(
            visible=False, spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Text("Step 2: Choose Models", size=20, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Pick or type model names. You can change these later in Settings.",
                    size=13, color=ft.Colors.WHITE70, text_align=ft.TextAlign.CENTER,
                ),
                _make_model_row("Main (reasoning, chat)", model_main_field, SUGGESTED_MODELS["main"], page_ref),
                _make_model_row("Code (editing, commits)", model_code_field, SUGGESTED_MODELS["code"], page_ref),
                _make_model_row("Light (dedup, safety checks)", model_light_field, SUGGESTED_MODELS["light"], page_ref),
                ft.Container(height=8),
                ft.Row([
                    ft.TextButton("Back", on_click=lambda _: _go_step(1)),
                    ft.FilledButton("Launch Ouroboros", on_click=_on_finish, icon=ft.Icons.ROCKET_LAUNCH),
                ], alignment=ft.MainAxisAlignment.CENTER),
            ],
        )

        step_views = [step0, step1, step2]
        page.add(ft.Container(
            expand=True, padding=30,
            alignment=ft.alignment.center,
            content=ft.Stack(controls=step_views),
        ))

    ft.app(target=_wizard)
    return _completed[0]
