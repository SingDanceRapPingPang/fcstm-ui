import os
import sys
from enum import IntEnum, unique
from typing import Union

import qtmodern.styles
from PyQt5.Qt import QApplication
from PyQt5.QtCore import QTimer
from hbutils.model import int_enum_loads

from .widget import AppMainWindow


@int_enum_loads(enable_int=False, name_preprocess=str.upper)
@unique
class AppTheme(IntEnum):
    NOTHING = 0
    LIGHT = 1
    DARK = 2

    @property
    def theme(self):
        if self == self.NOTHING:
            return lambda x: x
        elif self == self.LIGHT:
            return qtmodern.styles.light
        elif self == self.DARK:
            return qtmodern.styles.dark
        else:
            raise ValueError(f'Invalid theme - {repr(self)}.')

    def __call__(self, app: QApplication):
        return self.theme(app)


def _smoke_test_requested(argv) -> bool:
    if os.environ.get('FCSTM_UI_SMOKE_TEST') == '1':
        return True
    return any(a == '--smoke-test' for a in argv)


def run_app(argv=None, theme: Union[str, AppTheme] = 'nothing'):
    argv = argv if argv is not None else sys.argv
    smoke = _smoke_test_requested(argv)
    if smoke:
        argv = [a for a in argv if a != '--smoke-test']
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

    app = QApplication(argv)
    AppTheme.loads(theme)(app)

    main_window = AppMainWindow()
    main_window.show()

    if smoke:
        # Spin the event loop briefly to confirm the window can paint,
        # then exit cleanly with 0 so packaging smoke tests can assert
        # an end-to-end startup actually reached app.exec_().
        QTimer.singleShot(800, lambda: (print('fcstm-ui smoke test: OK'), app.quit()))

    sys.exit(app.exec_())


if __name__ == '__main__':
    run_app()
