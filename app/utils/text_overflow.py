from PyQt5 import QtCore, QtGui, QtWidgets


class _TextOverflowFilter(QtCore.QObject):
    def eventFilter(self, obj, event):
        if isinstance(obj, QtWidgets.QComboBox):
            return self._handle_combo_event(obj, event)
        if isinstance(obj, QtWidgets.QLabel):
            return self._handle_label_event(obj, event)
        return False

    def _handle_combo_event(self, combo: QtWidgets.QComboBox, event) -> bool:
        if event.type() in {
            QtCore.QEvent.Enter,
            QtCore.QEvent.FocusIn,
            QtCore.QEvent.MouseButtonPress,
            QtCore.QEvent.KeyPress,
            QtCore.QEvent.Show,
            QtCore.QEvent.Paint,
        }:
            _refresh_combo_overflow(combo)

        if event.type() == QtCore.QEvent.Paint and not combo.isEditable():
            option = QtWidgets.QStyleOptionComboBox()
            combo.initStyleOption(option)
            full_text = combo.currentText()
            if full_text:
                available_width = max(24, combo.rect().width() - 36)
                option.currentText = combo.fontMetrics().elidedText(
                    full_text,
                    QtCore.Qt.ElideMiddle,
                    available_width,
                )
            painter = QtGui.QPainter(combo)
            combo.style().drawComplexControl(QtWidgets.QStyle.CC_ComboBox, option, painter, combo)
            combo.style().drawControl(QtWidgets.QStyle.CE_ComboBoxLabel, option, painter, combo)
            return True
        return False

    def _handle_label_event(self, label: QtWidgets.QLabel, event) -> bool:
        if event.type() in {QtCore.QEvent.Resize, QtCore.QEvent.Show, QtCore.QEvent.Paint}:
            _refresh_label_tooltip(label)

        if event.type() != QtCore.QEvent.Paint or not _should_elide_label(label):
            return False

        text = label.text()
        if not text:
            return False

        painter = QtGui.QPainter(label)
        option = QtWidgets.QStyleOption()
        option.initFrom(label)
        rect = label.contentsRect()
        margin = label.margin()
        if margin:
            rect = rect.adjusted(margin, margin, -margin, -margin)

        flags = int(label.alignment()) | QtCore.Qt.TextSingleLine
        elided = label.fontMetrics().elidedText(text, QtCore.Qt.ElideMiddle, rect.width())
        color_role = QtGui.QPalette.WindowText
        label.style().drawItemText(
            painter,
            rect,
            flags,
            option.palette,
            label.isEnabled(),
            elided,
            color_role,
        )
        return True


def _should_elide_label(label: QtWidgets.QLabel) -> bool:
    force_elide = bool(label.property("fcstm_elide_text"))
    if (label.wordWrap() and not force_elide) or label.pixmap() is not None or label.movie() is not None:
        return False
    if label.textFormat() == QtCore.Qt.RichText:
        return False
    text = label.text()
    if label.textFormat() == QtCore.Qt.AutoText and ("<" in text and ">" in text):
        return False
    return bool(text)


def _refresh_label_tooltip(label: QtWidgets.QLabel) -> None:
    if not _should_elide_label(label):
        return
    text = label.text()
    if not text:
        return
    label.setToolTip(text)


def _refresh_combo_overflow(combo: QtWidgets.QComboBox) -> None:
    current_text = combo.currentText()
    if current_text:
        combo.setToolTip(current_text)

    for index in range(combo.count()):
        text = combo.itemText(index)
        if text:
            combo.setItemData(index, text, QtCore.Qt.ToolTipRole)

    view = combo.view()
    if view is not None:
        view.setTextElideMode(QtCore.Qt.ElideMiddle)
        width = view.sizeHintForColumn(0)
        if width > 0:
            view.setMinimumWidth(max(combo.width(), width + 28))


def refresh_text_overflow(root: QtWidgets.QWidget) -> None:
    for combo in root.findChildren(QtWidgets.QComboBox):
        _refresh_combo_overflow(combo)
    for label in root.findChildren(QtWidgets.QLabel):
        _refresh_label_tooltip(label)


def apply_text_overflow_handling(root: QtWidgets.QWidget) -> None:
    existing = getattr(root, "_text_overflow_filter", None)
    if existing is None:
        existing = _TextOverflowFilter(root)
        root._text_overflow_filter = existing

    for label in root.findChildren(QtWidgets.QLabel):
        label.installEventFilter(existing)
        _refresh_label_tooltip(label)

    for combo in root.findChildren(QtWidgets.QComboBox):
        combo.installEventFilter(existing)
        combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        if not combo.property("fcstm_overflow_connected"):
            combo.currentTextChanged.connect(lambda _text, target=combo: _refresh_combo_overflow(target))
            combo.setProperty("fcstm_overflow_connected", True)
        _refresh_combo_overflow(combo)

    for view in root.findChildren(QtWidgets.QAbstractItemView):
        view.setTextElideMode(QtCore.Qt.ElideMiddle)
        view.setMouseTracking(True)
