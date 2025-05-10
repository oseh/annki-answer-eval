from __future__ import annotations

import json
import os
import threading
import urllib.request
from datetime import datetime
from typing import Any, Dict

from aqt import gui_hooks, mw
from aqt.qt import QMessageBox, Qt, QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QSizePolicy
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, QObject




ADDON_DIR = os.path.dirname(__file__)
LOG_FILE = os.path.join(ADDON_DIR, "answer_eval.log")

_dialogs: list[QMessageBox] = []

def _log(message: str) -> None:
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
    except Exception:
        pass

_log("Add-on loaded")


def _config() -> Dict[str, Any]:
    cfg = mw.addonManager.getConfig(__name__) or {}
    cfg.setdefault("openai_api_key", os.getenv("OPENAI_API_KEY", ""))
    cfg.setdefault("model", "gpt-4o-mini")
    cfg.setdefault("field_name", "Back")
    cfg.setdefault("temperature", 0.0)
    return cfg

def _get_openai_key(cfg: dict) -> str:
    return cfg.get("openai_api_key", "").strip()

def _call_openai_api(messages, cfg, temperature=0.2):
    key = _get_openai_key(cfg)
    if not key:
        return None, "No OpenAI API key configured."
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}"
    }
    payload = {
        "model": cfg["model"],
        "temperature": temperature,
        "messages": messages,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data, headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            resp = json.loads(res.read().decode("utf-8"))
        content = resp.get("choices", [])[0].get("message", {}).get("content", "")
        return content.strip(), None
    except Exception as exc:
        return None, f"OpenAI API call failed: {exc}"

def _generate_mnemonic(expected: str, cfg: dict) -> str:
    messages = [
        {"role": "system", "content": (
            "You are a helpful assistant that creates short, memorable mnemonics for learning. "
            "Return only the mnemonic, no extra text."
        )},
        {"role": "user", "content": f"Create a mnemonic to remember: {expected}"}
    ]
    mnemonic, error = _call_openai_api(messages, cfg, temperature=0.2)
    if error:
        return error
    return mnemonic

def _grade_with_fallback(expected: str, user: str, cfg: dict) -> dict:
    messages = [
        {"role": "system", "content": (
            "You are grading an Anki flash-card answer. "
            "Return strict JSON: {\"score\": <0-1 float>, \"feedback\": <short comment>} "
            "Only JSON, no extra text."
        )},
        {"role": "user", "content": f"Expected: {expected}\nUser: {user}"},
    ]
    result_json, error = _call_openai_api(messages, cfg, temperature=cfg.get("temperature", 0.0))
    if error:
        return {"score": 0, "feedback": error}
    try:
        result = json.loads(result_json)
    except Exception as exc:
        return {"score": 0, "feedback": f"Invalid JSON from API: {exc}"}
    return result

def _score_to_ease(score: float) -> tuple[int, str, str]:
    """Map AI score to Anki ease value, label, and color."""
    if score < 0.3:
        return 1, "Again", "#e74c3c"  # Red
    elif score < 0.6:
        return 2, "Hard", "#f39c12"   # Orange
    elif score < 0.85:
        return 3, "Good", "#27ae60"   # Green
    else:
        return 4, "Easy", "#2980b9"   # Blue

class FeedbackDialog(QDialog):
    def __init__(self, mw, score, feedback, expected, ai_ease, ai_label, ai_color, mnemonic, parent=None, card=None):
        super().__init__(parent or mw)
        self.setWindowTitle("AI Evaluation")
        self.selected_ease = ai_ease
        self.setMinimumWidth(420)
        self.setMinimumHeight(260)
        layout = QVBoxLayout()
        percent = score * 100

        html = f"""
        <div style='text-align:center; font-size:18px;'>
            <b>Score:</b> <span style='color:{ai_color}; font-size:22px;'>{percent:.0f}%</span><br>
            <b>AI Suggests:</b> <span style='color:{ai_color}; font-size:20px;'>{ai_label}</span><br><br>
            <span style='color:#444; font-size:16px;'><i>{feedback}</i></span>
        </div>
        """

        if mnemonic:
            html += f"<div style='margin-top:12px; color:#8e44ad; font-size:15px;'><b>Mnemonic:</b> {mnemonic}</div>"
        else:
            html += f"<div style='margin-top:12px; color:#8e44ad; font-size:15px;'><b>Mnemonic:</b> <i>No mnemonic available.</i></div>"

        label = QLabel()
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setText(html)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)


        if expected:
            show_expected_btn = QPushButton("Show Expected Answer")
            def show_expected():
                QMessageBox.information(self, "Expected Answer", expected)
            show_expected_btn.clicked.connect(show_expected)
            layout.addWidget(show_expected_btn)


        copy_btn = QPushButton("Copy Feedback")
        def copy_feedback():
            mw.app.clipboard().setText(feedback)
        copy_btn.clicked.connect(copy_feedback)
        layout.addWidget(copy_btn)


        btn_layout = QHBoxLayout()
        self.ease_buttons = {}
        for ease, label_text, color in [
            (1, "Again", "#e74c3c"),
            (2, "Hard", "#f39c12"),
            (3, "Good", "#27ae60"),
            (4, "Easy", "#2980b9")
        ]:
            btn = QPushButton(label_text)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setProperty('ease', str(ease))
            btn.setStyleSheet(f"QPushButton[ease='{ease}'] {{ background: {color}; color: white; font-weight: bold; font-size: 16px; padding: 8px; border-radius: 6px; }}")
            if ease == ai_ease:
                btn.setChecked(True)
            btn.clicked.connect(lambda _, e=ease: self.select_ease(e))
            self.ease_buttons[ease] = btn
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)


        self.setStyleSheet('''
QPushButton:checked { border: 3px solid #222; box-shadow: 0 0 8px #222; }
QPushButton:!checked { border: none; box-shadow: none; }
''')


        confirm_btn = QPushButton("Confirm")
        confirm_btn.setStyleSheet("font-size: 16px; font-weight: bold; padding: 8px; margin-top: 12px;")
        confirm_btn.clicked.connect(self.accept)
        layout.addWidget(confirm_btn)

        self.setLayout(layout)

    def select_ease(self, ease):
        self.selected_ease = ease


class LoadingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Evaluation")
        self.setModal(True)
        self.setMinimumWidth(250)
        self.setMinimumHeight(100)
        layout = QVBoxLayout()
        label = QLabel("<b>Loading AI evaluation...</b>")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        self.setLayout(layout)





def _on_answer(reviewer, card, ease):
    try:

        if not hasattr(reviewer, "typedAnswer") or reviewer.typedAnswer is None:
            _log("No typed answer available; skipping AI evaluation.")
            return
        cfg = _config()
        try:
            expected = card.note()[cfg["field_name"]].strip()
        except Exception:
            _log("Field not found or empty, skipping grading")
            return
        if not expected:
            _log("Expected field is empty, skipping grading")
            return

        if card.note().model().get("type") == "Cloze":
            _log("Cloze card detected, skipping AI evaluation.")
            return
        user_answer = getattr(reviewer, "typedAnswer", "").strip()
        _log(f"Answer event: expected='{expected}', user='{user_answer}'")


        loading = LoadingDialog(mw)
        loading.show()
        mw.app.processEvents()


        class Worker(QThread):
            finished = pyqtSignal(dict, str)
            def run(self):
                result = _grade_with_fallback(expected, user_answer, cfg)
                mnemonic = _generate_mnemonic(expected, cfg)
                self.finished.emit(result, mnemonic)
        def on_done(result, mnemonic):
            loading.close()
            score = float(result.get("score", 0))
            ai_ease, ai_label, ai_color = _score_to_ease(score)
            dlg = FeedbackDialog(mw, score, result.get("feedback", "No feedback returned."), expected, ai_ease, ai_label, ai_color, mnemonic, card=card)
            dlg.exec()
            chosen_ease = dlg.selected_ease
            _log(f"User confirmed ease: {chosen_ease} (AI suggested {ai_ease})")
            reviewer._ease = chosen_ease
        worker = Worker()
        worker.finished.connect(on_done)
        worker.start()

        while worker.isRunning():
            mw.app.processEvents()
    except Exception as exc:
        _log(f"Exception in _on_answer: {exc}")
        try:
            QMessageBox.warning(mw, "AI Evaluation Error", "An error occurred in the AI evaluation add-on. Please check the log for details.")
        except Exception:
            pass




gui_hooks.reviewer_did_answer_card.append(_on_answer)
