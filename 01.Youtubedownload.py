# Youtube 영상을 다운로드 하는 프로그램입니다.
# 항상 최고의 퀄리티로 다운로드 한다.
# 주소를 물어보고 해당 주소의 영상을 다운로드 한다.
# 영상의 소리는 반드시 포함해서 제공한다.

"""
YouTube 영상을 최고 화질(오디오 포함)로 다운로드하는 PyQt6 기반 데스크톱 앱.

필수 패키지:
    pip install pyqt6 yt-dlp
"""

import sys
import shutil
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QProgressBar, QTextEdit, QMessageBox, QFileDialog
)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
import yt_dlp


def has_audio_stream(file_path: Path) -> bool | None:
    """ffprobe로 오디오 스트림 존재 여부를 확인한다."""
    if shutil.which("ffprobe") is None:
        return None

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=index",
        "-of",
        "csv=p=0",
        str(file_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return None
        return bool(result.stdout.strip())
    except Exception:
        return None


class DownloadWorker(QThread):
    """다운로드 작업을 백그라운드에서 수행하는 스레드"""
    progress = pyqtSignal(str)  # 진행 상황 텍스트
    finished = pyqtSignal(str, bool)  # 완료 시그널: (메시지, 성공 여부)
    error = pyqtSignal(str)  # 에러 시그널

    def __init__(self, url, output_dir):
        super().__init__()
        self.url = url
        self.output_dir = output_dir

    def run(self):
        """다운로드 실행"""
        if not self.url:
            self.error.emit("유효한 주소를 입력해야 합니다.")
            return

        if "youtube.com" not in self.url and "youtu.be" not in self.url:
            self.error.emit("YouTube 주소 형식이 아닙니다. 다시 확인해 주세요.")
            return

        try:
            import yt_dlp  # 지연 import
        except ImportError:
            self.error.emit("필수 패키지 'yt-dlp'가 설치되어 있지 않습니다.\n설치: pip install yt-dlp")
            return

        output_dir = self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        has_ffmpeg = shutil.which("ffmpeg") is not None

        if has_ffmpeg:
            format_selector = "bv*+ba/b"
            ffmpeg_options = {
                "merge_output_format": "mp4",
                "recodevideo": "mp4",
                "prefer_ffmpeg": True,
                "postprocessor_args": ["-c:a", "aac", "-b:a", "192k"],
            }
        else:
            format_selector = "best[acodec!=none][vcodec!=none]/best"
            ffmpeg_options = {}
            self.progress.emit("ffmpeg를 찾을 수 없어 오디오 포함 단일 스트림으로 다운로드합니다.")

        options = {
            "format": format_selector,
            "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "progress_hooks": [self.progress_hook],
            **ffmpeg_options,
        }

        try:
            self.progress.emit("다운로드 시작 중...")
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(self.url, download=True)
                downloaded_path = Path(ydl.prepare_filename(info))

            # 최종 파일 경로 확인
            final_path = downloaded_path
            mp4_path = downloaded_path.with_suffix(".mp4")
            if mp4_path.exists():
                final_path = mp4_path

            message = f"다운로드 완료: {final_path.resolve()}"

            audio_ok = has_audio_stream(final_path)
            if audio_ok is True:
                message += "\n오디오 트랙 확인 완료: 소리가 포함되어 있습니다."
            elif audio_ok is False:
                message += "\n경고: 오디오 트랙이 확인되지 않았습니다."
            else:
                message += "\n오디오 트랙 자동 검증을 건너뛰었습니다."

            self.finished.emit(message, True)

        except Exception as e:
            self.error.emit(f"다운로드 중 오류가 발생했습니다: {str(e)}")

    def progress_hook(self, d):
        """진행 상황 업데이트"""
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', 'N/A')
            speed = d.get('_speed_str', 'N/A')
            eta = d.get('_eta_str', 'N/A')
            self.progress.emit(f"진행: {percent} | 속도: {speed} | 남은시간: {eta}")

        elif d['status'] == 'finished':
            self.progress.emit("다운로드 완료, 음성과 비디오 병합 중...")


class YouTubeDownloader(QWidget):
    """메인 GUI 클래스"""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.output_dir = Path("downloads")  # 기본 저장 폴더
        self.init_ui()

    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("YouTube 영상 다운로더")
        self.setGeometry(300, 300, 700, 500)
        self.setFixedSize(700, 500)

        # 레이아웃
        layout = QVBoxLayout()

        # 제목
        title_label = QLabel("🎬 YouTube 영상 다운로드 (최고 화질 + 오디오 포함)")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #333; margin-bottom: 20px;")
        layout.addWidget(title_label)

        # URL 입력
        url_layout = QHBoxLayout()
        url_label = QLabel("YouTube URL:")
        url_label.setFont(QFont("Arial", 12))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.url_input.setFont(QFont("Arial", 10))
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        layout.addLayout(url_layout)

        # 폴더 선택
        folder_layout = QHBoxLayout()
        self.folder_label = QLabel(f"저장 폴더: {self.output_dir}")
        self.folder_label.setFont(QFont("Arial", 10))
        self.select_folder_btn = QPushButton("폴더 선택")
        self.select_folder_btn.setFont(QFont("Arial", 10))
        self.select_folder_btn.clicked.connect(self.select_folder)
        folder_layout.addWidget(self.folder_label)
        folder_layout.addWidget(self.select_folder_btn)
        layout.addLayout(folder_layout)

        # 다운로드 버튼
        self.download_btn = QPushButton("다운로드 시작")
        self.download_btn.setFont(QFont("Arial", 12))
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.download_btn.clicked.connect(self.start_download)
        layout.addWidget(self.download_btn)

        # 진행 바
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 상태 텍스트
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(200)
        self.status_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.status_text)

        # 클리어 버튼
        clear_btn = QPushButton("상태 클리어")
        clear_btn.setFont(QFont("Arial", 10))
        clear_btn.clicked.connect(self.clear_status)
        layout.addWidget(clear_btn)

        self.setLayout(layout)

    def start_download(self):
        """다운로드 시작"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "입력 오류", "URL을 입력해주세요.")
            return

        self.download_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_text.append("다운로드 준비 중...\n")

        # 워커 스레드 시작
        self.worker = DownloadWorker(url, self.output_dir)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.download_finished)
        self.worker.error.connect(self.download_error)
        self.worker.start()

    def update_progress(self, message):
        """진행 상황 업데이트"""
        self.status_text.append(message + "\n")
        # 진행 바 업데이트 (퍼센트 추출 시도)
        if "%" in message:
            try:
                percent_str = message.split("%")[0].split()[-1]
                percent = float(percent_str)
                self.progress_bar.setValue(int(percent))
            except:
                pass

    def download_finished(self, message, success):
        """다운로드 완료"""
        self.status_text.append(message + "\n")
        self.progress_bar.setVisible(False)
        self.download_btn.setEnabled(True)
        if success:
            QMessageBox.information(self, "완료", message.split('\n')[0])

    def download_error(self, error_msg):
        """다운로드 에러"""
        self.status_text.append(error_msg + "\n")
        self.progress_bar.setVisible(False)
        self.download_btn.setEnabled(True)
        QMessageBox.critical(self, "오류", error_msg)

    def clear_status(self):
        """상태 텍스트 클리어"""
        self.status_text.clear()

    def select_folder(self):
        """저장 폴더 선택"""
        folder = QFileDialog.getExistingDirectory(self, "저장 폴더 선택", str(self.output_dir))
        if folder:
            self.output_dir = Path(folder)
            self.folder_label.setText(f"저장 폴더: {self.output_dir}")


def main():
    """메인 함수"""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 기본 스타일
    app.setStyleSheet("""
        QWidget {
            background-color: #f0f0f0;
        }
        QLineEdit, QTextEdit {
            border: 1px solid #ccc;
            border-radius: 3px;
            padding: 5px;
        }
    """)

    window = YouTubeDownloader()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()