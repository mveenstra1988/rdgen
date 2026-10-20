# Morgen — VIT AI Hub 2.6.6

## Crash-fix (Python 3.9 / str | None)
macOS Xcode-Python 3.9 crashte op pydantic. Fix: `eval_type_backport` + venv rebuild.

```bash
pkill -f vit_ai_hub.main 2>/dev/null || true
rm -rf "/Applications/VIT AI Hub.app/hub/.venv" "$HOME/AI-projecten/VIT-ai-hub/.venv"
curl -fsSL https://raw.githubusercontent.com/mveenstra1988/rdgen/cursor/vit-ai-hub-a440/vit-ai-hub/scripts/pull-to-ai-projecten.sh | bash
bash ~/AI-projecten/VIT-ai-hub/scripts/install-mac-clean.sh "$HOME/AI-projecten/VIT-ai-hub/packaging/mac/VIT AI Hub.app"
```
