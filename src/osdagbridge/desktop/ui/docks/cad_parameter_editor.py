import math

from PySide6.QtCore import Qt, QRectF
from PySide6.QtWidgets import QLineEdit


class CADParameterEditorMixin:
    def _init_parameter_editor(self):
        self._editable_parameter_regions = []
        self._parameter_editor = None

    def _register_editable_parameter(
        self, key, rect, value, display_divisor=1.0, decimals=2
    ):
        self._editable_parameter_regions.append(
            (QRectF(rect), key, value, display_divisor, decimals)
        )

    def mouseDoubleClickEvent(self, event):
        position = event.position() if hasattr(event, "position") else event.pos()
        for rect, key, value, display_divisor, decimals in reversed(
            self._editable_parameter_regions
        ):
            if rect.contains(position):
                if self._parameter_editor is not None:
                    self._parameter_editor.deleteLater()

                editor = QLineEdit(self)
                editor.setGeometry(rect.toAlignedRect())
                editor.setAlignment(Qt.AlignCenter)
                editor.setStyleSheet(
                    "QLineEdit { background-color: white; color: black; "
                    "border: 1px solid #90AF13; }"
                )
                editor.setText(f"{value / display_divisor:.{decimals}f}")
                editor.editingFinished.connect(self._finish_parameter_edit)
                self._parameter_editor = (editor, key)
                editor.show()
                editor.setFocus()
                editor.selectAll()
                event.accept()
                return

        super().mouseDoubleClickEvent(event)

    def _finish_parameter_edit(self):
        if self._parameter_editor is None:
            return

        editor, key = self._parameter_editor
        self._parameter_editor = None
        text = editor.text().strip()
        editor.hide()
        editor.deleteLater()

        try:
            value = float(text)
        except ValueError:
            self.update()
            return

        if not math.isfinite(value) or value <= 0:
            self.update()
            return

        self.parameter_edit_requested.emit(key, value)
        self.update()
