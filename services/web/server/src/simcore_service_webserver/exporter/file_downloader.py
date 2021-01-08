import sys
import logging

from parfive.downloader import Downloader
from pathlib import Path

from aiofiles import os as aiofiles_os

from .utils import makedirs

log = logging.getLogger(__name__)

if sys.version_info.major == 3 and sys.version_info.minor >= 7:
    raise RuntimeError("Upgrade parfive version to a newer one")


class ParallelDownloader:
    def __init__(self):

        self.downloader = Downloader(
            progress=False, file_progress=False, notebook=False, overwrite=True
        )

    async def append_file(self, link: str, download_path: Path):
        await makedirs(download_path.parent, exist_ok=True)
        self.downloader.enqueue_file(
            url=link, path=download_path.parent, filename=download_path.name
        )

    async def download_files(self):
        """starts the download and waits for all files to finish"""

        # run this async
        wrapped_function = aiofiles_os.wrap(self.downloader.download)
        results = await wrapped_function()
        log.debug("Download results %s", results)
        # TODO: check if all files have been downloaded
