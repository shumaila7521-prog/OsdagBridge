import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit

from osdagbridge.core.utils.common import (
    KEY_CARRIAGEWAY_WIDTH,
    KEY_SPAN,
    KEY_TS_DECK_THICKNESS,
    KEY_TS_GIRDER_SPACING,
    KEY_TS_OVERALL_WIDTH,
)
from osdagbridge.core.bridge_types.plate_girder.validator import BridgeInputValidator
from osdagbridge.desktop.ui.docks.cad_cross_section import CrossSectionCADWidget
from osdagbridge.desktop.ui.docks.cad_top_view import TopViewCADWidget
from osdagbridge.desktop.ui import template_page


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


def _show_widget(widget, application):
    widget.resize(1100, 900)
    widget.show()
    application.processEvents()


def _double_click_parameter(widget, application, key):
    region = next(
        region for region in widget._editable_parameter_regions if region[1] == key
    )
    point = region[0].center().toPoint()
    QTest.mouseDClick(widget, Qt.LeftButton, pos=point)
    application.processEvents()
    return widget.findChild(QLineEdit)


def test_only_requested_cad_dimensions_are_editable(application):
    cross_section = CrossSectionCADWidget()
    top_view = TopViewCADWidget()
    _show_widget(cross_section, application)
    _show_widget(top_view, application)

    assert {region[1] for region in cross_section._editable_parameter_regions} == {
        KEY_CARRIAGEWAY_WIDTH,
        KEY_TS_GIRDER_SPACING,
        KEY_TS_DECK_THICKNESS,
    }
    assert {region[1] for region in top_view._editable_parameter_regions} == {
        KEY_SPAN,
        KEY_TS_GIRDER_SPACING,
    }

    cross_section.close()
    top_view.close()


def test_enter_commits_cad_dimension_in_display_units(application):
    widget = TopViewCADWidget()
    _show_widget(widget, application)
    edits = []
    widget.parameter_edit_requested.connect(
        lambda key, value: edits.append((key, value))
    )

    editor = _double_click_parameter(widget, application, KEY_SPAN)
    assert editor is not None
    assert editor.text() == "35.0"

    editor.setText("40.5")
    QTest.keyClick(editor, Qt.Key_Return)
    application.processEvents()

    assert edits == [(KEY_SPAN, 40.5)]
    widget.close()


def test_focus_out_commits_cad_dimension(application):
    widget = CrossSectionCADWidget()
    _show_widget(widget, application)
    edits = []
    widget.parameter_edit_requested.connect(
        lambda key, value: edits.append((key, value))
    )

    editor = _double_click_parameter(widget, application, KEY_TS_DECK_THICKNESS)
    assert editor is not None
    editor.setText("240")
    editor.clearFocus()
    application.processEvents()

    assert edits == [(KEY_TS_DECK_THICKNESS, 240.0)]
    widget.close()


@pytest.mark.parametrize("text", ["not a number", "0", "-1", "nan", "inf"])
def test_invalid_cad_dimension_does_not_commit(application, text):
    widget = TopViewCADWidget()
    _show_widget(widget, application)
    edits = []
    widget.parameter_edit_requested.connect(
        lambda key, value: edits.append((key, value))
    )

    editor = _double_click_parameter(widget, application, KEY_SPAN)
    assert editor is not None
    editor.setText(text)
    QTest.keyClick(editor, Qt.Key_Return)
    application.processEvents()

    assert edits == []
    widget.close()


def _edit_handler_harness():
    inputs = {
        KEY_SPAN: 35.0,
        KEY_CARRIAGEWAY_WIDTH: 10.5,
        KEY_TS_GIRDER_SPACING: 3.0,
        KEY_TS_DECK_THICKNESS: 250.0,
        KEY_TS_OVERALL_WIDTH: 10.0,
    }
    working_inputs = dict(inputs)
    additional_inputs = SimpleNamespace(
        default_input_dict=inputs,
        working_input_dict=working_inputs,
        validator=BridgeInputValidator(),
    )
    input_dock = SimpleNamespace(
        validator=BridgeInputValidator(),
        is_require_field_changed=False,
        findChild=lambda *_: None,
    )
    redraws = []
    window = SimpleNamespace(
        input_dict=inputs,
        input_dock=input_dock,
        _additional_inputs_dialog=additional_inputs,
        cad_comp_widget=SimpleNamespace(
            update_from_osdag_inputs=lambda current: redraws.append(dict(current))
        ),
        _sync_cad_parameter_field=lambda *_: None,
    )
    return window, additional_inputs, redraws


def test_valid_edit_updates_both_dictionaries_and_redraws(monkeypatch):
    class MessageBoxStub:
        def __init__(self, **kwargs):
            pass

        def exec(self):
            pass

    monkeypatch.setattr(template_page, "CustomMessageBox", MessageBoxStub)
    window, additional_inputs, redraws = _edit_handler_harness()

    template_page.CustomWindow._on_cad_parameter_edited(
        window, KEY_TS_GIRDER_SPACING, 4.5
    )

    assert window.input_dict[KEY_TS_GIRDER_SPACING] == 4.5
    assert additional_inputs.working_input_dict[KEY_TS_GIRDER_SPACING] == 4.5
    assert additional_inputs.default_input_dict[KEY_TS_GIRDER_SPACING] == 4.5
    assert len(redraws) == 1


@pytest.mark.parametrize(
    ("key", "value"),
    [(KEY_SPAN, 40.0), (KEY_CARRIAGEWAY_WIDTH, 12.0)],
)
def test_valid_basic_edit_updates_dictionaries_and_redraws(
    monkeypatch, key, value
):
    monkeypatch.setattr(
        template_page, "solve_extend_basic_input_dict", lambda inputs: None
    )
    window, additional_inputs, redraws = _edit_handler_harness()

    template_page.CustomWindow._on_cad_parameter_edited(window, key, value)

    assert window.input_dict[key] == value
    assert additional_inputs.working_input_dict[key] == value
    assert len(redraws) == 1


def test_basic_edit_keeps_parsed_value_when_layout_solver_fails(monkeypatch):
    warnings = []

    def fail_layout_solve(inputs):
        inputs[KEY_TS_OVERALL_WIDTH] = 99.0
        raise TypeError("float() argument must be a string or a real number, not 'NoneType'")

    monkeypatch.setattr(
        template_page, "solve_extend_basic_input_dict", fail_layout_solve
    )
    monkeypatch.setattr(template_page.bridge_logger, "warning", warnings.append)
    window, additional_inputs, redraws = _edit_handler_harness()

    template_page.CustomWindow._on_cad_parameter_edited(window, KEY_SPAN, 40.0)

    assert window.input_dict[KEY_SPAN] == 40.0
    assert window.input_dict[KEY_TS_OVERALL_WIDTH] == 10.0
    assert additional_inputs.working_input_dict[KEY_SPAN] == 40.0
    assert len(redraws) == 1
    assert warnings and "using the edited value" in warnings[0]


def test_out_of_range_edit_does_not_update_dictionaries_or_redraw(monkeypatch):
    class MessageBoxStub:
        def __init__(self, **kwargs):
            pass

        def exec(self):
            pass

    monkeypatch.setattr(template_page, "CustomMessageBox", MessageBoxStub)
    window, additional_inputs, redraws = _edit_handler_harness()
    initial_inputs = dict(window.input_dict)

    template_page.CustomWindow._on_cad_parameter_edited(
        window, KEY_TS_GIRDER_SPACING, 5.1
    )
    template_page.CustomWindow._on_cad_parameter_edited(window, KEY_SPAN, 50.0)

    assert window.input_dict == initial_inputs
    assert additional_inputs.working_input_dict == initial_inputs
    assert redraws == []
