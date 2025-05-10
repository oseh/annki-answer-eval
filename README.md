# Anki Answer Evaluation Add-on

Evaluates the learner's typed answer with OpenAI and shows immediate AI feedback in a pop-up.

## Features
- Grades typed answers using OpenAI's API
- Provides instant feedback and suggested ease
- Generates mnemonics for answers
- Integrates seamlessly with Anki's review flow

## Installation
1. Download the latest `.ankiaddon` release or package the add-on as described below.
2. In Anki, go to **Tools > Add-ons > Install from file...** and select the `.ankiaddon` file.
3. Restart Anki if prompted.

## Manual Packaging
If you are developing or modifying the add-on:
```bash
# From the project root
zip -r answer_eval.ankiaddon __init__.py manifest.json config.json
```
- Ensure `manifest.json` is at the root of the archive (not inside a folder).

## Configuration
Edit `config.json` to set your OpenAI API key and model:
```json
{
  "openai_api_key": "sk-...",
  "model": "gpt-4o-mini",
  "field_name": "Back",
  "temperature": 0.0
}
```

## License
MIT License. See [LICENSE](LICENSE) for details. 