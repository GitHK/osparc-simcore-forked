import logging
import sys
from pathlib import Path

from aiofiles import os as aiofiles_os
from aiohttp import web
from parfive.downloader import Downloader

from .exceptions import ExporterException
from .utils import makedirs

log = logging.getLogger(__name__)

if sys.version_info.major == 3 and sys.version_info.minor >= 7:
    raise RuntimeError(
        "Upgrade parfive version to a newer one. Also remember to implement "
        "a better check for the downloaded files. The new version has "
        "supprot for failed and not failed futures"
    )


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

    async def download_files(self):
        """starts the download and waits for all files to finish"""

        # run this async, newer versions do not require this trick
        wrapped_function = aiofiles_os.wrap(self.downloader.download)
        results = await wrapped_function()
        log.debug("Download results %s", results)

        if len(results) != self.total_files_added:
            raise ExporterException(
                "Not all files were downloaded. Please check the logs above."
            )
