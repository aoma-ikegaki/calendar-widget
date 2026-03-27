"""
Googleカレンダー デスクトップウィジェット
PyQt6 / フレームレス / ミニマルデザイン
"""

import sys
import json
import threading
import winreg
import ctypes
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QScrollArea, QPushButton, QMenu, QMessageBox,
    QSizePolicy, QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPoint, QSize
from PyQt6.QtGui import QFont, QCursor
import qtawesome as qta

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

SCOPES       = ['https://www.googleapis.com/auth/calendar.readonly']
CONFIG_DIR   = Path.home() / '.calendar_widget'
STARTUP_KEY  = r'Software\Microsoft\Windows\CurrentVersion\Run'
STARTUP_NAME = 'CalendarWidget'

HWND_TOPMOST   = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE     = 0x0002
SWP_NOSIZE     = 0x0001

# ── デザイン定数 ────────────────────────────────────
BG       = '#fafafa'
CARD_BG  = '#ffffff'
BORDER   = '#ebebeb'
TEXT     = '#1a1a1a'
SUB      = '#666666'
MUTED    = '#aaaaaa'
ACCENT   = '#3b82f6'

# イベント種別カラー（左バーの色）
CLR_ALLDAY  = '#ef4444'
CLR_WORK    = '#3b82f6'
CLR_IVEW    = '#8b5cf6'
CLR_DEFAULT = '#94a3b8'

FONT   = 'Segoe UI Variable Text'
RADIUS = 14


# ──────────────────────────────────────────────────
class FetchThread(QThread):
    done = pyqtSignal(list)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        self.done.emit(self._fn())


# ──────────────────────────────────────────────────
# イベント行 — 左カラーバー + テキストのシンプル構成
# ──────────────────────────────────────────────────

class EventRow(QWidget):
    """1件分のイベント行"""

    def __init__(self, event: Dict[str, Any], parent=None):
        super().__init__(parent)
        self._event = event
        self._url   = event.get('html_link', '')
        self._color = self._pick_color()
        self._build()

    def _pick_color(self) -> str:
        title = self._event.get('title', '').lower()
        if self._event.get('is_allday'):
            return CLR_ALLDAY
        if '面接' in title or 'interview' in title:
            return CLR_IVEW
        if 'バイト' in title or '勤務' in title or 'work' in title:
            return CLR_WORK
        return CLR_DEFAULT

    def _build(self):
        self.setStyleSheet(f"""
            EventRow {{
                background: {CARD_BG};
                border-radius: 6px;
            }}
        """)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 左カラーバー
        bar = QWidget()
        bar.setFixedWidth(4)
        bar.setStyleSheet(f'background: {self._color}; border-radius: 2px;')
        outer.addWidget(bar)

        # テキスト部
        inner = QVBoxLayout()
        inner.setContentsMargins(10, 7, 10, 7)
        inner.setSpacing(1)

        # 1行目: タイトル（＋終日ラベル）
        row1 = QHBoxLayout()
        row1.setSpacing(6)
        row1.setContentsMargins(0, 0, 0, 0)

        t = QLabel(self._event.get('title', ''))
        t.setFont(QFont(FONT, 11))
        t.setStyleSheet(f'color: {TEXT}; background: transparent;')
        t.setWordWrap(True)
        row1.addWidget(t, 1)

        if self._event.get('is_allday'):
            tag = QLabel('終日')
            tag.setFont(QFont(FONT, 8))
            tag.setStyleSheet(
                f'color: {self._color}; background: transparent; border: none;'
            )
            tag.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            row1.addWidget(tag)

        inner.addLayout(row1)

        # 2行目: 時間
        time_str = self._event.get('time_str', '')
        if time_str:
            tl = QLabel(time_str)
            tl.setFont(QFont(FONT, 9))
            tl.setStyleSheet(f'color: {SUB}; background: transparent;')
            inner.addWidget(tl)

        outer.addLayout(inner)

        if self._url:
            self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def enterEvent(self, e):
        self.setStyleSheet(f'EventRow {{ background: #f0f4ff; border-radius: 6px; }}')

    def leaveEvent(self, e):
        self.setStyleSheet(f'EventRow {{ background: {CARD_BG}; border-radius: 6px; }}')

    def mousePressEvent(self, e):
        if self._url:
            import webbrowser
            webbrowser.open(self._url)
        super().mousePressEvent(e)


# ──────────────────────────────────────────────────
# メインウィジェット
# ──────────────────────────────────────────────────

class CalendarWidget(QWidget):

    def __init__(self):
        super().__init__()
        self.always_on_top: bool = True
        self.events: List[Dict[str, Any]] = []
        self.service = None
        self._thread: FetchThread | None = None
        self._drag_pos: QPoint | None = None

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.config = self._load_config()
        self._setup_window()
        self._build_ui()

        QTimer(self, timeout=self.refresh_events, interval=300_000).start()
        QTimer.singleShot(300, self._init_async)

    # ── ウィンドウ ──────────────────────────────

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(380, 560)

        x = self.config.get('window_x')
        y = self.config.get('window_y')
        if x is not None and y is not None:
            self.move(x, y)
        else:
            screen = QApplication.primaryScreen().geometry()
            self.move(screen.width() - 400, 20)

        self.always_on_top = self.config.get('always_on_top', True)
        if not self.always_on_top:
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
            )
        QTimer.singleShot(200, self._apply_topmost)

    def _apply_topmost(self):
        hwnd = int(self.winId())
        flag = HWND_TOPMOST if self.always_on_top else HWND_NOTOPMOST
        ctypes.windll.user32.SetWindowPos(
            hwnd, flag, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
        # Windows 11 角丸 (DWMWA_WINDOW_CORNER_PREFERENCE = 33, DWMWCP_ROUND = 2)
        try:
            pref = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
        except Exception:
            pass
        self._update_pin_style()

    # ── UI ──────────────────────────────────────

    def _build_ui(self):
        self.setStyleSheet(f'CalendarWidget {{ background: {BG}; }}')

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── ヘッダー ──
        header = QWidget()
        header.setFixedHeight(44)
        header.setStyleSheet(f'background: {BG};')
        header.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        hb = QHBoxLayout(header)
        hb.setContentsMargins(16, 0, 8, 0)

        title = QLabel('schedule')
        title.setFont(QFont(FONT, 10))
        title.setStyleSheet(f'color: {MUTED}; background: transparent;')
        hb.addWidget(title)
        hb.addStretch()

        for icon_name, slot, tip in [
            ('mdi.pin',     self.toggle_pin,     '最前面'),
            ('mdi.refresh', self.refresh_events, '更新'),
            ('mdi.dots-vertical', self._show_menu, '設定'),
        ]:
            btn = QPushButton()
            btn.setIcon(qta.icon(icon_name, color=MUTED))
            btn.setIconSize(QSize(18, 18))
            btn.setToolTip(tip)
            btn.setFixedSize(28, 28)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(
                f'QPushButton {{ background: transparent; border: none; border-radius: 4px; }}'
                f'QPushButton:hover {{ background: {BORDER}; }}'
            )
            btn.clicked.connect(slot)
            hb.addWidget(btn)
            if icon_name == 'mdi.pin':
                self._pin_btn = btn

        root.addWidget(header)

        # ── スクロールエリア ──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: {BG}; }}
            QScrollBar:vertical {{ width: 3px; background: {BG}; }}
            QScrollBar::handle:vertical {{
                background: #d0d0d0; border-radius: 1px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{ background: none; }}
        """)

        self._content = QWidget()
        self._content.setStyleSheet(f'background: {BG};')
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(12, 4, 12, 12)
        self._layout.setSpacing(0)
        self._layout.addStretch()

        self._scroll.setWidget(self._content)
        root.addWidget(self._scroll)

        # ── フッター ──
        self._status = QLabel()
        self._status.setFont(QFont(FONT, 8))
        self._status.setStyleSheet(f'color: {MUTED}; background: {BG}; padding: 4px 16px;')
        root.addWidget(self._status)

        self._update_pin_style()

    # ── ドラッグ ────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    # ── イベント表示 ──────────────────────────────

    def _clear(self):
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_msg(self, text: str):
        self._clear()
        lbl = QLabel(text)
        lbl.setFont(QFont(FONT, 10))
        lbl.setStyleSheet(f'color: {MUTED}; background: transparent;')
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.insertWidget(0, lbl)

    def update_event_list(self):
        self._clear()
        if not self.events:
            self._show_msg('今後2週間の予定はありません')
            return

        grouped: Dict[str, list] = {}
        for ev in self.events:
            grouped.setdefault(ev.get('date_key', ''), []).append(ev)

        idx = 0
        for date_key in sorted(grouped.keys()):
            # 日付ヘッダー
            lbl = QLabel(self._fmt_date(date_key))
            lbl.setFont(QFont(FONT, 10, QFont.Weight.Bold))
            lbl.setStyleSheet(
                f'color: {SUB}; background: transparent;'
                'padding-top: 14px; padding-bottom: 4px; padding-left: 2px;'
            )
            self._layout.insertWidget(idx, lbl)
            idx += 1

            for ev in grouped[date_key]:
                row = EventRow(ev)
                self._layout.insertWidget(idx, row)
                idx += 1

                sp = QWidget()
                sp.setFixedHeight(4)
                sp.setStyleSheet('background: transparent;')
                self._layout.insertWidget(idx, sp)
                idx += 1

        QTimer.singleShot(0, lambda: self._scroll.verticalScrollBar().setValue(0))

    def _fmt_date(self, dk: str) -> str:
        try:
            dt = datetime.strptime(dk, '%Y-%m-%d')
            wd = ['月','火','水','木','金','土','日'][dt.weekday()]
            s = f'{dt.month}/{dt.day}（{wd}）'
            today = datetime.now().date()
            if dt.date() == today:
                s += '  今日'
            elif dt.date() == today + timedelta(days=1):
                s += '  明日'
            return s
        except ValueError:
            return dk

    # ── Google Calendar API ──────────────────────

    def _init_async(self):
        def task():
            self.service = self._get_service()
            self.events  = self._fetch()
            QTimer.singleShot(0, self._on_loaded)
        threading.Thread(target=task, daemon=True).start()

    def _on_loaded(self):
        self.update_event_list()
        self._update_status()

    def _get_service(self):
        if not GOOGLE_API_AVAILABLE:
            return None
        creds_path = CONFIG_DIR / 'credentials.json'
        token_path = CONFIG_DIR / 'token.json'
        if not creds_path.exists():
            local = Path('credentials.json')
            if local.exists():
                import shutil; shutil.copy(local, creds_path)
            else:
                return None
        try:
            creds = None
            if token_path.exists():
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                    except Exception:
                        # リフレッシュトークン失効 → 削除して再認証
                        token_path.unlink(missing_ok=True)
                        creds = None
                if not creds:
                    flow  = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
                    creds = flow.run_local_server(port=0)
                with open(token_path, 'w') as f:
                    f.write(creds.to_json())
            return build('calendar', 'v3', credentials=creds)
        except Exception as e:
            print(f'API認証エラー: {e}')
            return None

    def _fetch(self) -> List[Dict[str, Any]]:
        if self.service is None:
            return self._demo()
        try:
            now = datetime.now(tz=timezone.utc)
            res = self.service.events().list(
                calendarId='primary',
                timeMin=now.isoformat(),
                timeMax=(now + timedelta(days=14)).isoformat(),
                maxResults=50, singleEvents=True, orderBy='startTime',
            ).execute()
            result = []
            for item in res.get('items', []):
                result.extend(self._parse(item))
            return result
        except Exception as e:
            print(f'取得エラー: {e}')
            return self._demo()

    def _parse(self, item: Dict) -> List[Dict[str, Any]]:
        title = item.get('summary', '（タイトルなし）')
        start = item.get('start', {})
        end   = item.get('end', {})
        is_allday = 'date' in start and 'dateTime' not in start
        if is_allday:
            start_date = datetime.strptime(start.get('date', ''), '%Y-%m-%d').date()
            end_date   = datetime.strptime(end.get('date', ''), '%Y-%m-%d').date()
            # end.date は終了日の翌日なので1日戻す
            days = (end_date - start_date).days
            return [
                {'title': title,
                 'date_key': (start_date + timedelta(days=i)).strftime('%Y-%m-%d'),
                 'time_str': '', 'is_allday': True,
                 'html_link': item.get('htmlLink', '')}
                for i in range(max(days, 1))
            ]
        try:
            s = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00')).astimezone().replace(tzinfo=None)
            e = datetime.fromisoformat(end['dateTime'].replace('Z', '+00:00')).astimezone().replace(tzinfo=None)
            return [{'title': title, 'date_key': s.strftime('%Y-%m-%d'),
                     'time_str': f'{s.strftime("%H:%M")} – {e.strftime("%H:%M")}',
                     'is_allday': False, 'html_link': item.get('htmlLink', '')}]
        except Exception:
            return [{'title': title, 'date_key': start.get('dateTime', '')[:10],
                     'time_str': '', 'is_allday': False, 'html_link': ''}]

    def _demo(self) -> List[Dict[str, Any]]:
        today = datetime.now()
        return [
            {'title': 'チームミーティング', 'date_key': today.strftime('%Y-%m-%d'),                'time_str': '10:00 – 11:00', 'is_allday': False, 'html_link': ''},
            {'title': '徳島マラソン',       'date_key': (today+timedelta(3)).strftime('%Y-%m-%d'),  'time_str': '',              'is_allday': True,  'html_link': ''},
            {'title': '面接＠株式会社◯◯',  'date_key': (today+timedelta(5)).strftime('%Y-%m-%d'),  'time_str': '15:00 – 16:30', 'is_allday': False, 'html_link': ''},
            {'title': 'バイト',             'date_key': (today+timedelta(5)).strftime('%Y-%m-%d'),  'time_str': '18:00 – 22:00', 'is_allday': False, 'html_link': ''},
            {'title': '歯医者',             'date_key': (today+timedelta(8)).strftime('%Y-%m-%d'),  'time_str': '14:00 – 14:30', 'is_allday': False, 'html_link': ''},
        ]

    # ── 更新 ──────────────────────────────────────

    def refresh_events(self):
        if self._thread and self._thread.isRunning():
            return
        self._status.setText('更新中...')
        self._thread = FetchThread(self._fetch, self)
        self._thread.done.connect(self._on_refreshed)
        self._thread.start()

    def _on_refreshed(self, events):
        self.events = events
        self.update_event_list()
        self._update_status()

    def _update_status(self):
        prefix = 'デモ  ' if self.service is None else ''
        self._status.setText(f'{prefix}更新 {datetime.now().strftime("%H:%M")}')

    # ── ピン ──────────────────────────────────────

    def toggle_pin(self):
        self.always_on_top = not self.always_on_top
        pos = self.pos()
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        if self.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.move(pos)
        self.show()
        QTimer.singleShot(50, self._apply_topmost)

    def _update_pin_style(self):
        if self.always_on_top:
            self._pin_btn.setIcon(qta.icon('mdi.pin', color=ACCENT))
            self._pin_btn.setStyleSheet(
                f'QPushButton {{ background: #eff6ff; border: none; border-radius: 4px; }}'
                f'QPushButton:hover {{ background: #dbeafe; }}'
            )
        else:
            self._pin_btn.setIcon(qta.icon('mdi.pin-off-outline', color=MUTED))
            self._pin_btn.setStyleSheet(
                f'QPushButton {{ background: transparent; border: none; border-radius: 4px; }}'
                f'QPushButton:hover {{ background: {BORDER}; }}'
            )

    # ── メニュー ──────────────────────────────────

    def _show_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: white; border: 1px solid {BORDER};
                padding: 4px; border-radius: 6px;
            }}
            QMenu::item {{
                padding: 6px 16px; font-family: {FONT}; font-size: 10pt; color: {TEXT};
            }}
            QMenu::item:selected {{ background: #f5f5f5; }}
            QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}
        """)

        if self._is_startup():
            menu.addAction('自動起動を解除').triggered.connect(self._unreg_startup)
        else:
            menu.addAction('PC起動時に自動起動').triggered.connect(self._reg_startup)
        menu.addSeparator()
        menu.addAction('閉じる').triggered.connect(self.close)

        pos = self._pin_btn.mapToGlobal(QPoint(0, self._pin_btn.height()))
        menu.exec(pos)

    def _is_startup(self) -> bool:
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_READ)
            winreg.QueryValueEx(k, STARTUP_NAME)
            winreg.CloseKey(k)
            return True
        except Exception:
            return False

    def _reg_startup(self):
        try:
            pw = Path(sys.executable).parent / 'pythonw.exe'
            if not pw.exists():
                pw = Path(sys.executable)
            cmd = f'"{pw}" "{Path(__file__).resolve()}"'
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(k, STARTUP_NAME, 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(k)
            QMessageBox.information(self, '完了', '自動起動を登録しました。')
        except Exception as e:
            QMessageBox.critical(self, 'エラー', str(e))

    def _unreg_startup(self):
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_SET_VALUE)
            winreg.DeleteValue(k, STARTUP_NAME)
            winreg.CloseKey(k)
            QMessageBox.information(self, '完了', '自動起動を解除しました。')
        except Exception as e:
            QMessageBox.critical(self, 'エラー', str(e))

    # ── 設定 ──────────────────────────────────────

    def _load_config(self) -> Dict[str, Any]:
        p = CONFIG_DIR / 'config.json'
        try:
            if p.exists():
                return json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            pass
        return {}

    def _save_config(self):
        p = CONFIG_DIR / 'config.json'
        try:
            pos = self.pos()
            p.write_text(json.dumps({
                'window_x': pos.x(), 'window_y': pos.y(),
                'always_on_top': self.always_on_top,
            }, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            pass

    def closeEvent(self, e):
        self._save_config()
        super().closeEvent(e)


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    w = CalendarWidget()
    w.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
