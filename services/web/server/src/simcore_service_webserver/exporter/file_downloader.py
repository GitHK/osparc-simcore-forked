import logging
from pathlib import Path

from aiohttp.web import Application
from parfive.downloader import Downloader

from .config import get_settings
from .exceptions import ExporterException
from .utils import makedirs

log = logging.getLogger(__name__)


class ParallelDownloader:
    def __init__(self):
        self.downloader = Downloader(
            progress=False, file_progress=False, notebook=False, overwrite=True
        )
        self.total_files_added = 0

    async def append_file(self, link: str, download_path: Path):
        await makedirs(download_path.parent, exist_ok=True)
        self.downloader.enqueue_file(
            url=link, path=download_path.parent, filename=download_path.name
        )
        self.total_files_added += 1

    async def download_files(self, app: Application):
        """starts the download and waits for all files to finish"""
        exporter_settings = get_settings(app)
        results = await self.downloader.run_download(
            timeouts={
                "total": exporter_settings.downloader_max_timeout_seconds,
                "sock_read": 90,  # default as in parfive code
            }
        )

        log.debug("Download results %s", results)
        if len(results) != self.total_files_added or len(results.errors) > 0:
            raise ExporterException(
                f"Not all files were downloaded. Please check the logs above. Errors: {results.errors}"
            )
